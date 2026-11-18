"""Keypoint + heading regressor for NM26 skaters, trained on renders only (hypothesis experiment, PROPOSED).

    python3 scripts/synth/figexp/train_kp.py train [epochs] [out.pt]
    python3 scripts/synth/figexp/train_kp.py ft <epochs> out.pt start.pt   (adds the user labels of games 1,2,4,6)

Network: ImageNet ResNet-18 -> 8 numbers: cos/sin of the figure heading and three keypoints (head top, stick root =
blade heel, stick tip) in a 144 x 144 window around the pivot. Heading is also recovered from the two stick keypoints
(back-projected to the table plane). Training images: the renders of render_kp.py (out/synth/figexp/r_*), composited on
the games' empty-rink background plates with camera degradations (blur, motion blur, JPEG, noise, colour, small shifts)
and random occluders. No real label is used in training.
"""
import json, math, random, sys
from pathlib import Path
import cv2, numpy as np, torch, torch.nn as nn, torchvision

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "scripts")); sys.path.insert(0, str(REPO / "scripts/synth"))
import table_common  # noqa: E402
from compose import degrade  # noqa: E402

torch.set_num_threads(4)
W0, H0, WS = 28, 48, 144              # window in the 200 px crop
ROI0 = (240, 440)                     # background.png origin in reference video px
K, R, T = table_common.ref_camera()
PLATES = [cv2.imread(str(REPO / f"data/games/nm26-semifinal/g{k}/background.png")) for k in range(1, 8)]
MEAN, STD = np.array([0.406, 0.456, 0.485], np.float32), np.array([0.225, 0.224, 0.229], np.float32)  # BGR order


def plate_for(origin, rnd):
    P = rnd.choice(PLATES); x0, y0 = origin[0] - ROI0[0], origin[1] - ROI0[1]
    pad = 220; Pp = cv2.copyMakeBorder(P, pad, pad, pad, pad, cv2.BORDER_REPLICATE)
    return Pp[y0 + pad:y0 + pad + 200, x0 + pad:x0 + pad + 200].astype(np.float32)


