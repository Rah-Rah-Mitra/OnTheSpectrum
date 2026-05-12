"""Generated OnTheSpectrum asset generator for Compact Clockwork Reading Chair.

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

ASSET_SPEC = json.loads("{\n  \"slug\": \"compact-clockwork-reading-chair\",\n  \"assetFamily\": \"furniture\",\n  \"pipelineId\": \"furniture.static_or_mechanical\",\n  \"name\": \"Compact Clockwork Reading Chair\",\n  \"subject\": \"Compact clockwork reading chair for pipeline QA with dark walnut frame, teal upholstery, brass accents, and a small tilting back mechanism.\",\n  \"visualStyle\": \"Stylized compact mechanical reading chair with polished clockwork details and QA-friendly clear part separation.\",\n  \"requiredParts\": [\n    \"dark walnut chair frame\",\n    \"teal upholstered seat cushion\",\n    \"teal upholstered back cushion\",\n    \"brass accent trim\",\n    \"visible clockwork details\",\n    \"small tilting back mechanical part\"\n  ],\n  \"materialPalette\": [\n    \"dark walnut wood\",\n    \"teal upholstery fabric\",\n    \"brass metal accents\"\n  ],\n  \"styleConfig\": {\n    \"preset\": \"studio teal\",\n    \"colors\": {\n      \"primary\": \"#0F6F73\",\n      \"secondary\": \"#3A2417\",\n      \"accent\": \"#C49A3A\",\n      \"neutral\": \"#2B2B2B\",\n      \"emission\": \"#000000\"\n    }\n  },\n  \"rigTarget\": \"simple transform rig\",\n  \"animationClips\": [\n    {\n      \"name\": \"Recline_Test\",\n      \"label\": \"Recline_Test transform animation\"\n    }\n  ],\n  \"rigPlan\": {\n    \"preset\": \"simple transform rig\",\n    \"exportMixamo\": false,\n    \"controls\": [\n      \"tilting back transform control\"\n    ]\n  },\n  \"viewerFraming\": \"Compact chair centered in view, three-quarter angle showing upholstery, brass clockwork accents, and tilting back mechanism.\",\n  \"budget\": {\n    \"maxTriangles\": 12000,\n    \"maxMaterials\": 4,\n    \"maxGlbMb\": 8,\n    \"approvedOverBudget\": false\n  },\n  \"vfx\": null,\n  \"character\": null,\n  \"furniture\": {\n    \"category\": \"chair\",\n    \"woodStyle\": \"dark walnut\",\n    \"upholstery\": \"teal upholstery\",\n    \"mechanicalParts\": [\n      \"small tilting back\"\n    ]\n  },\n  \"plant\": null,\n  \"prop\": null\n}")

from pipelines import run_asset_pipeline  # noqa: E402


def main() -> dict:
    return run_asset_pipeline(ASSET_SPEC)


if __name__ == "__main__":
    print(json.dumps(main(), indent=2))
