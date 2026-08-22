"""
Dedicated launcher for Option 2: AI Voice (Incoming + Outbound) & WhatsApp Lead Closer Engine.
Runs FastAPI + Uvicorn on Port 8095.
"""

import os
import sys
import uvicorn

# Ensure the current directory is in sys.path
sys.path.insert(0, os.path.dirname(__file__))

from server import app

if __name__ == "__main__":
    port = int(os.getenv("PORT", "8095"))
    print("===========================================================")
    print(f"Starting Option 2 AI Voice & WhatsApp Lead Closer Server")
    print(f"Localhost URL: http://localhost:{port}")
    print("===========================================================")
    uvicorn.run(app, host="0.0.0.0", port=port)
