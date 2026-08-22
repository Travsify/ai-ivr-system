"""
Multi-Department & Nested Sub-Menu Configuration for VoiceFlow AI.
Includes Silence Keep-Alive Prompts & Vapi Operator Forwarding Integration.
"""

from typing import Dict, Any

HOLD_MUSIC_CATALOG = {
    "stinger_corporate": "🔔 Corporate Brass Stinger & Chime (Fortune 500)",
    "stinger_tech": "🎵 Modern Tech Pulse Stinger (SaaS & Startup)",
    "stinger_sax": "🎷 Smooth Elegant Saxophone Jingle (Executive Concierge)",
    "stinger_retail": "🎸 Upbeat Acoustic Retail Jingle (E-Commerce)",
    "stinger_piano": "🎹 Grand Piano Harmony Chime (Professional Services)",
    "stinger_meditation": "🧘 Calming Spa & Wellness Chime (Healthcare)",
    "stinger_funk": "⚡ Upbeat Marketing Funk Jingle (Sales Focus)",
    "smooth_jazz": "🎷 Classic Smooth Jazz Elevator Track",
    "lofi_beats": "🎧 Lo-Fi Chill Beats Track",
    "custom_upload": "📤 Custom Uploaded Audio File (.mp3, .wav)"
}

DEFAULT_DEPARTMENTS: Dict[str, Dict[str, Any]] = {
    "router": {
        "id": "router",
        "name": "IVR Main Menu Router",
        "digit": "0",
        "voice": "en-US-AvaNeural",
        "hold_music": "custom_upload",
        "system_prompt": "You are Ava, the main IVR Receptionist for Drivri Logistics. Guide callers to Sales & Vehicle Hire, Same-Day Couriers & Freight, Warehousing & Storage, Parking, Accounts, or Live Representative Jenny.",
        "greeting": (
            "Hello, welcome to Drivri UK Logistics Solution! How may I help you today? "
            "Please listen carefully to our options: "
            "Press 1 for Vehicle Rentals and Driver Hire. "
            "Press 2 for Same-Day Couriers, European Freight and Customs Clearance. "
            "Press 3 for Warehousing and Pallet Storage. "
            "Press 4 for Reserved City Parking Bays. "
            "Press 5 for Accounts and Billing. "
            "Press 0 to speak directly with Jenny, Senior Operations Manager."
        ),
        "silence_prompt": (
            "We noticed you haven't selected an option yet. "
            "Press 1 for Vehicle Hire, press 2 for Couriers & Freight, press 3 for Warehousing, press 4 for Parking, or press 0 for Jenny."
        ),
        "sub_menus": {
            "1": "sales",
            "2": "freight_and_courier",
            "3": "warehousing",
            "4": "parking",
            "5": "accounts",
            "0": "operator"
        }
    },
    "operator": {
        "id": "operator",
        "name": "Live Human AI Representative",
        "digit": "0",
        "voice": "en-US-JennyNeural",
        "hold_music": "stinger_corporate",
        "system_prompt": (
            "You are Jenny, Senior Operations Manager at Drivri Logistics. "
            "Assist callers with complex transport requirements, custom quotes, or resolving issues."
        ),
        "greeting": "Hello! Thank you for holding. This is Jenny, Senior Operations Manager. How can I personally assist you today?"
    },
    "sales": {
        "id": "sales",
        "name": "Vehicle Rentals & Driver Hire Department",
        "digit": "1",
        "voice": "en-US-GuyNeural",
        "hold_music": "stinger_funk",
        "system_prompt": "You are David from Drivri Sales. Guide callers through booking a driver & van, van only, or driver only.",
        "greeting": (
            "Thank you for contacting Drivri Vehicle Rentals and Driver Hire! "
            "Please select from our booking sub-options: "
            "Press 1 to Book a Driver and Van Package. "
            "Press 2 for Van Only Self-Drive Rental. "
            "Press 3 to Hire a Professional UK Driver Only. "
            "Press 4 for Corporate Commercial Fleet Services. "
            "Press 9 to return to the Main Menu."
        ),
        "sub_menus": {
            "1": "sales_driver_and_van",
            "2": "sales_van_only",
            "3": "sales_hire_driver",
            "4": "sales_fleet"
        }
    },
    "sales_driver_and_van": {
        "id": "sales_driver_and_van",
        "name": "Book Driver & Van",
        "digit": "1",
        "parent_id": "sales",
        "voice": "en-US-GuyNeural",
        "hold_music": "stinger_retail",
        "system_prompt": "You are Marcus, Van and Driver Operations Manager at Drivri Transport. Help callers book van + driver packages.",
        "greeting": "Hello! Thanks for reaching Drivri Transport. I'm Marcus, Van and Driver Operations Manager. Where are we picking up your cargo today?"
    },
    "sales_van_only": {
        "id": "sales_van_only",
        "name": "Van Only Rental",
        "digit": "2",
        "parent_id": "sales",
        "voice": "en-US-GuyNeural",
        "hold_music": "stinger_tech",
        "system_prompt": "You are Marcus, Fleet Rental Manager. Help callers choose self-drive commercial vans.",
        "greeting": "Hello! Thanks for reaching Drivri Fleet Rentals. I'm Marcus, Fleet Manager. How many days do you need your van rental for?"
    },
    "sales_hire_driver": {
        "id": "sales_hire_driver",
        "name": "Driver Only Hire",
        "digit": "3",
        "parent_id": "sales",
        "voice": "en-US-GuyNeural",
        "hold_music": "stinger_sax",
        "system_prompt": "You are David, Head of Driver Operations. Help clients hire experienced UK-licensed drivers (Cat B, C1, C, C+E).",
        "greeting": "Hello! Thanks for reaching Drivri Driver Hire. I'm David, Head of Driver Operations. How can I assist with your driver requirements today?"
    },
    "sales_fleet": {
        "id": "sales_fleet",
        "name": "Corporate Fleet Services",
        "digit": "4",
        "parent_id": "sales",
        "voice": "en-US-GuyNeural",
        "hold_music": "stinger_piano",
        "system_prompt": "You are Marcus, Corporate Fleet Director. Assist business clients with commercial fleet contracts.",
        "greeting": "Hello! Thanks for reaching Drivri Corporate Logistics. I'm Marcus, Fleet Director. How many commercial vehicles does your business require?"
    },
    "freight_and_courier": {
        "id": "freight_and_courier",
        "name": "Couriers & Customs Freight Department",
        "digit": "2",
        "voice": "en-US-JennyNeural",
        "hold_music": "stinger_tech",
        "system_prompt": "You are Sarah, Courier and International Freight Director. Guide callers through courier dispatch or customs freight clearance.",
        "greeting": (
            "Welcome to Drivri Couriers and European Shipping! "
            "Press 1 for Instant Same-Day UK Couriers. "
            "Press 2 for European Freight Forwarding and Customs Clearance. "
            "Press 9 for Main Menu."
        ),
        "sub_menus": {
            "1": "courier",
            "2": "freight"
        }
    },
    "courier": {
        "id": "courier",
        "name": "Instant Same-Day Courier Service",
        "digit": "1",
        "parent_id": "freight_and_courier",
        "voice": "en-US-JennyNeural",
        "hold_music": "stinger_tech",
        "system_prompt": "You are Sarah, Courier Dispatch Director. Help clients book same-day courier parcels and express deliveries.",
        "greeting": "Hello! Thanks for reaching Drivri Instant Couriers. I'm Sarah, Courier Director. Where are we dispatching your urgent parcel today?"
    },
    "freight": {
        "id": "freight",
        "name": "Customs Freight & Clearance",
        "digit": "2",
        "parent_id": "freight_and_courier",
        "voice": "en-US-JennyNeural",
        "hold_music": "stinger_piano",
        "system_prompt": "You are Sarah, International Customs Freight Director. Help clients with European freight forwarding and UK customs declaration.",
        "greeting": "Hello! Thanks for reaching Drivri Freight Forwarding and Customs Clearance. I'm Sarah. What ports or European countries are you shipping cargo between?"
    },
    "warehousing": {
        "id": "warehousing",
        "name": "Warehousing & Storage Department",
        "digit": "3",
        "voice": "en-US-GuyNeural",
        "hold_music": "stinger_piano",
        "system_prompt": "You are Alex, Warehousing and Storage Director. Help clients book pallet storage and fulfillment.",
        "greeting": "Hello! Thanks for reaching Drivri Warehousing and Multi-Storage. I'm Alex, Storage Director. What UK postcode or city do you need pallet storage in today?"
    },
    "parking": {
        "id": "parking",
        "name": "City Parking Space Booking",
        "digit": "4",
        "voice": "en-US-AvaNeural",
        "hold_music": "stinger_retail",
        "system_prompt": "You are Chloe, City Parking Coordinator. Help clients reserve commercial van or truck parking bays.",
        "greeting": "Hello! Thanks for reaching Drivri Reserved Parking Bays. I'm Chloe, City Parking Coordinator. Where do you need a reserved van or commercial parking space today?"
    },
    "accounts": {
        "id": "accounts",
        "name": "Accounts & Invoicing",
        "digit": "5",
        "voice": "en-US-AvaNeural",
        "hold_music": "stinger_piano",
        "system_prompt": "You are Rachel, Accounts and Billing Lead. Help callers with statements, invoices, and payment receipts.",
        "greeting": "Hello! Thanks for reaching Drivri Accounts and Billing. I'm Rachel. How can I assist with your invoice or statement today?"
    }
}

