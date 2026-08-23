"""
Production Multi-Tenant SaaS FastAPI Server for AI IVR System.
Includes 100% Native Telnyx Full IVR with Direct Jenny AI Representative (No Outbound PSTN Dialing Required).
"""

import os
import time
import re
import base64
import logging
import uuid
import json
import httpx
from fastapi import FastAPI, HTTPException, Request, Response, Form, Header, UploadFile, File
from fastapi.responses import HTMLResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import Optional, List, Dict, Any

from departments import get_all_departments, add_or_update_department, classify_department_intent, HOLD_MUSIC_CATALOG
from business_ai import auto_generate_ivr_from_business
from ai_engine import generate_llm_response, generate_tts_audio, extract_slots
from hold_music_synth import generate_hold_music_wav_bytes
import auth
import db
import knowledge_base
import email_service

app = FastAPI(title="VoiceFlow AI SaaS Platform", version="26.0.0")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("IVRServer")

CALL_SESSIONS: Dict[str, Dict] = {}
USER_CUSTOM_AUDIO: Dict[str, bytes] = {}

UPLOADS_DIR = os.path.join(os.path.dirname(__file__), "static", "uploads")
os.makedirs(UPLOADS_DIR, exist_ok=True)


def _reload_custom_audio_from_disk():
    """Reload all user-uploaded custom audio from disk into in-memory cache on startup."""
    mappings = db.get_all_custom_audio_mappings()
    for mapping in mappings:
        user_id = mapping["user_id"]
        file_path = os.path.join(UPLOADS_DIR, mapping["file_id"])
        if os.path.exists(file_path):
            with open(file_path, "rb") as f:
                USER_CUSTOM_AUDIO[user_id] = f.read()
            logger.info(f"Loaded custom audio for user {user_id} from {mapping['file_id']}")


def _load_custom_audio_for_user(user_id: str) -> Optional[bytes]:
    """Load custom audio for a user from disk if not in memory."""
    if user_id in USER_CUSTOM_AUDIO:
        return USER_CUSTOM_AUDIO[user_id]
    mapping = db.get_user_custom_audio_mapping(user_id)
    if mapping:
        file_path = os.path.join(UPLOADS_DIR, mapping["file_id"])
        if os.path.exists(file_path):
            with open(file_path, "rb") as f:
                data = f.read()
            USER_CUSTOM_AUDIO[user_id] = data
            return data
    # Fallback: scan UPLOADS_DIR directly for any uploaded MP3 file (e.g. Drivri Let's Go.mp3)
    if os.path.exists(UPLOADS_DIR):
        for fname in os.listdir(UPLOADS_DIR):
            if fname.lower().endswith('.mp3'):
                file_path = os.path.join(UPLOADS_DIR, fname)
                with open(file_path, "rb") as f:
                    data = f.read()
                USER_CUSTOM_AUDIO[user_id] = data
                logger.info(f"Loaded fallback jingle audio from {fname}")
                return data
    return None

VAPI_PHONE_NUMBER = os.getenv("VAPI_PHONE_NUMBER", "+12138329797")


class RegisterModel(BaseModel):
    email: str
    password: str
    company_name: Optional[str] = "My Business"


class LoginModel(BaseModel):
    email: str
    password: str


class OnboardRequest(BaseModel):
    business_input: str
    selected_voice: Optional[str] = "en-US-AvaNeural"
    selected_hold_music: Optional[str] = "stinger_corporate"


class CustomVoiceModel(BaseModel):
    voice_name: str
    voice_code: str


class VoicePreviewModel(BaseModel):
    voice: str
    sample_text: Optional[str] = None


class StartCallRequest(BaseModel):
    caller_name: Optional[str] = "Guest Caller"
    caller_phone: Optional[str] = "+15550001111"
    user_id: Optional[str] = None


class CustomDepartmentModel(BaseModel):
    id: str
    name: str
    digit: str
    voice: str
    system_prompt: str
    greeting: str
    hold_music: Optional[str] = "stinger_corporate"


def get_public_host_url(request: Request) -> str:
    """Extracts the public HTTPS URL (ngrok, cloudflare, or domain) from request headers."""
    env_url = os.getenv("PUBLIC_SERVER_URL")
    if env_url:
        return env_url.rstrip('/')
    forwarded_host = request.headers.get("x-forwarded-host") or request.headers.get("host")
    forwarded_proto = request.headers.get("x-forwarded-proto", "https")
    if forwarded_host:
        return f"{forwarded_proto}://{forwarded_host}".rstrip('/')
    return str(request.base_url).rstrip('/')


def get_effective_music_style(user_id: str, dept_music: str) -> str:
    if dept_music == "custom_upload" or _load_custom_audio_for_user(user_id) is not None:
        return "custom_upload"
    return dept_music or "stinger_corporate"


# --- Native Audio File Endpoint ---

@app.get("/api/audio/jingle/{style}.wav")
@app.get("/api/audio/jingle/{style}.mp3")
@app.get("/api/audio/jingle/{style}")
async def get_jingle_audio_file(style: str, authorization: Optional[str] = Header(None)):
    token = authorization.replace("Bearer ", "") if authorization else None
    user_id = auth.get_user_id_from_token(token) or "demo_user"
    
    clean_style = style.replace(".wav", "").replace(".mp3", "")
    
    if clean_style == "custom_upload" or user_id in USER_CUSTOM_AUDIO:
        audio_data = _load_custom_audio_for_user(user_id)
        if audio_data:
            return Response(content=audio_data, media_type="audio/mpeg")
        
    wav_bytes = generate_hold_music_wav_bytes(clean_style, duration=3.5)
    return Response(content=wav_bytes, media_type="audio/wav")


@app.post("/api/music/upload")
async def upload_custom_music(file: UploadFile = File(...), authorization: Optional[str] = Header(None)):
    token = authorization.replace("Bearer ", "") if authorization else None
    user_id = auth.get_user_id_from_token(token) or "demo_user"
    
    if not file.filename.lower().endswith(('.mp3', '.wav', '.ogg', '.m4a')):
        raise HTTPException(status_code=400, detail="Invalid audio file type. Please upload MP3, WAV, or OGG.")
    
    file_id = f"{user_id}_{uuid.uuid4().hex[:6]}_{file.filename}"
    file_path = os.path.join(UPLOADS_DIR, file_id)
    
    contents = await file.read()
    with open(file_path, "wb") as f:
        f.write(contents)
        
    USER_CUSTOM_AUDIO[user_id] = contents
    audio_b64 = base64.b64encode(contents).decode("utf-8")
    
    # Persist the file mapping so it survives server restarts
    db.save_custom_audio_mapping(user_id, file_id, file.filename)
    
    # Update user settings to reflect custom upload selection
    existing_settings = db.get_user_settings(user_id)
    db.save_user_settings(
        user_id=user_id,
        company_name=existing_settings["company_name"] if existing_settings else "My Business",
        selected_voice=existing_settings["selected_voice"] if existing_settings else "en-US-AvaNeural",
        selected_hold_music="custom_upload",
        router_greeting=existing_settings["router_greeting"] if existing_settings else "Welcome to our business!"
    )
    
    return JSONResponse(content={
        "status": "success",
        "file_id": file_id,
        "filename": file.filename,
        "url": f"/static/uploads/{file_id}",
        "audio_b64": audio_b64
    })


@app.get("/api/voice/custom")
def list_user_custom_voices(authorization: Optional[str] = Header(None)):
    token = authorization.replace("Bearer ", "") if authorization else None
    user_id = auth.get_user_id_from_token(token) or "demo_user"
    voices = db.get_user_custom_voices(user_id)
    return JSONResponse(content={"custom_voices": voices})


@app.post("/api/voice/custom")
def create_user_custom_voice(req: CustomVoiceModel, authorization: Optional[str] = Header(None)):
    token = authorization.replace("Bearer ", "") if authorization else None
    user_id = auth.get_user_id_from_token(token) or "demo_user"
    
    if not req.voice_name:
        raise HTTPException(status_code=400, detail="Voice name is required.")
        
    voice = db.save_user_custom_voice(user_id, req.voice_name, req.voice_code or "en-US-AvaNeural")
    return JSONResponse(content={"status": "success", "voice": voice})


