import wave
import math
import struct
import random

SAMPLE_RATE = 44100
DURATION = 60 # seconds
TOTAL_SAMPLES = SAMPLE_RATE * DURATION

def generate_lofi_music(filename="lofi_beat.wav"):
    bpm = 85
    beat_sec = 60.0 / bpm
    step_sec = beat_sec / 4.0 # 16th note

    # Chord frequencies (Hz) - Upbeat Lo-fi progression: Fmaj7 -> Em7 -> Dm7 -> Cmaj7
    chords = [
        [349.23, 440.00, 523.25, 659.25], # Fmaj7
        [329.63, 392.00, 493.88, 587.33], # Em7
        [293.66, 349.23, 440.00, 523.25], # Dm7
        [261.63, 329.63, 392.00, 493.88]  # Cmaj7
    ]

    bass_notes = [174.61, 164.81, 146.83, 130.81] # F2, E2, D2, C2

    output_samples = []

    for i in range(TOTAL_SAMPLES):
        t = i / SAMPLE_RATE
        measure = int(t / (4 * beat_sec)) % 4
        chord = chords[measure]
        bass_freq = bass_notes[measure]

        beat_in_measure = (t % (4 * beat_sec)) / beat_sec
        step_in_measure = int((t % (4 * beat_sec)) / step_sec)

        # 1. Warm Synth Pad / Electric Piano Sound
        chord_signal = 0.0
        for freq in chord:
            # Soft sine with subtle vibrato
            vib = 1.0 + 0.003 * math.sin(2 * math.pi * 5 * t)
            val = math.sin(2 * math.pi * (freq * vib) * t)
            # Gentle harmonic
            val += 0.3 * math.sin(2 * math.pi * (freq * 2 * vib) * t)
            chord_signal += val
        chord_signal /= len(chord)

        # 2. Smooth Sub Bass
        bass_signal = math.sin(2 * math.pi * bass_freq * t) + 0.4 * math.sin(2 * math.pi * (bass_freq * 2) * t)

        # 3. Lo-Fi Drum Beat (Kick, Snare, Hi-hat)
        drum_signal = 0.0
        time_in_beat = t % beat_sec
        time_in_step = t % step_sec

        # Kick on 1 and 3
        is_kick = (int(beat_in_measure) == 0 or int(beat_in_measure) == 2) and (time_in_beat < 0.15)
        if is_kick:
            kick_env = math.exp(-time_in_beat * 30)
            kick_freq = 110 * math.exp(-time_in_beat * 40) + 40
            drum_signal += 0.8 * math.sin(2 * math.pi * kick_freq * time_in_beat) * kick_env

        # Soft Snare on 2 and 4
        is_snare = (int(beat_in_measure) == 1 or int(beat_in_measure) == 3) and (time_in_beat < 0.2)
        if is_snare:
            snare_env = math.exp(-time_in_beat * 25)
            noise = (random.random() * 2.0 - 1.0)
            snare_tone = math.sin(2 * math.pi * 180 * time_in_beat)
            drum_signal += 0.4 * (0.7 * noise + 0.3 * snare_tone) * snare_env

        # Hi-hat on every 8th note
        is_hihat = (int(step_in_measure) % 2 == 0) and (time_in_step < 0.05)
        if is_hihat:
            hihat_env = math.exp(-time_in_step * 80)
            noise = (random.random() * 2.0 - 1.0)
            drum_signal += 0.2 * noise * hihat_env

        # 4. Vinyl Crackle / Ambient Texture
        crackle = 0.015 * (random.random() * 2.0 - 1.0) if random.random() < 0.08 else 0.0

        # Mix with master balance
        mixed = 0.25 * chord_signal + 0.35 * bass_signal + 0.35 * drum_signal + crackle

        # Soft limiter / clipping protection
        mixed = max(-0.95, min(0.95, mixed))

        # Convert to 16-bit PCM integer
        sample_int = int(mixed * 32767)
        output_samples.append(sample_int)

    # Write WAV file
    with wave.open(filename, "wb") as wf:
        wf.setnchannels(1) # Mono
        wf.setsampwidth(2) # 16-bit
        wf.setframerate(SAMPLE_RATE)
        packed_data = struct.pack(f"<{len(output_samples)}h", *output_samples)
        wf.writeframes(packed_data)

    print(f"Generated lo-fi beat track: {filename} ({DURATION}s)")

if __name__ == "__main__":
    generate_lofi_music()
