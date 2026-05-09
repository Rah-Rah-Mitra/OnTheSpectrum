---
name: threejs-asset-viewer
description: Build or adapt the repo's React, Vite, and Three.js GLB viewer for Blender-exported assets. Use when loading GLB models with GLTFLoader, tuning OrbitControls camera framing, exposing model metadata, or verifying responsive 3D asset inspection workflows.
---

# Three.js Asset Viewer

Use the existing React/Vite/Three.js app as the viewer surface. Keep the 3D canvas as the main experience, not a landing page.

## Viewer Requirements

- Load the GLB with `GLTFLoader`.
- Use `OrbitControls` with damping.
- Auto-spin must be opt-in.
- Include controls for reset, focus, zoom in/out, spin play/pause, model download, snapshot, and lighting mode.
- Show a compact inspector with runtime model metadata and authored asset metadata.
- Keep desktop and mobile layouts stable, with no text overflow or overlapping controls.

## Framing Rules

- Use an asset manifest for model URL, source `.blend`, preview render, camera presets, initial transform, focus pose, download filename, and authored notes.
- First load should be front-facing and unclipped on desktop and mobile.
- Tune orientation in Three.js if GLB axis export appears rotated.
- After changes, test desktop around `1440x900` and mobile around `390x844`.

## Verification

Run `npm run build`, load the local app, verify console health, and test mode switch, reset/focus, spin, zoom, download, and snapshot.
