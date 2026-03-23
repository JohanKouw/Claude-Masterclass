#!/usr/bin/env python3
"""Generate all 25 koolmees (great tit) vocalizations as .wav files.

Replicates the Web Audio API synthesis from the original index.html.
"""

import math
import os
import struct
import wave
import random

SAMPLE_RATE = 44100
OUTPUT_DIR = "sounds"

# ── WAV writing helper ──

def write_wav(filename, samples):
    """Write mono 16-bit PCM WAV file from float samples [-1, 1]."""
    filepath = os.path.join(OUTPUT_DIR, filename)
    with wave.open(filepath, "w") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(SAMPLE_RATE)
        data = b""
        for s in samples:
            s = max(-1.0, min(1.0, s))
            data += struct.pack("<h", int(s * 32767))
        wf.writeframes(data)
    print(f"  Written: {filepath} ({len(samples)} samples, {len(samples)/SAMPLE_RATE:.2f}s)")


# ── Buffer class for mixing ──

class AudioBuffer:
    """Simple mixing buffer."""

    def __init__(self, duration, sample_rate=SAMPLE_RATE):
        self.sample_rate = sample_rate
        self.length = int(duration * sample_rate) + 1
        self.data = [0.0] * self.length

    def ensure_length(self, needed):
        if needed > self.length:
            self.data.extend([0.0] * (needed - self.length))
            self.length = needed

    def add_chirp(self, freq_start, freq_end, start_time, duration, gain_val=0.25):
        """Frequency sweep with envelope (replicates createChirp)."""
        start_sample = int(start_time * self.sample_rate)
        num_samples = int(duration * self.sample_rate)
        if num_samples <= 0:
            return
        self.ensure_length(start_sample + num_samples + 1)

        attack = min(int(0.008 * self.sample_rate), int(num_samples * 0.15))
        release_start = num_samples - min(int(0.015 * self.sample_rate), int(num_samples * 0.2))

        # Exponential frequency sweep
        log_start = math.log(max(freq_start, 20))
        log_end = math.log(max(freq_end, 20))

        phase = 0.0
        for i in range(num_samples):
            t_frac = i / max(num_samples - 1, 1)
            # Log interpolation for frequency
            freq = math.exp(log_start + (log_end - log_start) * t_frac)

            # Envelope
            if i < attack:
                env = i / max(attack, 1)
            elif i >= release_start:
                env = (num_samples - i) / max(num_samples - release_start, 1)
            else:
                env = 1.0

            sample = math.sin(phase) * env * gain_val
            self.data[start_sample + i] += sample
            phase += 2.0 * math.pi * freq / self.sample_rate

    def add_harmonic(self, base_freq, harmonic, start_time, duration, gain_val=0.08):
        """Add a harmonic (replicates addHarmonic)."""
        f = base_freq * harmonic
        self.add_chirp(f, f, start_time, duration, gain_val)

    def add_noise(self, start_time, duration, gain_val=0.1, center_freq=4000, q=2.0):
        """Bandpass filtered noise (replicates createNoise)."""
        start_sample = int(start_time * self.sample_rate)
        num_samples = int(duration * self.sample_rate)
        if num_samples <= 0:
            return
        self.ensure_length(start_sample + num_samples + 1)

        # Generate white noise
        noise = [random.uniform(-1, 1) for _ in range(num_samples)]

        # Simple 2nd-order bandpass filter (biquad)
        w0 = 2.0 * math.pi * center_freq / self.sample_rate
        alpha = math.sin(w0) / (2.0 * q)
        b0 = alpha
        b1 = 0.0
        b2 = -alpha
        a0 = 1.0 + alpha
        a1 = -2.0 * math.cos(w0)
        a2 = 1.0 - alpha

        # Normalize
        b0 /= a0; b1 /= a0; b2 /= a0
        a1 /= a0; a2 /= a0

        x1 = x2 = y1 = y2 = 0.0
        filtered = []
        for x0 in noise:
            y0 = b0 * x0 + b1 * x1 + b2 * x2 - a1 * y1 - a2 * y2
            filtered.append(y0)
            x2, x1 = x1, x0
            y2, y1 = y1, y0

        # Envelope
        attack_samples = int(0.005 * self.sample_rate)
        release_samples = int(0.01 * self.sample_rate)
        for i in range(num_samples):
            if i < attack_samples:
                env = i / max(attack_samples, 1)
            elif i >= num_samples - release_samples:
                env = (num_samples - i) / max(release_samples, 1)
            else:
                env = 1.0
            self.data[start_sample + i] += filtered[i] * env * gain_val

    def add_click(self, start_time, gain_val=0.4):
        """Percussive click (replicates createClick)."""
        num_samples = int(0.008 * self.sample_rate)
        start_sample = int(start_time * self.sample_rate)
        self.ensure_length(start_sample + num_samples + 1)

        # Generate decaying noise burst with highpass character
        for i in range(num_samples):
            env = math.exp(-i / (num_samples * 0.1))
            sample = random.uniform(-1, 1) * env * gain_val
            self.data[start_sample + i] += sample

    def get_samples(self):
        """Return trimmed sample data."""
        # Trim trailing silence
        end = len(self.data) - 1
        while end > 0 and abs(self.data[end]) < 0.0001:
            end -= 1
        return self.data[:end + int(0.05 * self.sample_rate)]  # add 50ms tail


