"""Test script: Verify SignalWire -> Vapi handoff never reads IVR menus."""
import requests
import json

host = "http://localhost:8000"
session_id = "test_permanent_vapi_fix_001"

print("=" * 60)
print("TEST 1: SignalWire Full IVR Entry Point")
print("=" * 60)
r1 = requests.get(f"{host}/telephony/full-ivr/6a083847")
print(f"Status: {r1.status_code}")
# Should contain jingle + Gather + "Press 1" (this is SignalWire cXML, expected)
print(f"Has Gather: {'<Gather' in r1.text}")
print(f"Has Play jingle: {'<Play' in r1.text}")

print("\n" + "=" * 60)
print("TEST 2: Press 1 (Sales) from main menu")
print("=" * 60)
r2 = requests.post(
    f"{host}/telephony/gather/6a083847?current_dept=router",
    data={"Digits": "1", "CallSid": session_id, "From": "+447911123456"},
)
print(f"Status: {r2.status_code}")
# Should show Sales sub-menu (expected in SignalWire cXML)
print(f"Has Gather: {'<Gather' in r2.text}")

print("\n" + "=" * 60)
print("TEST 3: Press 3 (Hire Driver Only) from sales sub-menu -> Dial to Vapi")
print("=" * 60)
r3 = requests.post(
    f"{host}/telephony/gather/6a083847?current_dept=sales",
    data={"Digits": "3", "CallSid": session_id, "From": "+447911123456"},
)
print(f"Status: {r3.status_code}")
print(f"Response:\n{r3.text}")
has_dial = "<Dial" in r3.text
has_caller_id = 'callerId' in r3.text
print(f"Has <Dial>: {has_dial}")
print(f"Has callerId: {has_caller_id}")

print("\n" + "=" * 60)
print("TEST 4: Vapi webhook (known caller from SignalWire)")
print("=" * 60)
r4 = requests.post(
    f"{host}/telephony/inbound/6a083847",
    data={"From": "+447911123456", "CallSid": "vapi_call_001"},
)
j4 = r4.json()
first_msg = j4.get("assistant", {}).get("firstMessage", "")
sys_prompt = j4.get("assistant", {}).get("systemPrompt", "")
name = j4.get("assistant", {}).get("name", "")
print(f"firstMessage: {first_msg}")
print(f"Assistant name: {name}")
has_press_fm = "Press" in first_msg or "press" in first_msg
has_press_sp = "Press 1" in sys_prompt or "press 1" in sys_prompt
print(f"firstMessage has 'Press': {has_press_fm}")
print(f"systemPrompt has 'Press 1': {has_press_sp}")

print("\n" + "=" * 60)
print("TEST 5: Vapi webhook (UNKNOWN caller -> should default to Jenny)")
print("=" * 60)
r5 = requests.post(
    f"{host}/telephony/inbound/6a083847",
    data={"From": "+449999999999", "CallSid": "vapi_call_002"},
)
j5 = r5.json()
first_msg5 = j5.get("assistant", {}).get("firstMessage", "")
name5 = j5.get("assistant", {}).get("name", "")
print(f"firstMessage: {first_msg5}")
print(f"Assistant name (should be Jenny): {name5}")
has_press5 = "Press" in first_msg5 or "press" in first_msg5
print(f"firstMessage has 'Press': {has_press5}")

print("\n" + "=" * 60)
print("TEST 6: Vapi webhook (router dept_id explicitly -> should NOT show IVR)")
print("=" * 60)
r6 = requests.post(
    f"{host}/telephony/inbound/6a083847/router",
    data={"From": "+440000000000", "CallSid": "vapi_call_003"},
)
j6 = r6.json()
first_msg6 = j6.get("assistant", {}).get("firstMessage", "")
name6 = j6.get("assistant", {}).get("name", "")
print(f"firstMessage: {first_msg6}")
print(f"Assistant name: {name6}")
has_press6 = "Press" in first_msg6 or "press" in first_msg6
print(f"firstMessage has 'Press': {has_press6}")

print("\n" + "=" * 60)
print("SUMMARY")
print("=" * 60)
all_pass = (
    not has_press_fm
    and not has_press_sp
    and not has_press5
    and not has_press6
    and has_dial
    and has_caller_id
)
print(f"ALL TESTS PASS (Vapi never reads IVR menus): {all_pass}")
if all_pass:
    print("SUCCESS: SignalWire -> Vapi handoff is permanently fixed!")
else:
    failures = []
    if has_press_fm:
        failures.append("TEST 4 firstMessage has Press")
    if has_press_sp:
        failures.append("TEST 4 systemPrompt has Press 1")
    if has_press5:
        failures.append("TEST 5 unknown caller firstMessage has Press")
    if has_press6:
        failures.append("TEST 6 router dept_id firstMessage has Press")
    if not has_dial:
        failures.append("TEST 3 missing <Dial>")
    if not has_caller_id:
        failures.append("TEST 3 missing callerId")
    print(f"FAILURES: {failures}")
