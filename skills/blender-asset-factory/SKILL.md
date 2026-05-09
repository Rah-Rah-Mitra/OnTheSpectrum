---
name: blender-asset-factory
description: Create production-useful procedural assets with Blender MCP, including .blend source scenes, GLB exports, preview renders, baked export-safe effects, metadata, and stable public asset paths. Use for Blender-generated characters, props, organic assets, terrain, hard-surface objects, or reusable asset families in this repo.
---

# Blender Asset Factory

Use Blender as the source of truth. Build the real asset in Blender first, save the `.blend`, export a `.glb`, render a preview, and only then update the web viewer.

## Workflow

1. Run `python tools/asset-pipeline/preflight_blender.py`.
2. Prefer the live Blender MCP bridge on `localhost:9876`.
3. Use `BLENDER_PATH` background Blender only when the bridge is unavailable and the environment is configured.
4. Generate assets under stable paths:
   - `public/models/<slug>.blend`
   - `public/models/<slug>.glb`
   - `public/renders/<slug>-preview.png`
   - `public/models/<slug>.metadata.json`
   - optional textures in `public/textures/<slug>/`
5. Use named collections, objects, materials, cameras, lights, and armatures.
6. Bake or finalize visible effects into export-safe geometry, compact textures, or GLB-compatible materials. Do not depend on Blender compositor effects for required GLB appearance.
7. Record object count, mesh count, triangle count, material names, bounds, file sizes, export settings, and known limitations.

## Quality Bar

- Organic assets need asymmetry, curvature, readable silhouettes, layered geometry, and surface detail.
- Hard-surface assets need bevels, seams, paneling, material contrast, and scale cues.
- Character assets should separate logical parts, use deformation-friendly names, and include at least a basic armature when rig-ready is requested.
- Keep GLB exports performant for the web. Warn above 100k triangles, 16 materials, or 12 MB.

## Repo Helpers

- `tools/asset-pipeline/blender_common.py`: shared Blender geometry, material, export, and metadata helpers.
- `tools/asset-pipeline/create_on_the_spectrum_painter_chibi.py`: reference character generator.
- `tools/asset-pipeline/run_blender_asset.py`: background Blender runner for non-MCP use.
- `tools/asset-pipeline/inspect_glb.mjs`: GLB metadata inspection.
- `tools/asset-pipeline/validate_glb_budget.mjs`: web budget validation.
