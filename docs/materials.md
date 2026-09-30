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

- **Byggmax crease logos** (both goals): the lettering is lost and the area is reconstructed. Also the Gorilla logo (partly) and the WD-40 edge.
- **Boards:** sponsor band and black top rail not reconstructed (placeholder grey). Only the side photos show the boards frontally, with perspective, and the ends are not seen.
- **Housing:** the "PLAY OFF 21 / STIGA" print and the legs are not modelled.
- **Baked-in photo effects:** lighting, vignetting and board reflections near the ice edge remain in the texture.
- **Colours and screens:** the goal and housing colours include photo lighting; the gloss is assumed. Screen thickness, profile and clips are not modelled.