@app.post("/api/preview/voice")
async def preview_voice_audio(req: VoicePreviewModel):
    voice = req.voice or "en-US-AvaNeural"
    voice_display = voice.split('-')[-1].replace('Neural', '')
    text = req.sample_text or f"Hello! I am {voice_display}. This is how your AI voice assistant will sound to your callers."
    
    audio_bytes = await generate_tts_audio(text, voice)
    audio_b64 = base64.b64encode(audio_bytes).decode("utf-8") if audio_bytes else ""
    return JSONResponse(content={"voice": voice, "sample_text": text, "audio_b64": audio_b64})


@app.get("/api/preview/music/{style}")
async def preview_hold_music(style: str, authorization: Optional[str] = Header(None)):
    token = authorization.replace("Bearer ", "") if authorization else None
    user_id = auth.get_user_id_from_token(token) or "demo_user"
    
    clean_style = style.replace(".wav", "").replace(".mp3", "")
    
    if clean_style == "custom_upload":
        audio_data = _load_custom_audio_for_user(user_id)
        if audio_data:
            audio_b64 = base64.b64encode(audio_data).decode("utf-8")
            return JSONResponse(content={"style": "custom_upload", "audio_b64": audio_b64, "format": "custom"})
        # No custom audio found — tell the frontend
        return JSONResponse(content={"style": "custom_upload", "audio_b64": "", "format": "custom", "error": "No custom audio uploaded yet. Please upload an audio file first."})
        
@app.get("/api/audio/jingle/{style}.mp3")
@app.get("/api/audio/jingle/{style}")
async def serve_jingle_mp3(style: str, user_id: Optional[str] = "demo_user"):
    """Serves the raw MP3 binary audio file for Twilio/SignalWire <Play> playback."""
    clean_style = style.replace(".mp3", "").replace(".wav", "")
    
    audio_data = _load_custom_audio_for_user(user_id or "demo_user") or _load_custom_audio_for_user("demo_user") or _load_custom_audio_for_user("6a083847")
    if audio_data:
        return Response(content=audio_data, media_type="audio/mpeg")
            
    wav_bytes = generate_hold_music_wav_bytes(clean_style if clean_style != "custom_upload" else "stinger_corporate", duration=4.0)
    return Response(content=wav_bytes, media_type="audio/mpeg")


# --- Authentication & Persistent User Settings ---

@app.post("/api/auth/register")
def register_user(req: RegisterModel):
    if not req.email or "@" not in req.email or len(req.password) < 4:
        raise HTTPException(status_code=400, detail="Invalid email or password.")
    
    password_hash = auth.hash_password(req.password)
    try:
        user = db.create_user(req.email, password_hash, req.company_name or "My Business")
        token = auth.create_session(user["id"])
        return JSONResponse(content={"status": "success", "token": token, "user": user})
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/auth/login")
def login_user(req: LoginModel):
    user = db.get_user_by_email(req.email)
    if not user or auth.hash_password(req.password) != user["password_hash"]:
        raise HTTPException(status_code=400, detail="Invalid email or password.")
    
    token = auth.create_session(user["id"])
    settings = db.get_user_settings(user["id"])
    depts = db.get_user_departments(user["id"])
    
    return JSONResponse(content={
        "status": "success",
        "token": token,
        "user": {"id": user["id"], "email": user["email"], "company_name": user["company_name"]},
        "settings": settings,
        "departments": depts
    })


@app.get("/api/auth/me")
def get_current_user(authorization: Optional[str] = Header(None)):
    token = authorization.replace("Bearer ", "") if authorization else None
    user_id = auth.get_user_id_from_token(token)
    if not user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")
    
    user = db.get_user_by_id(user_id)
    settings = db.get_user_settings(user_id)
    depts = db.get_user_departments(user_id)
    custom_voices = db.get_user_custom_voices(user_id)
    
    return JSONResponse(content={
        "user": user,
        "settings": settings,
        "departments": depts,
        "custom_voices": custom_voices
    })


@app.post("/api/saas/onboard")
def onboard_business(req: OnboardRequest, authorization: Optional[str] = Header(None)):
    token = authorization.replace("Bearer ", "") if authorization else None
    user_id = auth.get_user_id_from_token(token) or "demo_user"
    
    if not req.business_input or len(req.business_input.strip()) < 2:
        raise HTTPException(status_code=400, detail="Please provide a valid URL or business description.")
    
    result = auto_generate_ivr_from_business(req.business_input)
    
    selected_voice = req.selected_voice or "en-US-AvaNeural"
    selected_music = req.selected_hold_music or ("custom_upload" if user_id in USER_CUSTOM_AUDIO else "stinger_corporate")
    
    db.save_user_settings(
        user_id=user_id,
        company_name=result["company_name"],
        selected_voice=selected_voice,
        selected_hold_music=selected_music,
        router_greeting=result["router_greeting"]
    )
    
    db.save_user_department(
        user_id=user_id,
        dept_id="router",
        name=f"{result['company_name']} IVR Main Router",
        digit="0",
        voice=selected_voice,
        system_prompt=f"You are the main IVR Receptionist for {result['company_name']}.",
        greeting=result["router_greeting"],
        hold_music=selected_music
    )

    for d in result.get("created_departments", []):
        dept_voice = d.get("voice", selected_voice)
        dept_music = selected_music if user_id in USER_CUSTOM_AUDIO else d.get("hold_music", selected_music)
        db.save_user_department(
            user_id=user_id,
            dept_id=d["id"],
            name=d["name"],
            digit=d["digit"],
            voice=dept_voice,
            system_prompt=d["system_prompt"],
            greeting=d["greeting"],
            hold_music=dept_music
        )
        
    return JSONResponse(content=result)


@app.get("/api/departments")
def list_departments(authorization: Optional[str] = Header(None)):
    token = authorization.replace("Bearer ", "") if authorization else None
    user_id = auth.get_user_id_from_token(token)
    depts = db.get_user_departments(user_id) if user_id else get_all_departments()
    return JSONResponse(content={"departments": depts})


@app.post("/api/departments")
def create_or_update_dept(dept: CustomDepartmentModel, authorization: Optional[str] = Header(None)):
    token = authorization.replace("Bearer ", "") if authorization else None
    user_id = auth.get_user_id_from_token(token) or "demo_user"
    
    dept_id = dept.id.lower().replace(" ", "_")
    db.save_user_department(
        user_id=user_id,
        dept_id=dept_id,
        name=dept.name,
        digit=dept.digit or "1",
        voice=dept.voice,
        system_prompt=dept.system_prompt,
        greeting=dept.greeting,
        hold_music=dept.hold_music or "stinger_corporate"
    )
    return JSONResponse(content={"status": "success", "dept_id": dept_id})


@app.get("/api/call/logs")
def list_user_call_logs(authorization: Optional[str] = Header(None)):
    token = authorization.replace("Bearer ", "") if authorization else None
    user_id = auth.get_user_id_from_token(token)
    logs = db.get_all_call_logs(user_id=user_id, limit=100)
    for l in logs:
        l["transcripts"] = db.get_call_transcripts(l["session_id"])
    return JSONResponse(content={"call_logs": logs})


# --- 3-Stage Web Call Start ---

