"""Bring-up step 3: measure the microphone.  On the board:  import calibrate_mic

Follow the prompts (3 s to get ready, then 4 s of measuring per phase).
It prints real numbers and suggested values for config.py.
If raw values touch 0 or 4095 the signal is clipped: turn the gain
trimmer on the MAX4466 down.
"""

import time
from audio import AudioAnalyzer

mic = AudioAnalyzer()

started = time.ticks_us()
mic._read_samples()
window = time.ticks_diff(time.ticks_us(), started)
count = len(mic.samples)
print("Window: {} us for {} samples -> about {} Hz sampling".format(
    window, count, count * 1000000 // max(1, window)))

results = {}
for label in ("silence", "speech", "music", "clap"):
    print("Now:", label, "- starting in 3 s")
    time.sleep(3)
    rms_list = []
    zcr_list = []
    low = 4095
    high = 0
    t0 = time.ticks_ms()
    while time.ticks_diff(time.ticks_ms(), t0) < 4000:
        mic._read_samples()
        rms, zcr = mic._features()
        rms_list.append(rms)
        zcr_list.append(zcr)
        low = min(low, min(mic.samples))
        high = max(high, max(mic.samples))
    results[label] = (min(rms_list), max(rms_list), min(zcr_list), max(zcr_list))
    print("  {}: rms {}-{}  zcr {:.3f}-{:.3f}  raw {}-{}".format(
        label, results[label][0], results[label][1],
        results[label][2], results[label][3], low, high))

print("")
print("Suggested config.py values (check against the numbers above):")
print("AUDIO_SILENCE_RMS =", int(results["silence"][1] * 1.5) + 2)
print("AUDIO_LOUD_RMS =", int(results["clap"][1] * 0.7))
print("AUDIO_SPEECH_ZCR_MIN =", round(results["speech"][2] * 0.8, 3))
print("AUDIO_SPEECH_ZCR_MAX =", round(results["speech"][3] * 1.2, 3))
print("Music should fall OUTSIDE the speech ZCR range:",
      round(results["music"][2], 3), "-", round(results["music"][3], 3))
