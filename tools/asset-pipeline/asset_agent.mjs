import { spawnSync } from "node:child_process";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";
import { probeBlenderMcp, runGeneratorViaMcp } from "./blender_mcp_client.mjs";
import {
  assetFamilies,
  assetSpecJsonSchema,
  defaultPipelineForFamily,
  pipelineCatalog,
  pipelineIds,
  rigTargets,
} from "./asset_spec_schema.mjs";

const repoRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../..");
const generatedRegistryPath = path.join(repoRoot, "src", "assets", "generatedAssetRegistry.json");
const generatedSpecDir = path.join(repoRoot, "tools", "asset-pipeline", "generated_specs");
const defaultBudget = { maxTriangles: 100000, maxMaterials: 16, maxGlbMb: 12, approvedOverBudget: false };

function parseArgs(argv) {
  const args = {};
  for (let index = 0; index < argv.length; index += 1) {
    const item = argv[index];
    if (!item.startsWith("--")) continue;
    const key = item.slice(2);
    const next = argv[index + 1];
    if (!next || next.startsWith("--")) {
      args[key] = true;
    } else {
      args[key] = next;
      index += 1;
    }
  }
  return args;
}

function loadDotEnv(filePath = path.join(repoRoot, ".env")) {
  if (!fs.existsSync(filePath)) return;
  const text = fs.readFileSync(filePath, "utf8");
  for (const rawLine of text.split(/\r?\n/)) {
    const line = rawLine.trim();
    if (!line || line.startsWith("#")) continue;
    const match = line.match(/^([^=]+)=(.*)$/);
    if (!match) continue;
    const key = match[1].trim();
    let value = match[2].trim();
    if ((value.startsWith('"') && value.endsWith('"')) || (value.startsWith("'") && value.endsWith("'"))) {
      value = value.slice(1, -1);
    }
    if (!process.env[key]) process.env[key] = value;
  }
}

