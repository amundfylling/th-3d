#!/usr/bin/env python3
"""Local Norwegian text-to-speech with Piper (open source, no network at synthesis time).

Reads a JSON job list on stdin: [{"id", "text", "length_scale", "out"}], writes one trimmed mono 16-bit WAV per job
(leading/trailing silence removed so the speech onset is exactly the file start) and prints
{"id": {"duration_s", "trim_lead_s", "sample_rate"}} on stdout.
The voice model is fetched once (sha256 pinned in narration.ts) into out/voices/.
"""
import json, sys, wave, array
from pathlib import Path
from piper import PiperVoice, SynthesisConfig

model = Path(sys.argv[1])
voice = PiperVoice.load(str(model))
jobs = json.load(sys.stdin)
res = {}
THRESH = 300  # int16 amplitude counted as speech
for j in jobs:
    tmp = Path(j["out"]).with_suffix(".raw.wav")
    with wave.open(str(tmp), "wb") as w:
        voice.synthesize_wav(j["text"], w, syn_config=SynthesisConfig(length_scale=j.get("length_scale", 1.0)))
    with wave.open(str(tmp)) as r:
        sr, n = r.getframerate(), r.getnframes()
        a = array.array("h"); a.frombytes(r.readframes(n))
    lo = next((i for i, v in enumerate(a) if abs(v) > THRESH), 0)
    hi = n - next((i for i, v in enumerate(reversed(a)) if abs(v) > THRESH), 0)
    b = a[lo:hi]
    with wave.open(j["out"], "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(sr); w.writeframes(b.tobytes())
    tmp.unlink()
    res[j["id"]] = {"duration_s": len(b) / sr, "trim_lead_s": lo / sr, "sample_rate": sr}
json.dump(res, sys.stdout)
