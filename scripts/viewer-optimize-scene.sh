#!/bin/sh
# Rebuilds viewer/public/scene.glb from the Blender export (17 MB -> ~0.9 MB): meshopt, WebP textures (max 2048),
# meshes simplified to 15 % at a relative error of 0.002 (STL skater 80k -> 12k triangles, goalie 160k -> 25k).
# Node names (Figure.*, Puck) are kept. Needs network for npx. Checked visually in docs/viewer.md.
set -e
npx --yes @gltf-transform/cli optimize assets/scene/full_static_appearance.glb viewer/public/scene.glb \
  --compress meshopt --texture-compress webp --texture-size 2048 \
  --flatten false --join false --instance false --palette false \
  --simplify true --simplify-ratio 0.15 --simplify-error 0.002
