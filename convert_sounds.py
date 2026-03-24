#!/usr/bin/env python3
"""
Converteer alle .wav bestanden in de sounds/ map naar sounds_data.js
zodat de app ze kan afspelen.

Gebruik:
    python convert_sounds.py

Plaats je eigen .wav bestanden in de sounds/ map en draai dit script opnieuw.
De bestandsnamen moeten overeenkomen met de namen in de app (bijv. 01_teacher.wav).
"""

import base64
import os
import glob

SOUNDS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sounds")
OUTPUT_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sounds_data.js")

def convert():
    wav_files = sorted(glob.glob(os.path.join(SOUNDS_DIR, "*.wav")))

    if not wav_files:
        print("Geen .wav bestanden gevonden in sounds/")
        return

    print(f"Gevonden: {len(wav_files)} .wav bestanden")

    with open(OUTPUT_FILE, "w") as out:
        out.write("const SOUND_DATA = {\n")
        for i, filepath in enumerate(wav_files):
            filename = os.path.basename(filepath)
            with open(filepath, "rb") as f:
                data = f.read()
            b64 = base64.b64encode(data).decode("ascii")
            comma = "," if i < len(wav_files) - 1 else ""
            out.write(f'"{filename}": "data:audio/wav;base64,{b64}"{comma}\n')
            size_kb = len(data) / 1024
            print(f"  {filename} ({size_kb:.1f} KB)")
        out.write("};\n")

    size_mb = os.path.getsize(OUTPUT_FILE) / (1024 * 1024)
    print(f"\nKlaar! sounds_data.js gegenereerd ({size_mb:.1f} MB)")

if __name__ == "__main__":
    convert()
