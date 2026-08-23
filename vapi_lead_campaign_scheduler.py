"""
Vapi Outbound Vertical Lead Campaign Scheduler & AI Dialing Engine.
Dispatches scheduled outbound sales calls with category-specific scripts (Courier, Van Hire, Warehousing).
"""

import os
import sys
import json
import time
import requests
from typing import List, Dict, Any, Optional

VAPI_API_KEY = os.getenv("VAPI_API_KEY", "YOUR_VAPI_API_KEY")
VAPI_API_URL = "https://api.vapi.ai/call/phone"

# Category-Specific AI Sales Prompts
VERTICAL_SALES_SCRIPTS = {
    "courier_express": {
        "first_message": "Hello {name}! This is Amélie calling from Drivri Express Courier. I noticed your business handles regular UK freight. Do you have 60 seconds to hear how we save 20% on same-day deliveries?",
        "system_prompt": """You are Amélie, Senior Specialist for Drivri Express Courier UK.
Your goal is to pitch same-day UK courier, pallet shipping, and express freight.
Offer a 15% discount on their first 3 shipments. Ask about their current delivery volume and close a booking or quote request."""
    },
    "van_hire": {
        "first_message": "Hello {name}! This is Amélie from Drivri Commercial Fleet Hire. We're currently providing Luton van hire with driver in your area with 200 free miles daily.",
        "system_prompt": """You are Amélie, Rental Specialist for Drivri Commercial Van Hire.
Your goal is to pitch Luton van hire, self-drive, and driver hire options for commercial transport.
Highlight no-deposit options and 24-hour daily rates. Close a reservation or send a rate sheet."""
    },
    "warehousing": {
        "first_message": "Hello {name}! Amélie here from Drivri Storage & Warehousing. We have secure pallet storage slots open in London and Manchester this week.",
        "system_prompt": """You are Amélie, Storage Logistics Manager for Drivri Warehousing.
Your goal is to pitch pallet storage, inventory fulfillment, and secure city parking bays.
Ask how many pallets they currently store and offer a free 1-week storage trial."""
    }
}

def dispatch_vertical_lead_call(
    phone_number: str,
    lead_name: str,
    vertical: str = "courier_express",
    company_name: Optional[str] = None,
    api_key: Optional[str] = None
) -> Dict[str, Any]:
    """Dispatches a category-tailored outbound sales call via Vapi API."""
    key = api_key or VAPI_API_KEY
    if key == "YOUR_VAPI_API_KEY":
        return {
            "status": "error",
            "message": "VAPI_API_KEY not set. Set environment variable VAPI_API_KEY or pass api_key."
        }

    script_info = VERTICAL_SALES_SCRIPTS.get(vertical, VERTICAL_SALES_SCRIPTS["courier_express"])
    first_msg = script_info["first_message"].format(name=lead_name or "there")
    sys_prompt = script_info["system_prompt"]

    headers = {
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json"
    }

    payload = {
        "phoneNumber": phone_number,
        "customer": {
            "name": lead_name,
            "number": phone_number
        },
        "assistant": {
            "firstMessage": first_msg,
            "model": {
                "provider": "openai",
                "model": "gpt-4o-mini",
                "messages": [
                    {
                        "role": "system",
                        "content": sys_prompt
                    }
                ]
            },
            "voice": {
                "provider": "azure",
                "voiceId": "en-US-AvaNeural"
            }
        }
    }

    try:
        response = requests.post(VAPI_API_URL, headers=headers, json=payload, timeout=15)
        return {
            "status": "success" if response.status_code in [200, 201] else "failed",
            "http_code": response.status_code,
            "lead": {"name": lead_name, "phone": phone_number, "vertical": vertical},
            "vapi_response": response.json()
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}

def run_lead_campaign_by_vertical(leads: List[Dict[str, str]], api_key: Optional[str] = None) -> List[Dict[str, Any]]:
    """Runs a batch campaign across leads with industry vertical routing."""
    results = []
    print(f"🚀 Processing Vapi Vertical Campaign for {len(leads)} leads...")
    for idx, lead in enumerate(leads, 1):
        name = lead.get("name", "Prospect")
        phone = lead.get("phone", "")
        vertical = lead.get("vertical", "courier_express")
        print(f"[{idx}/{len(leads)}] Dialing {name} ({phone}) for vertical '{vertical}'...")
        res = dispatch_vertical_lead_call(phone, name, vertical=vertical, api_key=api_key)
        results.append(res)
        time.sleep(1.5)
    return results

if __name__ == "__main__":
    sample_leads = [
        {"name": "David Miller", "phone": "+447911123456", "vertical": "courier_express"},
        {"name": "Rachel Adams", "phone": "+447922233445", "vertical": "van_hire"},
        {"name": "Mark Stevens", "phone": "+447933344556", "vertical": "warehousing"}
    ]
    print("Vapi Category-Specific Outbound Campaign Scheduler Engine Ready.")