# ── Sound implementations ──

def gen_teacher(speed=1.0):
    """1. Teacher-teacher song."""
    buf = AudioBuffer(4.0 / speed)
    gap = 0.18 / speed
    note_len = 0.12 / speed
    phrase_gap = 0.4 / speed
    for rep in range(4):
        offset = rep * (2 * note_len + gap + phrase_gap)
        buf.add_chirp(4200, 3800, offset, note_len, 0.25)
        buf.add_harmonic(4000, 2, offset, note_len, 0.06)
        buf.add_chirp(3400, 3000, offset + note_len + gap, note_len, 0.25)
        buf.add_harmonic(3200, 2, offset + note_len + gap, note_len, 0.06)
    return buf.get_samples()


def gen_song_complex(speed=1.0):
    """2. Complex 3-syllable song."""
    buf = AudioBuffer(5.0 / speed)
    note_len = 0.1 / speed
    gap = 0.1 / speed
    phrase_gap = 0.45 / speed
    offset = 0.0
    for rep in range(3):
        buf.add_chirp(4800, 4600, offset, note_len * 0.7, 0.22)
        offset += note_len * 0.7 + gap * 0.5
        buf.add_chirp(4000, 3700, offset, note_len * 0.8, 0.25)
        offset += note_len * 0.8 + gap * 0.5
        buf.add_chirp(3600, 2800, offset, note_len * 1.4, 0.25)
        buf.add_harmonic(3200, 2, offset, note_len * 1.4, 0.05)
        offset += note_len * 1.4 + phrase_gap
    return buf.get_samples()


def gen_saw_song(speed=1.0):
    """3. Saw-sharpening song."""
    buf = AudioBuffer(5.0 / speed)
    offset = 0.0
    for rep in range(3):
        for i in range(3):
            dur = 0.06 / speed
            buf.add_chirp(6200, 5800, offset, dur, 0.22)
            offset += dur + 0.04 / speed
        end_dur = 0.14 / speed
        buf.add_chirp(3800, 2800, offset, end_dur, 0.28)
        buf.add_harmonic(3300, 2, offset, end_dur, 0.06)
        offset += end_dur + 0.35 / speed
    return buf.get_samples()


def gen_pietoe(speed=1.0):
    """4. Pie-toe song."""
    buf = AudioBuffer(5.0 / speed)
    offset = 0.0
    for rep in range(4):
        dur1 = 0.1 / speed
        dur2 = 0.12 / speed
        buf.add_chirp(3800, 4800, offset, dur1, 0.24)
        offset += dur1 + 0.06 / speed
        buf.add_chirp(4600, 3200, offset, dur2, 0.26)
        buf.add_harmonic(3900, 2, offset, dur2, 0.05)
        offset += dur2 + 0.38 / speed
    return buf.get_samples()