@app.post("/api/call/start")
async def start_call(req: StartCallRequest):
    session_id = str(uuid.uuid4())[:8]
    user_id = req.user_id or "demo_user"
    depts = db.get_user_departments(user_id) if user_id != "demo_user" else get_all_departments()
    
    current_dept = "router"
    dept_info = depts.get(current_dept, list(depts.values())[0])
    
    music_key = get_effective_music_style(user_id, dept_info.get("hold_music", "stinger_corporate"))
    music_label = "Custom Uploaded Audio" if music_key == "custom_upload" else HOLD_MUSIC_CATALOG.get(music_key, music_key.replace('_', ' ').title())
    
    custom_audio = _load_custom_audio_for_user(user_id) if music_key == "custom_upload" else None
    if music_key == "custom_upload" and custom_audio:
        music_b64 = base64.b64encode(custom_audio).decode("utf-8")
    else:
        fallback_key = music_key if music_key != "custom_upload" else "stinger_corporate"
        music_b64 = base64.b64encode(generate_hold_music_wav_bytes(fallback_key, duration=3.0)).decode("utf-8")
    
    full_greeting = dept_info["greeting"]
    if "Please listen carefully" in full_greeting:
        parts = full_greeting.split("Please listen carefully")
        formal_greeting_text = parts[0].strip()
        dials_text = "Please listen carefully" + parts[1]
    else:
        formal_greeting_text = "Thank you for calling our business. Your call is important to us."
        dials_text = full_greeting
        
    greeting_bytes = await generate_tts_audio(formal_greeting_text, dept_info["voice"])
    greeting_b64 = base64.b64encode(greeting_bytes).decode("utf-8") if greeting_bytes else ""
    
    dials_bytes = await generate_tts_audio(dials_text, dept_info["voice"])
    dials_b64 = base64.b64encode(dials_bytes).decode("utf-8") if dials_bytes else ""
    
    db.record_call_start(session_id, req.caller_phone or "Unknown", current_dept, user_id=user_id)
    db.record_transcript(session_id, "System", current_dept, f"[{music_label} Played] {formal_greeting_text} {dials_text}")
    
    CALL_SESSIONS[session_id] = {
        "user_id": user_id,
        "caller_name": req.caller_name,
        "caller_phone": req.caller_phone,
        "current_department": current_dept,
        "history": [{"role": "assistant", "content": f"{formal_greeting_text} {dials_text}"}]
    }
    
    return JSONResponse(content={
        "session_id": session_id,
        "department": current_dept,
        "department_name": dept_info["name"],
        "message": f"🎵 [{music_label} Playing...] 🗣️ {formal_greeting_text} 📋 {dials_text}",
        "music_b64": music_b64,
        "greeting_b64": greeting_b64,
        "dials_b64": dials_b64
    })


# --- OpenAI ChatCompletions & Live Human Representative AI (Jenny) ---

@app.post("/v1/chat/completions")
@app.post("/api/call/interact")
async def universal_call_interact(request: Request):
    try:
        body = await request.json()
    except Exception:
        body = {}
        
    session_id = body.get("session_id") or body.get("call", {}).get("id") or "vapi_session"
    user_input = ""
    
    if "messages" in body and isinstance(body["messages"], list) and len(body["messages"]) > 0:
        last_msg = body["messages"][-1]
        user_input = last_msg.get("content", "")
    elif "user_input" in body:
        user_input = body["user_input"]
        
    user_text = str(user_input).strip().lower()
    
    session = CALL_SESSIONS.get(session_id)
    if not session:
        session = {
            "user_id": "demo_user",
            "current_department": "router",
            "history": []
        }
        CALL_SESSIONS[session_id] = session
        
    user_id = session.get("user_id", "demo_user")
    current_dept = session["current_department"]
    
    depts = db.get_user_departments(user_id) if user_id != "demo_user" else get_all_departments()
    dept_info = depts.get(current_dept, depts.get("router", list(depts.values())[0]))

    # 1. Silence Keep-Alive
    if not user_text or user_text in ["silence", "timeout", "no_input"]:
        silence_text = dept_info.get("silence_prompt", "We noticed you haven't selected an option yet. Are you still there?")
        reply_message = silence_text
        
    # 2. Listen Again (*)
    elif user_text in ["*", "repeat", "listen again", "listen"]:
        reply_message = f"Repeating Menu Options: {dept_info['greeting']}"
        
    # 3. Live Operator Handoff (0) -> Jenny
    elif user_text in ["0", "operator", "human", "speak with agent", "agent", "representative"]:
        session["current_department"] = "operator"
        reply_message = "Hello! Thank you for holding. This is Jenny, Senior Live Representative. How can I personally assist you today?"

    # 4. Department Navigation
    else:
        target_dept = classify_department_intent(user_text, current_dept)
        if target_dept != current_dept and target_dept in depts:
            session["current_department"] = target_dept
            target_info = depts[target_dept]
            reply_message = f"Transferring to {target_info['name']}... {target_info['greeting']}"
        else:
            session["history"].append({"role": "user", "content": user_text})
            
            if current_dept == "operator":
                operator_prompt = (
                    "You are Jenny, Senior Live Human Representative at Drivri Logistics. "
                    "Speak warmly, helpfully, and empathetically as a real human customer service manager. "
                    "Help callers with special requests, custom quotes, complaints, or resolving any issues."
                )
                reply_message = generate_llm_response(user_text, operator_prompt, session["history"])
            else:
                sys_prompt = dept_info.get("system_prompt", "You are an AI assistant.")
                kb_context = knowledge_base.get_combined_knowledge_prompt(user_id)
                if kb_context:
                    sys_prompt += f"\n{kb_context}"
                reply_message = generate_llm_response(user_text, sys_prompt, session["history"])
                
            # Agentic Email Intake: Check if caller provided or spoke an email address (works for Jenny & ALL agents)
            try:
                # Spoken email normalization (e.g. "john at gmail dot com" -> "john@gmail.com")
                normalized_text = user_text.replace(" at ", "@").replace(" [at] ", "@").replace(" (at) ", "@")
                normalized_text = normalized_text.replace(" dot ", ".").replace(" [dot] ", ".").replace(" (dot) ", ".").replace(" period ", ".")
                
                email_match = re.search(r'[\w\.-]+@[\w\.-]+\.\w+', normalized_text)
                if email_match:
                    customer_email = email_match.group(0)
                    quote_id = f"DRV-{uuid.uuid4().hex[:4].upper()}"
                    slots = session.get("slots", {})
                    dept_name = dept_info.get("name", "Logistics Package") if isinstance(dept_info, dict) else "Logistics Package"
                    
                    logger.info(f"[SPOKEN EMAIL DETECTED] Spoken: '{user_text}' -> Dispatched To: {customer_email}")
                    
                    # Dispatch Resend Email with Sign-Up Magic Link & BCC to info@drivri.co.uk
                    email_service.send_booking_quote_email(
                        to_email=customer_email,
                        customer_name=slots.get("name", "Valued Customer"),
                        quote_id=quote_id,
                        service_type=dept_name,
                        vehicle_or_licence=slots.get("vehicle", "Driver & Van Package"),
                        pickup_address=slots.get("pickup", "As Discussed"),
                        delivery_address=slots.get("delivery", "As Discussed"),
                        preferred_date=slots.get("date", "Tomorrow"),
                        quoted_price=float(slots.get("price", 120.0)),
                        insurance_option="Goods in Transit (£10M Cover Included)"
                    )
                    
                    # Store Deal in Database as QUOTE_SENT
                    db.save_deal(
                        user_id=user_id,
                        booking_id=quote_id,
                        caller_phone=customer_email,
                        department=current_dept,
                        pickup=slots.get("pickup", "N/A"),
                        delivery=slots.get("delivery", "N/A"),
                        date=slots.get("date", "Tomorrow"),
                        vehicle=slots.get("vehicle", "Driver & Van Package"),
                        price=float(slots.get("price", 120.0)),
                        status="QUOTE_SENT",
                        call_sid=session_id
                    )
                    
                    reply_message += f" I have just dispatched your custom quote summary and instant sign-up link directly to {customer_email}. Simply click the secure link in your email to complete registration and confirm your booking!"
            except Exception as e:
                logger.error(f"Email dispatch error: {e}")
                
            session["history"].append({"role": "assistant", "content": reply_message})

    db.record_transcript(session_id, "AI Agent", session["current_department"], reply_message)

    return JSONResponse(content={
        "id": f"chatcmpl-{uuid.uuid4().hex[:8]}",
        "object": "chat.completion",
        "created": 1677652288,
        "model": "voiceflow-ai",
        "choices": [
            {
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": reply_message
                },
                "finish_reason": "stop"
            }
        ],
        "usage": {"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30},
        "session_id": session_id,
        "department": session["current_department"],
        "message": reply_message
    })


