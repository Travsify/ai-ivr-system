"""
Vapi Outbound AI Lead Dialing & Sales Closing Engine.
Dispatches phone calls to lead lists using Vapi API to pitch services, qualify prospects, and close deals.
"""

import os
import sys
import json
import time
import requests
from typing import List, Dict, Any, Optional

VAPI_API_KEY = os.getenv("VAPI_API_KEY", "YOUR_VAPI_API_KEY")
VAPI_PHONE_NUMBER_ID = os.getenv("VAPI_PHONE_NUMBER_ID", "YOUR_VAPI_PHONE_NUMBER_ID")
VAPI_ASSISTANT_ID = os.getenv("VAPI_ASSISTANT_ID", "YOUR_VAPI_ASSISTANT_ID")
VAPI_API_URL = "https://api.vapi.ai/call/phone"

DEFAULT_SALES_PROMPT = """
You are Amélie, Senior Sales Specialist for Drivri UK Logistics Solution.
Your goal is to call phone leads, introduce Drivri's courier and logistics services, qualify their transport needs, and close the deal.

Key Selling Points:
- Same-day UK courier dispatch & Luton van hire with driver.
- 15% discount for first-time corporate clients.
- Guaranteed 60-minute pickup window across Greater London and major UK cities.

Steps:
1. Warm greeting to the prospect by name.
2. Briefly explain how Drivri saves 20% on UK logistics costs.
3. Ask about their current shipping/transport volume.
4. Offer an instant quote and request to confirm their initial delivery booking today.
"""

def dispatch_vapi_outbound_call(
    phone_number: str,
    lead_name: str,
    company_name: Optional[str] = None,
    api_key: Optional[str] = None,
    assistant_id: Optional[str] = None,
    phone_number_id: Optional[str] = None
) -> Dict[str, Any]:
    """Dispatches a single AI sales outbound phone call via Vapi API."""
    key = api_key or VAPI_API_KEY
    if key == "YOUR_VAPI_API_KEY":
        return {
            "status": "error",
            "message": "VAPI_API_KEY not set. Set environment variable VAPI_API_KEY or pass api_key."
        }

    headers = {
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json"
    }

    payload = {
        "phoneNumber": phone_number,
        "customer": {
            "name": lead_name,
            "number": phone_number
        }
    }

    if assistant_id and assistant_id != "YOUR_VAPI_ASSISTANT_ID":
        payload["assistantId"] = assistant_id
    else:
        # Transient inline sales assistant payload
        payload["assistant"] = {
            "firstMessage": f"Hello {lead_name}! This is Amélie calling from Drivri UK Logistics. How are you today?",
            "model": {
                "provider": "openai",
                "model": "gpt-4o-mini",
                "messages": [
                    {
                        "role": "system",
                        "content": DEFAULT_SALES_PROMPT
                    }
                ]
            },
            "voice": {
                "provider": "azure",
                "voiceId": "en-US-AvaNeural"
            }
        }

    if phone_number_id and phone_number_id != "YOUR_VAPI_PHONE_NUMBER_ID":
        payload["phoneNumberId"] = phone_number_id

    try:
        response = requests.post(VAPI_API_URL, headers=headers, json=payload, timeout=15)
        res_data = response.json()
        return {
            "status": "success" if response.status_code in [200, 201] else "failed",
            "http_code": response.status_code,
            "vapi_response": res_data
        }
    except Exception as e:
        return {
            "status": "error",
            "message": str(e)
        }

def run_lead_campaign(leads: List[Dict[str, str]], api_key: Optional[str] = None) -> List[Dict[str, Any]]:
    """Runs batch outbound call campaign across lead list."""
    results = []
    print(f"🚀 Launching Vapi Outbound Lead Campaign for {len(leads)} leads...")
    for idx, lead in enumerate(leads, 1):
        name = lead.get("name", "Prospect")
        phone = lead.get("phone", "")
        company = lead.get("company", "")
        print(f"[{idx}/{len(leads)}] Dialing {name} ({phone})...")
        res = dispatch_vapi_outbound_call(phone, name, company, api_key=api_key)
        results.append({"lead": lead, "result": res})
        time.sleep(1)
    return results

if __name__ == "__main__":
    sample_leads = [
        {"name": "John Smith", "phone": "+447911123456", "company": "Smith Logistics UK"},
        {"name": "Sarah Jenkins", "phone": "+447922233445", "company": "Jenkins Freight Ltd"}
    ]
    print("Vapi Outbound Sales Lead Engine Ready.")
    print("To launch, set VAPI_API_KEY environment variable and call run_lead_campaign(leads).")
