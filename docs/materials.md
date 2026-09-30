# Materials and artwork (iterations 17-18)

## Rink, housing, goals, screens (iteration 17)

```sh
/root/venvs/blender/bin/python assets/blender/make_ice_texture.py   # about 1 min
/root/venvs/blender/bin/python assets/blender/build_materials.py    # about 4 min, 2 renders
```

**Environment note.** OpenCV (for inpainting) must stay NumPy-1 compatible, because bpy 4.5 is compiled against NumPy 1.x: `pip install "numpy<2" "opencv-python-headless<4.11"`. An unpinned install broke bpy's NumPy import once; it was fixed by pinning.

### Ice artwork

**Source:** only the official overhead of the selected variant 71-1145-01. The older bare-sheet print is **not** used.

1. **Rectification.** Each texel samples the overhead through the inverse of the ASSUMED preview similarity (0.1796 mm/texel, 4708 × 2616, bicubic). Lens bow and keystone (≤ about 16 px) are not corrected.
2. **Mask** (26% of the ice) of everything that must not be baked in:
   - the 12 figures with their metal sticks and soft shadows (automatic discs plus operator boxes read from a gridded view);
   - both goal cages and shadows, and the puck;
   - slot and cut-out bands (holes in the geometry).
3. **Reconstruction.**
   - Texels outside the ice are pre-filled with the ice colour, and line bands near masks are included in the mask, so no board or line colour bleeds.
   - Two-source Telea inpainting: inside the fitted centre disc (radius 61.1 mm) from disc texels only, outside it from ice texels only.
   - The five straight lines are redrawn only across gaps where the original shows the line on both sides. The centre line stays absent under the disc.
4. **UVs** are planar from world millimetres over the inner-boundary bounds, so the texture has the calibrated preview scale.

Numbers and the list of masked regions: `validation/17-ice-texture-report.json`. Mask overlay: `validation/17-ice-texture-mask.png`.

### Sponsors dropped (user decision D6)

```sh
/root/venvs/blender/bin/python assets/blender/drop_sponsors.py   # after make_ice_texture.py; about 45 s
```

`make_ice_texture.py` now writes the reference-variant print to `assets/rink/textures/ice_basecolor_reference.png`
(kept for traceability). `drop_sponsors.py` writes the sponsor-free `ice_basecolor.png`, which the materials use.

- **Removed (26% of the ice wiped):** the four face-off circle fills and logos, both crease fills (including the part behind the goal line), the centre disc, the Scandic, Gigant, WD-40 and Gorilla logos, and the coloured smudges those fills had left nearby.
- **Fill:** a cubic polynomial ice shade fitted to clean ice, plus the local residual inpainted at quarter resolution. There is no visible seam, even at 2.5× contrast.
- **Markings.** Face-off rings (r ≈ 286 texels = 51.5 mm at the preview scale) and crease arcs (r ≈ 415 texels = 74.5 mm) are redrawn from circles fitted to their own red pixels. Hash marks and the four spots keep their original pixels. The lines are redrawn where they crossed wiped areas, and the centre line is continued across the former disc (inferred).
- **Report and before/after:** `validation/drop-sponsors-report.json`, `validation/drop-sponsors-compare.png`.

### Materials

| Part | Material |
| --- | --- |
| Ice | Printed texture, roughness 0.25 |
| Housing | Black plastic; sRGB (46, 50, 59) sampled from side A (includes photo lighting); roughness 0.35 |
| Goals | Red plastic; sRGB (179, 38, 47) = median of the traced cage pixels in the overhead |
| End screens | Clear plastic, transmission 1, IOR 1.49 (assumed) |
| Boards | **Placeholder** light grey |

**Light:** fixed and restrained: one sun (2.2) and a grey world (0.55), Cycles with a fixed seed. The same cameras as iteration 16.

**Review** (AI): `validation/17-overhead-vs-reference.png` (render above, reference crop below, same world window), and `17-oblique.png`. Lines, logos, spots, slots and the disc align with the reference; no figure, stick or goal remnants.

### Texture gaps and material mismatches

- **Sponsor artwork:** removed at the user's request (D6). The ice now carries hockey markings only.
- **Boards:** plain placeholder grey. There are no sponsors, by the user's choice. The black top rail is not reconstructed. Only the side photos show the boards frontally, with perspective, and the ends are not seen.
- **Housing:** the "PLAY OFF 21 / STIGA" print and the legs are not modelled.
- **Baked-in photo effects:** lighting, vignetting and board reflections near the ice edge remain in the texture.
- **Colours and screens:** the goal and housing colours include photo lighting; the gloss is assumed. Screen thickness, profile and clips are not modelled.

## Figures and puck (iteration 18)

```sh
/root/venvs/blender/bin/python assets/blender/build_appearance.py   # materials on assets and scene (about 1 min)
/root/venvs/blender/bin/python assets/blender/render_appearance.py  # review renders (about 8 min)
```

- **Team choice:** the documented reference variant, Finland = W (white/blue), Sweden = E (yellow/blue). The user's own teams have not been supplied.
- **Colours** are sampled from tight boxes on the figures in the official overhead (`validation/18-colour-samples.json`, with pixel boxes). One earlier attempt sampled the side photos and picked up a blue board and the ice; it was replaced. Both whites use the brightest sample (230, 226, 225), because the W-RD jersey sample is shaded.
- **Assignment by face.**
  - Body faces take the colour of their nearest layout element: helmet, gloves, pants and skates blue; jersey, sleeves and socks white; face and neck skin.
  - Separate mesh islands are classified by position: the skater's blade and shaft are metal, the skate blocks blue, the goalie stick tan (overhead sample).
  - Puck: black (roughness 0.55). Placeholders: team two-tone, still placeholders.
- **Geometry unchanged:** vertex positions checked in Blender for both assets and the scene, plus GLB bounds in the tests.
- **Renders** with the iteration-17 benchmark light:
  - intended output `validation/18-oblique-1080p.png` (1920 × 1080);
  - close-ups `18-skater-front/side/back.png`, `18-blade-puck.png`, `18-goalie-front.png`. Cameras are inside the rink; the first side camera was hidden by the boards (repair 1).

**Remaining visual defects (AI review)**
1. **At the intended output**, figures are about 60–90 px tall. Colours read correctly, but the proxy bodies look like smooth toys, not the moulded STIGA figures (no pad and helmet edges, no jersey seams).
2. **Stair-stepped colour boundaries**, because colours are assigned per face (visible in close-ups).
3. **No decals:** numbers (W-RD no. 4), FINLAND lettering, helmet and mask details, stripes and the puck logo are unresolved and not invented.
4. **Placeholders:** 10 of 12 figures are generic placeholders.
5. **Debug geometry visible:** the skate blocks and the lifted right leg of W-RD (iteration-14 conflict) show in the close-ups.
6. **Photo lighting:** the whites and blues come from photo pixels that include lighting, so the albedo is approximate.
