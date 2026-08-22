import requests

project_id = "65ff041f-b517-4717-807e-6a2fb5218f78"
token = "PT2921bb96175a179053f9a482fa5ae4f4b579fed1c7cdd68b"
space_url = "globalline-logistics-limited.signalwire.com"
bin_sid = "5e2e66b4-d9b6-40ed-9b71-e191cf5ea647"
phone_sid = "c54ffe6c-df51-451a-a185-8f53490368d0"
voice_url = "https://uncinctured-pseudoancestrally-madisyn.ngrok-free.dev/telephony/signalwire/6a083847"

# SignalWire LaML Bin with instant <Say> answer & redirect to live server
xml_contents = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Redirect method="POST">{voice_url}</Redirect>
</Response>"""

ep_bin = f"https://{space_url}/api/laml/2010-04-01/Accounts/{project_id}/LamlBins/{bin_sid}.json"
r_bin = requests.post(ep_bin, auth=(project_id, token), data={"Contents": xml_contents, "Name": "Drivri IVR Instant Answer"})
print("Update LaML Bin status:", r_bin.status_code)

# Ensure Phone Number points directly to voice_url
ep_phone = f"https://{space_url}/api/laml/2010-04-01/Accounts/{project_id}/IncomingPhoneNumbers/{phone_sid}.json"
r_phone = requests.post(ep_phone, auth=(project_id, token), data={
    "VoiceUrl": voice_url,
    "VoiceMethod": "POST",
    "VoiceFallbackUrl": voice_url,
    "VoiceFallbackMethod": "POST"
})
print("Update Phone Number status:", r_phone.status_code)
