# Asset Spec Schema

Use this contract for future generated assets.

```json
{
  "slug": "on_the_spectrum-painter-chibi",
  "name": "OnTheSpectrum Painter Chibi",
  "family": "character",
  "subject": "original anime chibi painter mascot",
  "target": "rig-ready web showcase",
  "seed": "optional deterministic seed",
  "paths": {
    "blend": "public/models/<slug>.blend",
    "glb": "public/models/<slug>.glb",
    "preview": "public/renders/<slug>-preview.png",
    "metadata": "public/models/<slug>.metadata.json"
  },
  "components": ["head", "hair", "eyes", "outfit", "props", "base", "armature"],
  "materials": ["MAT_*"],
  "budget": {
    "triangle_warning": 100000,
    "glb_size_warning_bytes": 12582912,
    "material_warning": 16
  },
  "viewer": {
    "front": "-Y in Blender, tuned in Three.js",
    "auto_spin": false,
    "desktop_camera": [2.1, 1.25, 5.1],
    "mobile_camera": [1.1, 1.05, 6.2],
    "focus_target": [0, 0.0, 2.2]
  },
  "validation": {
    "build": "npm run build",
    "browser": "desktop and mobile",
    "controls": ["mode", "reset", "focus", "spin", "zoom", "download", "snapshot"]
  }
}
```