def motion_blur(img, rnd):
    n = rnd.randint(3, 9); k = np.zeros((n, n), np.float32); a = rnd.uniform(0, math.pi)
    cv2.line(k, (n // 2 - int(round(math.cos(a) * n / 2)), n // 2 - int(round(math.sin(a) * n / 2))),
             (n // 2 + int(round(math.cos(a) * n / 2)), n // 2 + int(round(math.sin(a) * n / 2))), 1.0, 1)
    return cv2.filter2D(img, -1, k / max(k.sum(), 1e-6))


def to_tensor(bgr, dx=0, dy=0):
    w = bgr[H0 + dy:H0 + dy + WS, W0 + dx:W0 + dx + WS].astype(np.float32) / 255.0
    return torch.from_numpy(((w - MEAN) / STD).transpose(2, 0, 1).copy())


def backproject(q, z):
    """Reference video px -> table plane point (mm) at height z."""
    Ri = np.linalg.inv(K @ R); v = Ri @ np.array([q[0], q[1], 1.0]); c = Ri @ (K @ T)
    s = (z + c[2]) / v[2]
    return (s * v - c)[:2]


def heading_from_kp(kp_px, crop_origin):
    root = np.array(kp_px[1]) + crop_origin; tip = np.array(kp_px[2]) + crop_origin
    a = backproject(tip, 0.95) - backproject(root, 2.0)
    return (math.degrees(math.atan2(a[1], a[0])) - 90.0) % 360.0


def load_renders():
    rows = []
    for d in sorted((REPO / "out/synth/figexp").glob("r_*")):
        if not (d / "labels.jsonl").exists(): continue
        for l in open(d / "labels.jsonl"):
            if not l.strip(): continue
            r = json.loads(l)
            if r["present"] != 1 or r["kind"] not in ("base", "hard") or not (d / f"{r['seed']}.png").exists(): continue
            r["path"] = str(d / f"{r['seed']}.png"); rows.append(r)
    return rows


class RenderSet(torch.utils.data.Dataset):
    def __init__(self, rows, train): self.rows, self.train = rows, train
    def __len__(self): return len(self.rows)
    def __getitem__(self, i):
        r = self.rows[i]; rnd = random.Random((i * 7919 + (random.randrange(1 << 30) if self.train else 5)))
        rgba = cv2.imread(r["path"], cv2.IMREAD_UNCHANGED)
        plate = plate_for(r["crop_origin_ref_px"], rnd)
        a = rgba[..., 3:4].astype(np.float32) / 255.0; fg = rgba[..., :3].astype(np.float32)
        fg = np.clip((fg - 128) * rnd.uniform(1.0, 1.35) + 128 + rnd.uniform(-15, 15), 0, 255)
        img = plate * (1 - a) + fg * a
        if self.train and rnd.random() < 0.3:  # occluder (hand, neighbour, advert): a random patch of a kit/skin/white colour
            for _ in range(rnd.randint(1, 2)):
                w, h = rnd.randint(10, 40), rnd.randint(10, 40); x, y = rnd.randint(W0, W0 + WS - w), rnd.randint(H0, H0 + WS - h)
                img[y:y + h, x:x + w] = np.array([rnd.uniform(0, 255) for _ in range(3)], np.float32)
        Ms = []
        img = degrade(img, rnd, out_M=Ms) if self.train else degrade(img, random.Random(i), blur=(0.8, 0.8), jpeg=(60, 60), out_M=Ms)
        if self.train and rnd.random() < 0.33: img = motion_blur(img, rnd)
        M = Ms[0]; kp = np.array(r["kp_px"], np.float32); kp = kp @ M[:, :2].T + M[:, 2]
        dx, dy = (rnd.randint(-8, 8), rnd.randint(-8, 8)) if self.train else (0, 0)
        kpn = ((kp - np.array([W0 + dx, H0 + dy])) / WS).reshape(-1)
        h = math.radians(r["heading_deg"])  # the 1.5 deg rotation of degrade() is camera roll; the label stays
        y = np.concatenate([[math.cos(h), math.sin(h)], kpn]).astype(np.float32)
        return to_tensor(img, dx, dy), torch.from_numpy(y), torch.tensor(1.0)


class RealSet(torch.utils.data.Dataset):
    """Real label crops (heading only): the fine-tuning variant that mirrors v3's recipe (renders + the user's labels)."""
    def __init__(self, items, repeat): self.items, self.repeat = items, repeat
    def __len__(self): return len(self.items) * self.repeat
    def __getitem__(self, i):
        r = self.items[i % len(self.items)]; rnd = random.Random(random.randrange(1 << 30))
        img = cv2.imread(str(REPO / f"out/synth/figexp/real/{r['id']}.png")).astype(np.float32)
        img = degrade(img, rnd, blur=(0.01, 0.6), jpeg=(60, 92))
        dx, dy = rnd.randint(-8, 8), rnd.randint(-8, 8); h = math.radians(r["facing_deg"])
        y = np.zeros(8, np.float32); y[0], y[1] = math.cos(h), math.sin(h)
        return to_tensor(img, dx, dy), torch.from_numpy(y), torch.tensor(0.0)


def make_model():
    m = torchvision.models.resnet18(weights="IMAGENET1K_V1"); m.fc = nn.Linear(512, 8); return m


def ang_diff(a, b): return (a - b + 180.0) % 360.0 - 180.0


def predict(model, X):
    model.eval(); out = []
    with torch.no_grad():
        for i in range(0, len(X), 64): out.append(model(torch.stack(X[i:i + 64])).numpy())
    return np.concatenate(out)


def decode(o, crop_origin, dx=0, dy=0):
    kp = (o[2:].reshape(3, 2) * WS + np.array([W0 + dx, H0 + dy])).tolist()
    direct = math.degrees(math.atan2(o[1], o[0])) % 360.0
    stick = heading_from_kp(kp, np.array(crop_origin, float))
    c = np.exp(1j * np.radians([direct, stick])).sum(); comb = math.degrees(math.atan2(c.imag, c.real)) % 360.0
    return {"direct": direct, "stick": stick, "comb": comb, "kp": kp}


def train(epochs, out, ft=False):
    rows = load_renders(); rnd = random.Random(1); rnd.shuffle(rows)
    nv = max(100, len(rows) // 10); val, tr = rows[:nv], rows[nv:]
    print(len(tr), "train", len(val), "val renders", flush=True)
    ds = RenderSet(tr, True)
    if ft:  # fine-tune: renders + the user's labels of games 1, 2, 4, 6 (the games v3 trained on); games 3, 5, 7 stay unseen
        idx = json.loads((REPO / "out/synth/figexp/real/index.json").read_text()); ds = torch.utils.data.ConcatDataset([ds, RealSet([r for r in idx if r["game"] in ("g1", "g2", "g4", "g6")], 6)])
    dl = torch.utils.data.DataLoader(ds, batch_size=32, shuffle=True, num_workers=3, drop_last=True, persistent_workers=True)
    model = make_model(); lr = 1e-3
    if ft: model.load_state_dict(torch.load(sys.argv[4])); lr = 3e-4
    opt = torch.optim.AdamW(model.parameters(), lr, weight_decay=1e-4)
    sched = torch.optim.lr_scheduler.OneCycleLR(opt, lr, total_steps=epochs * len(dl))
    for ep in range(epochs):
        model.train(); tot = 0
        for x, y, m_ in dl:
            o = model(x); loss = nn.functional.mse_loss(o[:, :2], y[:, :2]) * 4 + (nn.functional.smooth_l1_loss(o[:, 2:], y[:, 2:], beta=0.02, reduction="none").mean(1) * m_).mean() * 20
            opt.zero_grad(); loss.backward(); opt.step(); sched.step(); tot += loss.item()
        V = RenderSet(val, False); X = [V[i][0] for i in range(len(V))]; P = predict(model, X)
        e = {k: [] for k in ("direct", "stick", "comb")}
        for p, r in zip(P, val):
            d = decode(p, r["crop_origin_ref_px"])
            for k in e: e[k].append(abs(ang_diff(d[k], r["heading_deg"])))
        print(f"ep {ep + 1} loss {tot / len(dl):.4f} val median deg " + " ".join(f"{k} {np.median(v):.1f}" for k, v in e.items()), flush=True)
        torch.save(model.state_dict(), out)


if __name__ == "__main__":
    if sys.argv[1] == "train":
        train(int(sys.argv[2]) if len(sys.argv) > 2 else 12, sys.argv[3] if len(sys.argv) > 3 else str(REPO / "out/synth/figexp/kp.pt"))
    elif sys.argv[1] == "ft":  # ft <epochs> <out.pt> <start.pt>
        train(int(sys.argv[2]), sys.argv[3], ft=True)
