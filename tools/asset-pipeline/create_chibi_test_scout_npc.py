"""Generated OnTheSpectrum asset generator for Chibi Test Scout NPC.

This file is intentionally thin: the embedded AssetSpec selects a reusable
pipeline under tools/asset-pipeline/pipelines/.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

ASSET_SPEC = json.loads("{\n  \"slug\": \"chibi-test-scout-npc\",\n  \"assetFamily\": \"character\",\n  \"pipelineId\": \"character.chibi_mascot\",\n  \"name\": \"Chibi Test Scout NPC\",\n  \"subject\": \"Compact stylized scout non-player character for pipeline QA\",\n  \"visualStyle\": \"Stylized chibi, small web-friendly game asset with clean readable shapes and teal/amber scout colors\",\n  \"requiredParts\": [\n    \"chibi body\",\n    \"head\",\n    \"ponytail hair\",\n    \"hooded outfit\",\n    \"satchel accessory\",\n    \"hands\",\n    \"feet\",\n    \"simple facial features\"\n  ],\n  \"materialPalette\": [\n    \"teal fabric\",\n    \"amber accents\",\n    \"warm skin\",\n    \"dark neutral boots and belt\",\n    \"brown satchel\"\n  ],\n  \"styleConfig\": {\n    \"preset\": \"custom\",\n    \"colors\": {\n      \"primary\": \"#168C8C\",\n      \"secondary\": \"#F2A23A\",\n      \"accent\": \"#C07A2C\",\n      \"neutral\": \"#3A3330\",\n      \"emission\": \"#000000\"\n    }\n  },\n  \"rigTarget\": \"humanoid Mixamo best-effort\",\n  \"animationClips\": [\n    {\n      \"name\": \"Idle_Stationary\",\n      \"label\": \"Idle Stationary\"\n    },\n    {\n      \"name\": \"Walk_InPlace\",\n      \"label\": \"Walk In Place\"\n    },\n    {\n      \"name\": \"Wave_Greeting\",\n      \"label\": \"Wave Greeting\"\n    }\n  ],\n  \"rigPlan\": {\n    \"preset\": \"humanoid Mixamo best-effort\",\n    \"exportMixamo\": true,\n    \"controls\": [\n      \"humanoid root\",\n      \"hips\",\n      \"spine\",\n      \"head\",\n      \"arms\",\n      \"hands\",\n      \"legs\",\n      \"feet\",\n      \"ponytail helper control\"\n    ]\n  },\n  \"viewerFraming\": \"Centered full-body front three-quarter view with compact chibi proportions and satchel visible\",\n  \"budget\": {\n    \"maxTriangles\": 12000,\n    \"maxMaterials\": 4,\n    \"maxGlbMb\": 4,\n    \"approvedOverBudget\": false\n  },\n  \"vfx\": null,\n  \"character\": {\n    \"silhouette\": \"compact chibi scout with oversized head, small body, hood framing the face, side-visible satchel, and ponytail silhouette\",\n    \"hairType\": \"ponytail\",\n    \"hairColor\": \"#3A3330\",\n    \"bodyType\": \"chibi\",\n    \"skinTone\": \"#C98F68\",\n    \"outfit\": \"hooded scout outfit with tunic, short cloak or hood panel, belt, boots, and satchel\",\n    \"outfitStyle\": \"stylized adventure scout with teal main fabric and amber trim\",\n    \"accessories\": [\n      \"satchel\"\n    ]\n  },\n  \"furniture\": null,\n  \"plant\": null,\n  \"prop\": null\n}")

from pipelines import run_asset_pipeline  # noqa: E402


def main() -> dict:
    return run_asset_pipeline(ASSET_SPEC)


if __name__ == "__main__":
    print(json.dumps(main(), indent=2))
