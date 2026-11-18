"""Top-down stills of a rollout (matplotlib): board, goal, figure footprints at chosen times, puck path coloured by time."""
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon as MPoly, Circle
from . import env
from shotlib import world as W


def figs_of(r):
    figs = {}
    for pid in W.ALL_FIGURES:
        if pid in r["keys"]:
            figs[pid] = env.figure_from_keys(pid, *r["keys"][pid])
        elif pid == "E-G":
            gk = r["goalie_keys"]
            figs[pid] = W.Figure(pid, [{"t": k["t"], "arc_mm": k["arc_mm"]} for k in gk], [{"t": 0.0, "theta_deg": 0.0}])
        else:
            figs[pid] = W.assembly_figure(pid)
    return figs


def draw(ax, r, figs, t, title=None, trail=True):
    b = np.array(W.BOARD.exterior.coords)
    ax.fill(b[:, 0], b[:, 1], color="#e9f1f8", zorder=0); ax.plot(b[:, 0], b[:, 1], color="#335", lw=1)
    for g in (env.G_E, W.GOALS["W"]):
        ax.plot([g.x, g.x + g.sign * g.depth, g.x + g.sign * g.depth, g.x], [g.y - g.half, g.y - g.half, g.y + g.half, g.y + g.half], color="#a33", lw=2)
    for pid, f in figs.items():
        poly = W.world_polygon(f, t)
        geoms = [poly] if poly.geom_type == "Polygon" else list(poly.geoms)
        col = "#2a6fd6" if pid.startswith("W") else "#d6a82a"
        att = pid in r["keys"]
        for gm in geoms:
            ax.add_patch(MPoly(np.array(gm.exterior.coords), closed=True, fc=col, ec="k", lw=1.2 if att else 0.5, alpha=0.95 if att or pid == "E-G" else 0.45, zorder=3))
        if att or pid == "E-G":
            piv = f.pose(t)[0]; ax.text(piv[0], piv[1] + 18, pid, fontsize=6, ha="center", zorder=5)
    T, P = r["T"], r["P"]
    i = min(int(np.searchsorted(T, t)), len(T) - 1)
    if trail:
        ax.scatter(P[:i + 1:8, 0], P[:i + 1:8, 1], c=T[:i + 1:8], s=2, cmap="viridis", vmin=T[0], vmax=T[-1], zorder=4)
    ax.add_patch(Circle(P[i], W.R_PUCK, fc="k", ec="w", zorder=6))
    ax.set_aspect("equal"); ax.set_xlim(-230, 420); ax.set_ylim(-140, 140); ax.set_xticks([]); ax.set_yticks([])
    ax.set_title(title or f"t = {t:.2f} s", fontsize=8)


def strip(r, times, path, suptitle=""):
    figs = figs_of(r)
    fig, axs = plt.subplots(1, len(times), figsize=(4.0 * len(times), 2.6), dpi=130)
    for ax, t in zip(np.atleast_1d(axs), times):
        draw(ax, r, figs, t)
    fig.suptitle(suptitle, fontsize=9)
    fig.tight_layout(); fig.savefig(path); plt.close(fig)