def gen_subsong(speed=1.0):
    """5. Subsong (whisper song)."""
    random.seed(42)  # deterministic
    buf = AudioBuffer(3.0 / speed)
    phrases = [
        (3200, 3800), (4500, 4100), (5000, 5400), (3600, 3200),
        (4800, 5200), (3400, 2900), (5500, 5100), (4200, 4600),
        (3000, 3500), (5800, 5200), (4000, 3600), (4400, 4900)
    ]
    offset = 0.0
    for f1, f2 in phrases:
        dur = (0.05 + random.random() * 0.08) / speed
        gap = (0.04 + random.random() * 0.1) / speed
        gain = 0.06 + random.random() * 0.04
        buf.add_chirp(f1, f2, offset, dur, gain)
        offset += dur + gap
    return buf.get_samples()


def gen_dawn_chorus(speed=1.0):
    """6. Dawn chorus (fast teacher-teacher)."""
    buf = AudioBuffer(4.0 / speed)
    note_len = 0.07 / speed
    gap = 0.08 / speed
    phrase_gap = 0.15 / speed
    offset = 0.0
    for rep in range(6):
        buf.add_chirp(4400, 4000, offset, note_len, 0.28)
        buf.add_harmonic(4200, 2, offset, note_len, 0.07)
        offset += note_len + gap
        buf.add_chirp(3600, 3100, offset, note_len, 0.28)
        buf.add_harmonic(3350, 2, offset, note_len, 0.07)
        offset += note_len + phrase_gap
    return buf.get_samples()


def gen_courtship(speed=1.0):
    """7. Courtship warble."""
    buf = AudioBuffer(4.0 / speed)
    offset = 0.0
    for rep in range(2):
        for i in range(4):
            dur = 0.04 / speed
            f = 2800 + math.sin(i * 4) * 400
            buf.add_chirp(f, f + 200, offset, dur, 0.18)
            offset += dur
        zee_dur = 0.2 / speed
        buf.add_chirp(2400, 2200, offset, zee_dur, 0.2)
        buf.add_harmonic(2300, 2, offset, zee_dur, 0.06)
        offset += zee_dur + 0.15 / speed
    for rep in range(3):
        dur = 0.12 / speed
        buf.add_chirp(3200, 2800, offset, dur, 0.15)
        for h in range(2, 5):
            buf.add_chirp(3000 * h * 0.5, 2800 * h * 0.5, offset, dur * 0.6, 0.03)
        offset += dur + 0.08 / speed
    return buf.get_samples()


def gen_alarm(speed=1.0):
    """8. Alarm (tink)."""
    buf = AudioBuffer(3.0 / speed)
    gap = 0.22 / speed
    note_len = 0.06 / speed
    for i in range(8):
        offset = i * gap
        buf.add_chirp(5500, 4800, offset, note_len, 0.3)
        buf.add_chirp(5500 * 1.5, 4800 * 1.5, offset, note_len * 0.7, 0.05)
        buf.add_chirp(5500 * 2.2, 4800 * 2.2, offset, note_len * 0.5, 0.03)
    return buf.get_samples()


def gen_seet(speed=1.0):
    """9. Seet call."""
    buf = AudioBuffer(2.0 / speed)
    dur = 0.8 / speed
    # Main tone with slight vibrato
    num_samples = int(dur * SAMPLE_RATE)
    buf.ensure_length(num_samples + 1)
    phase = 0.0
    for i in range(num_samples):
        t = i / SAMPLE_RATE
        # Vibrato: 6 Hz, 30 Hz depth
        freq = 8300 + 30 * math.sin(2 * math.pi * 6 * t)
        # Slight sweep
        freq += (8400 - 8200) * (i / num_samples)
        # Envelope
        if t < 0.05:
            env = t / 0.05
        elif t > dur - 0.1:
            env = (dur - t) / 0.1
        else:
            env = 1.0
        sample = math.sin(phase) * env * 0.18
        buf.data[i] += sample
        phase += 2 * math.pi * freq / SAMPLE_RATE
    return buf.get_samples()


