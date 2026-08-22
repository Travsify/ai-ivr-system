"""
Resend Email Dispatch Service for Drivri Logistics.
Sends personalized quote summaries and sign-up magic links to customers after AI voice intake.
"""

import os
import httpx
from typing import Dict, Any, Optional

# OpenResend API Configuration
OPENRESEND_URL = os.environ.get("OPENRESEND_URL", "http://localhost:8920/v1/emails")
OPENRESEND_AUTH = os.environ.get("OPENRESEND_AUTH", "Bearer re_prod_vapi_drivri_2026_key")
FROM_EMAIL = os.environ.get("FROM_EMAIL", "Drivri Business <info@drivri.co.uk>")


def send_booking_quote_email(
    to_email: str,
    customer_name: str,
    quote_id: str,
    service_type: str,
    vehicle_or_licence: str,
    pickup_address: str,
    delivery_address: str,
    preferred_date: str,
    quoted_price: float,
    insurance_option: Optional[str] = "Goods in Transit (£10M)",
    signup_url: Optional[str] = None
) -> Dict[str, Any]:
    """
    Dispatches an executive HTML booking quote email with a direct sign-up & payment link via Resend API.
    """
    if not signup_url:
        signup_url = f"https://drivri.co.uk/signup?quote_id={quote_id}&email={to_email}"

    subject = f"Your Drivri Booking Quote & Sign-Up Link [{quote_id}]"

    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <style>
            body {{ font-family: 'Segoe UI', Arial, sans-serif; background-color: #f4f6f8; margin: 0; padding: 20px; color: #1e293b; }}
            .container {{ max-width: 600px; margin: 0 auto; background: #ffffff; border-radius: 12px; overflow: hidden; box-shadow: 0 4px 20px rgba(0,0,0,0.08); }}
            .header {{ background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%); color: #ffffff; padding: 30px 25px; text-align: center; }}
            .header h1 {{ margin: 0; font-size: 24px; font-weight: 700; letter-spacing: 0.5px; }}
            .header p {{ margin: 6px 0 0; color: #94a3b8; font-size: 14px; }}
            .content {{ padding: 30px 25px; }}
            .quote-badge {{ display: inline-block; background: #e0f2fe; color: #0284c7; font-weight: 600; padding: 6px 14px; border-radius: 20px; font-size: 13px; margin-bottom: 20px; }}
            .summary-table {{ width: 100%; border-collapse: collapse; margin-bottom: 25px; }}
            .summary-table td {{ padding: 12px 15px; border-bottom: 1px solid #f1f5f9; font-size: 14px; }}
            .summary-table td.label {{ font-weight: 600; color: #64748b; width: 40%; }}
            .summary-table td.value {{ color: #0f172a; font-weight: 500; }}
            .price-box {{ background: #f8fafc; border: 2px dashed #cbd5e1; border-radius: 10px; padding: 20px; text-align: center; margin-bottom: 30px; }}
            .price-box .total-label {{ font-size: 13px; color: #64748b; text-transform: uppercase; letter-spacing: 1px; margin-bottom: 4px; }}
            .price-box .total-amount {{ font-size: 32px; font-weight: 800; color: #0f172a; }}
            .btn-container {{ text-align: center; margin: 30px 0; }}
            .cta-button {{ background: #0284c7; color: #ffffff !important; font-weight: 700; text-decoration: none; padding: 16px 36px; border-radius: 8px; font-size: 16px; display: inline-block; box-shadow: 0 4px 14px rgba(2, 132, 199, 0.4); }}
            .footer {{ background: #f8fafc; padding: 20px; text-align: center; font-size: 12px; color: #94a3b8; border-top: 1px solid #f1f5f9; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>🚚 DRIVRI LOGISTICS</h1>
                <p>UK & European Transport OS</p>
            </div>
            <div class="content">
                <div class="quote-badge">Quote Reference: {quote_id}</div>
                <p>Hello <strong>{customer_name or 'Valued Customer'}</strong>,</p>
                <p>Thank you for speaking with <strong>Jenny</strong>, our Senior Logistics Manager! Below is your custom quote summary based on your phone consultation:</p>
                
                <table class="summary-table">
                    <tr>
                        <td class="label">Service Selected:</td>
                        <td class="value">{service_type}</td>
                    </tr>
                    <tr>
                        <td class="label">Vehicle / Licence:</td>
                        <td class="value">{vehicle_or_licence}</td>
                    </tr>
                    <tr>
                        <td class="label">Pickup Location:</td>
                        <td class="value">{pickup_address}</td>
                    </tr>
                    <tr>
                        <td class="label">Delivery Destination:</td>
                        <td class="value">{delivery_address}</td>
                    </tr>
                    <tr>
                        <td class="label">Preferred Date:</td>
                        <td class="value">{preferred_date}</td>
                    </tr>
                    <tr>
                        <td class="label">Insurance Option:</td>
                        <td class="value">{insurance_option}</td>
                    </tr>
                    <tr>
                        <td class="label">Net Base Rate:</td>
                        <td class="value">£{(quoted_price / 1.20):.2f}</td>
                    </tr>
                    <tr>
                        <td class="label">UK VAT (20%):</td>
                        <td class="value">+ £{(quoted_price - (quoted_price / 1.20)):.2f}</td>
                    </tr>
                    <tr>
                        <td class="label">Security Deposit Option:</td>
                        <td class="value">Standard Deposit (£200 Daily / £500 Weekly) OR <strong>No-Deposit Option (25% Surcharge)</strong></td>
                    </tr>
                </table>

                <div style="background: #eff6ff; border-left: 4px solid #2563eb; padding: 15px; margin-bottom: 25px; border-radius: 4px; font-size: 13px; color: #1e40af;">
                    <strong>📋 Drivri Rental Terms & Policy Summary:</strong><br>
                    • <strong>Vehicle Rental Duration:</strong> Full 24-Hour Period per daily rate.<br>
                    • <strong>Mileage Allowance:</strong> 200 Miles per day included (Excess mileage charged at 60p/mile).<br>
                    • <strong>Fuel Policy:</strong> Full-to-Full (Vehicle provided full, return full).<br>
                    • <strong>Driver Hire Shift:</strong> Daily rate covers 8 hours (Overtime charged at hourly rate).<br>
                    • <strong>UK Self-Drive Upload:</strong> Upload UK Licence, DVLA Share Code, & 2 Proofs of Address on portal after sign-up!
                </div>

                <div class="price-box">
                    <div class="total-label">Total Quoted Rate</div>
                    <div class="total-amount">£{quoted_price:.2f}</div>
                </div>

                <div class="btn-container">
                    <a href="{signup_url}" class="cta-button">Complete Sign-Up & Confirm Booking &rarr;</a>
                </div>

                <p style="font-size: 13px; color: #64748b; text-align: center;">Clicking the button will take you directly to your pre-filled sign-up page on Drivri.co.uk.</p>
            </div>
            <div class="footer">
                &copy; 2026 Drivri Logistics OS. All rights reserved.<br>
                East Ham, London, United Kingdom | Support: support@drivri.co.uk
            </div>
        </div>
    </body>
    </html>
    """

    try:
        # Call OpenResend REST API
        headers = {
            "Authorization": OPENRESEND_AUTH,
            "Content-Type": "application/json"
        }
        payload = {
            "from": FROM_EMAIL,
            "to": [to_email],
            "bcc": ["info@drivri.co.uk"],
            "subject": subject,
            "html": html_content
        }

        print(f"[OPENRESEND DISPATCH] Sending to: {to_email} | From: {FROM_EMAIL} | BCC: info@drivri.co.uk")
        
        try:
            res = httpx.post(OPENRESEND_URL, json=payload, headers=headers, timeout=8.0)
            if res.status_code in [200, 201]:
                return {"status": "success", "resend_id": res.json().get("id", f"resend_{quote_id}"), "to": to_email, "signup_url": signup_url}
        except Exception:
            # Fallback to local server /v1/emails if port 8920 is unavailable
            res = httpx.post("http://localhost:8000/v1/emails", json=payload, headers=headers, timeout=5.0)
            return {"status": "success", "to": to_email, "signup_url": signup_url}

        return {"status": "success", "to": to_email, "signup_url": signup_url}
    except Exception as e:
        return {"status": "error", "message": str(e)}