function slugify(value) {
  return String(value || "asset")
    .toLowerCase()
    .replace(/['"]/g, "")
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/(^-|-$)/g, "")
    .slice(0, 64) || "asset";
}

function toTitle(value) {
  return String(value || "Generated Asset")
    .replace(/[-_]+/g, " ")
    .replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function asList(value, fallback = []) {
  if (Array.isArray(value)) return value.map((item) => String(item).trim()).filter(Boolean);
  if (typeof value === "string") {
    const items = value
      .split(/\n|,/)
      .map((item) => item.trim())
      .filter(Boolean);
    return items.length ? items : fallback;
  }
  return fallback;
}

function normalizeClips(clips, pipelineId, assetFamily) {
  const provided = Array.isArray(clips)
    ? clips
        .map((clip) => ({
          name: String(clip?.name || "").replace(/[^A-Za-z0-9_]/g, "_"),
          label: String(clip?.label || clip?.name || "").trim(),
        }))
        .filter((clip) => clip.name && clip.label)
    : [];
  if (provided.length) return provided;
  if (assetFamily === "furniture" || assetFamily === "prop") return [];
  return pipelineCatalog[pipelineId]?.defaultClips ?? [];
}

function normalizeSpec(rawSpec, sourceBrief = "") {
  const name = String(rawSpec.name || rawSpec.subject || "Generated Asset").trim();
  const assetFamily = String(rawSpec.assetFamily || rawSpec.family || "prop").toLowerCase();
  const normalizedFamily = assetFamilies.includes(assetFamily) ? assetFamily : "prop";
  const pipelineId = rawSpec.pipelineId || defaultPipelineForFamily(normalizedFamily, sourceBrief);
  const rigTarget = rigTargets.includes(rawSpec.rigTarget)
    ? rawSpec.rigTarget
    : pipelineCatalog[pipelineId]?.defaultRig ?? "none";
  const requiredParts = asList(rawSpec.requiredParts, ["primary silhouette", "detail accents", "display base"]);
  const materialPalette = asList(rawSpec.materialPalette, ["matte main color", "secondary accent", "soft contact shadow"]);
  return {
    slug: slugify(rawSpec.slug || name),
    assetFamily: normalizedFamily,
    pipelineId,
    name,
    subject: String(rawSpec.subject || name).trim(),
    visualStyle: String(rawSpec.visualStyle || rawSpec.style || "Stylized Artomata procedural asset").trim(),
    requiredParts,
    materialPalette,
    rigTarget,
    animationClips: normalizeClips(rawSpec.animationClips, pipelineId, normalizedFamily),
    viewerFraming: String(rawSpec.viewerFraming || "Centered front-quarter viewer framing").trim(),
    budget: {
      ...defaultBudget,
      ...(rawSpec.budget && typeof rawSpec.budget === "object" ? rawSpec.budget : {}),
    },
    vfx: rawSpec.vfx ?? null,
    character: rawSpec.character ?? null,
    furniture: rawSpec.furniture ?? null,
    plant: rawSpec.plant ?? null,
    prop: rawSpec.prop ?? null,
  };
}

function validateSpec(spec) {
  const errors = [];
  if (!/^[a-z0-9]+(?:-[a-z0-9]+)*$/.test(spec.slug)) errors.push("slug must be lowercase kebab-case");
  if (!assetFamilies.includes(spec.assetFamily)) errors.push(`assetFamily must be one of: ${assetFamilies.join(", ")}`);
  if (!pipelineIds.includes(spec.pipelineId)) errors.push(`pipelineId must be one of: ${pipelineIds.join(", ")}`);
  const pipeline = pipelineCatalog[spec.pipelineId];
  if (pipeline && pipeline.family !== spec.assetFamily) {
    errors.push(`pipelineId ${spec.pipelineId} is for ${pipeline.family}, not ${spec.assetFamily}`);
  }
  if (!spec.name) errors.push("name is required");
  if (!spec.subject) errors.push("subject is required");
  if (!spec.visualStyle) errors.push("visualStyle is required");
  if (!spec.requiredParts.length) errors.push("requiredParts must include at least one part");
  if (!spec.materialPalette.length) errors.push("materialPalette must include at least one material/color");
  if (!rigTargets.includes(spec.rigTarget)) errors.push(`rigTarget must be one of: ${rigTargets.join(", ")}`);
  if (spec.assetFamily === "vfx" && !spec.vfx) errors.push("vfx details are required for VFX assets");
  if (spec.budget.maxTriangles > 100000 && !spec.budget.approvedOverBudget) {
    errors.push("maxTriangles exceeds 100000 without approvedOverBudget");
  }
  if (spec.budget.maxMaterials > 16 && !spec.budget.approvedOverBudget) {
    errors.push("maxMaterials exceeds 16 without approvedOverBudget");
  }
  if (spec.budget.maxGlbMb > 12 && !spec.budget.approvedOverBudget) {
    errors.push("maxGlbMb exceeds 12 without approvedOverBudget");
  }
  if (errors.length) throw new Error(`Invalid AssetSpec:\n- ${errors.join("\n- ")}`);
}

function extractResponseText(responseJson) {
  if (typeof responseJson.output_text === "string") return responseJson.output_text;
  const chunks = [];
  for (const item of responseJson.output || []) {
    for (const content of item.content || []) {
      if (content.type === "output_text" && typeof content.text === "string") chunks.push(content.text);
      if (content.type === "refusal") throw new Error(`OpenAI refused the brief: ${content.refusal}`);
    }
  }
  return chunks.join("");
}

async function specFromOpenAI({ brief, family }) {
  const apiKey = process.env.OPENAI_API_KEY || process.env["OPENAI-KEY"];
  if (!apiKey) throw new Error("Missing OPENAI_API_KEY in .env. OPENAI-KEY is also supported for local compatibility.");
  const model = process.env.OPENAI_MODEL || "gpt-5.5";
  const requestBody = {
    model,
    input: [
      {
        role: "system",
        content:
          "You normalize Artomata Blender asset briefs into one strict AssetSpec. Select only an allowed pipelineId. Do not invent file paths. Keep budgets at or below warning limits unless explicitly approved.",
      },
      {
        role: "user",
        content: `Requested family: ${family || "unspecified"}\n\nAsset brief:\n${brief}`,
      },
    ],
    text: {
      format: {
        type: "json_schema",
        name: "artomata_asset_spec",
        strict: true,
        schema: assetSpecJsonSchema,
      },
    },
  };
  if (/^gpt-5/i.test(model)) {
    requestBody.reasoning = { effort: process.env.OPENAI_REASONING_EFFORT || "low" };
  }
  const response = await fetch("https://api.openai.com/v1/responses", {
    method: "POST",
    headers: {
      Authorization: `Bearer ${apiKey}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify(requestBody),
  });
  const body = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(`OpenAI request failed (${response.status}): ${JSON.stringify(body)}`);
  const outputText = extractResponseText(body);
  if (!outputText) throw new Error("OpenAI response did not include output_text JSON.");
  return JSON.parse(outputText);
}

function ensureGeneratedDirs() {
  fs.mkdirSync(path.join(repoRoot, "tools", "asset-pipeline"), { recursive: true });
  fs.mkdirSync(generatedSpecDir, { recursive: true });
}

function writeSpecAndGenerator(spec) {
  ensureGeneratedDirs();
  const specPath = path.join(generatedSpecDir, `${spec.slug}.json`);
  const generatorPath = path.join(repoRoot, "tools", "asset-pipeline", `create_${spec.slug.replace(/-/g, "_")}.py`);
  const specJson = JSON.stringify(spec, null, 2);
  const pythonJsonLiteral = JSON.stringify(specJson);
  const script = `"""Generated Artomata asset generator for ${spec.name}.

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

ASSET_SPEC = json.loads(${pythonJsonLiteral})

from pipelines import run_asset_pipeline  # noqa: E402


def main() -> dict:
    return run_asset_pipeline(ASSET_SPEC)


if __name__ == "__main__":
    print(json.dumps(main(), indent=2))
`;
  fs.writeFileSync(specPath, `${specJson}\n`, "utf8");
  fs.writeFileSync(generatorPath, script, "utf8");
  return { specPath, generatorPath };
}

function runCommand(command, args, options = {}) {
  const executable = process.platform === "win32" && command === "npm" ? process.execPath : command;
  const finalArgs = process.platform === "win32" && command === "npm"
    ? [path.join(path.dirname(process.execPath), "node_modules", "npm", "bin", "npm-cli.js"), ...args]
    : args;
  const result = spawnSync(executable, finalArgs, {
    cwd: repoRoot,
    encoding: "utf8",
    shell: false,
    ...options,
  });
  return {
    status: result.status ?? 1,
    stdout: result.stdout || "",
    stderr: result.stderr || result.error?.message || "",
  };
}

function runPreflight() {
  const result = runCommand("npm", ["run", "asset:preflight"]);
  const output = `${result.stdout}\n${result.stderr}`.trim();
  let report = null;
  const jsonStart = output.indexOf("{");
  if (jsonStart >= 0) {
    try {
      report = JSON.parse(output.slice(jsonStart));
    } catch {
      report = null;
    }
  }
  return { ...result, output, report };
}

function hasBackgroundBlender(report) {
  return Boolean(report?.background_blender?.BLENDER_PATH || report?.background_blender?.blender_on_path);
}

function validateGeneratedFiles(spec) {
  const glbPath = path.join(repoRoot, "public", "models", `${spec.slug}.glb`);
  const metadataPath = path.join(repoRoot, "public", "models", `${spec.slug}.metadata.json`);
  const previewPath = path.join(repoRoot, "public", "renders", `${spec.slug}-preview.png`);
  for (const filePath of [glbPath, metadataPath, previewPath]) {
    if (!fs.existsSync(filePath)) throw new Error(`Expected generated file is missing: ${path.relative(repoRoot, filePath)}`);
  }
  const inspect = runCommand("node", ["tools/asset-pipeline/inspect_glb.mjs", `public/models/${spec.slug}.glb`]);
  if (inspect.status !== 0) throw new Error(`inspect_glb failed:\n${inspect.stdout}\n${inspect.stderr}`);
  const budget = runCommand("node", ["tools/asset-pipeline/validate_glb_budget.mjs", `public/models/${spec.slug}.glb`]);
  if (budget.status !== 0) throw new Error(`validate_glb_budget failed:\n${budget.stdout}\n${budget.stderr}`);
  return {
    inspect: JSON.parse(inspect.stdout),
    budget: JSON.parse(budget.stdout),
    metadata: JSON.parse(fs.readFileSync(metadataPath, "utf8")),
  };
}

function displayFamily(family) {
  if (family === "vfx") return "VFX";
  if (family === "plant") return "Botanical";
  return family.charAt(0).toUpperCase() + family.slice(1);
}

function defaultCameraForFamily(family) {
  if (family === "furniture") {
    return {
      desktop: { position: [1.9, 0.9, 3.1], target: [0, 0.55, 0] },
      mobile: { position: [0.95, 0.82, 3.8], target: [0, 0.55, 0] },
      focus: { position: [1.1, 0.78, 2.0], target: [0, 0.62, 0] },
    };
  }
  if (family === "vfx") {
    return {
      desktop: { position: [2.35, 1.38, 5.0], target: [0, 1.18, 0] },
      mobile: { position: [1.08, 1.28, 6.05], target: [0, 1.2, 0] },
      focus: { position: [1.18, 1.32, 3.2], target: [0, 1.2, 0] },
    };
  }
  return {
    desktop: { position: [2.0, 1.45, 6.2], target: [0, 1.35, 0] },
    mobile: { position: [1.05, 1.25, 6.8], target: [0, 1.45, 0] },
    focus: { position: [1.0, 1.85, 4.05], target: [0, 1.95, 0] },
  };
}

function registryEntryFromMetadata(spec, validation) {
  const metadata = validation.metadata;
  const clips = spec.animationClips || [];
  const exports = [
    {
      id: "web-glb",
      label: "Web GLB",
      detail: clips.length ? "Animated viewer file" : "Static viewer file",
      href: `/models/${spec.slug}.glb`,
      downloadName: `${spec.slug}.glb`,
    },
  ];
  const mixamoDir = path.join(repoRoot, "public", "exports", spec.slug);
  const mixamoFbx = path.join(mixamoDir, `${spec.slug}-mixamo.fbx`);
  const mixamoObjZip = path.join(mixamoDir, `${spec.slug}-mixamo-obj.zip`);
  if (fs.existsSync(mixamoFbx)) {
    exports.push({
      id: "mixamo-fbx",
      label: "Mixamo FBX",
      detail: "Best-effort rigged upload",
      href: `/exports/${spec.slug}/${spec.slug}-mixamo.fbx`,
      downloadName: `${spec.slug}-mixamo.fbx`,
    });
  }
  if (fs.existsSync(mixamoObjZip)) {
    exports.push({
      id: "mixamo-obj-zip",
      label: "OBJ ZIP",
      detail: "Unrigged Mixamo fallback",
      href: `/exports/${spec.slug}/${spec.slug}-mixamo-obj.zip`,
      downloadName: `${spec.slug}-mixamo-obj.zip`,
    });
  }
  exports.push({
    id: "blend",
    label: "Blender source",
    detail: clips.length ? "Animated source scene" : "Static source scene",
    href: `/models/${spec.slug}.blend`,
    downloadName: `${spec.slug}.blend`,
  });
  return {
    id: spec.slug,
    name: spec.name,
    shortName: spec.name,
    description: `${spec.visualStyle} ${spec.subject}, generated procedurally in Blender.`,
    modelUrl: `/models/${spec.slug}.glb`,
    blendUrl: `/models/${spec.slug}.blend`,
    previewUrl: `/renders/${spec.slug}-preview.png`,
    metadataUrl: `/models/${spec.slug}.metadata.json`,
    downloadName: `${spec.slug}.glb`,
    blendDownloadName: `${spec.slug}.blend`,
    snapshotName: `${spec.slug}-snapshot.png`,
    sourceLabel: "Artomata asset agent",
    defaultAnimation: metadata.animations?.default ?? clips[0]?.name ?? "",
    animationClips: clips,
    exports,
    placement: metadata.viewer?.placement ?? { mode: "floor-y", offset: [0, 0, 0] },
    initialTransform: metadata.viewer?.initialTransform ?? { rotation: [0, -0.22, 0], scale: 1 },
    camera: metadata.viewer?.camera ?? defaultCameraForFamily(spec.assetFamily),
    authored: {
      family: displayFamily(spec.assetFamily),
      target: metadata.authored?.target ?? `${displayFamily(spec.assetFamily)} asset-generation showcase`,
      rig: metadata.rig?.type ?? spec.rigTarget,
      effects: metadata.authored?.effects ?? [...spec.requiredParts, ...spec.materialPalette].join(", "),
      sourceScene: `public/models/${spec.slug}.blend`,
      preview: `public/renders/${spec.slug}-preview.png`,
    },
    metadataFallback: {
      counts: metadata.counts,
      bounds: metadata.bounds,
      file_sizes: metadata.file_sizes,
    },
  };
}

function appendGeneratedRegistry(entry) {
  const registry = fs.existsSync(generatedRegistryPath)
    ? JSON.parse(fs.readFileSync(generatedRegistryPath, "utf8"))
    : [];
  const nextRegistry = [...registry.filter((item) => item.id !== entry.id), entry].sort((a, b) =>
    a.name.localeCompare(b.name),
  );
  fs.writeFileSync(generatedRegistryPath, `${JSON.stringify(nextRegistry, null, 2)}\n`, "utf8");
}

function relativeToRepo(filePath) {
  return path.relative(repoRoot, filePath).replace(/\\/g, "/");
}

function getOpenAISettings() {
  loadDotEnv();
  return {
    hasApiKey: Boolean(process.env.OPENAI_API_KEY || process.env["OPENAI-KEY"]),
    model: process.env.OPENAI_MODEL || "gpt-5.5",
    reasoningEffort: process.env.OPENAI_REASONING_EFFORT || "low",
  };
}

function emitProgress(onProgress, update) {
  if (typeof onProgress === "function") onProgress({ at: new Date().toISOString(), ...update });
}

function summarizeValidation(validation) {
  return {
    triangles: validation.budget.triangles,
    materials: validation.budget.materials,
    animations: validation.budget.animationNames,
    warnings: validation.budget.warnings,
    metadataCounts: validation.metadata.counts,
  };
}

function generatedFileSummary(spec) {
  return [
    { id: "blend", label: "Blender source", path: `public/models/${spec.slug}.blend`, href: `/models/${spec.slug}.blend` },
    { id: "glb", label: "Web GLB", path: `public/models/${spec.slug}.glb`, href: `/models/${spec.slug}.glb` },
    { id: "preview", label: "Preview render", path: `public/renders/${spec.slug}-preview.png`, href: `/renders/${spec.slug}-preview.png` },
    { id: "metadata", label: "Metadata", path: `public/models/${spec.slug}.metadata.json`, href: `/models/${spec.slug}.metadata.json` },
  ];
}

async function prepareAssetGenerator({ brief = "", family = "", rawSpec = null, specFile = "", onProgress } = {}) {
  emitProgress(onProgress, {
    step: "normalize",
    status: "running",
    detail: rawSpec || specFile ? "Reading local AssetSpec." : `Calling OpenAI ${getOpenAISettings().model}.`,
  });
  const loadedSpec = specFile ? JSON.parse(fs.readFileSync(path.resolve(repoRoot, specFile), "utf8")) : rawSpec;
  const sourceSpec = loadedSpec || (await specFromOpenAI({ brief, family }));
  const spec = normalizeSpec(sourceSpec, brief);
  validateSpec(spec);
  emitProgress(onProgress, {
    step: "normalize",
    status: "completed",
    detail: `${spec.name} will use ${spec.pipelineId}.`,
    payload: { slug: spec.slug, pipelineId: spec.pipelineId, assetFamily: spec.assetFamily },
  });

  emitProgress(onProgress, { step: "write", status: "running", detail: "Writing AssetSpec and Blender generator." });
  const paths = writeSpecAndGenerator(spec);
  emitProgress(onProgress, {
    step: "write",
    status: "completed",
    detail: relativeToRepo(paths.generatorPath),
    payload: { specPath: relativeToRepo(paths.specPath), generatorPath: relativeToRepo(paths.generatorPath) },
  });
  return { spec, paths };
}

function runBackgroundGeneration(generatorPath) {
  return runCommand("python", [
    "tools/asset-pipeline/run_blender_asset.py",
    "--script",
    relativeToRepo(generatorPath),
  ]);
}

async function generateAsset({ brief = "", family = "", rawSpec = null, specFile = "", dryRun = false, onProgress } = {}) {
  loadDotEnv();
  const { spec, paths } = await prepareAssetGenerator({ brief, family, rawSpec, specFile, onProgress });
  const baseResult = {
    status: "spec_ready",
    slug: spec.slug,
    pipelineId: spec.pipelineId,
    assetFamily: spec.assetFamily,
    spec,
    specPath: relativeToRepo(paths.specPath),
    generatorPath: relativeToRepo(paths.generatorPath),
  };
  if (dryRun) return baseResult;

  emitProgress(onProgress, { step: "preflight", status: "running", detail: "Checking Blender MCP and background Blender." });
  const preflight = runPreflight();
  emitProgress(onProgress, {
    step: "preflight",
    status: preflight.status === 0 ? "completed" : "failed",
    detail: preflight.report?.mcp_bridge?.listening
      ? "Live Blender MCP bridge is available."
      : hasBackgroundBlender(preflight.report)
        ? "Background Blender is available."
        : "No Blender runtime is available.",
    payload: { report: preflight.report, output: preflight.output },
  });
  if (preflight.status !== 0) {
    throw new Error(
      [
        "asset:preflight failed, so generation was skipped.",
        preflight.output,
        "Start Blender MCP on 127.0.0.1:9876 or configure BLENDER_PATH, then retry.",
      ].join("\n\n"),
    );
  }

  let mcpProbe = { ok: false };
  const backgroundAvailable = hasBackgroundBlender(preflight.report);
  if (preflight.report?.mcp_bridge?.listening) {
    emitProgress(onProgress, {
      step: "preflight",
      status: "running",
      detail: "Verifying Blender MCP execute handoff.",
    });
    mcpProbe = await probeBlenderMcp();
    emitProgress(onProgress, {
      step: "preflight",
      status: mcpProbe.ok || backgroundAvailable ? "completed" : "failed",
      detail: mcpProbe.ok
        ? "Live Blender MCP execute handoff verified."
        : backgroundAvailable
          ? `Blender MCP socket is listening but execute failed, using background Blender fallback: ${mcpProbe.error}`
          : `Blender MCP socket is listening but execute failed: ${mcpProbe.error}`,
      payload: { mcpProbe },
    });
    if (!mcpProbe.ok && !backgroundAvailable) {
      throw new Error(
        [
          "Blender MCP is listening, but the execute handoff failed.",
          mcpProbe.error,
          "Restart Blender with the MCP add-on server enabled, or configure BLENDER_PATH for background generation.",
        ].filter(Boolean).join("\n\n"),
      );
    }
  }

  const useMcp = Boolean(preflight.report?.mcp_bridge?.listening && mcpProbe.ok);
  emitProgress(onProgress, {
    step: "generate",
    status: "running",
    detail: useMcp ? "Running generator through Blender MCP." : "Running generator through background Blender.",
  });
  if (useMcp) {
    await runGeneratorViaMcp(paths.generatorPath, repoRoot);
  } else if (backgroundAvailable) {
    const generation = runBackgroundGeneration(paths.generatorPath);
    if (generation.status !== 0) throw new Error(`Blender generation failed:\n${generation.stdout}\n${generation.stderr}`);
  } else {
    throw new Error("No Blender runtime is available. Start Blender MCP or configure BLENDER_PATH.");
  }
  emitProgress(onProgress, {
    step: "generate",
    status: "completed",
    detail: useMcp ? "Blender MCP finished generation." : "Background Blender finished generation.",
  });

  emitProgress(onProgress, { step: "validate", status: "running", detail: "Inspecting GLB and budget." });
  const validation = validateGeneratedFiles(spec);
  emitProgress(onProgress, {
    step: "validate",
    status: "completed",
    detail: `${validation.budget.triangles} triangles, ${validation.budget.materials} materials.`,
    payload: summarizeValidation(validation),
  });

  emitProgress(onProgress, { step: "register", status: "running", detail: "Updating generated asset registry." });
  const registryEntry = registryEntryFromMetadata(spec, validation);
  appendGeneratedRegistry(registryEntry);
  emitProgress(onProgress, {
    step: "register",
    status: "completed",
    detail: "Asset registered for the viewer and world palette.",
    payload: { id: registryEntry.id },
  });

  return {
    ...baseResult,
    status: "asset_generated",
    files: generatedFileSummary(spec),
    validation: summarizeValidation(validation),
    registryEntry,
  };
}

async function main() {
  loadDotEnv();
  const args = parseArgs(process.argv.slice(2));
  const brief = args.brief || "";
  const family = args.family || "";
  if (args.help || (!brief && !args["spec-file"])) {
    console.log(`Usage:
  npm run asset:agent -- --family character --brief "stylized ranger NPC"
  npm run asset:agent -- --spec-file tools/asset-pipeline/generated_specs/my-asset.json

Options:
  --dry-run       Write/validate the AssetSpec and generator script, then stop before preflight.
  --spec-file     Use a local AssetSpec JSON file instead of calling OpenAI.
`);
    return;
  }

  const result = await generateAsset({
    brief,
    family,
    specFile: args["spec-file"] || "",
    dryRun: Boolean(args["dry-run"]),
    onProgress: (event) => {
      console.error(`[${event.step}] ${event.status}: ${event.detail}`);
    },
  });
  console.log(JSON.stringify(result, null, 2));
}

export {
  appendGeneratedRegistry,
  generatedFileSummary,
  generateAsset,
  getOpenAISettings,
  hasBackgroundBlender,
  loadDotEnv,
  normalizeSpec,
  prepareAssetGenerator,
  registryEntryFromMetadata,
  repoRoot,
  runCommand,
  runPreflight,
  specFromOpenAI,
  validateGeneratedFiles,
  validateSpec,
  writeSpecAndGenerator,
};

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  main().catch((error) => {
    console.error(error.message || error);
    process.exit(1);
  });
}