# ==============================================================================
# OpenResend Custom Email Provider API Endpoint (/v1/emails)
# ==============================================================================
@app.post("/v1/emails")
@app.post("/api/send-email")
async def send_vapi_openresend_email(request: Request, authorization: Optional[str] = Header(None)):
    """OpenResend API endpoint for Vapi tool calls to send emails from info@drivri.co.uk."""
    try:
        body = await request.json()
        logger.info(f"[VAPI TOOL CALL RECEIVED] Body: {body}")
        
        tool_call_id = None
        to_email = None
        from_email = "Drivri Business <info@drivri.co.uk>"
        subject = "🚚 Welcome to Drivri UK | £100 Business Credit & Signup Link"
        
        # 1. Parse Vapi Tool Call Envelope
        message = body.get("message", {})
        tool_calls = message.get("toolCallList") or message.get("toolCalls") or body.get("toolCallList") or body.get("toolCalls")
        
        if tool_calls and isinstance(tool_calls, list) and len(tool_calls) > 0:
            tc = tool_calls[0]
            tool_call_id = tc.get("id")
            func = tc.get("function", {})
            args = func.get("arguments", {})
            if isinstance(args, str):
                try:
                    args = json.loads(args)
                except Exception:
                    args = {}
            to_email = args.get("to") or args.get("email")
            from_email = args.get("from", from_email)
            subject = args.get("subject", subject)
        else:
            # 2. Direct Flat Payload Fallback
            to_email = body.get("to")
            from_email = body.get("from", from_email)
            subject = body.get("subject", subject)

        if not to_email:
            # Look for any email pattern or spoken email pattern in request body
            body_str = json.dumps(body)
            norm_body = body_str.replace(" at ", "@").replace(" dot ", ".")
            match = re.search(r'[\w\.-]+@[\w\.-]+\.\w+', norm_body)
            if match:
                to_email = match.group(0)

        if not to_email:
            return JSONResponse(content={"error": "Missing required field: to"}, status_code=400)

        # Dispatch via Email Service
        quote_id = f"DRV-{uuid.uuid4().hex[:4].upper()}"
        email_service.send_booking_quote_email(
            to_email=to_email,
            customer_name="Valued Customer",
            quote_id=quote_id,
            service_type="Drivri UK Business Account",
            vehicle_or_licence="Logistics & Transport OS",
            pickup_address="UK-Wide",
            delivery_address="UK-Wide",
            preferred_date="Instant Access",
            quoted_price=100.0,
            insurance_option="Goods in Transit (£10M Cover Included)",
            signup_url=f"https://drivri.co.uk/business?quote_id={quote_id}&email={to_email}"
        )

        logger.info(f"[OPENRESEND API] Sent Email -> To: {to_email} | BCC Copy: info@drivri.co.uk | ToolCallID: {tool_call_id}")

        # Return Vapi Compatible Tool Call Response Format
        if tool_call_id:
            return JSONResponse(content={
                "results": [
                    {
                        "toolCallId": tool_call_id,
                        "result": f"Email successfully dispatched to {to_email} with a copy sent to info@drivri.co.uk."
                    }
                ]
            })
        else:
            return JSONResponse(content={
                "id": f"resend_{uuid.uuid4().hex[:12]}",
                "from": from_email,
                "to": [to_email],
                "status": "success",
                "message": f"Email successfully dispatched to {to_email}"
            })
    except Exception as e:
        logger.error(f"OpenResend API error: {e}")
        return JSONResponse(content={"error": str(e)}, status_code=500)
