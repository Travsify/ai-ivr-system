"""
Supersonic Autonomous Agentic AI Engine supporting Stateful Slot Extraction,
Anti-Parroting Prompting, Instant Deal Closing, Edge-TTS, and Ollama LLM.
Requires ZERO paid API keys and ZERO external platform subscriptions.
"""

import os
import io
import re
import random
import asyncio
import logging
import requests
import edge_tts
from typing import Dict, List, Optional, Any
from departments import get_all_departments

logger = logging.getLogger("AIEngine")
logging.basicConfig(level=logging.INFO)

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434/api/generate")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.2")


async def generate_tts_audio(text: str, voice_name: str = "en-US-AvaNeural") -> bytes:
    """Generates neural TTS audio bytes (MP3) for free using edge-tts."""
    try:
        communicate = edge_tts.Communicate(text, voice_name)
        buffer = io.BytesIO()
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                buffer.write(chunk["data"])
        return buffer.getvalue()
    except Exception as e:
        logger.error(f"TTS generation error: {e}")
        return b""


def extract_slots(prompt: str, history: Optional[List[Dict[str, str]]] = None, existing_slots: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Extracts logistics parameters (pickup, delivery, vehicle, date, price) statefully across conversation turns.
    """
    slots = existing_slots.copy() if existing_slots else {
        "pickup": None,
        "delivery": None,
        "vehicle": None,
        "date": None,
        "price": None,
        "booking_id": None,
        "deal_status": "QUALIFYING"
    }

    p_text = prompt.strip()
    p_lower = p_text.lower()

    # Combine prompt + history for context scanning
    all_text = p_lower
    if history:
        all_text += " " + " ".join([m.get("content", "").lower() for m in history])

    # 1. Vehicle Class & Pricing Detection
    if not slots["vehicle"]:
        if "luton" in all_text:
            slots["vehicle"] = "Large Luton Van with Tail-lift"
            slots["price"] = 145.0
        elif "transit" in all_text or "medium" in all_text:
            slots["vehicle"] = "Medium Transit Van"
            slots["price"] = 120.0
        elif "van only" in all_text or "self drive" in all_text:
            slots["vehicle"] = "Small Van Rental"
            slots["price"] = 85.0
        elif "driver only" in all_text:
            slots["vehicle"] = "Certified Driver Only"
            slots["price"] = 75.0
        elif "corporate" in all_text or "fleet" in all_text:
            slots["vehicle"] = "Corporate Commercial Fleet"
            slots["price"] = 250.0
        elif "driver" in all_text or "van" in all_text:
            slots["vehicle"] = "Driver & Van Service"
            slots["price"] = 120.0

    # 2. Pickup Location / Postcode Extraction
    if not slots["pickup"]:
        postcode_match = re.search(r'\b[a-z]{1,2}\d[a-z0-9]?\s*\d[a-z]{2}\b|\b\d{5}\b', p_text, re.IGNORECASE)
        if postcode_match:
            slots["pickup"] = postcode_match.group(0).upper()
        elif any(w in p_lower for w in ["street", "road", "london", "pickup", "from", "avenue", "lane", "drive", "east ham", "high street", "station"]):
            slots["pickup"] = p_text

    # 3. Delivery / Destination Extraction
    elif not slots["delivery"]:
        postcode_match = re.search(r'\b[a-z]{1,2}\d[a-z0-9]?\s*\d[a-z]{2}\b|\b\d{5}\b', p_text, re.IGNORECASE)
        if postcode_match and slots["pickup"] and postcode_match.group(0).upper() != slots["pickup"]:
            slots["delivery"] = postcode_match.group(0).upper()
        elif any(w in p_lower for w in ["to", "destination", "deliver", "dropoff", "drop", "street", "road", "manchester", "birmingham"]):
            slots["delivery"] = p_text

    # 4. Date & Time Extraction
    if not slots["date"]:
        for date_keyword in ["tomorrow morning", "tomorrow afternoon", "tomorrow", "today", "next monday", "monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]:
            if date_keyword in all_text:
                slots["date"] = date_keyword.title()
                break

    # Sensible fallbacks if partially filled
    if not slots["date"]:
        slots["date"] = "Tomorrow Morning"

    if not slots["vehicle"]:
        slots["vehicle"] = "Driver & Van Package"
        slots["price"] = 120.0

    return slots


def generate_llm_response(prompt: str, system_prompt: str, history: Optional[List[Dict[str, str]]] = None, slots: Optional[Dict[str, Any]] = None) -> str:
    """
    Supersonic Autonomous Voice Agent Engine:
    - Never repeats user input or uses conversational filler ("Got it", "I understand").
    - Tracks missing parameter slots statefully.
    - Autonomously calculates quotes and closes sales with booking IDs.
    """
    current_slots = slots or {}
    p_lower = prompt.lower().strip()

    # Detect Closing Affirmation ("yes", "book it", "lock it in", "go ahead", "sure", "sounds good")
    if any(w in p_lower for w in ["yes", "book it", "lock it in", "go ahead", "sure", "sounds good", "confirm", "ok", "do it"]):
        if not current_slots.get("booking_id"):
            b_id = f"DRV-{random.randint(1000, 9999)}"
            current_slots["booking_id"] = b_id
            current_slots["deal_status"] = "CLOSED_WON"
        return f"Locked in! Your booking confirmation is {current_slots['booking_id']}. A text summary has been dispatched to your mobile."

    # Try local Ollama LLM if running with supersonic anti-parroting instructions
    full_system = (
        f"{system_prompt}\n"
        "SUPERSONIC AGENTIC RULES:\n"
        "1. DO NOT say 'Got it', 'I understand', 'Thank you for providing that', or repeat back user speech.\n"
        "2. DO NOT ask questions for parameters already collected.\n"
        f"3. CURRENT SLOTS GATHERED: Pickup: {current_slots.get('pickup')}, Delivery: {current_slots.get('delivery')}, Vehicle: {current_slots.get('vehicle')}, Price: £{current_slots.get('price')}.\n"
        "4. Keep response under 18 words. Speak directly, confidently, and professionally."
    )

    full_prompt = f"System: {full_system}\n"
    if history:
        for msg in history[-4:]:
            full_prompt += f"{msg['role'].capitalize()}: {msg['content']}\n"
    full_prompt += f"User: {prompt}\nAssistant:"

    try:
        payload = {
            "model": OLLAMA_MODEL,
            "prompt": full_prompt,
            "stream": False
        }
        res = requests.post(OLLAMA_URL, json=payload, timeout=3)
        if res.status_code == 200:
            data = res.json()
            response_text = data.get("response", "").strip()
            if response_text and len(response_text) > 5:
                # Clean filler phrases if LLM accidentally outputs them
                clean_text = re.sub(r'^(got it|i understand|thank you|great|awesome|okay)[,!.\s]*', '', response_text, flags=re.IGNORECASE).strip()
                if clean_text:
                    return clean_text[:180]
    except Exception:
        pass

    # High-Velocity Fallback Engine (No Parroting, Direct Conversational Closing)
    pickup = current_slots.get("pickup")
    delivery = current_slots.get("delivery")
    vehicle = current_slots.get("vehicle", "Driver & Van Package")
    price = current_slots.get("price", 120.0)
    date = current_slots.get("date", "Tomorrow Morning")

    # Slot 1: Missing Pickup
    if not pickup:
        return "Where is your pickup location or postcode?"

    # Slot 2: Missing Delivery
    if not delivery:
        return "And what is your delivery destination address?"

    # Slot 3: Both Pickup & Delivery gathered -> Pitch Closing Quote
    if pickup and delivery and not current_slots.get("deal_status") == "CLOSED_WON":
        return f"I have a {vehicle} available for {date} at £{int(price)} total including fuel and driver. Shall I lock this slot in for you now?"

    # Generic High-Speed Turn
    return f"Our {vehicle} rate is £{int(price)} for {date}. Would you like me to confirm this booking for you?"