def gen_mobbing(speed=1.0):
    """10. Mobbing D-calls."""
    random.seed(10)
    buf = AudioBuffer(6.0 / speed)
    offset = 0.0
    for series in range(3):
        buf.add_chirp(7000, 6500, offset, 0.06 / speed, 0.15)
        offset += 0.1 / speed
        num_d = 5 + random.randint(0, 2)
        for i in range(num_d):
            dur = 0.05 / speed
            buf.add_chirp(4200, 3800, offset, dur, 0.22)
            buf.add_chirp(4200 * 1.5, 3800 * 1.5, offset, dur * 0.5, 0.06)
            buf.add_chirp(2100, 1900, offset, dur, 0.1)
            offset += dur + 0.04 / speed
        offset += 0.3 / speed
    return buf.get_samples()


def gen_churr(speed=1.0):
    """11. Churr/rattle."""
    buf = AudioBuffer(3.0 / speed)
    offset = 0.0
    for rep in range(2):
        rattle_dur = 0.6 / speed
        pulse_rate = 30 * speed
        num_pulses = int(rattle_dur * pulse_rate)
        for i in range(num_pulses):
            pulse_dur = 0.015 / speed
            pulse_time = offset + i / pulse_rate
            freq = 3500 + (i / num_pulses) * 1500
            gain = 0.12 + (i / num_pulses) * 0.1
            buf.add_chirp(freq, freq + 100, pulse_time, pulse_dur, gain)
            buf.add_chirp(freq * 0.5, freq * 0.5 + 50, pulse_time, pulse_dur, 0.05)
        offset += rattle_dur + 0.25 / speed
    return buf.get_samples()


def gen_scold(speed=1.0):
    """12. Scold call."""
    buf = AudioBuffer(3.0 / speed)
    offset = 0.0
    for rep in range(2):
        for j in range(2):
            dur = 0.08 / speed
            buf.add_chirp(6000, 5200, offset, dur, 0.2)
            buf.add_chirp(6000 * 1.3, 5200 * 1.3, offset, dur * 0.6, 0.08)
            buf.add_chirp(3000, 2800, offset, dur, 0.1)
            offset += dur + 0.06 / speed
        for j in range(2):
            dur = 0.12 / speed
            buf.add_chirp(3200, 2600, offset, dur, 0.3)
            buf.add_chirp(3200 * 2, 2600 * 2, offset, dur, 0.08)
            buf.add_chirp(1600, 1300, offset, dur, 0.12)
            offset += dur + 0.06 / speed
        offset += 0.2 / speed
    return buf.get_samples()


def gen_peetink(speed=1.0):
    """13. Pee-tink."""
    buf = AudioBuffer(3.0 / speed)
    offset = 0.0
    for rep in range(5):
        buf.add_chirp(7500, 7200, offset, 0.08 / speed, 0.15)
        offset += 0.1 / speed
        buf.add_chirp(5500, 4800, offset, 0.05 / speed, 0.28)
        buf.add_chirp(5500 * 1.5, 4800 * 1.5, offset, 0.03 / speed, 0.06)
        offset += 0.25 / speed
    return buf.get_samples()


def gen_jar(speed=1.0):
    """14. Jar/rattle (ground predator)."""
    buf = AudioBuffer(4.0 / speed)
    offset = 0.0
    for rep in range(3):
        dur = 0.35 / speed
        pulse_rate = 25 * speed
        num_pulses = int(dur * pulse_rate)
        for i in range(num_pulses):
            pulse_dur = 0.02 / speed
            pulse_time = offset + i / pulse_rate
            buf.add_chirp(2800, 2600, pulse_time, pulse_dur, 0.18)
            buf.add_chirp(2800 * 1.8, 2600 * 1.8, pulse_time, pulse_dur * 0.6, 0.06)
        offset += dur + 0.3 / speed
    return buf.get_samples()


