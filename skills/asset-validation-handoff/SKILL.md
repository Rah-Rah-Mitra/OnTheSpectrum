---
name: asset-validation-handoff
description: Validate and hand off generated Blender and web viewer assets. Use after producing .blend, .glb, preview renders, metadata, or a Three.js viewer to check builds, browser loading, controls, screenshots, file paths, budgets, and final response contents.
---

# Asset Validation Handoff

Use this skill before final delivery of any generated asset set.

## Required Checks

- Confirm `.blend`, `.glb`, preview `.png`, and metadata JSON exist at stable paths.
- Run `node tools/asset-pipeline/inspect_glb.mjs <path>`.
- Run `node tools/asset-pipeline/validate_glb_budget.mjs <path>`.
- Run `npm run build`.
- Start the app and verify the GLB loads in the browser.
- Test mode switch, reset/focus, play/pause spin, zoom in/out, download, and snapshot.
- Inspect desktop and mobile screenshots for blank canvas, clipping, camera drift, text overflow, or overlapping UI.

## Handoff Content

Include the local URL, generated asset paths, build/test result, known limitations, metadata highlights, and a short description of what was generated.
