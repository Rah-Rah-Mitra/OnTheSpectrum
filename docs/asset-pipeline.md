# Artomata Asset Pipeline

This repo produces Blender-sourced assets plus a web-ready Three.js viewer. Blender is the source of truth: do not substitute browser primitives for a requested Blender model.

## Flow

1. Convert the brief into an asset spec with slug, subject, asset family, required components, material palette, rig target, budget, and viewer pose.
2. Run `python tools/asset-pipeline/preflight_blender.py`.
3. Use the live Blender MCP bridge when available. Use `BLENDER_PATH` background Blender only when configured.
4. Generate the source scene procedurally in Blender.
5. Save `.blend`, export animated `.glb`, render preview `.png`, and write metadata JSON.
6. Update the React/Vite/Three.js viewer manifest to load the new GLB.
7. For humanoid assets that need Mixamo upload support, generate best-effort `.fbx` plus OBJ/MTL `.zip` exports.
8. Run build and browser QA on desktop and mobile.

Use `npm run asset:mixamo-exports` to refresh only existing humanoid Mixamo upload files without rewriting web GLBs, preview renders, or source blends.

## Stable Paths

- `public/models/<slug>.blend`
- `public/models/<slug>.glb`
- `public/models/<slug>.metadata.json`
- `public/renders/<slug>-preview.png`
- `public/textures/<slug>/` when external textures are useful
- `public/exports/<slug>/<slug>-mixamo.fbx` for best-effort rigged Mixamo upload
- `public/exports/<slug>/<slug>-mixamo-obj.zip` for an unrigged OBJ/MTL Mixamo fallback

## Naming

- Collections: `RIG`, `CHARACTER_BODY`, `FACE`, `HAIR`, `OUTFIT`, `PROPS`, `BAKED_EFFECTS`, `LIGHTING_CAMERA`.
- Materials: prefix with `MAT_`.
- Character meshes: prefix with `CHR_`, `FACE_`, `HAIR_`, `OUT_`, `PROP_`, or `BASE_`.
- Armatures: prefix with `RIG_`; armature data prefix with `ARM_`.

## Web Budgets

- Preferred triangle range: 35k-80k for showcase character assets.
- Warning budget: 100k triangles, 16 materials, or 12 MB GLB.
- Keep auto-spin off on first load.
- Verify front-facing framing after export because GLB orientation can drift.

## Animation and Mixamo

- Embedded viewer clips should be named in metadata and exposed through the asset registry.
- Mixamo upload links are character-focused. Adobe documents custom Mixamo uploads as FBX, OBJ, or ZIP, and rigged-character uploads as FBX.
- Humanoid Mixamo exports are front-corrected with a 180-degree forward-axis flip; Blender source scenes and web GLBs keep the authored `-Y` front.
- Do not expose Mixamo exports for non-humanoid assets such as the flower; keep those animations in GLB/Blender source only.