def gen_tsee_tsui(speed=1.0):
    """15. Tsee-tsui."""
    buf = AudioBuffer(3.0 / speed)
    offset = 0.0
    for rep in range(4):
        buf.add_chirp(7800, 7200, offset, 0.08 / speed, 0.14)
        offset += 0.1 / speed
        buf.add_chirp(6800, 5500, offset, 0.07 / speed, 0.16)
        offset += 0.28 / speed
    return buf.get_samples()


def gen_contact(speed=1.0):
    """16. Contact si-si."""
    buf = AudioBuffer(3.0 / speed)
    note_len = 0.1 / speed
    gap = 0.15 / speed
    total = 0.0
    for i in range(5):
        offset = i * (note_len + gap)
        freq_var = 6800 + math.sin(i * 1.5) * 400
        buf.add_chirp(freq_var, freq_var + 200, offset, note_len, 0.15)
        total = offset + note_len
    buf.add_chirp(7200, 6200, total + gap, note_len * 2, 0.18)
    return buf.get_samples()


def gen_flight(speed=1.0):
    """17. Flight call."""
    random.seed(17)
    buf = AudioBuffer(3.0 / speed)
    note_len = 0.035 / speed
    gap = 0.18 / speed
    offset = 0.0
    for i in range(6):
        f_var = 5800 + (random.random() - 0.5) * 600
        buf.add_chirp(f_var, f_var - 400, offset, note_len, 0.15)
        offset += note_len + gap + (random.random() - 0.5) * 0.04
    return buf.get_samples()


def gen_pit(speed=1.0):
    """18. Pit/spick contact notes."""
    random.seed(18)
    buf = AudioBuffer(4.0 / speed)
    offset = 0.0
    for i in range(8):
        dur = 0.025 / speed
        freq = 4500 + (random.random() - 0.5) * 800
        buf.add_chirp(freq, freq - 200, offset, dur, 0.13)
        offset += dur + (0.2 + random.random() * 0.15) / speed
    return buf.get_samples()


def gen_peh_puuh(speed=1.0):
    """19. Peh-puuh."""
    buf = AudioBuffer(4.0 / speed)
    offset = 0.0
    for rep in range(4):
        buf.add_chirp(3500, 4800, offset, 0.1 / speed, 0.2)
        offset += 0.12 / speed
        buf.add_chirp(4600, 3000, offset, 0.15 / speed, 0.22)
        buf.add_harmonic(3800, 2, offset, 0.15 / speed, 0.04)
        offset += 0.4 / speed
    return buf.get_samples()


def gen_begging(speed=1.0):
    """20. Begging call."""
    buf = AudioBuffer(3.0 / speed)
    note_len = 0.04 / speed
    gap = 0.05 / speed
    offset = 0.0
    for burst in range(3):
        for i in range(6):
            freq = 7500 + math.sin(i * 3) * 500
            buf.add_chirp(freq, freq + 300, offset, note_len, 0.18)
            offset += note_len + gap
        offset += 0.12 / speed
    return buf.get_samples()


def gen_fledgling(speed=1.0):
    """21. Fledgling contact call."""
    buf = AudioBuffer(3.0 / speed)
    offset = 0.0
    for burst in range(2):
        for i in range(4):
            dur = 0.06 / speed
            buf.add_chirp(6500, 7200, offset, dur * 0.4, 0.2)
            buf.add_chirp(7200, 6000, offset + dur * 0.4, dur * 0.6, 0.2)
            offset += dur + 0.05 / speed
        offset += 0.15 / speed
    for i in range(5):
        dur = 0.04 / speed
        buf.add_chirp(7800, 7400, offset, dur, 0.18)
        offset += dur + 0.06 / speed
    return buf.get_samples()