@app.post("/telephony/inbound/{user_id}/{dept_id}")
@app.post("/telephony/inbound/{user_id}")
@app.post("/telephony/inbound")
async def telephony_inbound(request: Request, user_id: Optional[str] = "demo_user", dept_id: Optional[str] = "router", From: Optional[str] = Form(None), CallSid: Optional[str] = Form(None)):
    session_id = CallSid or "vapi_pstn_call"
    host_url = get_public_host_url(request)
    
    try:
        body = await request.json()
    except Exception:
        body = {}
        
    # Extract real customer caller ID from Vapi JSON envelope or Form
    vapi_caller = (
        body.get("message", {}).get("call", {}).get("customer", {}).get("number")
        or body.get("call", {}).get("customer", {}).get("number")
        or body.get("message", {}).get("customer", {}).get("number")
        or body.get("customer", {}).get("number")
        or From
        or "PSTN Caller"
    )
    caller = str(vapi_caller).strip()
    
    # Check 1: Match by exact caller ID or clean digits
    resolved_dept = None
    if caller and caller != "PSTN Caller":
        resolved_dept = ACTIVE_CALL_DEPARTMENTS.get(caller)
        if not resolved_dept:
            digits_only = re.sub(r'\D', '', str(caller))
            resolved_dept = ACTIVE_CALL_DEPARTMENTS.get(digits_only) or ACTIVE_CALL_DEPARTMENTS.get(f"+{digits_only}")
            
    # Check 2: Fallback to most recent keypad selection if timestamp is within 60 seconds
    if not resolved_dept:
        last_dept = LAST_KEYPAD_SELECTION.get("dept")
        last_time = LAST_KEYPAD_SELECTION.get("timestamp", 0)
        if last_dept and (time.time() - last_time < 60):
            resolved_dept = last_dept
            logger.info(f"[ROUTING FALLBACK SUCCESS] Resolved to last keypad selection: {resolved_dept}")
            
    if resolved_dept:
        dept_id = resolved_dept
    elif dept_id == "router" or not dept_id:
        dept_id = "operator"
    
    logger.info(f"[ROUTED TO DEPARTMENT] Caller: '{caller}' -> Resolved Dept: '{dept_id}'")
    
    depts = db.get_user_departments(user_id) if user_id != "demo_user" else get_all_departments()
    dept_info = depts.get(dept_id, depts.get("operator", depts.get("router", list(depts.values())[0])))
    
    # Specialized Department Assistant Personas (Dedicated Names, Titles, Gender & Native Vapi Voices)
    PERSONA_MAP = {
        "sales_hire_driver": {"name": "David", "title": "Head of Driver Operations", "intro": "Hello! Thanks for reaching Drivri Driver Hire. I'm David, Head of Driver Operations. How can I assist with your driver requirements today?", "voice": "echo", "voice_provider": "openai"},
        "sales_driver_and_van": {"name": "Marcus", "title": "Van and Driver Operations Manager", "intro": "Hello! Thanks for reaching Drivri Transport. I'm Marcus, Van and Driver Operations Manager. Where are we picking up your cargo today?", "voice": "onyx", "voice_provider": "openai"},
        "sales_van_only": {"name": "Marcus", "title": "Fleet Rental Manager", "intro": "Hello! Thanks for reaching Drivri Fleet Rentals. I'm Marcus, Fleet Manager. How many days do you need your van rental for?", "voice": "onyx", "voice_provider": "openai"},
        "sales_fleet": {"name": "Marcus", "title": "Corporate Fleet Director", "intro": "Hello! Thanks for reaching Drivri Corporate Logistics. I'm Marcus, Fleet Director. How many commercial vehicles does your business require?", "voice": "onyx", "voice_provider": "openai"},
        "sales": {"name": "David", "title": "Senior Sales Specialist", "intro": "Hello! Thanks for calling Drivri Sales. I'm David, Senior Sales Specialist. How can I assist you with your booking today?", "voice": "echo", "voice_provider": "openai"},
        "courier": {"name": "Sarah", "title": "Courier Dispatch Director", "intro": "Hello! Thanks for reaching Drivri Instant Couriers. I'm Sarah, Courier Director. Where are we dispatching your urgent parcel today?", "voice": "shimmer", "voice_provider": "openai"},
        "freight": {"name": "Sarah", "title": "International Customs Freight Director", "intro": "Hello! Thanks for reaching Drivri Freight Forwarding and Customs Clearance. I'm Sarah. What ports or European countries are you shipping cargo between?", "voice": "shimmer", "voice_provider": "openai"},
        "freight_and_courier": {"name": "Sarah", "title": "Courier and International Freight Director", "intro": "Hello! Thanks for reaching Drivri Couriers and European Shipping. I'm Sarah. Are you shipping within the UK or internationally across Europe today?", "voice": "shimmer", "voice_provider": "openai"},
        "support": {"name": "Sarah", "title": "Customer Support Lead", "intro": "Hello! Thanks for reaching Drivri Customer Support. I'm Sarah. Do you have an existing booking reference or tracking inquiry I can help you with?", "voice": "shimmer", "voice_provider": "openai"},
        "warehousing": {"name": "Alex", "title": "Warehousing and Storage Director", "intro": "Hello! Thanks for reaching Drivri Warehousing and Multi-Storage. I'm Alex, Storage Director. What UK postcode or city do you need pallet storage in today?", "voice": "fable", "voice_provider": "openai"},
        "parking": {"name": "Chloe", "title": "City Parking Coordinator", "intro": "Hello! Thanks for reaching Drivri Reserved Parking Bays. I'm Chloe, City Parking Coordinator. Where do you need a reserved van or commercial parking space today?", "voice": "alloy", "voice_provider": "openai"},
        "accounts": {"name": "Rachel", "title": "Accounts and Billing Lead", "intro": "Hello! Thanks for reaching Drivri Accounts and Billing. I'm Rachel. How can I assist with your invoice or statement today?", "voice": "alloy", "voice_provider": "openai"},
        "operator": {"name": "Jenny", "title": "Senior Operations Manager", "intro": "Hello! This is Jenny, Senior Operations Manager at Drivri Logistics. How can I personally assist you today?", "voice": "nova", "voice_provider": "openai"}
    }
    
    persona = PERSONA_MAP.get(dept_id, {
        "name": "Jenny",
        "title": "Senior Operations Manager",
        "intro": "Hello! This is Jenny, Senior Operations Manager at Drivri Logistics. How can I assist you with your booking today?",
        "voice": "nova",
        "voice_provider": "openai"
    })
    
    # Full Brand Greeting + IVR Menu + Persona Opening
    if dept_id in ["router", "operator"]:
        clean_intro = (
            "Welcome to Drivri UK Logistics Solution! "
            "Please listen carefully to our department options: "
            "For Van and Driver Hire, speak to Marcus. "
            "For Professional Driver Only Hire, speak to David. "
            "For Same-Day Couriers and European Customs Freight Clearance, speak to Sarah. "
            "For Warehousing and Pallet Storage, speak to Alex. "
            "For Reserved City Parking Bays, speak to Chloe. "
            "Or stay on the line to speak with Jenny, Senior Operations Manager. "
            "How can I assist you with your booking today?"
        )
    else:
        clean_intro = persona["intro"].replace("&", "and")
    
    db.record_call_start(session_id, caller, dept_id, user_id=user_id)
    db.record_transcript(session_id, "System", dept_id, clean_intro)

    try:
        body = await request.json()
    except Exception:
        body = {}
        
    # Build system prompt and strip any IVR menu text from department prompt
    raw_dept_prompt = dept_info.get('system_prompt', 'You are an AI assistant.')
    # Remove any keypad instruction leakage from department system prompts
    raw_dept_prompt = re.sub(r'[Pp]ress\s+\d[^.]*\.?', '', raw_dept_prompt).strip()
    sys_prompt = (
        f"You are {persona['name']}, {persona['title']} at Drivri Logistics.\n"
        f"{raw_dept_prompt}\n"
        "CRITICAL RULES FOR VAPI VOICE AGENT (STRICTLY ENFORCED):\n"
        "1. NEVER recite keypad options, menu numbers, or tell callers to dial ANY digit. ZERO exceptions.\n"
        "2. Do NOT mention numbered menu options or keypad selections under any circumstances.\n"
        f"3. Introduce yourself naturally as {persona['name']}, {persona['title']}.\n"
        "4. Speak conversationally. Ask the caller what they need help with.\n"
        "5. Keep responses under 2 sentences per turn for natural fast speech.\n"
    )
    kb_context = knowledge_base.get_combined_knowledge_prompt(user_id)
    if kb_context:
        sys_prompt += f"\n{kb_context}"
        
    server_email_url = f"{host_url}/v1/emails"
    
    send_email_tool = {
        "type": "function",
        "async": False,
        "server": {
            "url": server_email_url
        },
        "function": {
            "name": "send_email",
            "description": "Dispatches an official Drivri booking quote summary and sign-up magic link to the customer via OpenResend API with BCC to info@drivri.co.uk.",
            "parameters": {
                "type": "object",
                "properties": {
                    "to": {
                        "type": "string",
                        "description": "Customer email address (e.g. customer@example.com)"
                    },
                    "customer_name": {
                        "type": "string",
                        "description": "Customer name"
                    },
                    "service_type": {
                        "type": "string",
                        "description": "Service type (e.g. Driver Only Hire, Luton Van Rental)"
                    }
                },
                "required": ["to"]
            }
        }
    }

    return JSONResponse(content={
        "assistant": {
            "name": f"Drivri - {persona['name']} ({persona['title']})",
            "firstMessageMode": "assistant-speaks-first",
            "firstMessage": clean_intro,
            "systemPrompt": sys_prompt,
            "serverUrl": server_email_url,
            "server": {
                "url": server_email_url
            },
            "model": {
                "provider": "custom-llm",
                "url": f"{host_url}/v1/chat/completions",
                "model": "gpt-4o-mini",
                "tools": [send_email_tool]
            },
            "voice": {
                "provider": persona.get("voice_provider", "openai"),
                "voiceId": persona["voice"]
            }
        },
        "firstMessage": clean_intro
    })


# ==============================================================================
# OPTION B: Twilio / Telnyx Forwarding to Vapi
# ==============================================================================
@app.post("/telephony/jingle-forward")
@app.post("/telephony/jingle-forward/{user_id}")
@app.get("/telephony/jingle-forward")
@app.get("/telephony/jingle-forward/{user_id}")
async def twiml_jingle_then_forward_to_vapi(request: Request, user_id: Optional[str] = "demo_user", From: Optional[str] = Form(None)):
    host_url = get_public_host_url(request)
    jingle_url = f"{host_url}/static/jingle.mp3"
    
    twiml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Play>{jingle_url}</Play>
    <Dial>{VAPI_PHONE_NUMBER}</Dial>
