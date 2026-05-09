"""Generated Artomata asset generator for Codex Smoke Beacon Prop.

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

ASSET_SPEC = json.loads("{\n  \"slug\": \"codex-smoke-beacon-prop\",\n  \"assetFamily\": \"prop\",\n  \"pipelineId\": \"prop.static_or_turntable\",\n  \"name\": \"Codex Smoke Beacon Prop\",\n  \"subject\": \"A compact stylized test beacon prop for validating one-click generation\",\n  \"visualStyle\": \"Stylized Artomata procedural asset with readable silhouette and polished materials\",\n  \"requiredParts\": [\n    \"round primary core\",\n    \"equator band\",\n    \"base cap\",\n    \"small accent nodes\"\n  ],\n  \"materialPalette\": [\n    \"deep teal enamel\",\n    \"warm brass accent\",\n    \"dark graphite base\",\n    \"soft cyan highlight\"\n  ],\n  \"rigTarget\": \"none\",\n  \"animationClips\": [],\n  \"viewerFraming\": \"Centered front-quarter viewer framing with full object visible\",\n  \"budget\": {\n    \"maxTriangles\": 100000,\n    \"maxMaterials\": 16,\n    \"maxGlbMb\": 12,\n    \"approvedOverBudget\": false\n  },\n  \"vfx\": null,\n  \"character\": null,\n  \"furniture\": null,\n  \"plant\": null,\n  \"prop\": {\n    \"category\": \"test beacon\",\n    \"displayMotion\": \"static showcase prop\"\n  }\n}")

from pipelines import run_asset_pipeline  # noqa: E402


def main() -> dict:
    return run_asset_pipeline(ASSET_SPEC)


if __name__ == "__main__":
    print(json.dumps(main(), indent=2))
