import requests
r = requests.post('http://localhost:8000/telephony/signalwire/6a083847', data={'From': '+447911123456', 'CallSid': 'verify_fix'})
print('Status:', r.status_code)
print()
print(r.text)
print()
has_answer = 'Answer' in r.text and '/>' in r.text
has_comment = '<!--' in r.text
has_play = 'Play' in r.text
has_gather = 'Gather' in r.text
print(f'Has Answer tag: {has_answer}')
print(f'Has XML comments: {has_comment}')
print(f'Has Play tag: {has_play}')
print(f'Has Gather tag: {has_gather}')
if not has_answer and not has_comment and has_play and has_gather:
    print('CLEAN cXML - SignalWire will answer and play the jingle!')
else:
    print('WARNING: cXML may still have issues')
