"""Train three detectors on identical synthetic-blur batches (docs/streak-puck.md):
  P = point target (v1 architecture, v1 loss), S = streak target + endpoint regression (v1 architecture),
  L = streak target + endpoint regression, larger receptive field.
    python3 scripts/synth/streak/train-streak.py [--steps 2400] [--bs 12]"""
import json, sys, time
from pathlib import Path
import numpy as np, torch
sys.path.insert(0, str(Path(__file__).parent))
from streaklib import *
A = sys.argv[1:]
def arg(n, d): return A[A.index(n) + 1] if n in A else d
STEPS = int(arg("--steps", 2400)); BS = int(arg("--bs", 12)); torch.set_num_threads(4)
OUTD = REPO / "out/streak"
if __name__ == "__main__":
    real = load_real(); val_games = ["g7"]
    tr = [s for s in real if s["game"] not in val_games]
    print("real triplets", len(tr), flush=True)
    dl = torch.utils.data.DataLoader(DS(tr, STEPS * BS), batch_size=BS, num_workers=3, persistent_workers=True)
    nets = {"P": Net(False), "S": Net(False), "L": Net(True)}
    opts = {k: torch.optim.AdamW(n.parameters(), 2e-3, weight_decay=1e-4) for k, n in nets.items()}
    sch = {k: torch.optim.lr_scheduler.OneCycleLR(o, 2e-3, total_steps=STEPS, pct_start=0.15) for k, o in opts.items()}
    log = []; t0 = time.time()
    for step, (x, t) in enumerate(dl):
        row = {}
        for k, net in nets.items():
            lg, of, st = net(x)
            hm = t["hm_p"] if k == "P" else t["hm_s"]
            loss = focal(lg[:, 0], hm) + (torch.abs(of - t["off"]) * t["msk"][:, None]).sum() / t["msk"].sum().clamp(min=1)
            if k != "P": loss = loss + 2.0 * (torch.abs(st - t["st"]) * t["msk"][:, None]).sum() / t["msk"].sum().clamp(min=1) / 4
            opts[k].zero_grad(); loss.backward(); opts[k].step(); sch[k].step(); row[k] = round(loss.item(), 3)
        if step % 50 == 0:
            print(step, row, round((time.time() - t0) / 60, 1), "min", flush=True); log.append([step, row])
        if step % 200 == 199 or step == STEPS - 1:
            for k, n in nets.items(): torch.save(n.state_dict(), OUTD / f"streak-{k}.pt")
    (OUTD / "train-log.json").write_text(json.dumps(log))