USER_DEPARTMENTS: Dict[str, Dict[str, Any]] = DEFAULT_DEPARTMENTS.copy()


def get_all_departments() -> Dict[str, Dict[str, Any]]:
    return USER_DEPARTMENTS


def add_or_update_department(dept_id: str, name: str, digit: str, voice: str, system_prompt: str, greeting: str, hold_music: str = "stinger_corporate", parent_id: str = None):
    USER_DEPARTMENTS[dept_id] = {
        "id": dept_id,
        "name": name,
        "digit": digit,
        "parent_id": parent_id,
        "voice": voice,
        "hold_music": hold_music,
        "system_prompt": system_prompt,
        "greeting": greeting
    }
    return USER_DEPARTMENTS[dept_id]


def classify_department_intent(user_input: str, current_dept: str = "router") -> str:
    text = user_input.strip().lower()

    if text in ["*", "repeat", "listen again", "listen"]:
        return current_dept
    elif text in ["9", "main menu", "go back", "home"]:
        return "router"
    elif text in ["0", "operator", "human", "speak with agent", "agent", "representative"]:
        return "operator"

    current_data = USER_DEPARTMENTS.get(current_dept, USER_DEPARTMENTS.get("router"))
    sub_menus = current_data.get("sub_menus", {})
    if text in sub_menus and sub_menus[text] in USER_DEPARTMENTS:
        return sub_menus[text]

    for dept_id, dept_data in USER_DEPARTMENTS.items():
        if dept_id in ["router", "operator"]:
            continue
        if text == dept_data.get("digit") and dept_data.get("parent_id") == current_dept:
            return dept_id
        if text in dept_id or dept_data["name"].lower() in text:
            return dept_id

    return current_dept