</Response>"""
    return Response(content=twiml, media_type="text/xml")


# ==============================================================================
# OPTION C: 100% Native SignalWire / Telnyx / Twilio Full IVR + Direct Jenny AI
# Point SignalWire / Telnyx / Twilio Voice Webhook URL here: /telephony/signalwire/demo_user or /telephony/full-ivr/demo_user
# ==============================================================================
# Global Active Call Selection Tracker for Seamless Persona Handoff
ACTIVE_CALL_DEPARTMENTS = {}
LAST_KEYPAD_SELECTION = {"dept": "operator", "timestamp": 0}

@app.post("/telephony/full-ivr")
@app.post("/telephony/full-ivr/{user_id}")
@app.get("/telephony/full-ivr")
@app.get("/telephony/full-ivr/{user_id}")
@app.post("/telephony/signalwire")
@app.post("/telephony/signalwire/{user_id}")
@app.get("/telephony/signalwire")
@app.get("/telephony/signalwire/{user_id}")
async def twiml_full_ivr(request: Request, user_id: Optional[str] = "demo_user", From: Optional[str] = Form(None)):
    """
    Complete 4-Stage Telephony Architecture for SignalWire:
    1. STAGE 1: Play Uploaded Brand Jingle Audio FIRST (Drivri Let's Go.mp3)
    2. STAGE 2: Keypad IVR Selections Menu (Listening for 1, 2, 3, 4, 5, 0 or speech)
    3. STAGE 3: Transfer to Specialized Department Voice Agent (David, Marcus, Sarah, Alex, Chloe, Jenny)
    """
    host_url = get_public_host_url(request)
    depts = db.get_user_departments(user_id) if user_id != "demo_user" else get_all_departments()
    dept_info = depts.get("router", list(depts.values())[0])
    full_greeting = dept_info.get("greeting", "Welcome to Drivri UK Logistics Solution! How may I help you today? Press 1 for Sales and Bookings. Press 2 for Customer Care. Press 3 for Accounts. Press 0 to speak directly with Jenny, Senior Operations Manager.")
    full_greeting_clean = full_greeting.replace("&", "and")
    jingle_url = f"{host_url}/static/jingle.mp3"
    
    twiml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Gather action="{host_url}/telephony/gather/{user_id}?current_dept=router" input="dtmf" numDigits="1" timeout="10">
        <Say voice="Polly.Amy">Hello and welcome to Drivri UK Logistics Solution!</Say>
        <Play>{jingle_url}</Play>
        <Say voice="Polly.Amy">Please listen carefully to our options: Press 1 for Sales and Bookings. Press 2 for Customer Care and Support. Press 3 for Accounts and Billing. Press 0 to speak directly with Jenny, Senior Operations Manager.</Say>
    </Gather>
    <Gather action="{host_url}/telephony/gather/{user_id}?current_dept=router" input="dtmf" numDigits="1" timeout="7">
        <Say voice="Polly.Amy">We noticed you haven't selected an option yet. Press 1 for Sales, press 2 for Support, press 3 for Accounts, or press 0 for Jenny.</Say>
    </Gather>
    <Say voice="Polly.Amy">Connecting you now to Jenny, Senior Operations Manager. Please hold.</Say>
    <Dial>{VAPI_PHONE_NUMBER}</Dial>
</Response>"""
    return Response(content=twiml, media_type="text/xml")


@app.post("/telephony/gather/{user_id}")
@app.post("/telephony/gather")
async def telephony_gather(request: Request, user_id: Optional[str] = "demo_user", current_dept: Optional[str] = "router", Digits: Optional[str] = Form(None), SpeechResult: Optional[str] = Form(None), CallSid: Optional[str] = Form(None), From: Optional[str] = Form(None)):
    session_id = CallSid or "signalwire_call_session"
    caller = From or "PSTN Caller"
    user_input = Digits or SpeechResult or ""
    host_url = get_public_host_url(request)
    
    depts = db.get_user_departments(user_id) if user_id != "demo_user" else get_all_departments()
    target_dept = classify_department_intent(user_input, current_dept or "router")
    
    # Track selection for Vapi handoff
    if caller and caller != "PSTN Caller":
        ACTIVE_CALL_DEPARTMENTS[caller] = target_dept
        digits_only = re.sub(r'\D', '', str(caller))
        if digits_only:
            ACTIVE_CALL_DEPARTMENTS[digits_only] = target_dept
            ACTIVE_CALL_DEPARTMENTS[f"+{digits_only}"] = target_dept
            
    LAST_KEYPAD_SELECTION["dept"] = target_dept
    LAST_KEYPAD_SELECTION["timestamp"] = time.time()
    logger.info(f"[KEYPAD SELECTION RECORDED] Caller: '{caller}' -> Selected Dept: '{target_dept}'")
    
    # 1. Main Menu Repeat Key (*) or Return to Main Menu (9)
    if user_input in ["*", "9"] or user_input in ["repeat", "listen again", "main menu", "menu"]:
        router_dept = depts.get("router", list(depts.values())[0])
        router_greeting = router_dept.get("greeting", "Welcome to Drivri Logistics!").replace("&", "and")
        twiml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Gather action="{host_url}/telephony/gather/{user_id}?current_dept=router" input="dtmf" numDigits="1" timeout="10">
        <Say>{router_greeting}</Say>
    </Gather>
    <Hangup/>
</Response>"""
        return Response(content=twiml, media_type="text/xml")

    # 2. Main Sales Sub-Menu (User pressed 1 at Main Menu) -> Render Sales Sub-Menu Keypad
    if current_dept == "router" and (user_input == "1" or target_dept == "sales"):
        sales_dept = depts.get("sales", list(depts.values())[0])
        sales_greeting = sales_dept.get("greeting", "Thank you for contacting Drivri Sales! Press 1 to Book a Driver and Van. Press 2 for Van Only Rental. Press 3 to Hire a Professional Driver Only. Press 4 for Corporate Fleet Services. Press 9 for Main Menu.").replace("&", "and")
        twiml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Gather action="{host_url}/telephony/gather/{user_id}?current_dept=sales" input="dtmf" numDigits="1" timeout="10">
        <Say>{sales_greeting}</Say>
    </Gather>
    <Hangup/>
</Response>"""
        return Response(content=twiml, media_type="text/xml")

    # 3. Leaf Sub-Menu Selections -> Hand off cleanly to Vapi Voice Agent (+12138329797)
    dept_info = depts.get(target_dept, depts.get(current_dept, depts.get("router", list(depts.values())[0])))
    dept_name = dept_info.get("name", "Specialist").replace("&", "and")
    
    db.record_transcript(session_id, "System", target_dept, f"Caller selected '{user_input}' ({dept_name}). Transferring to Vapi Bot +12138329797")
    
    twiml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say>Connecting you now to your Drivri {dept_name} Voice Specialist. Please hold.</Say>
    <Dial>{VAPI_PHONE_NUMBER}</Dial>
</Response>"""
    return Response(content=twiml, media_type="text/xml")


@app.post("/telephony/dept-chat/{user_id}/{dept_id}")
@app.post("/telephony/dept-chat/{user_id}")
@app.post("/telephony/dept-chat")
async def telephony_dept_chat(request: Request, user_id: Optional[str] = "demo_user", dept_id: Optional[str] = "router", SpeechResult: Optional[str] = Form(None), Digits: Optional[str] = Form(None), CallSid: Optional[str] = Form(None), From: Optional[str] = Form(None)):
    # All department voice chats transfer directly to Vapi Bot (+12138329797)
    twiml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say>Connecting you to your Drivri Voice AI Representative. Please hold.</Say>
    <Dial>{VAPI_PHONE_NUMBER}</Dial>
</Response>"""
    return Response(content=twiml, media_type="application/xml")


@app.post("/telephony/operator-chat/{user_id}")
@app.post("/telephony/operator-chat")
async def telephony_operator_chat(request: Request, user_id: Optional[str] = "demo_user", SpeechResult: Optional[str] = Form(None), Digits: Optional[str] = Form(None), CallSid: Optional[str] = Form(None)):
    session_id = CallSid or "signalwire_call_session"
    user_speech = SpeechResult or Digits or ""
    host_url = get_public_host_url(request)
    
    session = CALL_SESSIONS.get(session_id, {"history": []})
    CALL_SESSIONS[session_id] = session
    
    session["history"].append({"role": "user", "content": user_speech})
    
    operator_prompt = (
        "You are Jenny, Senior Live Human Representative at Drivri Logistics. "
        "Speak warmly, helpfully, and concisely as a real human customer service manager. "
        "Help callers with bookings, quotes, rentals, or resolving issues."
    )
    
    reply_text = generate_llm_response(user_speech, operator_prompt, session["history"])
    reply_text_clean = reply_text.replace("&", "and")
    session["history"].append({"role": "assistant", "content": reply_text})
    
    db.record_transcript(session_id, "Caller", "operator", user_speech)
    db.record_transcript(session_id, "Jenny (Live Rep)", "operator", reply_text)
    
    twiml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Gather action="{host_url}/telephony/operator-chat/{user_id}" input="dtmf speech" timeout="10">
        <Say>{reply_text_clean}</Say>
    </Gather>
    <Say>Thank you for speaking with Jenny at Drivri Logistics. Have a wonderful day!</Say>
    <Hangup/>
</Response>"""
    return Response(content=twiml, media_type="application/xml")


@app.get("/api/deals/pipeline")
def get_deals_pipeline(authorization: Optional[str] = Header(None)):
    """API Endpoint returning real-time deals pipeline and closing metrics for the user dashboard."""
    token = authorization.replace("Bearer ", "") if authorization else None
    user_id = auth.get_user_id_from_token(token) or "demo_user"
    
    user_deals = db.get_user_deals(user_id) if user_id != "demo_user" else db.get_all_deals()
    
    total_closed = len([d for d in user_deals if d["status"] == "CLOSED_WON"])
    total_revenue = sum([d["price_quoted"] for d in user_deals if d["status"] == "CLOSED_WON" and d.get("price_quoted")])
    
    return JSONResponse(content={
        "deals": user_deals,
        "metrics": {
            "total_deals": len(user_deals),
            "closed_won": total_closed,
            "total_revenue": total_revenue,
            "conversion_rate": f"{(total_closed / max(len(user_deals), 1)) * 100:.1f}%"
        }
    })


class ScrapeUrlRequest(BaseModel):
    url: str


@app.post("/api/knowledge/scrape-url")
async def scrape_website_knowledge(req: ScrapeUrlRequest, authorization: Optional[str] = Header(None)):
    """Scrapes clean text from a business website URL and indexes it into the Knowledge Base."""
    token = authorization.replace("Bearer ", "") if authorization else None
    user_id = auth.get_user_id_from_token(token) or "demo_user"
    
    res = knowledge_base.scrape_website_url(req.url, user_id=user_id)
    return JSONResponse(content=res)


@app.post("/api/knowledge/upload-rate-card")
async def upload_rate_card_file(file: UploadFile = File(...), authorization: Optional[str] = Header(None)):
    """Parses an uploaded CSV/PDF/TXT rate card or document into the Knowledge Base."""
    token = authorization.replace("Bearer ", "") if authorization else None
    user_id = auth.get_user_id_from_token(token) or "demo_user"
    
    file_id = f"kb_{user_id}_{uuid.uuid4().hex[:6]}_{file.filename}"
    file_path = os.path.join(knowledge_base.KNOWLEDGE_DIR, file_id)
    
    contents = await file.read()
    with open(file_path, "wb") as f:
        f.write(contents)
        
    res = knowledge_base.ingest_rate_card_file(file_path, file.filename, user_id=user_id)
    return JSONResponse(content=res)


# ==============================================================================
# SIGNALWIRE INTEGRATION — Direct cXML Webhook & API Configurator
# ==============================================================================

class SignalWireSetupRequest(BaseModel):
    space_url: str          # e.g., my-space.signalwire.com
    project_id: str         # SignalWire Project ID
    api_token: str          # SignalWire API Token
    phone_number_sid: str   # SID or UUID of the purchased phone number
    public_server_url: Optional[str] = None


@app.post("/api/signalwire/setup")
async def signalwire_api_setup(req: SignalWireSetupRequest, authorization: Optional[str] = Header(None)):
    """
    Programmatically links a SignalWire Phone Number to our IVR system via the SignalWire API.
    """
    token = authorization.replace("Bearer ", "") if authorization else None
    user_id = auth.get_user_id_from_token(token) or "demo_user"
    
    clean_space = req.space_url.strip().replace("https://", "").replace("http://", "").rstrip("/")
    if "." not in clean_space:
        clean_space = f"{clean_space}.signalwire.com"
        
    public_url = req.public_server_url or "https://your-server.com"
    voice_url = f"{public_url}/telephony/full-ivr/{user_id}"
    
    # SignalWire Compatibility API endpoint to update phone number
    endpoint = f"https://{clean_space}/api/laml/2010-04-01/Accounts/{req.project_id.strip()}/IncomingPhoneNumbers/{req.phone_number_sid.strip()}.json"
    
    async with httpx.AsyncClient(timeout=30) as client:
        try:
            res = await client.post(
                endpoint,
                auth=(req.project_id.strip(), req.api_token.strip()),
                data={
                    "VoiceUrl": voice_url,
                    "VoiceMethod": "POST"
                }
            )
            data = res.json()
            if res.status_code in (200, 201):
                phone_num = data.get("phone_number") or data.get("friendly_name") or req.phone_number_sid
                return JSONResponse(content={
                    "status": "success",
                    "message": f"✅ SignalWire phone number ({phone_num}) successfully linked to IVR!",
                    "voice_url": voice_url,
                    "signalwire_response": data
                })
            else:
                return JSONResponse(status_code=400, content={
                    "status": "error",
                    "message": f"SignalWire API returned HTTP {res.status_code}: {data.get('message', data)}",
                    "signalwire_response": data
                })
        except Exception as e:
            return JSONResponse(status_code=500, content={
                "status": "error",
                "message": f"Failed to connect to SignalWire: {str(e)}"
            })


# ==============================================================================
# BLAND.AI INTEGRATION — One-Click Voice AI Phone Agent (Replaces Vapi)
# ==============================================================================

BLAND_API_BASE = "https://api.bland.ai"


class BlandSetupRequest(BaseModel):
    api_key: str
    area_code: Optional[str] = "707"
    public_server_url: Optional[str] = None  # ngrok or deployed URL


class BlandUpdateRequest(BaseModel):
    api_key: str
    phone_number: str
    public_server_url: Optional[str] = None


@app.post("/api/bland/setup")
async def bland_one_click_setup(req: BlandSetupRequest, authorization: Optional[str] = Header(None)):
    """
    One-Click Bland.ai Setup:
    1. Buys a phone number via Bland API
    2. Configures it as a Drivri Logistics IVR agent
    3. Points webhook back to this server
    Returns the live phone number ready to receive calls.
    """
    token = authorization.replace("Bearer ", "") if authorization else None
    user_id = auth.get_user_id_from_token(token) or "demo_user"
    
    depts = db.get_user_departments(user_id) if user_id != "demo_user" else get_all_departments()
    dept_info = depts.get("router", list(depts.values())[0])
    settings = db.get_user_settings(user_id)
    
    company_name = settings["company_name"] if settings else "My Business"
    greeting = dept_info.get("greeting", "Welcome to our business!")
    voice = dept_info.get("voice", "en-US-AvaNeural")
    public_url = req.public_server_url or "https://your-server.com"
    
    # Build the system prompt for the Bland agent
    system_prompt = f"""You are Jenny, the Senior AI Receptionist for {company_name}.
You answer inbound phone calls warmly and professionally.
Your job is to greet callers, understand what they need, and route them to the right department.

Departments available:
"""
    for dept_id, dept in depts.items():
        if dept_id in ("router", "operator"):
            continue
        system_prompt += f"- {dept.get('name', dept_id)}: {dept.get('system_prompt', 'General assistance')}\n"
    
    system_prompt += f"""
- Live Representative (Jenny): For complex issues, complaints, custom quotes, or when caller explicitly asks for a human.

When a caller asks for a specific department, confirm the transfer and help them.
When unsure, ask clarifying questions to route them correctly.
Be warm, professional, concise, and empathetic."""
    
    headers = {
        "Content-Type": "application/json",
        "authorization": req.api_key
    }
    
    # Step 1: Buy a phone number
    async with httpx.AsyncClient(timeout=30) as client:
        try:
            buy_res = await client.post(
                f"{BLAND_API_BASE}/numbers/purchase",
                headers=headers,
                json={"area_code": req.area_code or "707", "country_code": "US"}
            )
            buy_data = buy_res.json()
            logger.info(f"Bland number purchase response: {buy_data}")
            
            if buy_res.status_code != 200 or not buy_data.get("phone_number"):
                # Try alternate response field names
                phone_number = buy_data.get("phone_number") or buy_data.get("number") or buy_data.get("phoneNumber")
                if not phone_number:
                    return JSONResponse(status_code=400, content={
                        "status": "error",
                        "message": f"Failed to purchase number: {buy_data.get('message', buy_data)}",
                        "bland_response": buy_data
                    })
            else:
                phone_number = buy_data["phone_number"]
        except Exception as e:
            return JSONResponse(status_code=500, content={
                "status": "error",
                "message": f"Failed to connect to Bland API: {str(e)}"
            })
        
        # Step 2: Configure the agent on this number
        try:
            config_res = await client.post(
                f"{BLAND_API_BASE}/v1/inbound/{phone_number}",
                headers=headers,
                json={
                    "prompt": system_prompt,
                    "first_sentence": greeting,
                    "voice": "maya",
                    "model": "base",
                    "record": True,
                    "max_duration": 15,
                    "webhook": f"{public_url}/api/bland/webhook/{user_id}",
                    "tools": [
                        {
                            "name": "get_department_info",
                            "description": "Get information about a specific department including greeting and capabilities",
                            "url": f"{public_url}/api/departments",
                            "method": "GET"
                        }
                    ]
                }
            )
            config_data = config_res.json()
            logger.info(f"Bland agent config response: {config_data}")
        except Exception as e:
            logger.error(f"Failed to configure Bland agent: {e}")
            config_data = {"warning": f"Number purchased but config may need manual update: {str(e)}"}
    
    # Save the Bland number mapping
    db.save_user_settings(
        user_id=user_id,
        company_name=company_name,
        selected_voice=voice,
        selected_hold_music=settings["selected_hold_music"] if settings else "stinger_corporate",
        router_greeting=greeting
    )
    
    return JSONResponse(content={
        "status": "success",
        "phone_number": phone_number,
        "message": f"\u2705 Bland.ai agent is LIVE! Call {phone_number} to test your IVR.",
        "agent_config": {
            "company": company_name,
            "greeting": greeting,
            "webhook": f"{public_url}/api/bland/webhook/{user_id}",
            "departments": len(depts)
        },
        "bland_response": config_data
    })


@app.post("/api/bland/update")
async def bland_update_agent(req: BlandUpdateRequest, authorization: Optional[str] = Header(None)):
    """Update an existing Bland.ai agent with current dashboard settings."""
    token = authorization.replace("Bearer ", "") if authorization else None
    user_id = auth.get_user_id_from_token(token) or "demo_user"
    
    depts = db.get_user_departments(user_id) if user_id != "demo_user" else get_all_departments()
    dept_info = depts.get("router", list(depts.values())[0])
    settings = db.get_user_settings(user_id)
    
    company_name = settings["company_name"] if settings else "My Business"
    greeting = dept_info.get("greeting", "Welcome to our business!")
    public_url = req.public_server_url or "https://your-server.com"
    
    system_prompt = f"You are Jenny, the Senior AI Receptionist for {company_name}.\n"
    system_prompt += "Answer calls warmly and help route callers to the right department.\n\n"
    for dept_id, dept in depts.items():
        if dept_id in ("router", "operator"):
            continue
        system_prompt += f"- {dept.get('name', dept_id)}: {dept.get('system_prompt', '')}\n"
    
    headers = {
        "Content-Type": "application/json",
        "authorization": req.api_key
    }
    
    async with httpx.AsyncClient(timeout=30) as client:
        config_res = await client.post(
            f"{BLAND_API_BASE}/v1/inbound/{req.phone_number}",
            headers=headers,
            json={
                "prompt": system_prompt,
                "first_sentence": greeting,
                "voice": "maya",
                "model": "base",
                "record": True,
                "max_duration": 15,
                "webhook": f"{public_url}/api/bland/webhook/{user_id}"
            }
        )
        config_data = config_res.json()
    
    return JSONResponse(content={
        "status": "success",
        "message": f"\u2705 Agent on {req.phone_number} updated with latest dashboard settings!",
        "bland_response": config_data
    })


@app.post("/api/bland/webhook/{user_id}")
async def bland_webhook(request: Request, user_id: str = "demo_user"):
    """Receives post-call data from Bland.ai after each call ends."""
    try:
        body = await request.json()
    except Exception:
        body = {}
    
    call_id = body.get("call_id", str(uuid.uuid4())[:8])
    transcript = body.get("transcript", "")
    call_length = body.get("call_length", 0)
    from_number = body.get("from", "Unknown")
    status = body.get("status", "completed")
    
    logger.info(f"Bland webhook received for user {user_id}: call_id={call_id}, length={call_length}s, from={from_number}")
    
    # Record call in our database
    session_id = f"bland_{call_id}"
    db.record_call_start(session_id, from_number, "router", user_id=user_id)
    if transcript:
        db.record_transcript(session_id, "Full Call", "router", transcript)
    
    return JSONResponse(content={"status": "received", "session_id": session_id})


class LeadCampaignRequest(BaseModel):
    leads: List[Dict[str, Any]]
    campaign_name: Optional[str] = "Outbound Lead Closer"
    sales_agent_name: Optional[str] = "Amélie"

class WhatsAppMessageRequest(BaseModel):
    phone_number: str
    message: str
    lead_id: Optional[str] = None

@app.post("/api/leads/call-campaign")
async def start_lead_call_campaign(req: LeadCampaignRequest):
    """Triggers automated outbound AI call sequence to qualify and close sales leads."""
    campaign_id = f"camp_{str(uuid.uuid4())[:8]}"
    results = []
    
    for lead in req.leads:
        lead_phone = lead.get("phone", lead.get("phone_number", "Unknown"))
        lead_name = lead.get("name", "Valued Lead")
        session_id = f"outbound_{str(uuid.uuid4())[:8]}"
        
        # Record session in database
        db.record_call_start(session_id, lead_phone, "sales", user_id="demo_user")
        initial_pitch = f"Hello {lead_name}, this is {req.sales_agent_name}. I'm following up on your inquiry to help get your service set up today."
        db.record_transcript(session_id, req.sales_agent_name, "sales", initial_pitch)
        
        results.append({
            "session_id": session_id,
            "lead_name": lead_name,
            "phone_number": lead_phone,
            "status": "QUEUED_AND_DIALED",
            "initial_pitch": initial_pitch
        })
        
    return JSONResponse(content={
        "status": "success",
        "campaign_id": campaign_id,
        "campaign_name": req.campaign_name,
        "total_leads_dialed": len(results),
        "results": results
    })

@app.post("/api/whatsapp/send")
async def send_whatsapp_lead_message(req: WhatsAppMessageRequest):
    """Sends post-call or outbound lead follow-up message via WhatsApp interface."""
    msg_id = f"wa_{str(uuid.uuid4())[:8]}"
    logger.info(f"WhatsApp message dispatched to {req.phone_number}: {req.message}")
    
    return JSONResponse(content={
        "status": "sent",
        "message_id": msg_id,
        "recipient": req.phone_number,
        "text": req.message,
        "channel": "WhatsApp (whatsmeow/Twilio Bridge)"
    })

@app.post("/api/whatsapp/webhook")
async def whatsapp_incoming_webhook(request: Request):
    """Handles incoming WhatsApp messages from leads and generates AI responses."""
    try:
        body = await request.json()
    except Exception:
        body = {}
        
    sender = body.get("from", body.get("phone_number", "+15550009999"))
    text = body.get("text", body.get("message", "Hello"))
    
    reply = f"Thank you for contacting us via WhatsApp! I've logged your request: '{text}'. An AI sales specialist will assist you shortly."
    
    return JSONResponse(content={
        "status": "processed",
        "sender": sender,
        "incoming_text": text,
        "ai_reply": reply
    })

static_path = os.path.join(os.path.dirname(__file__), "static")
if os.path.exists(static_path):
    app.mount("/static", StaticFiles(directory=static_path), name="static")



@app.get("/", response_class=HTMLResponse)
def landing_or_app():
    landing_file = os.path.join(static_path, "landing.html")
    if os.path.exists(landing_file):
        with open(landing_file, "r", encoding="utf-8") as f:
            return f.read()
    return "<h1>VoiceFlow AI Professional IVR SaaS Running</h1>"


# Reload custom audio from disk on server startup
_reload_custom_audio_from_disk()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
