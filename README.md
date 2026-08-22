# Production AI IVR System — PSTN & WebRTC Gateway

A complete, production-grade self-hosted AI Interactive Voice Response (IVR) system. It handles incoming phone calls from real cell phones (PSTN) or web browsers, routes users via DTMF keypad presses (`1`, `2`, `3`, `0`) or natural speech intent, transfers callers to specialized AI department agents (**Sales**, **Marketing**, **Accounts**), supports **Human Operator fallback**, and logs all call history and transcripts to SQLite.

---

## 🛠️ Complete Architecture

```
[ Real Cell Phone / Browser Caller ]
                 │
                 ├───> (PSTN Carrier: Twilio / Telnyx / VoIP.ms / Asterisk)
                 │                   │
                 ▼                   ▼
    ┌────────────────────────────────────────────────────────┐
    │     FastAPI AI IVR Gateway (Port 8000)                 │
    │     Endpoints:                                         │
    │      - PSTN TwiML/TeXML: /telephony/inbound            │
    │      - WebRTC / Browser: /api/call/start              │
    │      - Call History DB: /api/logs                      │
    └────────────────────────┬───────────────────────────────┘
                             │
          ┌──────────────────┼──────────────────┐
          ▼                  ▼                  ▼
    ┌───────────┐      ┌───────────┐      ┌───────────┐
    │   Sales   │      │ Marketing │      │ Accounts  │
    └─────┬─────┘      └─────┬─────┘      └─────┬─────┘
          │                  │                  │
          └──────────────────┼──────────────────┘
                             │
                             ▼
              ┌─────────────────────────────┐
              │ SQLite Database & Log Store │
              └─────────────────────────────┘
```

---

## 🌐 How to Connect Real Cell Phone Numbers (Twilio / Telnyx / VoIP.ms)

To have real cell phones call into your AI IVR system:

### Step 1: Expose your Server Publicly (Free Webhook URL)
Use **Ngrok** (free) or host on your VPS:
```bash
ngrok http 8000
```
*(Copy the generated HTTPS URL, e.g., `https://xxxx.ngrok-free.app`)*

### Step 2: Configure your Carrier Webhook
1. Log into your **Twilio**, **Telnyx**, or **VoIP.ms** console.
2. Select your phone number.
3. Under **A Call Comes In** (Webhook), select **HTTP POST** and paste:
   ```
   https://xxxx.ngrok-free.app/telephony/inbound
   ```
4. Save settings.

### Step 3: Test Real Cell Phone Calling
Dial your phone number from any mobile phone in the world! 
* The server will answer automatically.
* Plays the neural IVR greeting.
* Press `1` for Sales, `2` for Marketing, `3` for Accounts, or `0` to transfer to a human operator!

---

## 💻 Local Running & Testing

1. Launch the server:
   ```bash
   python server.py
   ```
2. Open **`http://localhost:8000`** in your browser.
3. Use the web dialpad, test keypad DTMF inputs, view SQLite call logs, and test speech input directly from your microphone.
