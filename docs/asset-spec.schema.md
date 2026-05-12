# Asset Spec Schema

Use this contract for future generated assets.

```json
{
  "slug": "on_the_spectrum-painter-chibi",
  "name": "OnTheSpectrum Painter Chibi",
  "assetFamily": "character",
  "pipelineId": "character.chibi_mascot",
  "subject": "original anime chibi painter mascot",
  "visualStyle": "stylized readable game asset",
  "requiredParts": ["head", "hair", "eyes", "outfit", "props", "base", "armature"],
  "materialPalette": ["teal cloth", "ivory apron", "coral trim"],
  "styleConfig": {
    "preset": "studio teal",
    "colors": {
      "primary": "#5f95b8",
      "secondary": "#d96f52",
      "accent": "#2ed7e6",
      "neutral": "#22272b",
      "emission": "#45f0ff"
    }
  },
  "rigTarget": "humanoid Mixamo best-effort",
  "rigPlan": {
    "preset": "humanoid Mixamo best-effort",
    "exportMixamo": true,
    "controls": ["root", "pelvis", "spine", "head", "hands", "feet"]
  },
  "animationClips": [
    { "name": "Idle_Stationary", "label": "Idle" },
    { "name": "Walk_InPlace", "label": "Walk" }
  ],
  "character": {
    "silhouette": "compact chibi humanoid",
    "hairType": "short",
    "hairColor": "#22272b",
    "bodyType": "chibi",
    "skinTone": "#d9a77f",
    "outfit": "teal jacket and ivory apron",
    "outfitStyle": "stylized studio painter",
    "accessories": ["satchel", "stylus-brush"]
  },
  "furniture": null,
  "plant": null,
  "prop": null,
  "vfx": null,
  "budget": {
    "maxTriangles": 100000,
    "maxMaterials": 16,
    "maxGlbMb": 12,
    "approvedOverBudget": false
  },
  "viewerFraming": "Centered front-quarter viewer framing"
}
```