def gen_hiss(speed=1.0):
    """22. Hissing display."""
    random.seed(22)
    buf = AudioBuffer(7.0 / speed)
    offset = 0.0
    for rep in range(3):
        hiss_dur = 0.18 / speed
        buf.add_noise(offset, hiss_dur, 0.25, 4500, 0.5)
        buf.add_noise(offset, hiss_dur * 0.7, 0.08, 4000, 2.0)
        offset += hiss_dur + 0.08 / speed
        buf.add_click(offset, 0.35)
        offset += 1.8 / speed
    return buf.get_samples()


def gen_nest_exchange(speed=1.0):
    """23. Nest exchange calls."""
    buf = AudioBuffer(3.0 / speed)
    offset = 0.0
    for i in range(3):
        dur = 0.07 / speed
        buf.add_chirp(5800 + i * 200, 5400 + i * 200, offset, dur, 0.14)
        offset += dur + 0.06 / speed
    offset += 0.1 / speed
    for i in range(2):
        dur = 0.08 / speed
        buf.add_chirp(4200, 3800, offset, dur, 0.16)
        offset += dur + 0.08 / speed
    offset += 0.1 / speed
    for i in range(5):
        dur = 0.05 / speed
        buf.add_chirp(6200 + i * 100, 5800 + i * 100, offset, dur, 0.16)
        offset += dur + 0.04 / speed
    return buf.get_samples()


def gen_mate_separation(speed=1.0):
    """24. Mate separation call."""
    buf = AudioBuffer(3.0 / speed)
    offset = 0.0
    for rep in range(3):
        buf.add_chirp(4000, 3600, offset, 0.1 / speed, 0.08)
        offset += 0.12 / speed
        buf.add_chirp(3200, 2800, offset, 0.1 / speed, 0.08)
        offset += 0.1 / speed + 0.35 / speed
    return buf.get_samples()


def gen_food_chirp(speed=1.0):
    """25. Food chirp."""
    random.seed(25)
    buf = AudioBuffer(3.0 / speed)
    offset = 0.0
    for i in range(10):
        dur = 0.03 / speed
        freq = 5200 + (random.random() - 0.5) * 1000
        buf.add_chirp(freq, freq + 400, offset, dur, 0.16)
        offset += dur + (0.08 + random.random() * 0.12) / speed
    return buf.get_samples()


def gen_bill_snap(speed=1.0):
    """26. Bill snapping."""
    random.seed(26)
    buf = AudioBuffer(3.0 / speed)
    offset = 0.0
    for rep in range(6):
        buf.add_click(offset, 0.5)
        offset += (0.15 + random.random() * 0.1) / speed
    return buf.get_samples()


# ── Main ──

SOUND_MAP = [
    ("01_teacher", gen_teacher),
    ("02_song_complex", gen_song_complex),
    ("03_saw_song", gen_saw_song),
    ("04_pietoe", gen_pietoe),
    ("05_subsong", gen_subsong),
    ("06_dawn_chorus", gen_dawn_chorus),
    ("07_courtship", gen_courtship),
    ("08_alarm", gen_alarm),
    ("09_seet", gen_seet),
    ("10_mobbing", gen_mobbing),
    ("11_churr", gen_churr),
    ("12_scold", gen_scold),
    ("13_peetink", gen_peetink),
    ("14_jar", gen_jar),
    ("15_tsee_tsui", gen_tsee_tsui),
    ("16_contact", gen_contact),
    ("17_flight", gen_flight),
    ("18_pit", gen_pit),
    ("19_peh_puuh", gen_peh_puuh),
    ("20_begging", gen_begging),
    ("21_fledgling", gen_fledgling),
    ("22_hiss", gen_hiss),
    ("23_nest_exchange", gen_nest_exchange),
    ("24_mate_separation", gen_mate_separation),
    ("25_food_chirp", gen_food_chirp),
    ("26_bill_snap", gen_bill_snap),
]


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    print(f"Generating {len(SOUND_MAP)} koolmees sounds...\n")
    for name, gen_func in SOUND_MAP:
        print(f"Generating: {name}")
        samples = gen_func()
        write_wav(f"{name}.wav", samples)
    print(f"\nDone! All files written to '{OUTPUT_DIR}/'")


if __name__ == "__main__":
    main()
