# NM26 table kits for render-skater-crops.py (exec'd there; defines KITS). Kit check 2026-10-09 against real crops:
# the skater kits match the reference molds' layout (white or yellow jersey, blue pants, light socks, blue skates);
# only the blue differs. Real skater blue sRGB median (40, 60, 114) against the reference renders' (69, 96, 151), the
# same gap as on the W goalie, so every blue material takes the goalie's NM26 blue (render-goalie-crops.py) with the
# wider jitter. Status: assumed from broadcast crops.
def _colour(name, base):
    if name.startswith("fig_blue"):
        return (0.004, 0.03, 0.25), (0.75, 1.25)
    return base, (0.85, 1.15)


KITS = {"apply": lambda rnd: None, "colour": _colour}
