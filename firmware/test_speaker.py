"""Bring-up step 4: test the MAX98357A amplifier alone.  On the board:  import test_speaker

Plays a short melody at three volumes (very quiet first).
Wiring check if you hear nothing:
  BCLK -> GPIO15, LRC -> GPIO16, DIN -> GPIO17, SD -> GPIO4 (see config.py),
  VIN -> 5 V, GND -> GND, speaker on the amplifier's +/- output.
Loud hiss or hum: check the 5 V supply (add a 100 uF capacitor next to the
amplifier VIN) and keep the speaker wires away from the microphone.
Speaker load: the MAX98357A needs 4 ohm or more. Two 8 ohm speakers in
parallel are fine (4 ohm); two 4 ohm speakers must be wired in series.
"""

import time
from speaker import Speaker

s = Speaker()
melody = ((523, 150), (659, 150), (784, 150), (0, 100), (1047, 250))
for volume in (10, 25, 40):
    s.set_volume(volume)
    print("volume", volume, "%")
    s.play_sequence(melody, time.ticks_ms())
    while s.busy:
        s.update(time.ticks_ms())
        time.sleep_ms(20)
    time.sleep_ms(500)
s.deinit()
print("done")
