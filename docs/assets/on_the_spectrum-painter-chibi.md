# OnTheSpectrum Painter Chibi

## Brief

Create an original anime chibi studio mascot for OnTheSpectrum. The character is a small painter/maker companion with a large rounded head, expressive eyes, ink-violet hair with a cyan streak, teal jacket, ivory apron, coral trim, satchel, boots, stylus-brush prop, and a compact display base.

## Required Outputs

- `public/models/on_the_spectrum-painter-chibi.blend`
- `public/models/on_the_spectrum-painter-chibi.glb`
- `public/models/on_the_spectrum-painter-chibi.metadata.json`
- `public/renders/on_the_spectrum-painter-chibi-preview.png`

## Rig Target

Basic armature only. Include named bones and whole-part vertex groups so future iterations can animate or replace parts. Do not treat the v1 rig as a polished control rig.

## Baked Effects

- Geometry eye layers, catchlights, blush ovals, cloth shadow bands, cyan hair streak, paint-glow droplet, and contact shadow.
- GLB-compatible materials only. Avoid compositor-only effects.

## Acceptance Criteria

- Source `.blend`, exported `.glb`, preview render, and metadata exist.
- GLB stays below warning budgets.
- Viewer loads the model front-facing with auto-spin off.
- Inspector shows runtime and authored metadata.
- Desktop and mobile layouts are unclipped and usable.
