"""
Hold Music Pure Audio Synthesizer.
Generates real musical WAV audio streams for 10 royalty-free music styles.
"""

import math
import struct
import wave
import io
import base64

SAMPLE_RATE = 22050  # 22.05kHz PCM for fast streaming

def generate_tone(freq: float, duration: float, volume: float = 0.5, wave_type: str = "sine") -> bytes:
    num_samples = int(SAMPLE_RATE * duration)
    audio = bytearray()
    for i in range(num_samples):
        t = float(i) / SAMPLE_RATE
        if wave_type == "sine":
            val = math.sin(2.0 * math.pi * freq * t)
        elif wave_type == "square":
            val = 1.0 if math.sin(2.0 * math.pi * freq * t) > 0 else -1.0
        elif wave_type == "saw":
            val = 2.0 * (t * freq - math.floor(0.5 + t * freq))
        else:
            val = math.sin(2.0 * math.pi * freq * t)
            
        fade = min(i / 1000.0, 1.0) * min((num_samples - i) / 1000.0, 1.0)
        sample = int(val * volume * fade * 32767.0)
        audio.extend(struct.pack('<h', max(-32768, min(32767, sample))))
    return bytes(audio)


def generate_chord(freqs: list, duration: float, volume: float = 0.3) -> bytes:
    num_samples = int(SAMPLE_RATE * duration)
    audio = bytearray()
    for i in range(num_samples):
        t = float(i) / SAMPLE_RATE
        val = sum(math.sin(2.0 * math.pi * f * t) for f in freqs) / len(freqs)
        fade = min(i / 1500.0, 1.0) * min((num_samples - i) / 1500.0, 1.0)
        sample = int(val * volume * fade * 32767.0)
        audio.extend(struct.pack('<h', max(-32768, min(32767, sample))))
    return bytes(audio)


def generate_hold_music_wav_bytes(style: str, duration: float = 3.5) -> bytes:
    """Generates pure musical WAV audio bytes for the selected style."""
    out_io = io.BytesIO()
    
    with wave.open(out_io, 'wb') as wav_file:
        wav_file.setnchannels(1)  # Mono
        wav_file.setsampwidth(2)  # 16-bit PCM
        wav_file.setframerate(SAMPLE_RATE)
        
        frames = bytearray()
        
        if style in ["stinger_corporate", "smooth_jazz"]:
            chords = [[349, 440, 523, 659], [293, 349, 440, 523], [196, 293, 349, 440], [261, 329, 392, 466]]
            chord_dur = duration / len(chords)
            for c in chords:
                frames.extend(generate_chord(c, chord_dur, volume=0.35))
                
        elif style in ["stinger_tech", "lofi_beats"]:
            chords = [[220, 261, 329, 392], [174, 220, 261, 329], [196, 246, 293, 349], [164, 196, 246, 293]]
            chord_dur = duration / len(chords)
            for c in chords:
                frames.extend(generate_chord(c, chord_dur, volume=0.3))
                
        elif style in ["stinger_piano", "classical_piano"]:
            notes = [220, 261, 329, 440, 174, 220, 261, 349, 261, 329, 392, 523, 196, 246, 293, 392]
            note_dur = duration / len(notes)
            for n in notes:
                frames.extend(generate_tone(n, note_dur, volume=0.35, wave_type="sine"))
                
        elif style == "ambient_chill":
            frames.extend(generate_chord([110, 164, 220, 330, 440], duration, volume=0.3))
            
        elif style in ["stinger_retail", "acoustic_guitar"]:
            notes = [329, 392, 493, 587, 392, 329, 493, 587]
            note_dur = duration / len(notes)
            for n in notes:
                frames.extend(generate_tone(n, note_dur, volume=0.3, wave_type="sine"))
                
        elif style in ["stinger_sax", "tropical_chill"]:
            notes = [523, 587, 659, 783, 880, 783, 659, 587]
            note_dur = duration / len(notes)
            for n in notes:
                frames.extend(generate_tone(n, note_dur, volume=0.35, wave_type="sine"))
                
        elif style in ["stinger_funk", "upbeat_funk"]:
            notes = [146, 293, 146, 369, 146, 293, 220, 146]
            note_dur = duration / len(notes)
            for n in notes:
                frames.extend(generate_tone(n, note_dur, volume=0.4, wave_type="saw"))
                
        elif style in ["stinger_meditation", "meditation_spa"]:
            frames.extend(generate_chord([216, 288, 432, 576], duration, volume=0.25))
            
        elif style == "symphonic_strings":
            chords = [[220, 277, 329, 440], [174, 220, 261, 349], [196, 246, 293, 392]]
            chord_dur = duration / len(chords)
            for c in chords:
                frames.extend(generate_chord(c, chord_dur, volume=0.35))
                
        elif style == "retro_8bit":
            notes = [261, 329, 392, 523, 392, 329, 261, 196, 220, 277, 329, 440, 329, 277, 220, 164]
            note_dur = duration / len(notes)
            for n in notes:
                frames.extend(generate_tone(n, note_dur, volume=0.25, wave_type="square"))
                
        else:
            frames.extend(generate_chord([349, 440, 523, 659], duration, volume=0.35))
            
        wav_file.writeframes(frames)
        
    out_io.seek(0)
    return out_io.read()


def generate_hold_music_wav_b64(style: str, duration: float = 3.5) -> str:
    """Generates pure musical WAV audio Base64 for the selected style."""
    raw_bytes = generate_hold_music_wav_bytes(style, duration)
    return base64.b64encode(raw_bytes).decode('utf-8')
