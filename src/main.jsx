import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { createRoot } from "react-dom/client";
import {
  Box,
  BrickWall,
  Camera,
  ChevronDown,
  CheckCircle2,
  ClipboardCheck,
  Copy,
  Crosshair,
  DoorOpen,
  Download,
  Eraser,
  Film,
  Grid2X2,
  Home,
  LayoutGrid,
  Lightbulb,
  Map as MapIcon,
  Maximize,
  MousePointer2,
  Package,
  Paintbrush,
  Palette,
  Pause,
  Play,
  Plus,
  RefreshCw,
  RotateCcw,
  RotateCw,
  Save,
  ShieldCheck,
  SlidersHorizontal,
  Sparkles,
  StickyNote,
  SunMedium,
  Tags,
  TextCursorInput,
  Trash2,
  Upload,
  WandSparkles,
  ZoomIn,
  ZoomOut,
} from "lucide-react";
import * as THREE from "three";
import { GLTFLoader } from "three/examples/jsm/loaders/GLTFLoader.js";
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls.js";
import { clone as cloneModel } from "three/examples/jsm/utils/SkeletonUtils.js";
import { assetRegistry, defaultAssetId } from "./assets/assetRegistry.js";
import "./styles.css";

const sceneModes = {
  studio: {
    label: "Studio",
    backgroundTop: "#182023",
    backgroundBottom: "#050708",
    key: 3.1,
    fill: 1.25,
    rim: 2.4,
    accent: "#28e0ea",
  },
  toon: {
    label: "Toon",
    backgroundTop: "#222133",
    backgroundBottom: "#07070d",
    key: 3.75,
    fill: 1.7,
    rim: 2.7,
    accent: "#f47d69",
  },
  inspect: {
    label: "Inspect",
    backgroundTop: "#252b2c",
    backgroundBottom: "#0b0f10",
    key: 4.2,
    fill: 2.1,
    rim: 1.7,
    accent: "#e4cf9b",
  },
};

const pageTabs = [
  { id: "generator", page: "generator", hash: "#generator", label: "Asset Generator", Icon: WandSparkles },
  { id: "viewer", page: "viewer", hash: "#viewer", label: "Asset Viewer", Icon: Home },
  { id: "world", page: "world", hash: "#world", label: "World Creator", Icon: LayoutGrid },
  { id: "world-3d", page: "world", hash: "#world-3d", label: "World 3D", Icon: Box },
];

const brushModes = {
  place: { label: "Place", Icon: MousePointer2 },
  erase: { label: "Erase", Icon: Eraser },
  inspect: { label: "Inspect", Icon: SlidersHorizontal },
};

const worldThemes = [
  { id: "studio-atrium", label: "Studio Atrium", mood: "polished indoor set with practical lighting and display zones" },
  { id: "toon-lab", label: "Toon Lab", mood: "bright experimental room for animated characters and prop testing" },
  { id: "garden-room", label: "Garden Room", mood: "soft botanical interior with paths, blooms, and quiet staging pockets" },
  { id: "training-floor", label: "Training Floor", mood: "clear traversal lanes for action character blocking and animation tests" },
];

const assetGeneratorTypes = [
  { id: "character", label: "Character" },
  { id: "furniture", label: "Furniture" },
  { id: "plant", label: "Plant" },
  { id: "prop", label: "Prop" },
  { id: "vfx", label: "VFX" },
];

const vfxFamilies = [
  "aura",
  "portal",
  "fire",
  "smoke",
  "sparks",
  "lightning",
  "energy beam",
  "projectile",
  "impact burst",
  "magic circle",
  "hologram",
  "water splash",
  "wind trail",
  "custom",
];

const emissionSources = ["point", "ring", "object-bound", "ground plane", "character-bound", "free-floating"];
const transparencyStyles = ["additive glow", "alpha-blended smoke", "opaque stylized mesh", "mixed"];

const defaultAssetGeneratorForm = {
  type: "character",
  name: "",
  style: "",
  requiredParts: "",
  materials: "",
  rigging: "humanoid Mixamo best-effort",
  animations: "default",
  animationNotes: "",
  viewerFraming: "",
  freeformBrief: "",
  vfxFamily: "portal",
  motionBehavior: "",
  durationSeconds: "4",
  loopMode: "looping",
  emissionSource: "free-floating",
  transparencyStyle: "additive glow",
  implementationPreference: "GLB-compatible baked mesh/curve animation",
};

function slugifyForAsset(value) {
  return (
    String(value || "generated-asset")
      .toLowerCase()
      .replace(/['"]/g, "")
      .replace(/[^a-z0-9]+/g, "-")
      .replace(/(^-|-$)/g, "")
      .slice(0, 64) || "generated-asset"
  );
}

function splitFormList(value, fallback) {
  const items = String(value || "")
    .split(/\n|,/)
    .map((item) => item.trim())
    .filter(Boolean);
  return items.length ? items : fallback;
}

function toClipName(value, prefix = "") {
  const base = String(value || "Default")
    .replace(/[^A-Za-z0-9]+/g, "_")
    .replace(/(^_|_$)/g, "");
  const clipped = base || "Default";
  return `${prefix}${clipped.charAt(0).toUpperCase()}${clipped.slice(1)}`;
}

function getGeneratorPipeline(form) {
  if (form.type === "character") {
    return /chibi|mascot/i.test(`${form.name} ${form.style}`) ? "character.chibi_mascot" : "character.humanoid_basic";
  }
  if (form.type === "furniture") return "furniture.static_or_mechanical";
  if (form.type === "plant") return "plant.swaying_botanical";
  if (form.type === "vfx") return "vfx.baked_mesh_curve";
  return "prop.static_or_turntable";
}

function buildGeneratorClips(form) {
  if (form.animations === "none") return [];
  if (form.animations === "specific") {
    return splitFormList(form.animationNotes, []).map((clip) => ({
      name: toClipName(clip),
      label: clip.replace(/[_-]+/g, " "),
    }));
  }
  if (form.type === "character") {
    return [
      { name: "Idle_Stationary", label: "Idle" },
      { name: "Walk_InPlace", label: "Walk" },
    ];
  }
  if (form.type === "plant") return [{ name: "Sway_Gentle", label: "Sway" }];
  if (form.type === "vfx") return [{ name: toClipName(form.vfxFamily, "Loop_"), label: "Loop" }];
  return [];
}

function buildGeneratorSpec(form) {
  const name = form.name.trim() || `${assetGeneratorTypes.find((item) => item.id === form.type)?.label ?? "Asset"} Concept`;
  const requiredParts = splitFormList(form.requiredParts, ["primary silhouette", "detail accents", "display base"]);
  const materialPalette = splitFormList(form.materials, ["matte primary color", "secondary accent", "soft contact shadow"]);
  const animationClips = buildGeneratorClips(form);
  const baseSpec = {
    slug: slugifyForAsset(name),
    assetFamily: form.type,
    pipelineId: getGeneratorPipeline(form),
    name,
    subject: name,
    visualStyle: form.style.trim() || "Stylized Artomata procedural asset",
    requiredParts,
    materialPalette,
    rigTarget:
      form.type === "vfx"
        ? "simple transform rig"
        : form.type === "plant"
          ? "simple transform rig"
          : form.rigging,
    animationClips,
    viewerFraming: form.viewerFraming.trim() || "Centered front-quarter viewer framing",
    budget: {
      maxTriangles: 100000,
      maxMaterials: 16,
      maxGlbMb: 12,
      approvedOverBudget: false,
    },
    vfx: null,
    character: null,
    furniture: null,
    plant: null,
    prop: null,
  };
  if (form.type === "vfx") {
    baseSpec.vfx = {
      family: form.vfxFamily,
      motionBehavior: form.motionBehavior.trim() || "Looping transform motion with baked mesh accents",
      durationSeconds: Number(form.durationSeconds) || 4,
      loop: form.loopMode === "looping",
      emissionSource: form.emissionSource,
      transparencyStyle: form.transparencyStyle,
      implementationPreference: form.implementationPreference,
    };
  }
  if (form.type === "character") {
    baseSpec.character = {
      silhouette: form.style.trim() || "stylized readable humanoid",
      outfit: requiredParts.join(", "),
      accessories: requiredParts.slice(0, 4),
    };
  }
  if (form.type === "furniture") {
    baseSpec.furniture = { category: name, mechanicalParts: animationClips.length ? requiredParts.slice(0, 3) : [] };
  }
  if (form.type === "plant") {
    baseSpec.plant = { botanicalType: name, swayIntensity: animationClips.length ? "gentle" : "none" };
  }
  if (form.type === "prop") {
    baseSpec.prop = { category: name, displayMotion: animationClips.length ? animationClips[0].name : "none" };
  }
  return baseSpec;
}

function buildAssetGenerationBrief(form, spec) {
  const lines = [
    `Type: ${form.type === "vfx" ? "VFX" : form.type}`,
    form.type === "vfx" ? `VFX family: ${form.vfxFamily}` : null,
    `Name: ${spec.name}`,
    `Style: ${spec.visualStyle}`,
    `Required parts: ${spec.requiredParts.join(", ")}`,
    `Materials/colors: ${spec.materialPalette.join(", ")}`,
    `Rigging: ${spec.rigTarget}`,
    `Animations: ${spec.animationClips.length ? spec.animationClips.map((clip) => clip.name).join(", ") : "none"}`,
    form.type === "vfx" ? `Motion behavior: ${spec.vfx.motionBehavior}` : null,
    form.type === "vfx" ? `Duration and loop: ${spec.vfx.loop ? "looping" : "one-shot"}, ${spec.vfx.durationSeconds} seconds` : null,
    form.type === "vfx" ? `Emission source: ${spec.vfx.emissionSource}` : null,
    form.type === "vfx" ? `Transparency style: ${spec.vfx.transparencyStyle}` : null,
    form.type === "vfx" ? `Implementation preference: ${spec.vfx.implementationPreference}` : null,
    `Viewer framing notes: ${spec.viewerFraming}`,
    "Performance budget: keep under 100k triangles, 16 materials, 12 MB GLB unless explicitly approved",
  ].filter(Boolean);
  return [form.freeformBrief.trim(), lines.join("\n")].filter(Boolean).join("\n\n");
}

function quoteForPowerShell(value) {
  return `'${String(value).replace(/'/g, "''")}'`;
}

function buildAssetAgentCommand(form, brief) {
  return `npm run asset:agent -- --family ${form.type} --brief ${quoteForPowerShell(brief)}`;
}

function getAssetApiBase() {
  return import.meta.env.VITE_ASSET_API_BASE || `${window.location.protocol}//${window.location.hostname || "127.0.0.1"}:5174`;
}

async function assetApiRequest(path, options = {}) {
  const response = await fetch(`${getAssetApiBase()}${path}`, {
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    ...options,
  });
  const body = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(body.error || `Asset API request failed with status ${response.status}`);
  return body;
}

const generatorStepLabels = {
  queue: "Queue request",
  normalize: "Normalize spec",
  write: "Write generator",
  preflight: "Blender preflight",
  generate: "Generate in Blender",
  validate: "Validate GLB",
  register: "Register asset",
};

function isGeneratorJobActive(job) {
  return job?.status === "queued" || job?.status === "running";
}

function getBlenderStatusLabel(blender) {
  if (!blender) return "Checking local Blender runtime";
  if (blender.mcpBridge?.executable) return "Blender MCP ready";
  if (blender.mcpBridge?.listening) return "Blender MCP needs restart";
  if (blender.backgroundAvailable) return "Background Blender ready";
  return "Blender setup needed";
}

function getPublicHref(file) {
  if (file?.href) return file.href;
  const normalized = String(file?.path || "").replace(/\\/g, "/");
  return normalized.startsWith("public/") ? normalized.slice("public".length) : normalized;
}

function validateGeneratorSpec(spec) {
  return [
    { ok: Boolean(spec.name.trim()), label: "Name", detail: spec.name.trim() ? "Ready" : "Add an asset name." },
    {
      ok: spec.requiredParts.length > 0,
      label: "Parts",
      detail: spec.requiredParts.length ? `${spec.requiredParts.length} part(s)` : "Add at least one required part.",
    },
    {
      ok: spec.materialPalette.length > 0,
      label: "Materials",
      detail: spec.materialPalette.length ? `${spec.materialPalette.length} material note(s)` : "Add material or color notes.",
    },
    { ok: Boolean(spec.pipelineId), label: "Pipeline", detail: spec.pipelineId },
    {
      ok: spec.budget.maxTriangles <= 100000 && spec.budget.maxMaterials <= 16 && spec.budget.maxGlbMb <= 12,
      label: "Budget",
      detail: "100k triangles, 16 materials, 12 MB",
    },
    { ok: true, label: "Secrets", detail: "OpenAI runs only in the local CLI." },
  ];
}

const structurePalette = [
  {
    id: "floor",
    label: "Floor",
    family: "Structure",
    className: "floor",
    color: "#2e4241",
    Icon: Grid2X2,
    agentHint: "walkable tile",
  },
  {
    id: "wall",
    label: "Wall",
    family: "Structure",
    className: "wall",
    color: "#e4cf9b",
    Icon: BrickWall,
    agentHint: "blocking boundary wall",
  },
  {
    id: "door",
    label: "Door",
    family: "Structure",
    className: "door",
    color: "#f47d69",
    Icon: DoorOpen,
    agentHint: "entry or transition point",
  },
  {
    id: "light",
    label: "Light",
    family: "Utility",
    className: "light",
    color: "#28e0ea",
    Icon: Lightbulb,
    agentHint: "motivated scene light",
  },
  {
    id: "spawn",
    label: "Spawn",
    family: "Utility",
    className: "spawn",
    color: "#91f0a8",
    Icon: Sparkles,
    agentHint: "default character start point",
  },
];

const defaultWorldMeta = {
  name: "Painter Atelier Grid",
  theme: "studio-atrium",
  columns: 10,
  rows: 8,
  cellSize: "1m",
  rules: "Keep at least one door or spawn, keep characters reachable, and use walls only where they clarify room boundaries.",
};

const defaultWorldGenerationPrompt =
  "Create a compact playable forge training yard. Use a 12 x 9 grid with boundary walls, one spawn tile layered with a non-enemy character, one door, readable combat lanes, two enemies, cover walls, three lights, and a few workshop props. Keep all itemIds from the provided palette and add short tags/notes that explain placement intent.";

const worldLibrarySchemaVersion = "artomata.world-library.v1";
const worldLibraryStorageKey = worldLibrarySchemaVersion;
const worldSeedVersion = 1;
const seedWorldIds = {
  atelier: "seed-atelier-nexus",
  garden: "seed-garden-circuit",
  market: "seed-market-concourse",
  forge: "seed-forge-yard",
  rift: "seed-rift-arena",
};
const seedDoorRotations = {
  north: 180,
  south: 0,
  east: 90,
  west: 270,
};

function getCellKey(x, y) {
  return `${x}:${y}`;
}

const worldCellLayers = {
  structure: "structure",
  occupant: "occupant",
};

const combatRoles = [
  { id: "neutral", label: "Neutral" },
  { id: "player", label: "Player" },
  { id: "enemy-melee", label: "Enemy Melee" },
  { id: "enemy-ranged", label: "Enemy Ranged" },
];

const combatRoleLabels = Object.fromEntries(combatRoles.map((role) => [role.id, role.label]));

const combatStatFields = [
  { id: "maxHealth", label: "Health", min: 1, max: 999, step: 1 },
  { id: "damage", label: "Damage", min: 0, max: 250, step: 1 },
  { id: "range", label: "Range", min: 0.2, max: 12, step: 0.1 },
  { id: "moveSpeed", label: "Speed", min: 0.2, max: 8, step: 0.05 },
  { id: "cooldown", label: "Cooldown", min: 0.1, max: 10, step: 0.05 },
];

function clampGridValue(value, min, max) {
  const parsed = Number(value);
  if (!Number.isFinite(parsed)) return min;
  return Math.min(max, Math.max(min, Math.round(parsed)));
}

function findStructure(id) {
  return structurePalette.find((item) => item.id === id) ?? structurePalette[0];
}

function findAsset(id) {
  return assetRegistry.find((item) => item.id === id) ?? assetRegistry[0];
}

function isCharacterAsset(asset) {
  return asset?.authored?.family === "Character";
}

function isEnemyRole(role) {
  return role === "enemy-melee" || role === "enemy-ranged";
}

function getPaletteLayer(paletteItem) {
  return paletteItem?.type === "asset" ? worldCellLayers.occupant : worldCellLayers.structure;
}

function createLayeredCell(x, y, layers = {}) {
  return {
    id: `cell-${x}-${y}`,
    x,
    y,
    structure: layers.structure ?? null,
    occupant: layers.occupant ?? null,
  };
}

function getCellPlacements(cell) {
  if (!cell) return [];
  if (cell.type) return [cell];
  return [cell.structure, cell.occupant].filter(Boolean);
}

function getPrimaryCellPlacement(cell) {
  if (!cell) return null;
  if (cell.type) return cell;
  return cell.occupant ?? cell.structure ?? null;
}

function getSelectedCellPlacement(cell, paletteItem, brushMode) {
  if (!cell) return null;
  if (cell.type) return cell;
  if (brushMode === "inspect") return cell.occupant ?? cell.structure;
  const layer = getPaletteLayer(paletteItem);
  return cell[layer] ?? cell.occupant ?? cell.structure;
}

function setCellLayer(cells, placement) {
  const layer = placement.layer ?? (placement.type === "asset" ? worldCellLayers.occupant : worldCellLayers.structure);
  const key = getCellKey(placement.x, placement.y);
  const current = cells[key]?.type ? createLayeredCell(placement.x, placement.y) : cells[key] ?? createLayeredCell(placement.x, placement.y);
  cells[key] = { ...current, x: placement.x, y: placement.y, [layer]: { ...placement, layer } };
  return cells[key];
}

function removeCellLayer(cells, x, y, layer) {
  const key = getCellKey(x, y);
  const current = cells[key];
  if (!current) return;
  if (current.type) {
    if ((current.type === "asset" ? worldCellLayers.occupant : worldCellLayers.structure) === layer) {
      delete cells[key];
    }
    return;
  }
  const next = { ...current, [layer]: null };
  if (!next.structure && !next.occupant) {
    delete cells[key];
  } else {
    cells[key] = next;
  }
}

function getDefaultCombatStats(asset) {
  return {
    maxHealth: asset.combat?.stats?.maxHealth ?? 100,
    damage: asset.combat?.stats?.damage ?? 10,
    range: asset.combat?.stats?.range ?? 1,
    moveSpeed: asset.combat?.stats?.moveSpeed ?? worldMoveSpeed,
    cooldown: asset.combat?.stats?.cooldown ?? 1,
  };
}

function sanitizeCombatOverrides(overrides) {
  return Object.fromEntries(
    Object.entries(overrides ?? {})
      .map(([key, value]) => [key, Number(value)])
      .filter(([key, value]) => combatStatFields.some((field) => field.id === key) && Number.isFinite(value)),
  );
}

function createCombatState(asset, combat = {}) {
  if (!isCharacterAsset(asset)) return undefined;
  const defaultRole = asset.combat?.role ?? "neutral";
  const role = combatRoles.some((item) => item.id === combat.role) ? combat.role : defaultRole;
  return {
    role,
    statOverrides: sanitizeCombatOverrides(combat.statOverrides),
  };
}

function getResolvedCombatStats(asset, combat = {}) {
  return {
    ...getDefaultCombatStats(asset),
    ...sanitizeCombatOverrides(combat.statOverrides),
  };
}

function createStructureCell(item, x, y, overrides = {}) {
  return {
    id: `${item.id}-${x}-${y}`,
    type: "structure",
    layer: worldCellLayers.structure,
    itemId: item.id,
    label: item.label,
    family: item.family,
    x,
    y,
    rotation: overrides.rotation ?? 0,
    scale: overrides.scale ?? 1,
    elevation: overrides.elevation ?? 0,
    color: item.color,
    className: item.className,
    agentHint: item.agentHint,
    tags: overrides.tags ?? [item.family.toLowerCase()],
    notes: overrides.notes ?? "",
    ...(item.id === "door" && overrides.targetWorldId ? { targetWorldId: overrides.targetWorldId } : {}),
  };
}

function createAssetCell(asset, x, y, overrides = {}) {
  const combat = createCombatState(asset, overrides.combat);
  return {
    id: `${asset.id}-${x}-${y}`,
    type: "asset",
    layer: worldCellLayers.occupant,
    itemId: asset.id,
    label: asset.shortName,
    family: asset.authored.family,
    x,
    y,
    rotation: overrides.rotation ?? 0,
    scale: overrides.scale ?? 1,
    elevation: overrides.elevation ?? 0,
    previewUrl: asset.previewUrl,
    modelUrl: asset.modelUrl,
    blendUrl: asset.blendUrl,
    agentHint: asset.description,
    tags: overrides.tags ?? [asset.authored.family.toLowerCase()],
    notes: overrides.notes ?? "",
    ...(combat ? { combat } : {}),
  };
}

function createPalettePlacement(paletteItem, x, y, previousPlacement) {
  const overrides = previousPlacement
    ? {
        rotation: previousPlacement.rotation,
        scale: previousPlacement.scale,
        elevation: previousPlacement.elevation,
        tags: previousPlacement.tags,
        notes: previousPlacement.notes,
        combat: previousPlacement.combat,
        targetWorldId: previousPlacement.targetWorldId,
      }
    : {};
  if (paletteItem.type === "asset") {
    return createAssetCell(findAsset(paletteItem.id), x, y, overrides);
  }
  return createStructureCell(findStructure(paletteItem.id), x, y, overrides);
}

function createStarterWorldCells(columns = defaultWorldMeta.columns, rows = defaultWorldMeta.rows) {
  const cells = {};
  const wall = findStructure("wall");
  for (let y = 0; y < rows; y += 1) {
    for (let x = 0; x < columns; x += 1) {
      if (x === 0 || y === 0 || x === columns - 1 || y === rows - 1) {
        setCellLayer(cells, createStructureCell(wall, x, y, { tags: ["boundary", "wall"] }));
      }
    }
  }

  const door = findStructure("door");
  const spawn = findStructure("spawn");
  const light = findStructure("light");
  setCellLayer(cells, createStructureCell(door, Math.floor(columns / 2), rows - 1, {
    tags: ["entry", "south"],
    notes: "Primary entrance for generated scene traversal.",
  }));
  setCellLayer(cells, createStructureCell(spawn, 1, 1, {
    tags: ["start", "agent"],
    notes: "Default spawn point for character placement.",
  }));
  setCellLayer(cells, createStructureCell(light, columns - 2, 1, {
    tags: ["lighting", "key"],
    notes: "Key light anchor for the first generated room.",
  }));

  const character = assetRegistry.find((asset) => asset.authored.family === "Character") ?? assetRegistry[0];
  const goblin = assetRegistry.find((asset) => asset.id === "goblin-grunt-enemy");
  const ranger = assetRegistry.find((asset) => asset.id === "forest-ranger-npc");
  const table = assetRegistry.find((asset) => asset.id === "table");
  const chair = assetRegistry.find((asset) => asset.id === "chair");
  const flower = assetRegistry.find((asset) => asset.id === "flower");
  setCellLayer(cells, createAssetCell(character, 1, 1, { tags: ["hero", "character"], combat: { role: "player" } }));
  if (goblin) setCellLayer(cells, createAssetCell(goblin, 4, 3, { tags: ["enemy", "melee"], combat: { role: "enemy-melee" } }));
  if (ranger) setCellLayer(cells, createAssetCell(ranger, columns - 3, 2, { tags: ["enemy", "ranged"], combat: { role: "enemy-ranged" } }));
  if (table) setCellLayer(cells, createAssetCell(table, 5, 4, { rotation: 90, tags: ["furniture", "anchor"] }));
  if (chair) setCellLayer(cells, createAssetCell(chair, 5, 5, { rotation: 180, tags: ["furniture", "seat"] }));
  if (flower) setCellLayer(cells, createAssetCell(flower, columns - 3, rows - 3, {
    scale: 0.85,
    tags: ["botanical", "accent"],
  }));

  return cells;
}

function createSeedWorldBuilder(columns, rows) {
  const cells = {};

  function addStructure(id, x, y, overrides = {}) {
    setCellLayer(cells, createStructureCell(findStructure(id), x, y, overrides));
  }

  function addAsset(id, x, y, overrides = {}) {
    setCellLayer(cells, createAssetCell(findAsset(id), x, y, overrides));
  }

  function addBoundaryWalls() {
    for (let y = 0; y < rows; y += 1) {
      for (let x = 0; x < columns; x += 1) {
        if (x === 0 || y === 0 || x === columns - 1 || y === rows - 1) {
          addStructure("wall", x, y, { tags: ["boundary", "wall"] });
        }
      }
    }
  }

  function addVerticalWall(x, yStart, yEnd, gaps = []) {
    const gapSet = new Set(gaps);
    for (let y = Math.max(0, yStart); y <= Math.min(rows - 1, yEnd); y += 1) {
      if (!gapSet.has(y)) addStructure("wall", x, y, { tags: ["partition", "wall"] });
    }
  }

  function addHorizontalWall(y, xStart, xEnd, gaps = []) {
    const gapSet = new Set(gaps);
    for (let x = Math.max(0, xStart); x <= Math.min(columns - 1, xEnd); x += 1) {
      if (!gapSet.has(x)) addStructure("wall", x, y, { tags: ["partition", "wall"] });
    }
  }

  function addDoor(x, y, targetWorldId, rotation, targetName, tags = []) {
    addStructure("door", x, y, {
      targetWorldId,
      rotation,
      tags: ["door", "linked", ...tags],
      notes: `Linked passage to ${targetName}.`,
    });
  }

  function addLight(x, y, tags = []) {
    addStructure("light", x, y, {
      tags: ["lighting", ...tags],
      notes: "Readable 3D preview light anchor.",
    });
  }

  function addSpawn(x, y, tags = []) {
    addStructure("spawn", x, y, {
      tags: ["start", ...tags],
      notes: "Playable character spawn.",
    });
  }

  function addPlayer(id, x, y, overrides = {}) {
    addAsset(id, x, y, {
      ...overrides,
      tags: overrides.tags ?? ["player", "character"],
      combat: { ...overrides.combat, role: "player" },
    });
  }

  function addEnemy(id, x, y, role, overrides = {}) {
    addAsset(id, x, y, {
      ...overrides,
      tags: overrides.tags ?? ["enemy", role === "enemy-ranged" ? "ranged" : "melee"],
      combat: { ...overrides.combat, role },
    });
  }

  function addNeutral(id, x, y, overrides = {}) {
    addAsset(id, x, y, {
      ...overrides,
      tags: overrides.tags ?? ["neutral", "set-dressing"],
      combat: { ...overrides.combat, role: "neutral" },
    });
  }

  return {
    cells,
    addAsset,
    addBoundaryWalls,
    addDoor,
    addEnemy,
    addHorizontalWall,
    addLight,
    addNeutral,
    addPlayer,
    addSpawn,
    addStructure,
    addVerticalWall,
  };
}

function createAtelierNexusCells() {
  const world = createSeedWorldBuilder(14, 10);
  world.addBoundaryWalls();
  world.addDoor(6, 0, seedWorldIds.garden, seedDoorRotations.north, "Garden Circuit", ["north", "garden"]);
  world.addDoor(13, 4, seedWorldIds.market, seedDoorRotations.east, "Market Concourse", ["east", "market"]);
  world.addDoor(0, 5, seedWorldIds.forge, seedDoorRotations.west, "Forge Yard", ["west", "forge"]);
  world.addDoor(7, 9, seedWorldIds.rift, seedDoorRotations.south, "Rift Arena", ["south", "rift"]);
  world.addVerticalWall(4, 1, 8, [4, 5, 6]);
  world.addVerticalWall(9, 1, 8, [2, 4, 5, 6]);
  world.addHorizontalWall(2, 5, 8, [6]);
  world.addHorizontalWall(7, 1, 3, [2]);
  world.addSpawn(2, 5, ["atelier"]);
  world.addPlayer("artomata-painter-chibi", 2, 5, { rotation: 90, tags: ["player", "painter", "hub"] });
  world.addEnemy("goblin-grunt-enemy", 3, 5, "enemy-melee", { rotation: 270, tags: ["enemy", "melee", "spawn-pressure"] });
  world.addEnemy("goblin-grunt-enemy", 6, 4, "enemy-melee", { rotation: 270, tags: ["enemy", "melee", "center-lane"] });
  world.addEnemy("forest-ranger-npc", 10, 6, "enemy-ranged", { rotation: 270, tags: ["enemy", "ranged", "east-balcony"] });
  world.addNeutral("table", 2, 3, { rotation: 90, tags: ["furniture", "worktable"] });
  world.addNeutral("chair", 2, 4, { rotation: 180, scale: 0.95, tags: ["furniture", "seat"] });
  world.addNeutral("tavern-wooden-table", 6, 6, { rotation: 90, scale: 0.9, tags: ["furniture", "planning-table"] });
  world.addNeutral("tavern-chair", 7, 6, { rotation: 270, scale: 0.88, tags: ["furniture", "seat"] });
  world.addNeutral("violet-rift-portal", 7, 7, { scale: 0.78, tags: ["vfx", "rift-preview"] });
  world.addNeutral("flower", 11, 2, { scale: 0.72, tags: ["botanical", "display"] });
  world.addLight(2, 2, ["west-room"]);
  world.addLight(7, 4, ["center"]);
  world.addLight(11, 7, ["east-room"]);
  return world.cells;
}

function createGardenCircuitCells() {
  const world = createSeedWorldBuilder(16, 12);
  world.addBoundaryWalls();
  world.addDoor(0, 2, seedWorldIds.atelier, seedDoorRotations.west, "Atelier Nexus", ["west", "atelier"]);
  world.addDoor(15, 9, seedWorldIds.market, seedDoorRotations.east, "Market Concourse", ["east", "market"]);
  world.addVerticalWall(4, 1, 10, [2, 5, 9]);
  world.addVerticalWall(8, 1, 10, [2, 6, 10]);
  world.addVerticalWall(12, 1, 10, [4, 8, 10]);
  world.addHorizontalWall(6, 1, 3, [2]);
  world.addHorizontalWall(5, 9, 11, [10]);
  world.addSpawn(2, 2, ["garden"]);
  world.addPlayer("forest-ranger-npc", 2, 2, { rotation: 90, tags: ["player", "ranger", "garden"] });
  world.addEnemy("goblin-grunt-enemy", 9, 5, "enemy-melee", { rotation: 270, tags: ["enemy", "melee", "maze"] });
  world.addEnemy("goblin-grunt-enemy", 13, 8, "enemy-melee", { rotation: 270, tags: ["enemy", "melee", "exit-guard"] });
  world.addNeutral("tree", 2, 8, { scale: 0.9, tags: ["botanical", "tree"] });
  world.addNeutral("tree", 6, 3, { scale: 0.8, rotation: 35, tags: ["botanical", "tree"] });
  world.addNeutral("tree", 10, 9, { scale: 0.86, rotation: 180, tags: ["botanical", "tree"] });
  world.addNeutral("flower", 3, 4, { scale: 0.75, tags: ["botanical", "flower"] });
  world.addNeutral("flower", 6, 8, { scale: 0.7, tags: ["botanical", "flower"] });
  world.addNeutral("flower", 14, 4, { scale: 0.72, tags: ["botanical", "flower"] });
  world.addLight(2, 3, ["spawn"]);
  world.addLight(7, 7, ["maze"]);
  world.addLight(13, 9, ["exit"]);
  return world.cells;
}

function createMarketConcourseCells() {
  const world = createSeedWorldBuilder(16, 10);
  world.addBoundaryWalls();
  world.addDoor(0, 5, seedWorldIds.atelier, seedDoorRotations.west, "Atelier Nexus", ["west", "atelier"]);
  world.addDoor(15, 5, seedWorldIds.garden, seedDoorRotations.east, "Garden Circuit", ["east", "garden"]);
  world.addDoor(8, 0, seedWorldIds.forge, seedDoorRotations.north, "Forge Yard", ["north", "forge"]);
  world.addVerticalWall(4, 2, 3);
  world.addVerticalWall(4, 6, 7);
  world.addVerticalWall(11, 2, 3);
  world.addVerticalWall(11, 6, 7);
  world.addHorizontalWall(4, 6, 10, [8]);
  world.addSpawn(2, 5, ["market"]);
  world.addPlayer("toon-blaster-runner", 2, 5, { rotation: 90, tags: ["player", "blaster", "market"] });
  world.addEnemy("goblin-grunt-enemy", 12, 5, "enemy-melee", { rotation: 270, tags: ["enemy", "melee", "main-lane"] });
  world.addEnemy("forest-ranger-npc", 13, 3, "enemy-ranged", { rotation: 270, tags: ["enemy", "ranged", "stall-roof"] });
  world.addNeutral("village-market-stall", 5, 2, { rotation: 90, scale: 0.85, tags: ["market", "stall"] });
  world.addNeutral("village-market-stall", 10, 2, { rotation: 270, scale: 0.85, tags: ["market", "stall"] });
  world.addNeutral("village-market-stall", 5, 7, { rotation: 90, scale: 0.85, tags: ["market", "stall"] });
  world.addNeutral("village-blacksmith-npc", 8, 5, { rotation: 180, tags: ["neutral", "blacksmith", "vendor"] });
  world.addNeutral("tavern-wooden-table", 7, 7, { rotation: 90, scale: 0.86, tags: ["furniture", "market-table"] });
  world.addNeutral("tavern-chair", 8, 7, { rotation: 270, scale: 0.82, tags: ["furniture", "seat"] });
  world.addLight(2, 4, ["west-lane"]);
  world.addLight(8, 3, ["center"]);
  world.addLight(13, 6, ["east-lane"]);
  return world.cells;
}

function createForgeYardCells() {
  const world = createSeedWorldBuilder(14, 12);
  world.addBoundaryWalls();
  world.addDoor(13, 6, seedWorldIds.atelier, seedDoorRotations.east, "Atelier Nexus", ["east", "atelier"]);
  world.addDoor(7, 11, seedWorldIds.market, seedDoorRotations.south, "Market Concourse", ["south", "market"]);
  world.addDoor(0, 6, seedWorldIds.rift, seedDoorRotations.west, "Rift Arena", ["west", "rift"]);
  world.addVerticalWall(4, 2, 9, [5, 6]);
  world.addVerticalWall(9, 2, 9, [4, 6, 7]);
  world.addHorizontalWall(3, 5, 8, [6]);
  world.addHorizontalWall(8, 5, 8, [7]);
  world.addSpawn(2, 6, ["forge"]);
  world.addPlayer("village-blacksmith-npc", 2, 6, { rotation: 90, tags: ["player", "blacksmith", "forge"] });
  world.addEnemy("goblin-grunt-enemy", 6, 6, "enemy-melee", { rotation: 270, tags: ["enemy", "melee", "anvil-lane"] });
  world.addEnemy("goblin-grunt-enemy", 10, 8, "enemy-melee", { rotation: 270, tags: ["enemy", "melee", "yard"] });
  world.addEnemy("forest-ranger-npc", 10, 3, "enemy-ranged", { rotation: 270, tags: ["enemy", "ranged", "upper-cover"] });
  world.addNeutral("blacksmith-forge-workbench", 6, 5, { scale: 0.88, tags: ["forge", "workbench"] });
  world.addNeutral("table", 2, 3, { rotation: 90, scale: 0.92, tags: ["furniture", "tool-table"] });
  world.addNeutral("tavern-chair", 3, 3, { rotation: 270, scale: 0.78, tags: ["furniture", "seat"] });
  world.addNeutral("violet-rift-portal", 2, 9, { scale: 0.72, tags: ["vfx", "rift-anchor"] });
  world.addLight(2, 5, ["spawn"]);
  world.addLight(6, 4, ["forge"]);
  world.addLight(11, 7, ["yard"]);
  return world.cells;
}

function createRiftArenaCells() {
  const world = createSeedWorldBuilder(16, 12);
  world.addBoundaryWalls();
  world.addDoor(8, 11, seedWorldIds.atelier, seedDoorRotations.south, "Atelier Nexus", ["south", "atelier"]);
  world.addDoor(0, 6, seedWorldIds.forge, seedDoorRotations.west, "Forge Yard", ["west", "forge"]);
  world.addDoor(15, 6, seedWorldIds.garden, seedDoorRotations.east, "Garden Circuit", ["east", "garden"]);
  world.addVerticalWall(5, 2, 4);
  world.addVerticalWall(5, 8, 9);
  world.addVerticalWall(10, 2, 4);
  world.addVerticalWall(10, 8, 9);
  world.addHorizontalWall(6, 3, 4);
  world.addHorizontalWall(6, 11, 12);
  world.addSpawn(8, 9, ["rift"]);
  world.addPlayer("toon-blaster-runner", 8, 9, { rotation: 180, tags: ["player", "blaster", "arena"] });
  world.addEnemy("goblin-grunt-enemy", 6, 5, "enemy-melee", { rotation: 135, tags: ["enemy", "melee", "left-center"] });
  world.addEnemy("goblin-grunt-enemy", 10, 5, "enemy-melee", { rotation: 225, tags: ["enemy", "melee", "right-center"] });
  world.addEnemy("forest-ranger-npc", 4, 2, "enemy-ranged", { rotation: 135, tags: ["enemy", "ranged", "left-perch"] });
  world.addEnemy("forest-ranger-npc", 11, 2, "enemy-ranged", { rotation: 225, tags: ["enemy", "ranged", "right-perch"] });
  world.addNeutral("violet-rift-portal", 8, 5, { scale: 0.9, tags: ["vfx", "centerpiece", "rift"] });
  world.addNeutral("flower", 7, 5, { scale: 0.62, tags: ["botanical", "rift-flora"] });
  world.addNeutral("flower", 9, 5, { scale: 0.62, tags: ["botanical", "rift-flora"] });
  world.addLight(8, 4, ["portal"]);
  world.addLight(3, 8, ["west-cover"]);
  world.addLight(12, 8, ["east-cover"]);
  return world.cells;
}

function createSeedWorldRecords() {
  const createdAt = "2026-05-09T00:00:00.000Z";
  const rules =
    "Explore linked doors, keep the spawn character reachable, and use cover walls as navigation/combat structure.";
  return [
    createWorldRecord({
      id: seedWorldIds.atelier,
      createdAt,
      meta: {
        name: "Atelier Nexus",
        theme: "studio-atrium",
        columns: 14,
        rows: 10,
        cellSize: "1m",
        rules: `${rules} This hub branches to every authored world.`,
      },
      cells: createAtelierNexusCells(),
    }),
    createWorldRecord({
      id: seedWorldIds.garden,
      createdAt,
      meta: {
        name: "Garden Circuit",
        theme: "garden-room",
        columns: 16,
        rows: 12,
        cellSize: "1m",
        rules: `${rules} Hedge partitions should read as a looping botanical maze.`,
      },
      cells: createGardenCircuitCells(),
    }),
    createWorldRecord({
      id: seedWorldIds.market,
      createdAt,
      meta: {
        name: "Market Concourse",
        theme: "studio-atrium",
        columns: 16,
        rows: 10,
        cellSize: "1m",
        rules: `${rules} Keep the central bazaar lane open between east and west doors.`,
      },
      cells: createMarketConcourseCells(),
    }),
    createWorldRecord({
      id: seedWorldIds.forge,
      createdAt,
      meta: {
        name: "Forge Yard",
        theme: "training-floor",
        columns: 14,
        rows: 12,
        cellSize: "1m",
        rules: `${rules} Narrow lanes create short-range pressure around the forge bench.`,
      },
      cells: createForgeYardCells(),
    }),
    createWorldRecord({
      id: seedWorldIds.rift,
      createdAt,
      meta: {
        name: "Rift Arena",
        theme: "toon-lab",
        columns: 16,
        rows: 12,
        cellSize: "1m",
        rules: `${rules} The arena is symmetric so ranged and melee enemies pressure the center portal.`,
      },
      cells: createRiftArenaCells(),
    }),
  ];
}

function getSeedWorldRecord(worldId) {
  return createSeedWorldRecords().find((world) => world.id === worldId);
}

function resizeWorldCells(cells, columns, rows) {
  const next = {};
  Object.values(cells).forEach((cell) => {
    const placements = getCellPlacements(cell);
    placements.forEach((placement) => {
      if (placement.x < columns && placement.y < rows) {
        setCellLayer(next, placement);
      }
    });
  });

  const wall = findStructure("wall");
  for (let y = 0; y < rows; y += 1) {
    for (let x = 0; x < columns; x += 1) {
      const key = getCellKey(x, y);
      if ((x === 0 || y === 0 || x === columns - 1 || y === rows - 1) && !next[key]?.structure) {
        setCellLayer(next, createStructureCell(wall, x, y, { tags: ["boundary", "wall"] }));
      }
    }
  }
  return next;
}

function normaliseImportedPlacement(placement) {
  const x = Number(placement.x);
  const y = Number(placement.y);
  const overrides = {
    rotation: Number(placement.rotation) || 0,
    scale: Number(placement.scale) || 1,
    elevation: Number(placement.elevation) || 0,
    tags: Array.isArray(placement.tags) ? placement.tags : [],
    notes: typeof placement.notes === "string" ? placement.notes : "",
    combat: placement.combat,
    targetWorldId: typeof placement.targetWorldId === "string" ? placement.targetWorldId : undefined,
  };
  if (placement.type === "asset") {
    return createAssetCell(findAsset(placement.itemId ?? placement.assetId), x, y, overrides);
  }
  return createStructureCell(findStructure(placement.itemId ?? placement.structureId), x, y, overrides);
}

function getSerializedWorldPlacements(cells) {
  return Object.values(cells)
    .flatMap(getCellPlacements)
    .sort((a, b) => a.y - b.y || a.x - b.x || String(a.layer).localeCompare(String(b.layer)))
    .map(({ type, layer, itemId, label, family, x, y, rotation, scale, elevation, tags, notes, agentHint, combat, targetWorldId }) => ({
      type,
      layer,
      itemId,
      label,
      family,
      x,
      y,
      rotation,
      scale,
      elevation,
      tags,
      notes,
      agentHint,
      ...(combat ? { combat } : {}),
      ...(targetWorldId ? { targetWorldId } : {}),
    }));
}

function createCellsFromPlacements(placements, columns, rows) {
  const nextCells = {};
  placements.forEach((placement) => {
    const x = Number(placement.x);
    const y = Number(placement.y);
    if (!Number.isInteger(x) || !Number.isInteger(y) || x < 0 || y < 0 || x >= columns || y >= rows) return;
    setCellLayer(nextCells, normaliseImportedPlacement(placement));
  });
  return nextCells;
}

function normaliseWorldMeta(meta = {}) {
  const theme = worldThemes.some((item) => item.id === meta.theme) ? meta.theme : defaultWorldMeta.theme;
  return {
    name: typeof meta.name === "string" && meta.name.trim() ? meta.name : defaultWorldMeta.name,
    theme,
    columns: clampGridValue(meta.columns ?? meta.grid?.columns ?? defaultWorldMeta.columns, 6, 16),
    rows: clampGridValue(meta.rows ?? meta.grid?.rows ?? defaultWorldMeta.rows, 5, 12),
    cellSize: typeof (meta.cellSize ?? meta.grid?.cellSize) === "string" ? meta.cellSize ?? meta.grid?.cellSize : defaultWorldMeta.cellSize,
    rules: typeof meta.rules === "string" ? meta.rules : defaultWorldMeta.rules,
  };
}

function createWorldId() {
  if (globalThis.crypto?.randomUUID) return globalThis.crypto.randomUUID();
  return `world-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 8)}`;
}

function createWorldRecord({ id = createWorldId(), meta = defaultWorldMeta, cells, placements, createdAt } = {}) {
  const now = new Date().toISOString();
  const normalisedMeta = normaliseWorldMeta(meta);
  const sourceCells = Array.isArray(placements)
    ? createCellsFromPlacements(placements, normalisedMeta.columns, normalisedMeta.rows)
    : cells ?? createStarterWorldCells(normalisedMeta.columns, normalisedMeta.rows);
  return {
    id,
    createdAt: createdAt ?? now,
    updatedAt: now,
    meta: normalisedMeta,
    placements: getSerializedWorldPlacements(sourceCells),
  };
}

function createInitialWorldLibrary() {
  const worlds = createSeedWorldRecords();
  return {
    schemaVersion: worldLibrarySchemaVersion,
    seedVersion: worldSeedVersion,
    activeWorldId: worlds[0].id,
    worlds,
  };
}

function normaliseWorldRecord(record = {}) {
  const meta = normaliseWorldMeta(record.meta ?? record);
  const sourceCells = Array.isArray(record.placements)
    ? createCellsFromPlacements(record.placements, meta.columns, meta.rows)
    : createStarterWorldCells(meta.columns, meta.rows);
  const createdAt = typeof record.createdAt === "string" ? record.createdAt : new Date().toISOString();
  return {
    id: typeof record.id === "string" && record.id ? record.id : createWorldId(),
    createdAt,
    updatedAt: typeof record.updatedAt === "string" ? record.updatedAt : createdAt,
    meta,
    placements: getSerializedWorldPlacements(sourceCells),
  };
}

function ensureSeedWorlds(library) {
  const storedSeedVersion = Number(library?.seedVersion) || 0;
  if (storedSeedVersion >= worldSeedVersion) {
    return { ...library, seedVersion: worldSeedVersion };
  }
  const existingIds = new Set(library.worlds.map((world) => world.id));
  const missingSeeds = createSeedWorldRecords().filter((world) => !existingIds.has(world.id));
  return {
    ...library,
    seedVersion: worldSeedVersion,
    worlds: [...library.worlds, ...missingSeeds],
  };
}

function normaliseWorldLibrary(library) {
  const worldIds = new Set();
  const worlds = (Array.isArray(library?.worlds) ? library.worlds : [])
    .map(normaliseWorldRecord)
    .map((record) => {
      if (!worldIds.has(record.id)) {
        worldIds.add(record.id);
        return record;
      }
      const id = createWorldId();
      worldIds.add(id);
      return { ...record, id };
    });
  if (!worlds.length) return createInitialWorldLibrary();
  const activeWorldId = worlds.some((world) => world.id === library?.activeWorldId)
    ? library.activeWorldId
    : worlds[0].id;
  return ensureSeedWorlds({
    schemaVersion: worldLibrarySchemaVersion,
    seedVersion: Number(library?.seedVersion) || 0,
    activeWorldId,
    worlds,
  });
}

function loadWorldLibrary() {
  if (typeof window === "undefined") return createInitialWorldLibrary();
  try {
    const stored = window.localStorage.getItem(worldLibraryStorageKey);
    if (!stored) return createInitialWorldLibrary();
    return normaliseWorldLibrary(JSON.parse(stored));
  } catch {
    return createInitialWorldLibrary();
  }
}

function saveWorldLibrary(library) {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.setItem(worldLibraryStorageKey, JSON.stringify(library));
  } catch {
    // localStorage can be unavailable in private contexts; the in-memory library still works.
  }
}

function getCellsFromWorldRecord(record) {
  const meta = normaliseWorldMeta(record?.meta);
  if (Array.isArray(record?.placements)) {
    return createCellsFromPlacements(record.placements, meta.columns, meta.rows);
  }
  return createStarterWorldCells(meta.columns, meta.rows);
}

function getDefaultSelectedKey(cells) {
  const starterKey = getCellKey(1, 1);
  return cells[starterKey] ? starterKey : Object.keys(cells)[0] ?? null;
}

function getUniqueWorldName(baseName, worlds) {
  const base = baseName.trim() || "Untitled World";
  const existing = new Set(worlds.map((world) => world.meta.name));
  if (!existing.has(base)) return base;
  let index = 2;
  while (existing.has(`${base} ${index}`)) index += 1;
  return `${base} ${index}`;
}

function serializeWorld(meta, cells, worldId) {
  const theme = worldThemes.find((item) => item.id === meta.theme) ?? worldThemes[0];
  const placements = getSerializedWorldPlacements(cells);
  return {
    schemaVersion: "artomata.world-grid.v2",
    ...(worldId ? { id: worldId } : {}),
    name: meta.name,
    theme: meta.theme,
    mood: theme.mood,
    grid: {
      columns: meta.columns,
      rows: meta.rows,
      cellSize: meta.cellSize,
      coordinateSystem: "zero-based x,y from top-left",
    },
    rules: meta.rules,
    palette: {
      assets: assetRegistry.map((asset) => ({
        id: asset.id,
        label: asset.shortName,
        family: asset.authored.family,
        modelUrl: asset.modelUrl,
      })),
      structures: structurePalette.map((item) => ({
        id: item.id,
        label: item.label,
        family: item.family,
        agentHint: item.agentHint,
      })),
    },
    placements,
    agentContract: {
      oneStructureAndOneOccupantPerCell: true,
      validPlacementTypes: ["asset", "structure"],
      validLayers: ["structure", "occupant"],
      characterRoles: combatRoles.map((role) => role.id),
      doorTargetField: "targetWorldId",
      preferredWorkflow: "Edit placements, keep x/y inside grid bounds, then import JSON through the World Creator panel.",
    },
  };
}

function buildAgentBrief(world) {
  const characterCount = world.placements.filter((item) => item.family === "Character").length;
  const structureCount = world.placements.filter((item) => item.type === "structure").length;
  const enemyCount = world.placements.filter((item) => isEnemyRole(item.combat?.role)).length;
  return [
    `World: ${world.name}`,
    `Theme: ${world.theme} (${world.mood})`,
    `Grid: ${world.grid.columns} x ${world.grid.rows}, ${world.grid.cellSize} cells, coordinates are ${world.grid.coordinateSystem}.`,
    `Current contents: ${world.placements.length} placements, ${characterCount} character placement(s), ${enemyCount} enemy placement(s), ${structureCount} structure placement(s).`,
    `Rules: ${world.rules}`,
    "Agent task contract: use itemId values from the palette, place at integer x/y coordinates inside the grid, use structure and occupant layers for shared cells, assign character combat.role when needed, use rotation in 90-degree increments when possible, and add tags and notes for generation intent.",
  ].join("\n");
}

function validateWorld(world) {
  const placements = world.placements;
  const hasCharacter = placements.some((item) => item.family === "Character");
  const hasEntry = placements.some((item) => item.itemId === "door" || item.itemId === "spawn");
  const hasStructure = placements.some((item) => item.type === "structure");
  const spawnKeys = new Set(placements.filter((item) => item.itemId === "spawn").map((item) => getCellKey(item.x, item.y)));
  const hasControllableSpawn = placements.some(
    (item) => item.family === "Character" && item.combat?.role !== "enemy-melee" && item.combat?.role !== "enemy-ranged" && spawnKeys.has(getCellKey(item.x, item.y)),
  );
  const occupiedKeys = new Set();
  let duplicate = false;
  placements.forEach((item) => {
    const key = `${getCellKey(item.x, item.y)}:${item.layer ?? item.type}`;
    if (occupiedKeys.has(key)) duplicate = true;
    occupiedKeys.add(key);
  });
  return [
    { ok: hasCharacter, label: "Character anchor", detail: hasCharacter ? "Ready" : "Place at least one character asset." },
    { ok: hasControllableSpawn, label: "Playable spawn", detail: hasControllableSpawn ? "Ready" : "Layer a non-enemy character on a spawn tile." },
    { ok: hasEntry, label: "Entry point", detail: hasEntry ? "Ready" : "Add a door or spawn tile." },
    { ok: hasStructure, label: "Room structure", detail: hasStructure ? "Ready" : "Add walls, floors, lights, or spawn markers." },
    { ok: !duplicate, label: "Layer uniqueness", detail: duplicate ? "Resolve duplicate coordinates on the same layer." : "Ready" },
  ];
}

const worldViewModes = {
  grid: { label: "Grid", Icon: Grid2X2 },
  view3d: { label: "3D", Icon: Box },
};

const worldAssetCache = new Map();
const worldPlayerRadius = 0.28;
const worldEyeHeight = 1.45;
const worldMoveSpeed = 3.2;

function getWorldDimensions(world) {
  const columns = clampGridValue(world.grid?.columns ?? defaultWorldMeta.columns, 6, 16);
  const rows = clampGridValue(world.grid?.rows ?? defaultWorldMeta.rows, 5, 12);
  const parsedCellSize = Number.parseFloat(String(world.grid?.cellSize ?? defaultWorldMeta.cellSize).replace(/[^\d.-]/g, ""));
  const cellSize = Number.isFinite(parsedCellSize) ? Math.min(2.4, Math.max(0.75, parsedCellSize)) : 1;
  return { columns, rows, cellSize };
}

function getWorldCellCenter(x, y, world, elevation = 0) {
  const { columns, rows, cellSize } = getWorldDimensions(world);
  return new THREE.Vector3(
    (x - (columns - 1) / 2) * cellSize,
    Number(elevation) || 0,
    (y - (rows - 1) / 2) * cellSize,
  );
}

function getWorldCellKeyFromPosition(position, world, cellSize) {
  const { columns, rows } = getWorldDimensions(world);
  const x = Math.round(position.x / cellSize + (columns - 1) / 2);
  const y = Math.round(position.z / cellSize + (rows - 1) / 2);
  if (x < 0 || y < 0 || x >= columns || y >= rows) return "";
  return getCellKey(x, y);
}

function getWorldSolidKeys(world) {
  return new Set(world.placements.filter((placement) => placement.type === "structure" && placement.itemId === "wall").map((placement) => getCellKey(placement.x, placement.y)));
}

function canOccupyWorldPosition(position, world, solidKeys, cellSize) {
  const radius = worldPlayerRadius * cellSize;
  const samples = [
    [0, 0],
    [radius, 0],
    [-radius, 0],
    [0, radius],
    [0, -radius],
    [radius, radius],
    [-radius, radius],
    [radius, -radius],
    [-radius, -radius],
  ];
  return samples.every(([xOffset, zOffset]) => {
    const key = getWorldCellKeyFromPosition({ x: position.x + xOffset, z: position.z + zOffset }, world, cellSize);
    return Boolean(key) && !solidKeys.has(key);
  });
}

function getWorldSpawnPose(world) {
  const { columns, rows, cellSize } = getWorldDimensions(world);
  const spawn =
    world.placements.find((placement) => placement.itemId === "spawn") ??
    world.placements.find((placement) => placement.itemId === "door");
  const fallback = { x: Math.min(columns - 2, 1), y: Math.min(rows - 2, 1), rotation: 0, elevation: 0 };
  const anchor = spawn ?? fallback;
  const position = getWorldCellCenter(anchor.x, anchor.y, world, anchor.elevation);
  const center = getWorldCellCenter((columns - 1) / 2, (rows - 1) / 2, world, anchor.elevation);
  const centerYaw = Math.atan2(position.x - center.x, position.z - center.z);
  const authoredYaw = Number(anchor.rotation);
  position.y += worldEyeHeight * cellSize;
  return {
    position,
    yaw: Number.isFinite(authoredYaw) && authoredYaw !== 0 ? THREE.MathUtils.degToRad(authoredYaw) : centerYaw,
  };
}

function getWorldCellFromPosition(position, world, cellSize) {
  const { columns, rows } = getWorldDimensions(world);
  const x = Math.round(position.x / cellSize + (columns - 1) / 2);
  const y = Math.round(position.z / cellSize + (rows - 1) / 2);
  if (x < 0 || y < 0 || x >= columns || y >= rows) return null;
  return { x, y, key: getCellKey(x, y) };
}

function getWorldPlayablePlacement(world) {
  const spawnKeys = new Set(world.placements.filter((placement) => placement.itemId === "spawn").map((placement) => getCellKey(placement.x, placement.y)));
  return world.placements.find(
    (placement) =>
      placement.type === "asset" &&
      placement.family === "Character" &&
      !isEnemyRole(placement.combat?.role) &&
      spawnKeys.has(getCellKey(placement.x, placement.y)),
  );
}

function getGridNeighbors(cellKey, world, solidKeys) {
  const { columns, rows } = getWorldDimensions(world);
  const [x, y] = cellKey.split(":").map(Number);
  return [
    [x + 1, y],
    [x - 1, y],
    [x, y + 1],
    [x, y - 1],
  ]
    .filter(([nextX, nextY]) => nextX >= 0 && nextY >= 0 && nextX < columns && nextY < rows)
    .map(([nextX, nextY]) => getCellKey(nextX, nextY))
    .filter((key) => !solidKeys.has(key));
}

function findWorldPath(startKey, goalKey, world, solidKeys) {
  if (!startKey || !goalKey || startKey === goalKey || solidKeys.has(goalKey)) return [];
  const [goalX, goalY] = goalKey.split(":").map(Number);
  const open = new Set([startKey]);
  const cameFrom = new Map();
  const gScore = new Map([[startKey, 0]]);
  const fScore = new Map([[startKey, 0]]);

  function heuristic(key) {
    const [x, y] = key.split(":").map(Number);
    return Math.abs(goalX - x) + Math.abs(goalY - y);
  }

  while (open.size) {
    let current = null;
    let best = Infinity;
    open.forEach((key) => {
      const score = fScore.get(key) ?? Infinity;
      if (score < best) {
        best = score;
        current = key;
      }
    });
    if (current === goalKey) {
      const path = [current];
      while (cameFrom.has(current)) {
        current = cameFrom.get(current);
        path.unshift(current);
      }
      return path.slice(1);
    }
    open.delete(current);
    getGridNeighbors(current, world, solidKeys).forEach((neighbor) => {
      const tentative = (gScore.get(current) ?? Infinity) + 1;
      if (tentative >= (gScore.get(neighbor) ?? Infinity)) return;
      cameFrom.set(neighbor, current);
      gScore.set(neighbor, tentative);
      fScore.set(neighbor, tentative + heuristic(neighbor));
      open.add(neighbor);
    });
  }
  return [];
}

function hasWorldLineOfSight(start, end, world, solidKeys, cellSize) {
  const distance = start.distanceTo(end);
  const steps = Math.max(2, Math.ceil(distance / (cellSize * 0.35)));
  for (let index = 1; index < steps; index += 1) {
    const alpha = index / steps;
    const sample = start.clone().lerp(end, alpha);
    const cell = getWorldCellFromPosition(sample, world, cellSize);
    if (!cell || solidKeys.has(cell.key)) return false;
  }
  return true;
}

function setWorldCameraPose(camera, world) {
  const pose = getWorldSpawnPose(world);
  camera.position.copy(pose.position);
  camera.rotation.set(0, pose.yaw, 0, "YXZ");
}

function getAssetFitScale(asset, cellSize) {
  const bounds = asset.metadataFallback?.bounds?.size;
  if (!bounds?.length) return 0.62 * cellSize;
  const footprint = Math.max(bounds[0] || 1, bounds[1] || 1, 0.1);
  return Math.min(0.82, (0.82 * cellSize) / footprint);
}

function loadWorldAsset(loader, asset) {
  if (!worldAssetCache.has(asset.modelUrl)) {
    const assetPromise = loader.loadAsync(asset.modelUrl).then((gltf) => {
      const model = gltf.scene;
      placeLoadedModel(model, asset);
      model.traverse((child) => {
        if (!child.isMesh) return;
        child.frustumCulled = true;
        child.castShadow = false;
        child.receiveShadow = true;
        const materialList = Array.isArray(child.material) ? child.material : [child.material];
        materialList.forEach((material) => {
          if (!material) return;
          material.envMapIntensity = 0.45;
          material.needsUpdate = true;
        });
      });
      return { model, animations: gltf.animations || [] };
    });
    worldAssetCache.set(asset.modelUrl, assetPromise);
  }
  return worldAssetCache.get(asset.modelUrl);
}

function createGradientTexture(top, bottom) {
  const canvas = document.createElement("canvas");
  canvas.width = 2;
  canvas.height = 256;
  const context = canvas.getContext("2d");
  const gradient = context.createLinearGradient(0, 0, 0, canvas.height);
  gradient.addColorStop(0, top);
  gradient.addColorStop(1, bottom);
  context.fillStyle = gradient;
  context.fillRect(0, 0, canvas.width, canvas.height);
  const texture = new THREE.CanvasTexture(canvas);
  texture.colorSpace = THREE.SRGBColorSpace;
  return texture;
}

function readPose(pose) {
  return {
    position: new THREE.Vector3(...pose.position),
    target: new THREE.Vector3(...pose.target),
  };
}

function setCameraPose(camera, controls, pose) {
  const next = readPose(pose);
  camera.position.copy(next.position);
  controls.target.copy(next.target);
  controls.update();
}

function setCameraHome(camera, controls, asset, width) {
  setCameraPose(camera, controls, width < 700 ? asset.camera.mobile : asset.camera.desktop);
}

function formatBytes(bytes) {
  if (!bytes) return "...";
  if (bytes < 1024 * 1024) return `${Math.round(bytes / 1024).toLocaleString()} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function formatBounds(bounds, dimensions) {
  const size = bounds?.size ?? dimensions;
  if (!size) return "...";
  return `${size.map((value) => Number(value).toFixed(2)).join(" x ")} m`;
}

function placeLoadedModel(model, asset) {
  model.rotation.set(...asset.initialTransform.rotation);
  model.scale.setScalar(asset.initialTransform.scale);
  model.updateMatrixWorld(true);

  const box = new THREE.Box3().setFromObject(model);
  const center = box.getCenter(new THREE.Vector3());
  if (asset.placement?.mode === "center") {
    model.position.sub(center);
  } else {
    model.position.x -= center.x;
    model.position.z -= center.z;
    model.position.y -= box.min.y;
  }

  const offset = asset.placement?.offset;
  if (offset) model.position.add(new THREE.Vector3(...offset));
}

function disposeModel(model) {
  model.traverse((child) => {
    if (!child.isMesh) return;
    child.geometry?.dispose?.();
    const materialList = Array.isArray(child.material) ? child.material : [child.material];
    for (const material of materialList) {
      material?.dispose?.();
    }
  });
}

function extractModelMetadata(model, animations = []) {
  let meshes = 0;
  let triangles = 0;
  const materials = new Set();
  model.traverse((child) => {
    if (!child.isMesh) return;
    meshes += 1;
    const geometry = child.geometry;
    const indexCount = geometry.index?.count;
    const vertexCount = geometry.attributes.position?.count ?? 0;
    triangles += Math.round((indexCount ?? vertexCount) / 3);
    const materialList = Array.isArray(child.material) ? child.material : [child.material];
    for (const material of materialList) {
      if (material?.name) materials.add(material.name);
    }
  });

  const box = new THREE.Box3().setFromObject(model);
  const size = box.getSize(new THREE.Vector3());
  return {
    meshes,
    triangles,
    materials: materials.size,
    dimensions: [size.x, size.y, size.z],
    animations: animations.map((clip) => clip.name),
  };
}

async function fetchJson(url) {
  const response = await fetch(url);
  if (!response.ok) throw new Error(`Unable to load ${url}`);
  return response.json();
}

async function fetchFileSize(url) {
  const head = await fetch(url, { method: "HEAD" });
  const length = head.headers.get("content-length");
  if (length) return Number(length);
  const response = await fetch(url);
  const blob = await response.blob();
  return blob.size;
}

function SceneViewport({ asset, activeClipName, autoSpin, exposure, mode, onLoaded, commandRef }) {
  const mountRef = useRef(null);
  const stateRef = useRef({
    renderer: null,
    scene: null,
    camera: null,
    controls: null,
    model: null,
    mixer: null,
    animations: [],
    activeAction: null,
    activeClipName,
    playClip: null,
    lights: null,
    animationId: 0,
    autoSpin,
  });

  useEffect(() => {
    const mount = mountRef.current;
    let disposed = false;
    const scene = new THREE.Scene();
    const clock = new THREE.Clock();
    scene.background = createGradientTexture(sceneModes[mode].backgroundTop, sceneModes[mode].backgroundBottom);
    scene.fog = new THREE.Fog(sceneModes[mode].backgroundBottom, 7.2, 13.5);

    const camera = new THREE.PerspectiveCamera(35, mount.clientWidth / mount.clientHeight, 0.05, 100);
    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: false, preserveDrawingBuffer: true });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.setSize(mount.clientWidth, mount.clientHeight);
    renderer.outputColorSpace = THREE.SRGBColorSpace;
    renderer.toneMapping = THREE.ACESFilmicToneMapping;
    renderer.toneMappingExposure = exposure;
    mount.appendChild(renderer.domElement);

    const controls = new OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true;
    controls.dampingFactor = 0.06;
    controls.minDistance = 1.9;
    controls.maxDistance = 8.2;
    setCameraHome(camera, controls, asset, mount.clientWidth);

    const hemi = new THREE.HemisphereLight("#fcf5e5", "#101820", 0.85);
    const key = new THREE.DirectionalLight("#ffe6d3", sceneModes[mode].key);
    key.position.set(-3.2, 4.8, 4.2);
    const fill = new THREE.DirectionalLight("#8feaf0", sceneModes[mode].fill);
    fill.position.set(3.3, 2.3, 2.0);
    const rim = new THREE.DirectionalLight(sceneModes[mode].accent, sceneModes[mode].rim);
    rim.position.set(3.1, 2.7, -3.2);
    scene.add(hemi, key, fill, rim);

    function playClip(name, fadeDuration = 0.16) {
      const current = stateRef.current;
      if (!current.mixer || !current.animations.length) return;
      const clip = current.animations.find((item) => item.name === name) ?? current.animations[0];
      if (!clip) return;
      const nextAction = current.mixer.clipAction(clip);
      if (current.activeAction === nextAction && nextAction.isRunning()) return;
      if (current.activeAction) {
        current.activeAction.fadeOut(fadeDuration);
      }
      nextAction.reset().setLoop(THREE.LoopRepeat, Infinity).fadeIn(fadeDuration).play();
      current.activeAction = nextAction;
      current.activeClipName = clip.name;
    }

    const loader = new GLTFLoader();
    loader.load(
      asset.modelUrl,
      (gltf) => {
        if (disposed) {
          disposeModel(gltf.scene);
          return;
        }
        const model = gltf.scene;
        placeLoadedModel(model, asset);

        model.traverse((child) => {
          if (!child.isMesh) return;
          child.castShadow = true;
          child.receiveShadow = true;
          const materialList = Array.isArray(child.material) ? child.material : [child.material];
          for (const material of materialList) {
            if (!material) continue;
            material.envMapIntensity = 0.55;
            material.needsUpdate = true;
          }
        });
        scene.add(model);
        stateRef.current.model = model;
        stateRef.current.animations = gltf.animations || [];
        stateRef.current.mixer = gltf.animations?.length ? new THREE.AnimationMixer(model) : null;
        stateRef.current.playClip = playClip;
        playClip(stateRef.current.activeClipName || activeClipName, 0);
        onLoaded({ ...extractModelMetadata(model, gltf.animations), url: asset.modelUrl, status: "ready" });
      },
      undefined,
      (error) => {
        if (disposed) return;
        onLoaded({ error: error.message || "Unable to load model", url: asset.modelUrl, status: "error" });
      },
    );

    function resize() {
      const width = mount.clientWidth;
      const height = mount.clientHeight;
      camera.aspect = width / height;
      camera.updateProjectionMatrix();
      renderer.setSize(width, height);
    }

    function animate() {
      const delta = clock.getDelta();
      if (stateRef.current.mixer) {
        stateRef.current.mixer.update(delta);
      }
      const loadedModel = stateRef.current.model;
      if (loadedModel && stateRef.current.autoSpin) {
        loadedModel.rotation.y += 0.0042;
      }
      controls.update();
      renderer.render(scene, camera);
      stateRef.current.animationId = requestAnimationFrame(animate);
    }

    window.addEventListener("resize", resize);
    stateRef.current = {
      renderer,
      scene,
      camera,
      controls,
      model: null,
      mixer: null,
      animations: [],
      activeAction: null,
      activeClipName,
      playClip,
      lights: { key, fill, rim },
      animationId: 0,
      autoSpin,
    };
    animate();

    commandRef.current = {
      reset: () => {
        const loadedModel = stateRef.current.model;
        if (loadedModel) loadedModel.rotation.set(...asset.initialTransform.rotation);
        setCameraHome(camera, controls, asset, mount.clientWidth);
      },
      focus: () => setCameraPose(camera, controls, asset.camera.focus),
      zoomIn: () => {
        camera.position.lerp(controls.target, 0.18);
        controls.update();
      },
      zoomOut: () => {
        camera.position.lerpVectors(controls.target, camera.position, 1.18);
        controls.update();
      },
      snapshot: () => renderer.domElement.toDataURL("image/png"),
    };

    return () => {
      disposed = true;
      window.removeEventListener("resize", resize);
      cancelAnimationFrame(stateRef.current.animationId);
      commandRef.current = null;
      stateRef.current.mixer?.stopAllAction();
      if (stateRef.current.model) disposeModel(stateRef.current.model);
      controls.dispose();
      renderer.dispose();
      if (renderer.domElement.parentNode === mount) {
        mount.removeChild(renderer.domElement);
      }
    };
  }, [asset, commandRef, onLoaded]);

  useEffect(() => {
    stateRef.current.autoSpin = autoSpin;
  }, [autoSpin]);

  useEffect(() => {
    stateRef.current.activeClipName = activeClipName;
    stateRef.current.playClip?.(activeClipName);
  }, [activeClipName]);

  useEffect(() => {
    const current = stateRef.current;
    if (!current.renderer) return;
    current.renderer.toneMappingExposure = exposure;
    if (current.lights) {
      current.lights.key.intensity = sceneModes[mode].key;
      current.lights.fill.intensity = sceneModes[mode].fill;
      current.lights.rim.intensity = sceneModes[mode].rim;
      current.lights.rim.color.set(sceneModes[mode].accent);
    }
    const oldBackground = current.scene.background;
    current.scene.background = createGradientTexture(sceneModes[mode].backgroundTop, sceneModes[mode].backgroundBottom);
    current.scene.fog.color.set(sceneModes[mode].backgroundBottom);
    if (oldBackground?.dispose) oldBackground.dispose();
  }, [exposure, mode]);

  return <div className="viewport" ref={mountRef} aria-label={`${asset.name} interactive 3D model viewport`} />;
}

function WorldViewportLegacy({ world }) {
  const mountRef = useRef(null);
  const stateRef = useRef({
    renderer: null,
    camera: null,
    world,
    solidKeys: new Set(),
    cellSize: 1,
    keys: new Set(),
    pointerLocked: false,
    eyeY: worldEyeHeight,
    resetSpawn: null,
  });
  const [worldStatus, setWorldStatus] = useState("Building world");
  const [assetProgress, setAssetProgress] = useState({ loaded: 0, total: 0 });
  const [exploring, setExploring] = useState(false);
  const { columns, rows } = getWorldDimensions(world);
  const worldReady = worldStatus === "Ready" || worldStatus === "Ready with asset issue";

  useEffect(() => {
    const mount = mountRef.current;
    if (!mount) return undefined;

    let disposed = false;
    const resources = [];
    const { columns: worldColumns, rows: worldRows, cellSize } = getWorldDimensions(world);
    const solidKeys = getWorldSolidKeys(world);
    const scene = new THREE.Scene();
    const clock = new THREE.Clock();
    scene.background = createGradientTexture("#213033", "#060809");
    scene.fog = new THREE.Fog("#060809", cellSize * 9, cellSize * 26);
    resources.push(scene.background);

    const camera = new THREE.PerspectiveCamera(70, mount.clientWidth / mount.clientHeight, 0.04, 120);
    camera.rotation.order = "YXZ";
    setWorldCameraPose(camera, world);
    const renderer = new THREE.WebGLRenderer({
      antialias: true,
      alpha: false,
      powerPreference: "high-performance",
    });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
    renderer.setSize(Math.max(1, mount.clientWidth), Math.max(1, mount.clientHeight));
    renderer.outputColorSpace = THREE.SRGBColorSpace;
    renderer.toneMapping = THREE.ACESFilmicToneMapping;
    renderer.toneMappingExposure = 1.08;
    mount.appendChild(renderer.domElement);

    const hemi = new THREE.HemisphereLight("#fff8e8", "#132223", 1.1);
    const sun = new THREE.DirectionalLight("#ffe2bf", 2.15);
    sun.position.set(-4.2, 7.8, 4.8);
    const fill = new THREE.DirectionalLight("#86e6ec", 0.92);
    fill.position.set(5.5, 3.4, -5.2);
    scene.add(hemi, sun, fill);

    function track(resource) {
      resources.push(resource);
      return resource;
    }

    const floorGeometry = track(new THREE.BoxGeometry(cellSize * 0.96, cellSize * 0.08, cellSize * 0.96));
    const floorMaterial = track(new THREE.MeshStandardMaterial({ color: "#253f3d", roughness: 0.82, metalness: 0.02 }));
    const floorMesh = new THREE.InstancedMesh(floorGeometry, floorMaterial, worldColumns * worldRows);
    const matrix = new THREE.Matrix4();
    const position = new THREE.Vector3();
    const quaternion = new THREE.Quaternion();
    const scale = new THREE.Vector3(1, 1, 1);
    let floorIndex = 0;
    for (let y = 0; y < worldRows; y += 1) {
      for (let x = 0; x < worldColumns; x += 1) {
        position.copy(getWorldCellCenter(x, y, world, -cellSize * 0.04));
        matrix.compose(position, quaternion, scale);
        floorMesh.setMatrixAt(floorIndex, matrix);
        floorIndex += 1;
      }
    }
    floorMesh.instanceMatrix.needsUpdate = true;
    scene.add(floorMesh);

    const gridSize = Math.max(worldColumns, worldRows) * cellSize;
    const gridHelper = new THREE.GridHelper(gridSize, Math.max(worldColumns, worldRows), "#426261", "#253636");
    gridHelper.position.y = cellSize * 0.025;
    gridHelper.position.x = ((worldColumns % 2) * cellSize) / 2 - cellSize / 2;
    gridHelper.position.z = ((worldRows % 2) * cellSize) / 2 - cellSize / 2;
    resources.push(gridHelper.geometry, gridHelper.material);
    scene.add(gridHelper);

    const wallPlacements = world.placements.filter((placement) => placement.type === "structure" && placement.itemId === "wall");
    if (wallPlacements.length) {
      const wallGeometry = track(new THREE.BoxGeometry(cellSize * 0.95, cellSize * 1.95, cellSize * 0.95));
      const wallMaterial = track(new THREE.MeshStandardMaterial({ color: "#d6c28d", roughness: 0.76, metalness: 0.04 }));
      const wallMesh = new THREE.InstancedMesh(wallGeometry, wallMaterial, wallPlacements.length);
      wallPlacements.forEach((placement, index) => {
        position.copy(getWorldCellCenter(placement.x, placement.y, world, placement.elevation));
        position.y += cellSize * 0.975;
        matrix.compose(position, quaternion, new THREE.Vector3(placement.scale ?? 1, 1, placement.scale ?? 1));
        wallMesh.setMatrixAt(index, matrix);
      });
      wallMesh.instanceMatrix.needsUpdate = true;
      scene.add(wallMesh);
    }

    const floorPlacements = world.placements.filter((placement) => placement.type === "structure" && placement.itemId === "floor");
    if (floorPlacements.length) {
      const accentFloorGeometry = track(new THREE.BoxGeometry(cellSize * 0.82, cellSize * 0.09, cellSize * 0.82));
      const accentFloorMaterial = track(new THREE.MeshStandardMaterial({ color: "#315755", roughness: 0.74, metalness: 0.03 }));
      const accentFloorMesh = new THREE.InstancedMesh(accentFloorGeometry, accentFloorMaterial, floorPlacements.length);
      floorPlacements.forEach((placement, index) => {
        position.copy(getWorldCellCenter(placement.x, placement.y, world, (placement.elevation || 0) + cellSize * 0.02));
        matrix.compose(position, quaternion, new THREE.Vector3(placement.scale ?? 1, 1, placement.scale ?? 1));
        accentFloorMesh.setMatrixAt(index, matrix);
      });
      accentFloorMesh.instanceMatrix.needsUpdate = true;
      scene.add(accentFloorMesh);
    }

    const doorMaterial = track(new THREE.MeshStandardMaterial({ color: "#f47d69", roughness: 0.58, metalness: 0.02 }));
    const doorPostGeometry = track(new THREE.BoxGeometry(cellSize * 0.14, cellSize * 1.45, cellSize * 0.16));
    const doorBeamGeometry = track(new THREE.BoxGeometry(cellSize * 0.9, cellSize * 0.16, cellSize * 0.18));
    world.placements
      .filter((placement) => placement.type === "structure" && placement.itemId === "door")
      .forEach((placement) => {
        const group = new THREE.Group();
        const base = getWorldCellCenter(placement.x, placement.y, world, placement.elevation);
        group.position.copy(base);
        group.rotation.y = THREE.MathUtils.degToRad(Number(placement.rotation) || 0);
        [
          [-cellSize * 0.38, cellSize * 0.72, 0, doorPostGeometry],
          [cellSize * 0.38, cellSize * 0.72, 0, doorPostGeometry],
          [0, cellSize * 1.45, 0, doorBeamGeometry],
        ].forEach(([x, y, z, geometry]) => {
          const mesh = new THREE.Mesh(geometry, doorMaterial);
          mesh.position.set(x, y, z);
          group.add(mesh);
        });
        scene.add(group);
      });

    const markerGeometry = track(new THREE.BoxGeometry(cellSize * 0.28, cellSize * 0.28, cellSize * 0.28));
    const lightMaterial = track(new THREE.MeshStandardMaterial({ color: "#28e0ea", emissive: "#28e0ea", emissiveIntensity: 1.55 }));
    world.placements
      .filter((placement) => placement.type === "structure" && placement.itemId === "light")
      .forEach((placement, index) => {
        const lightMarker = new THREE.Mesh(markerGeometry, lightMaterial);
        lightMarker.position.copy(getWorldCellCenter(placement.x, placement.y, world, placement.elevation));
        lightMarker.position.y += cellSize * 1.22;
        scene.add(lightMarker);
        if (index < 4) {
          const point = new THREE.PointLight("#76f8ff", 1.15, cellSize * 5.5, 1.7);
          point.position.copy(lightMarker.position);
          scene.add(point);
        }
      });

    const spawnGeometry = track(new THREE.BoxGeometry(cellSize * 0.62, cellSize * 0.1, cellSize * 0.62));
    const spawnMaterial = track(new THREE.MeshStandardMaterial({ color: "#91f0a8", emissive: "#2c8c52", emissiveIntensity: 0.38 }));
    world.placements
      .filter((placement) => placement.type === "structure" && placement.itemId === "spawn")
      .forEach((placement) => {
        const spawnPad = new THREE.Mesh(spawnGeometry, spawnMaterial);
        spawnPad.position.copy(getWorldCellCenter(placement.x, placement.y, world, (placement.elevation || 0) + cellSize * 0.04));
        spawnPad.rotation.y = THREE.MathUtils.degToRad(Number(placement.rotation) || 0);
        scene.add(spawnPad);
      });

    const assetGroup = new THREE.Group();
    scene.add(assetGroup);
    const loader = new GLTFLoader();
    const assetPlacements = world.placements.filter((placement) => placement.type === "asset");
    setAssetProgress({ loaded: 0, total: assetPlacements.length });
    setWorldStatus(assetPlacements.length ? "Loading assets" : "Ready");
    Promise.all(
      assetPlacements.map(async (placement) => {
        const asset = findAsset(placement.itemId);
        const baseModel = await loadWorldAsset(loader, asset);
        if (disposed) return;
        const model = cloneModel(baseModel);
        model.position.copy(getWorldCellCenter(placement.x, placement.y, world, placement.elevation));
        model.rotation.y += THREE.MathUtils.degToRad(Number(placement.rotation) || 0);
        model.scale.multiplyScalar(getAssetFitScale(asset, cellSize) * (Number(placement.scale) || 1));
        model.name = `World_${asset.id}_${placement.x}_${placement.y}`;
        assetGroup.add(model);
        setAssetProgress((current) => ({ ...current, loaded: Math.min(current.total, current.loaded + 1) }));
      }),
    )
      .then(() => {
        if (!disposed) {
          setAssetProgress({ loaded: assetPlacements.length, total: assetPlacements.length });
          setWorldStatus("Ready");
        }
      })
      .catch(() => {
        if (!disposed) setWorldStatus("Ready with asset issue");
      });

    const movement = new THREE.Vector3();
    const forward = new THREE.Vector3();
    const right = new THREE.Vector3();

    function resize() {
      const width = Math.max(1, mount.clientWidth);
      const height = Math.max(1, mount.clientHeight);
      camera.aspect = width / height;
      camera.updateProjectionMatrix();
      renderer.setSize(width, height);
    }

    function handlePointerLockChange() {
      const locked = document.pointerLockElement === renderer.domElement;
      stateRef.current.pointerLocked = locked;
      setExploring(locked);
      if (!locked) {
        stateRef.current.keys.clear();
        if (document.fullscreenElement === mount.parentElement) {
          document.exitFullscreen?.().catch(() => undefined);
        }
      }
    }

    function handleMouseMove(event) {
      if (!stateRef.current.pointerLocked) return;
      const euler = new THREE.Euler(0, 0, 0, "YXZ");
      euler.setFromQuaternion(camera.quaternion);
      euler.y -= event.movementX * 0.0021;
      euler.x -= event.movementY * 0.0021;
      euler.x = Math.max(-Math.PI / 2 + 0.05, Math.min(Math.PI / 2 - 0.05, euler.x));
      camera.quaternion.setFromEuler(euler);
    }

    function handleKeyDown(event) {
      if (!stateRef.current.pointerLocked) return;
      if (event.code === "Escape") {
        event.preventDefault();
        document.exitPointerLock?.();
        if (document.fullscreenElement === mount.parentElement) {
          document.exitFullscreen?.().catch(() => undefined);
        }
        return;
      }
      if (["KeyW", "KeyA", "KeyS", "KeyD", "ArrowUp", "ArrowLeft", "ArrowDown", "ArrowRight"].includes(event.code)) {
        event.preventDefault();
        stateRef.current.keys.add(event.code);
      }
    }

    function handleKeyUp(event) {
      stateRef.current.keys.delete(event.code);
    }

    function stepPlayer(delta) {
      const current = stateRef.current;
      if (!current.pointerLocked) return;
      movement.set(0, 0, 0);
      camera.getWorldDirection(forward);
      forward.y = 0;
      forward.normalize();
      right.crossVectors(forward, camera.up).normalize();
      if (current.keys.has("KeyW") || current.keys.has("ArrowUp")) movement.add(forward);
      if (current.keys.has("KeyS") || current.keys.has("ArrowDown")) movement.sub(forward);
      if (current.keys.has("KeyD") || current.keys.has("ArrowRight")) movement.add(right);
      if (current.keys.has("KeyA") || current.keys.has("ArrowLeft")) movement.sub(right);
      if (movement.lengthSq() === 0) return;
      movement.normalize().multiplyScalar(worldMoveSpeed * cellSize * delta);
      const next = camera.position.clone().add(movement);
      next.y = current.eyeY;
      if (canOccupyWorldPosition(next, world, solidKeys, cellSize)) {
        camera.position.copy(next);
        return;
      }
      const xOnly = camera.position.clone();
      xOnly.x = next.x;
      if (canOccupyWorldPosition(xOnly, world, solidKeys, cellSize)) camera.position.x = next.x;
      const zOnly = camera.position.clone();
      zOnly.z = next.z;
      if (canOccupyWorldPosition(zOnly, world, solidKeys, cellSize)) camera.position.z = next.z;
    }

    function animate() {
      const delta = Math.min(clock.getDelta(), 0.05);
      stepPlayer(delta);
      renderer.render(scene, camera);
      stateRef.current.animationId = requestAnimationFrame(animate);
    }

    const resizeObserver = typeof ResizeObserver === "undefined" ? null : new ResizeObserver(resize);
    resizeObserver?.observe(mount);
    window.addEventListener("resize", resize);
    document.addEventListener("pointerlockchange", handlePointerLockChange);
    document.addEventListener("mousemove", handleMouseMove);
    document.addEventListener("keydown", handleKeyDown);
    document.addEventListener("keyup", handleKeyUp);

    const spawnPose = getWorldSpawnPose(world);
    stateRef.current = {
      renderer,
      camera,
      world,
      solidKeys,
      cellSize,
      keys: new Set(),
      pointerLocked: false,
      eyeY: spawnPose.position.y,
      animationId: 0,
      resetSpawn: () => {
        setWorldCameraPose(camera, world);
        stateRef.current.eyeY = getWorldSpawnPose(world).position.y;
      },
    };
    animate();

    return () => {
      disposed = true;
      if (document.pointerLockElement === renderer.domElement) document.exitPointerLock?.();
      resizeObserver?.disconnect();
      window.removeEventListener("resize", resize);
      document.removeEventListener("pointerlockchange", handlePointerLockChange);
      document.removeEventListener("mousemove", handleMouseMove);
      document.removeEventListener("keydown", handleKeyDown);
      document.removeEventListener("keyup", handleKeyUp);
      cancelAnimationFrame(stateRef.current.animationId);
      resources.forEach((resource) => resource?.dispose?.());
      renderer.dispose();
      if (renderer.domElement.parentNode === mount) {
        mount.removeChild(renderer.domElement);
      }
    };
  }, [world]);

  async function enterWorld() {
    const renderer = stateRef.current.renderer;
    const mount = mountRef.current;
    if (!renderer || !mount) return;
    stateRef.current.gameActive = true;
    const shell = mount.parentElement;
    if (shell?.requestFullscreen && !document.fullscreenElement && window.innerWidth >= 900) {
      await shell.requestFullscreen().catch(() => undefined);
    }
    const lockRequest = renderer.domElement.requestPointerLock?.();
    lockRequest?.catch?.(() => undefined);
  }

  async function exitWorld() {
    stateRef.current.gameActive = false;
    stateRef.current.keys?.clear?.();
    if (document.pointerLockElement) document.exitPointerLock?.();
    if (document.fullscreenElement === mountRef.current?.parentElement) {
      await document.exitFullscreen?.().catch(() => undefined);
    }
  }

  function resetSpawn() {
    stateRef.current.resetSpawn?.();
  }

  return (
    <div
      className="world-viewport-shell"
      data-world-status={worldReady ? "ready" : "loading"}
      data-exploring={exploring ? "true" : "false"}
      data-world-assets={`${assetProgress.loaded}/${assetProgress.total}`}
    >
      <div ref={mountRef} className="world-viewport" aria-label={`${world.name} interactive 3D world`} />
      <div className="world-viewport-overlay">
        <div className="world-viewport-actions" aria-label="3D world controls">
          <button type="button" onClick={enterWorld} disabled={!worldReady}>
            <DoorOpen aria-hidden="true" />
            <span>Enter World</span>
          </button>
          <button type="button" onClick={exitWorld} disabled={!exploring && !hudState.gameActive}>
            <Pause aria-hidden="true" />
            <span>Exit</span>
          </button>
          <button type="button" onClick={resetSpawn} disabled={!worldReady}>
            <Sparkles aria-hidden="true" />
            <span>Reset Spawn</span>
          </button>
        </div>
        <div className="world-viewport-status" aria-label="3D world status">
          <span>
            <Box aria-hidden="true" />
            {worldStatus}
          </span>
          <span>
            <Package aria-hidden="true" />
            {world.placements.length}
          </span>
          <span>
            <Grid2X2 aria-hidden="true" />
            {columns} x {rows}
          </span>
        </div>
      </div>
    </div>
  );
}

function WorldViewport({ world, worldTargets = [], onTravel }) {
  const mountRef = useRef(null);
  const stateRef = useRef({
    renderer: null,
    camera: null,
    world,
    solidKeys: new Set(),
    cellSize: 1,
    keys: new Set(),
    pointerLocked: false,
    gameActive: false,
    controlMode: "free",
    yaw: 0,
    pitch: -0.18,
    player: null,
    enemies: [],
    entities: [],
    projectiles: [],
    cooldowns: { primary: 0, secondary: 0, special: 0 },
    cooldownMax: { primary: 1, secondary: 1, special: 1 },
    downedTimer: 0,
    resetSpawn: null,
    nearbyDoor: null,
    nearbyDoorKey: "",
  });
  const [worldStatus, setWorldStatus] = useState("Building world");
  const [assetProgress, setAssetProgress] = useState({ loaded: 0, total: 0 });
  const [exploring, setExploring] = useState(false);
  const [hudState, setHudState] = useState({
    controlMode: "free",
    gameActive: false,
    label: "Free camera",
    playerName: "",
    health: 0,
    maxHealth: 0,
    enemiesAlive: 0,
    enemyHealth: 0,
    cooldowns: { primary: 0, secondary: 0, special: 0 },
  });
  const [doorPrompt, setDoorPrompt] = useState(null);
  const { columns, rows } = getWorldDimensions(world);
  const worldReady = worldStatus === "Ready" || worldStatus === "Ready with asset issue";

  const requestDoorTravel = useCallback(
    async (targetWorldId) => {
      if (!targetWorldId) return;
      if (document.pointerLockElement) document.exitPointerLock?.();
      if (document.fullscreenElement === mountRef.current?.parentElement) {
        await document.exitFullscreen?.().catch(() => undefined);
      }
      const targetName = worldTargets.find((target) => target.id === targetWorldId)?.name;
      onTravel?.(targetWorldId, targetName ? `Entered ${targetName}` : "Entered linked world");
    },
    [onTravel, worldTargets],
  );

  useEffect(() => {
    const mount = mountRef.current;
    if (!mount) return undefined;

    let disposed = false;
    const resources = [];
    const { columns: worldColumns, rows: worldRows, cellSize } = getWorldDimensions(world);
    const solidKeys = getWorldSolidKeys(world);
    const targetNameById = new Map(worldTargets.map((target) => [target.id, target.name]));
    const travelDoors = world.placements
      .filter((placement) => placement.type === "structure" && placement.itemId === "door" && placement.targetWorldId && targetNameById.has(placement.targetWorldId))
      .map((placement) => ({
        placement,
        key: `${placement.x}:${placement.y}:${placement.targetWorldId}`,
        targetWorldId: placement.targetWorldId,
        targetName: targetNameById.get(placement.targetWorldId),
        position: getWorldCellCenter(placement.x, placement.y, world, placement.elevation),
      }));
    const playablePlacement = getWorldPlayablePlacement(world);
    const playableKey = playablePlacement ? `${playablePlacement.itemId}:${playablePlacement.x}:${playablePlacement.y}` : "";
    const scene = new THREE.Scene();
    const clock = new THREE.Clock();
    scene.background = createGradientTexture("#213033", "#060809");
    scene.fog = new THREE.Fog("#060809", cellSize * 9, cellSize * 26);
    resources.push(scene.background);

    const spawnPose = getWorldSpawnPose(world);
    const camera = new THREE.PerspectiveCamera(70, mount.clientWidth / mount.clientHeight, 0.04, 120);
    camera.rotation.order = "YXZ";
    setWorldCameraPose(camera, world);
    const renderer = new THREE.WebGLRenderer({
      antialias: true,
      alpha: false,
      powerPreference: "high-performance",
    });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
    renderer.setSize(Math.max(1, mount.clientWidth), Math.max(1, mount.clientHeight));
    renderer.outputColorSpace = THREE.SRGBColorSpace;
    renderer.toneMapping = THREE.ACESFilmicToneMapping;
    renderer.toneMappingExposure = 1.08;
    mount.appendChild(renderer.domElement);

    const hemi = new THREE.HemisphereLight("#fff8e8", "#132223", 1.1);
    const sun = new THREE.DirectionalLight("#ffe2bf", 2.15);
    sun.position.set(-4.2, 7.8, 4.8);
    const fill = new THREE.DirectionalLight("#86e6ec", 0.92);
    fill.position.set(5.5, 3.4, -5.2);
    scene.add(hemi, sun, fill);

    function track(resource) {
      resources.push(resource);
      return resource;
    }

    const floorGeometry = track(new THREE.BoxGeometry(cellSize * 0.96, cellSize * 0.08, cellSize * 0.96));
    const floorMaterial = track(new THREE.MeshStandardMaterial({ color: "#253f3d", roughness: 0.82, metalness: 0.02 }));
    const floorMesh = new THREE.InstancedMesh(floorGeometry, floorMaterial, worldColumns * worldRows);
    const matrix = new THREE.Matrix4();
    const position = new THREE.Vector3();
    const quaternion = new THREE.Quaternion();
    const scale = new THREE.Vector3(1, 1, 1);
    let floorIndex = 0;
    for (let y = 0; y < worldRows; y += 1) {
      for (let x = 0; x < worldColumns; x += 1) {
        position.copy(getWorldCellCenter(x, y, world, -cellSize * 0.04));
        matrix.compose(position, quaternion, scale);
        floorMesh.setMatrixAt(floorIndex, matrix);
        floorIndex += 1;
      }
    }
    floorMesh.instanceMatrix.needsUpdate = true;
    scene.add(floorMesh);

    const gridSize = Math.max(worldColumns, worldRows) * cellSize;
    const gridHelper = new THREE.GridHelper(gridSize, Math.max(worldColumns, worldRows), "#426261", "#253636");
    gridHelper.position.y = cellSize * 0.025;
    gridHelper.position.x = ((worldColumns % 2) * cellSize) / 2 - cellSize / 2;
    gridHelper.position.z = ((worldRows % 2) * cellSize) / 2 - cellSize / 2;
    resources.push(gridHelper.geometry, gridHelper.material);
    scene.add(gridHelper);

    const wallPlacements = world.placements.filter((placement) => placement.type === "structure" && placement.itemId === "wall");
    if (wallPlacements.length) {
      const wallGeometry = track(new THREE.BoxGeometry(cellSize * 0.95, cellSize * 1.95, cellSize * 0.95));
      const wallMaterial = track(new THREE.MeshStandardMaterial({ color: "#d6c28d", roughness: 0.76, metalness: 0.04 }));
      const wallMesh = new THREE.InstancedMesh(wallGeometry, wallMaterial, wallPlacements.length);
      wallPlacements.forEach((placement, index) => {
        position.copy(getWorldCellCenter(placement.x, placement.y, world, placement.elevation));
        position.y += cellSize * 0.975;
        matrix.compose(position, quaternion, new THREE.Vector3(placement.scale ?? 1, 1, placement.scale ?? 1));
        wallMesh.setMatrixAt(index, matrix);
      });
      wallMesh.instanceMatrix.needsUpdate = true;
      scene.add(wallMesh);
    }

    const floorPlacements = world.placements.filter((placement) => placement.type === "structure" && placement.itemId === "floor");
    if (floorPlacements.length) {
      const accentFloorGeometry = track(new THREE.BoxGeometry(cellSize * 0.82, cellSize * 0.09, cellSize * 0.82));
      const accentFloorMaterial = track(new THREE.MeshStandardMaterial({ color: "#315755", roughness: 0.74, metalness: 0.03 }));
      const accentFloorMesh = new THREE.InstancedMesh(accentFloorGeometry, accentFloorMaterial, floorPlacements.length);
      floorPlacements.forEach((placement, index) => {
        position.copy(getWorldCellCenter(placement.x, placement.y, world, (placement.elevation || 0) + cellSize * 0.02));
        matrix.compose(position, quaternion, new THREE.Vector3(placement.scale ?? 1, 1, placement.scale ?? 1));
        accentFloorMesh.setMatrixAt(index, matrix);
      });
      accentFloorMesh.instanceMatrix.needsUpdate = true;
      scene.add(accentFloorMesh);
    }

    const doorMaterial = track(new THREE.MeshStandardMaterial({ color: "#f47d69", roughness: 0.58, metalness: 0.02 }));
    const doorPostGeometry = track(new THREE.BoxGeometry(cellSize * 0.14, cellSize * 1.45, cellSize * 0.16));
    const doorBeamGeometry = track(new THREE.BoxGeometry(cellSize * 0.9, cellSize * 0.16, cellSize * 0.18));
    world.placements
      .filter((placement) => placement.type === "structure" && placement.itemId === "door")
      .forEach((placement) => {
        const group = new THREE.Group();
        const base = getWorldCellCenter(placement.x, placement.y, world, placement.elevation);
        group.position.copy(base);
        group.rotation.y = THREE.MathUtils.degToRad(Number(placement.rotation) || 0);
        [
          [-cellSize * 0.38, cellSize * 0.72, 0, doorPostGeometry],
          [cellSize * 0.38, cellSize * 0.72, 0, doorPostGeometry],
          [0, cellSize * 1.45, 0, doorBeamGeometry],
        ].forEach(([x, y, z, geometry]) => {
          const mesh = new THREE.Mesh(geometry, doorMaterial);
          mesh.position.set(x, y, z);
          group.add(mesh);
        });
        scene.add(group);
      });

    const markerGeometry = track(new THREE.BoxGeometry(cellSize * 0.28, cellSize * 0.28, cellSize * 0.28));
    const lightMaterial = track(new THREE.MeshStandardMaterial({ color: "#28e0ea", emissive: "#28e0ea", emissiveIntensity: 1.55 }));
    world.placements
      .filter((placement) => placement.type === "structure" && placement.itemId === "light")
      .forEach((placement, index) => {
        const lightMarker = new THREE.Mesh(markerGeometry, lightMaterial);
        lightMarker.position.copy(getWorldCellCenter(placement.x, placement.y, world, placement.elevation));
        lightMarker.position.y += cellSize * 1.22;
        scene.add(lightMarker);
        if (index < 4) {
          const point = new THREE.PointLight("#76f8ff", 1.15, cellSize * 5.5, 1.7);
          point.position.copy(lightMarker.position);
          scene.add(point);
        }
      });

    const spawnGeometry = track(new THREE.BoxGeometry(cellSize * 0.62, cellSize * 0.1, cellSize * 0.62));
    const spawnMaterial = track(new THREE.MeshStandardMaterial({ color: "#91f0a8", emissive: "#2c8c52", emissiveIntensity: 0.38 }));
    world.placements
      .filter((placement) => placement.type === "structure" && placement.itemId === "spawn")
      .forEach((placement) => {
        const spawnPad = new THREE.Mesh(spawnGeometry, spawnMaterial);
        spawnPad.position.copy(getWorldCellCenter(placement.x, placement.y, world, (placement.elevation || 0) + cellSize * 0.04));
        spawnPad.rotation.y = THREE.MathUtils.degToRad(Number(placement.rotation) || 0);
        scene.add(spawnPad);
      });

    const assetGroup = new THREE.Group();
    scene.add(assetGroup);
    const healthBarGroup = new THREE.Group();
    scene.add(healthBarGroup);
    const projectileGroup = new THREE.Group();
    scene.add(projectileGroup);

    const healthBackMaterial = track(new THREE.MeshBasicMaterial({ color: "#1b2022", transparent: true, opacity: 0.82, depthTest: false }));
    const healthFillMaterial = track(new THREE.MeshBasicMaterial({ color: "#91f0a8", transparent: true, opacity: 0.95, depthTest: false }));
    const healthEnemyMaterial = track(new THREE.MeshBasicMaterial({ color: "#f47d69", transparent: true, opacity: 0.95, depthTest: false }));
    const healthPlaneGeometry = track(new THREE.PlaneGeometry(1, 0.1));
    const projectileGeometry = track(new THREE.SphereGeometry(cellSize * 0.07, 10, 10));
    const playerProjectileMaterial = track(new THREE.MeshBasicMaterial({ color: "#28e0ea" }));
    const enemyProjectileMaterial = track(new THREE.MeshBasicMaterial({ color: "#f47d69" }));
    const hitGeometry = track(new THREE.SphereGeometry(cellSize * 0.16, 12, 12));
    const hitMaterial = track(new THREE.MeshBasicMaterial({ color: "#fff1b8", transparent: true, opacity: 0.58 }));

    const current = {
      renderer,
      camera,
      world,
      solidKeys,
      cellSize,
      keys: new Set(),
      pointerLocked: false,
      gameActive: false,
      controlMode: playablePlacement ? "character" : "free",
      yaw: spawnPose.yaw,
      pitch: -0.18,
      player: null,
      enemies: [],
      entities: [],
      projectiles: [],
      effects: [],
      cooldowns: { primary: 0, secondary: 0, special: 0 },
      cooldownMax: { primary: 1, secondary: 1, special: 1 },
      downedTimer: 0,
      animationId: 0,
      lastHudAt: 0,
      resetSpawn: null,
      nearbyDoor: null,
      nearbyDoorKey: "",
    };
    stateRef.current = current;

    function publishHud(force = false) {
      const now = performance.now();
      if (!force && now - current.lastHudAt < 120) return;
      current.lastHudAt = now;
      const player = current.player;
      const playerName = player?.asset.shortName ?? "";
      const cooldowns = Object.fromEntries(
        Object.entries(current.cooldowns).map(([key, value]) => [key, Math.max(0, Number(value.toFixed(1)))]),
      );
      setHudState({
        controlMode: current.controlMode,
        gameActive: current.gameActive,
        label:
          current.controlMode === "character" && player
            ? current.gameActive
              ? `Controlling ${playerName}`
              : `Ready to enter ${playerName}`
            : "Free camera",
        playerName,
        health: player ? Math.max(0, Math.round(player.health)) : 0,
        maxHealth: player ? player.maxHealth : 0,
        enemiesAlive: current.enemies.filter((enemy) => enemy.alive).length,
        enemyHealth: Math.round(current.enemies.reduce((total, enemy) => total + (enemy.alive ? enemy.health : 0), 0)),
        cooldowns,
      });
    }

    function getTravelAnchorPosition() {
      if (current.controlMode === "character" && current.player?.group) {
        return current.player.group.position;
      }
      return camera.position;
    }

    function updateNearbyDoorPrompt() {
      if (!travelDoors.length) {
        if (current.nearbyDoorKey) {
          current.nearbyDoor = null;
          current.nearbyDoorKey = "";
          setDoorPrompt(null);
        }
        return;
      }
      const anchor = getTravelAnchorPosition();
      const nearestDoor = travelDoors
        .map((door) => {
          const dx = door.position.x - anchor.x;
          const dz = door.position.z - anchor.z;
          return { ...door, distance: Math.hypot(dx, dz) };
        })
        .filter((door) => door.distance <= cellSize * 1.12)
        .sort((a, b) => a.distance - b.distance)[0];
      const nextKey = nearestDoor?.key ?? "";
      if (nextKey === current.nearbyDoorKey) return;
      current.nearbyDoor = nearestDoor ?? null;
      current.nearbyDoorKey = nextKey;
      setDoorPrompt(
        nearestDoor
          ? {
              targetWorldId: nearestDoor.targetWorldId,
              targetName: nearestDoor.targetName,
            }
          : null,
      );
    }

    function playEntityClip(entity, preferredName, fadeDuration = 0.12) {
      if (!entity.mixer || !entity.animations.length) return;
      const fallbackName = entity.alive
        ? entity.asset.defaultAnimation || entity.animations[0]?.name
        : "Death";
      const clip =
        entity.animations.find((item) => item.name === preferredName) ??
        entity.animations.find((item) => item.name === fallbackName) ??
        entity.animations[0];
      if (!clip) return;
      const nextAction = entity.mixer.clipAction(clip, entity.group);
      const oneShot = /Attack|Shoot|Draw|Hammer|Hit|Death|Release|Slam/i.test(clip.name);
      if (!oneShot && entity.activeClipName === clip.name) return;
      if (entity.activeAction) entity.activeAction.fadeOut(fadeDuration);
      nextAction.reset();
      nextAction.setLoop(oneShot ? THREE.LoopOnce : THREE.LoopRepeat, oneShot ? 1 : Infinity);
      nextAction.clampWhenFinished = oneShot;
      nextAction.fadeIn(fadeDuration).play();
      entity.activeAction = nextAction;
      entity.activeClipName = clip.name;
    }

    function createHealthBar(entity) {
      const group = new THREE.Group();
      const back = new THREE.Mesh(healthPlaneGeometry, healthBackMaterial);
      const fill = new THREE.Mesh(healthPlaneGeometry, isEnemyRole(entity.role) ? healthEnemyMaterial : healthFillMaterial);
      back.renderOrder = 20;
      fill.renderOrder = 21;
      fill.position.z = 0.002;
      group.add(back, fill);
      group.scale.set(cellSize * 0.78, cellSize * 0.78, cellSize * 0.78);
      healthBarGroup.add(group);
      return { group, fill };
    }

    function updateHealthBar(entity) {
      if (!entity.healthBar) return;
      const ratio = Math.max(0, Math.min(1, entity.health / entity.maxHealth));
      entity.healthBar.group.visible = entity.alive && ratio > 0;
      entity.healthBar.fill.scale.x = ratio;
      entity.healthBar.fill.position.x = -(1 - ratio) / 2;
      entity.healthBar.group.position.copy(entity.group.position);
      entity.healthBar.group.position.y += cellSize * 1.72;
      entity.healthBar.group.lookAt(camera.position);
    }

    function spawnHitEffect(worldPosition, color = "#fff1b8") {
      const material = hitMaterial.clone();
      material.color.set(color);
      const mesh = new THREE.Mesh(hitGeometry, material);
      mesh.position.copy(worldPosition);
      mesh.position.y += cellSize * 0.75;
      scene.add(mesh);
      current.effects.push({ mesh, material, ttl: 0.35, maxTtl: 0.35 });
    }

    function applyDamage(entity, amount) {
      if (!entity?.alive || amount <= 0) return;
      entity.health = Math.max(0, entity.health - amount);
      spawnHitEffect(entity.group.position, entity.kind === "player" ? "#f47d69" : "#fff1b8");
      if (entity.health <= 0) {
        entity.alive = false;
        if (entity.kind === "player") {
          current.downedTimer = 1.15;
          playEntityClip(entity, "Hit_Reaction");
        } else {
          playEntityClip(entity, "Death");
          entity.deathTimer = 0.85;
        }
      } else {
        playEntityClip(entity, "Hit_Reaction");
      }
      updateHealthBar(entity);
      publishHud(true);
    }

    function spawnProjectile({ owner, target, direction, damage, color, speed, range }) {
      const mesh = new THREE.Mesh(projectileGeometry, owner === "player" ? playerProjectileMaterial : enemyProjectileMaterial);
      const source = owner === "player" ? current.player : owner;
      const start = source.group.position.clone();
      start.y += cellSize * 0.85;
      mesh.position.copy(start);
      projectileGroup.add(mesh);
      const targetPosition = target?.group?.position?.clone() ?? start.clone().add(direction.clone().multiplyScalar(range));
      targetPosition.y += cellSize * 0.65;
      const velocity = targetPosition.sub(start).normalize().multiplyScalar((speed ?? 7) * cellSize);
      current.projectiles.push({
        mesh,
        owner,
        target,
        damage,
        velocity,
        ttl: Math.max(0.35, (range ?? 5) / (speed ?? 7)),
      });
    }

    function removeProjectile(projectile) {
      projectileGroup.remove(projectile.mesh);
    }

    function findAttackTargets(attack, origin, direction) {
      const range = (attack.range ?? current.player.stats.range) * cellSize;
      return current.enemies
        .filter((enemy) => enemy.alive)
        .map((enemy) => {
          const toEnemy = enemy.group.position.clone().sub(origin);
          const distance = toEnemy.length();
          const alignment = distance > 0 ? toEnemy.clone().normalize().dot(direction) : 1;
          return { enemy, distance, alignment };
        })
        .filter(({ enemy, distance, alignment }) => {
          if (distance > range) return false;
          if (attack.type === "burst") return true;
          if (attack.type === "melee") return alignment > -0.15;
          return hasWorldLineOfSight(origin, enemy.group.position, world, solidKeys, cellSize);
        })
        .sort((a, b) => b.alignment - a.alignment || a.distance - b.distance);
    }

    function performPlayerAttack(slot) {
      const player = current.player;
      if (!player?.alive || current.downedTimer > 0 || current.cooldowns[slot] > 0) return;
      const slotIndex = slot === "secondary" ? 1 : slot === "special" ? 2 : 0;
      const attack =
        player.attacks[slotIndex] ??
        player.attacks[0] ?? {
          label: "Strike",
          type: "melee",
          damage: player.stats.damage,
          range: player.stats.range,
          cooldown: player.stats.cooldown,
        };
      current.cooldowns[slot] = attack.cooldown ?? player.stats.cooldown;
      current.cooldownMax[slot] = current.cooldowns[slot];
      playEntityClip(player, attack.clip);

      const direction = new THREE.Vector3(Math.sin(current.yaw), 0, -Math.cos(current.yaw)).normalize();
      if (attack.type === "dash") {
        const next = player.group.position.clone().add(direction.multiplyScalar((attack.range ?? 1.2) * cellSize));
        if (canOccupyWorldPosition(next, world, solidKeys, cellSize)) player.group.position.copy(next);
        publishHud(true);
        return;
      }
      if (attack.type === "guard") {
        player.health = Math.min(player.maxHealth, player.health + player.maxHealth * 0.08);
        publishHud(true);
        return;
      }

      const targets = findAttackTargets(attack, player.group.position, direction);
      if (attack.type === "ranged") {
        const target = targets[0]?.enemy;
        if (target) {
          spawnProjectile({
            owner: "player",
            target,
            direction,
            damage: attack.damage ?? player.stats.damage,
            speed: attack.projectileSpeed ?? 7,
            range: attack.range ?? player.stats.range,
          });
        }
      } else {
        const affected = attack.type === "burst" ? targets : targets.slice(0, 2);
        affected.forEach(({ enemy }) => applyDamage(enemy, attack.damage ?? player.stats.damage));
      }
      publishHud(true);
    }

    function resetEncounter() {
      if (current.controlMode === "free") {
        setWorldCameraPose(camera, world);
        current.yaw = getWorldSpawnPose(world).yaw;
      }
      current.projectiles.forEach(removeProjectile);
      current.projectiles = [];
      current.effects.forEach((effect) => {
        scene.remove(effect.mesh);
        effect.material.dispose();
      });
      current.effects = [];
      current.entities.forEach((entity) => {
        entity.group.visible = true;
        entity.group.position.copy(entity.initialPosition);
        entity.group.rotation.y = entity.initialYaw;
        entity.health = entity.maxHealth;
        entity.alive = true;
        entity.deathTimer = 0;
        entity.attackCooldown = 0;
        entity.path = [];
        entity.pathCooldown = 0;
        playEntityClip(entity, entity.asset.defaultAnimation);
        updateHealthBar(entity);
      });
      current.cooldowns = { primary: 0, secondary: 0, special: 0 };
      current.downedTimer = 0;
      publishHud(true);
    }

    current.resetSpawn = resetEncounter;

    const loader = new GLTFLoader();
    const assetPlacements = world.placements.filter((placement) => placement.type === "asset");
    setAssetProgress({ loaded: 0, total: assetPlacements.length });
    setWorldStatus(assetPlacements.length ? "Loading assets" : "Ready");
    Promise.all(
      assetPlacements.map(async (placement) => {
        const asset = findAsset(placement.itemId);
        const baseAsset = await loadWorldAsset(loader, asset);
        if (disposed) return null;
        const model = cloneModel(baseAsset.model);
        model.position.copy(getWorldCellCenter(placement.x, placement.y, world, placement.elevation));
        model.rotation.y += THREE.MathUtils.degToRad(Number(placement.rotation) || 0);
        model.scale.multiplyScalar(getAssetFitScale(asset, cellSize) * (Number(placement.scale) || 1));
        model.name = `World_${asset.id}_${placement.x}_${placement.y}`;
        assetGroup.add(model);

        const role = placement.combat?.role ?? asset.combat?.role ?? "neutral";
        const stats = getResolvedCombatStats(asset, placement.combat);
        const placementKey = `${placement.itemId}:${placement.x}:${placement.y}`;
        const entity = {
          id: placementKey,
          placement,
          asset,
          group: model,
          initialPosition: model.position.clone(),
          initialYaw: model.rotation.y,
          mixer: baseAsset.animations.length ? new THREE.AnimationMixer(model) : null,
          animations: baseAsset.animations,
          activeAction: null,
          activeClipName: "",
          role,
          kind: placementKey === playableKey ? "player" : isEnemyRole(role) ? "enemy" : "neutral",
          stats,
          attacks: asset.combat?.attacks ?? [],
          health: stats.maxHealth,
          maxHealth: stats.maxHealth,
          alive: true,
          deathTimer: 0,
          attackCooldown: 0,
          path: [],
          pathCooldown: 0,
          healthBar: null,
        };
        current.entities.push(entity);
        if (entity.kind === "player") current.player = entity;
        if (entity.kind === "enemy") {
          entity.healthBar = createHealthBar(entity);
          current.enemies.push(entity);
        }
        playEntityClip(entity, asset.defaultAnimation, 0);
        updateHealthBar(entity);
        setAssetProgress((progress) => ({ ...progress, loaded: Math.min(progress.total, progress.loaded + 1) }));
        return entity;
      }),
    )
      .then(() => {
        if (disposed) return;
        current.controlMode = current.player ? "character" : "free";
        if (current.player) {
          const nearestEnemy = current.enemies
            .filter((enemy) => enemy.alive)
            .map((enemy) => ({ enemy, distance: enemy.group.position.distanceTo(current.player.group.position) }))
            .sort((a, b) => a.distance - b.distance)[0]?.enemy;
          if (nearestEnemy) {
            const toEnemy = nearestEnemy.group.position.clone().sub(current.player.group.position);
            current.yaw = Math.atan2(toEnemy.x, -toEnemy.z);
          } else {
            current.yaw = current.player.group.rotation.y;
          }
        }
        setAssetProgress({ loaded: assetPlacements.length, total: assetPlacements.length });
        setWorldStatus("Ready");
        publishHud(true);
      })
      .catch(() => {
        if (!disposed) {
          setWorldStatus("Ready with asset issue");
          publishHud(true);
        }
      });

    const movement = new THREE.Vector3();
    const forward = new THREE.Vector3();
    const right = new THREE.Vector3();

    function resize() {
      const width = Math.max(1, mount.clientWidth);
      const height = Math.max(1, mount.clientHeight);
      camera.aspect = width / height;
      camera.updateProjectionMatrix();
      renderer.setSize(width, height);
    }

    function handlePointerLockChange() {
      const locked = document.pointerLockElement === renderer.domElement;
      current.pointerLocked = locked;
      if (locked) current.gameActive = true;
      setExploring(locked);
      if (!locked) {
        current.keys.clear();
        if (document.fullscreenElement === mount.parentElement) {
          document.exitFullscreen?.().catch(() => undefined);
        }
      }
      publishHud(true);
    }

    function handleMouseMove(event) {
      if (!current.pointerLocked) return;
      if (current.controlMode === "character") {
        current.yaw -= event.movementX * 0.0021;
        current.pitch = Math.max(-0.7, Math.min(0.45, current.pitch - event.movementY * 0.0015));
        return;
      }
      const euler = new THREE.Euler(0, 0, 0, "YXZ");
      euler.setFromQuaternion(camera.quaternion);
      euler.y -= event.movementX * 0.0021;
      euler.x -= event.movementY * 0.0021;
      euler.x = Math.max(-Math.PI / 2 + 0.05, Math.min(Math.PI / 2 - 0.05, euler.x));
      camera.quaternion.setFromEuler(euler);
    }

    function handleMouseDown(event) {
      if (!current.gameActive || current.controlMode !== "character") return;
      event.preventDefault();
      if (event.button === 0) performPlayerAttack("primary");
      if (event.button === 2) performPlayerAttack("secondary");
    }

    function handleContextMenu(event) {
      if (current.gameActive && current.controlMode === "character") event.preventDefault();
    }

    function handleKeyDown(event) {
      if (event.code === "KeyE" && current.nearbyDoor?.targetWorldId) {
        event.preventDefault();
        requestDoorTravel(current.nearbyDoor.targetWorldId);
        return;
      }
      if (!current.pointerLocked && !current.gameActive) return;
      if (event.code === "Escape") {
        event.preventDefault();
        current.gameActive = false;
        document.exitPointerLock?.();
        if (document.fullscreenElement === mount.parentElement) {
          document.exitFullscreen?.().catch(() => undefined);
        }
        publishHud(true);
        return;
      }
      if (event.code === "Space" && current.controlMode === "character") {
        event.preventDefault();
        performPlayerAttack("special");
        return;
      }
      if (current.controlMode === "character" && ["KeyJ", "KeyK", "KeyL"].includes(event.code)) {
        event.preventDefault();
        if (event.code === "KeyJ") performPlayerAttack("primary");
        if (event.code === "KeyK") performPlayerAttack("secondary");
        if (event.code === "KeyL") performPlayerAttack("special");
        return;
      }
      if (["KeyW", "KeyA", "KeyS", "KeyD", "ArrowUp", "ArrowLeft", "ArrowDown", "ArrowRight"].includes(event.code)) {
        event.preventDefault();
        current.keys.add(event.code);
      }
    }

    function handleKeyUp(event) {
      current.keys.delete(event.code);
    }

    function stepFreeCamera(delta) {
      if (!current.pointerLocked) return;
      movement.set(0, 0, 0);
      camera.getWorldDirection(forward);
      forward.y = 0;
      forward.normalize();
      right.crossVectors(forward, camera.up).normalize();
      if (current.keys.has("KeyW") || current.keys.has("ArrowUp")) movement.add(forward);
      if (current.keys.has("KeyS") || current.keys.has("ArrowDown")) movement.sub(forward);
      if (current.keys.has("KeyD") || current.keys.has("ArrowRight")) movement.add(right);
      if (current.keys.has("KeyA") || current.keys.has("ArrowLeft")) movement.sub(right);
      if (movement.lengthSq() === 0) return;
      movement.normalize().multiplyScalar(worldMoveSpeed * cellSize * delta);
      const next = camera.position.clone().add(movement);
      next.y = spawnPose.position.y;
      if (canOccupyWorldPosition(next, world, solidKeys, cellSize)) {
        camera.position.copy(next);
        return;
      }
      const xOnly = camera.position.clone();
      xOnly.x = next.x;
      if (canOccupyWorldPosition(xOnly, world, solidKeys, cellSize)) camera.position.x = next.x;
      const zOnly = camera.position.clone();
      zOnly.z = next.z;
      if (canOccupyWorldPosition(zOnly, world, solidKeys, cellSize)) camera.position.z = next.z;
    }

    function tryMoveEntity(entity, deltaVector) {
      const next = entity.group.position.clone().add(deltaVector);
      if (canOccupyWorldPosition(next, world, solidKeys, cellSize)) {
        entity.group.position.copy(next);
        return true;
      }
      const xOnly = entity.group.position.clone();
      xOnly.x = next.x;
      if (canOccupyWorldPosition(xOnly, world, solidKeys, cellSize)) entity.group.position.x = next.x;
      const zOnly = entity.group.position.clone();
      zOnly.z = next.z;
      if (canOccupyWorldPosition(zOnly, world, solidKeys, cellSize)) entity.group.position.z = next.z;
      return false;
    }

    function stepCharacter(delta, gameActive) {
      const player = current.player;
      if (!player) return;
      if (gameActive && current.downedTimer > 0) {
        current.downedTimer = Math.max(0, current.downedTimer - delta);
      }
      if (gameActive) {
        Object.keys(current.cooldowns).forEach((key) => {
          current.cooldowns[key] = Math.max(0, current.cooldowns[key] - delta);
        });
      }

      movement.set(0, 0, 0);
      forward.set(Math.sin(current.yaw), 0, -Math.cos(current.yaw)).normalize();
      right.set(Math.cos(current.yaw), 0, Math.sin(current.yaw)).normalize();
      if (gameActive && current.pointerLocked && player.alive && current.downedTimer <= 0) {
        if (current.keys.has("KeyW") || current.keys.has("ArrowUp")) movement.add(forward);
        if (current.keys.has("KeyS") || current.keys.has("ArrowDown")) movement.sub(forward);
        if (current.keys.has("KeyD") || current.keys.has("ArrowRight")) movement.add(right);
        if (current.keys.has("KeyA") || current.keys.has("ArrowLeft")) movement.sub(right);
      }
      if (movement.lengthSq() > 0) {
        const moveVector = movement.normalize().multiplyScalar(player.stats.moveSpeed * cellSize * delta);
        tryMoveEntity(player, moveVector);
        player.group.rotation.y = player.initialYaw + Math.atan2(moveVector.x, -moveVector.z);
        playEntityClip(player, player.animations.some((clip) => clip.name === "Run_InPlace") ? "Run_InPlace" : "Walk_InPlace");
      } else if (player.alive) {
        playEntityClip(player, player.asset.defaultAnimation);
      }

      const focus = player.group.position.clone();
      focus.y += cellSize * 1.15;
      const cameraTarget = focus.clone().add(forward.clone().multiplyScalar(cellSize * 0.85));
      const cameraPosition = focus
        .clone()
        .sub(forward.clone().multiplyScalar(cellSize * 3.2))
        .add(new THREE.Vector3(0, cellSize * (0.92 - current.pitch), 0));
      camera.position.lerp(cameraPosition, 0.2);
      camera.lookAt(cameraTarget);
    }

    function stepEnemyToward(enemy, targetPosition, delta) {
      const enemyCell = getWorldCellFromPosition(enemy.group.position, world, cellSize);
      const targetCell = getWorldCellFromPosition(targetPosition, world, cellSize);
      enemy.pathCooldown -= delta;
      if (enemy.pathCooldown <= 0 && enemyCell && targetCell) {
        enemy.path = findWorldPath(enemyCell.key, targetCell.key, world, solidKeys);
        enemy.pathCooldown = 0.45;
      }
      const nextKey = enemy.path[0];
      if (!nextKey) return;
      const [nextX, nextY] = nextKey.split(":").map(Number);
      const nextPosition = getWorldCellCenter(nextX, nextY, world, enemy.placement.elevation);
      const direction = nextPosition.sub(enemy.group.position);
      direction.y = 0;
      if (direction.length() < cellSize * 0.16) {
        enemy.path.shift();
        return;
      }
      const moveVector = direction.normalize().multiplyScalar(enemy.stats.moveSpeed * cellSize * delta);
      tryMoveEntity(enemy, moveVector);
      enemy.group.rotation.y = enemy.initialYaw + Math.atan2(moveVector.x, -moveVector.z);
      playEntityClip(enemy, enemy.animations.some((clip) => clip.name === "Run_InPlace") ? "Run_InPlace" : "Walk_InPlace");
    }

    function stepEnemyAway(enemy, targetPosition, delta) {
      const enemyCell = getWorldCellFromPosition(enemy.group.position, world, cellSize);
      if (!enemyCell) return;
      const neighbors = getGridNeighbors(enemyCell.key, world, solidKeys);
      if (!neighbors.length) return;
      const bestKey = neighbors
        .map((key) => {
          const [x, y] = key.split(":").map(Number);
          const center = getWorldCellCenter(x, y, world, enemy.placement.elevation);
          return { key, center, distance: center.distanceTo(targetPosition) };
        })
        .sort((a, b) => b.distance - a.distance)[0];
      const direction = bestKey.center.sub(enemy.group.position);
      direction.y = 0;
      if (direction.lengthSq() === 0) return;
      const moveVector = direction.normalize().multiplyScalar(enemy.stats.moveSpeed * cellSize * delta);
      tryMoveEntity(enemy, moveVector);
      enemy.group.rotation.y = enemy.initialYaw + Math.atan2(moveVector.x, -moveVector.z);
      playEntityClip(enemy, enemy.animations.some((clip) => clip.name === "Run_InPlace") ? "Run_InPlace" : "Walk_InPlace");
    }

    function enemyAttack(enemy, player, distance) {
      if (enemy.attackCooldown > 0 || !player.alive) return;
      const attack = enemy.attacks[0] ?? { type: enemy.role === "enemy-ranged" ? "ranged" : "melee", damage: enemy.stats.damage, range: enemy.stats.range, cooldown: enemy.stats.cooldown };
      const range = (attack.range ?? enemy.stats.range) * cellSize;
      if (distance > range) return;
      enemy.attackCooldown = attack.cooldown ?? enemy.stats.cooldown;
      playEntityClip(enemy, attack.clip);
      if (enemy.role === "enemy-ranged") {
        const direction = player.group.position.clone().sub(enemy.group.position).normalize();
        spawnProjectile({
          owner: enemy,
          target: player,
          direction,
          damage: attack.damage ?? enemy.stats.damage,
          speed: attack.projectileSpeed ?? 5.8,
          range: attack.range ?? enemy.stats.range,
        });
      } else {
        applyDamage(player, attack.damage ?? enemy.stats.damage);
      }
    }

    function stepEnemies(delta) {
      const player = current.player;
      if (!player?.alive) return;
      current.enemies.forEach((enemy) => {
        if (!enemy.alive) {
          enemy.deathTimer = Math.max(0, enemy.deathTimer - delta);
          if (enemy.deathTimer <= 0) enemy.group.visible = false;
          updateHealthBar(enemy);
          return;
        }
        enemy.attackCooldown = Math.max(0, enemy.attackCooldown - delta);
        const distance = enemy.group.position.distanceTo(player.group.position);
        const hasSight = hasWorldLineOfSight(enemy.group.position, player.group.position, world, solidKeys, cellSize);
        if (enemy.role === "enemy-ranged") {
          if (distance < cellSize * 2.2) {
            stepEnemyAway(enemy, player.group.position, delta);
          } else if (distance > enemy.stats.range * cellSize * 0.85 || !hasSight) {
            stepEnemyToward(enemy, player.group.position, delta);
          } else {
            playEntityClip(enemy, enemy.animations.some((clip) => clip.name === "Aim_Hold") ? "Aim_Hold" : enemy.asset.defaultAnimation);
            enemyAttack(enemy, player, distance);
          }
        } else if (distance > enemy.stats.range * cellSize) {
          stepEnemyToward(enemy, player.group.position, delta);
        } else {
          playEntityClip(enemy, enemy.asset.defaultAnimation);
          enemyAttack(enemy, player, distance);
        }
        updateHealthBar(enemy);
      });
    }

    function stepProjectiles(delta) {
      current.projectiles = current.projectiles.filter((projectile) => {
        projectile.ttl -= delta;
        projectile.mesh.position.addScaledVector(projectile.velocity, delta);
        const target = projectile.target;
        const targetPoint = target?.group?.position?.clone();
        if (targetPoint) targetPoint.y += cellSize * 0.65;
        const hit = target?.alive && targetPoint && projectile.mesh.position.distanceTo(targetPoint) < cellSize * 0.42;
        if (hit) {
          applyDamage(target, projectile.damage);
          removeProjectile(projectile);
          return false;
        }
        if (projectile.ttl <= 0) {
          removeProjectile(projectile);
          return false;
        }
        return true;
      });
    }

    function stepEffects(delta) {
      current.effects = current.effects.filter((effect) => {
        effect.ttl -= delta;
        const ratio = Math.max(0, effect.ttl / effect.maxTtl);
        effect.mesh.scale.setScalar(1 + (1 - ratio) * 2.5);
        effect.material.opacity = ratio * 0.58;
        if (effect.ttl > 0) return true;
        scene.remove(effect.mesh);
        effect.material.dispose();
        return false;
      });
    }

    function animate() {
      const delta = Math.min(clock.getDelta(), 0.05);
      current.entities.forEach((entity) => {
        entity.mixer?.update(delta);
      });
      if (current.controlMode === "character") {
        stepCharacter(delta, current.gameActive);
        if (current.gameActive) {
          stepEnemies(delta);
          stepProjectiles(delta);
          stepEffects(delta);
        }
      } else {
        stepFreeCamera(delta);
      }
      updateNearbyDoorPrompt();
      current.enemies.forEach(updateHealthBar);
      publishHud();
      renderer.render(scene, camera);
      current.animationId = requestAnimationFrame(animate);
    }

    const resizeObserver = typeof ResizeObserver === "undefined" ? null : new ResizeObserver(resize);
    resizeObserver?.observe(mount);
    window.addEventListener("resize", resize);
    document.addEventListener("pointerlockchange", handlePointerLockChange);
    document.addEventListener("mousemove", handleMouseMove);
    document.addEventListener("mousedown", handleMouseDown);
    document.addEventListener("contextmenu", handleContextMenu);
    document.addEventListener("keydown", handleKeyDown);
    document.addEventListener("keyup", handleKeyUp);
    publishHud(true);
    animate();

    return () => {
      disposed = true;
      setDoorPrompt(null);
      if (document.pointerLockElement === renderer.domElement) document.exitPointerLock?.();
      resizeObserver?.disconnect();
      window.removeEventListener("resize", resize);
      document.removeEventListener("pointerlockchange", handlePointerLockChange);
      document.removeEventListener("mousemove", handleMouseMove);
      document.removeEventListener("mousedown", handleMouseDown);
      document.removeEventListener("contextmenu", handleContextMenu);
      document.removeEventListener("keydown", handleKeyDown);
      document.removeEventListener("keyup", handleKeyUp);
      cancelAnimationFrame(current.animationId);
      current.projectiles.forEach(removeProjectile);
      current.effects.forEach((effect) => {
        scene.remove(effect.mesh);
        effect.material.dispose();
      });
      resources.forEach((resource) => resource?.dispose?.());
      renderer.dispose();
      if (renderer.domElement.parentNode === mount) {
        mount.removeChild(renderer.domElement);
      }
    };
  }, [requestDoorTravel, world, worldTargets]);

  async function enterWorld() {
    const renderer = stateRef.current.renderer;
    const mount = mountRef.current;
    if (!renderer || !mount) return;
    const shell = mount.parentElement;
    if (shell?.requestFullscreen && !document.fullscreenElement && window.innerWidth >= 900) {
      await shell.requestFullscreen().catch(() => undefined);
    }
    const lockRequest = renderer.domElement.requestPointerLock?.();
    lockRequest?.catch?.(() => undefined);
  }

  async function exitWorld() {
    if (document.pointerLockElement) document.exitPointerLock?.();
    if (document.fullscreenElement === mountRef.current?.parentElement) {
      await document.exitFullscreen?.().catch(() => undefined);
    }
  }

  function resetSpawn() {
    stateRef.current.resetSpawn?.();
  }

  const healthRatio = hudState.maxHealth ? Math.max(0, Math.min(1, hudState.health / hudState.maxHealth)) : 0;

  return (
    <div
      className="world-viewport-shell"
      data-world-status={worldReady ? "ready" : "loading"}
      data-exploring={exploring ? "true" : "false"}
      data-world-assets={`${assetProgress.loaded}/${assetProgress.total}`}
      data-control-mode={hudState.controlMode}
      data-game-active={hudState.gameActive ? "true" : "false"}
      data-player-health={`${hudState.health}/${hudState.maxHealth}`}
      data-enemies-alive={hudState.enemiesAlive}
      data-enemy-health={hudState.enemyHealth}
      data-active-world-id={world.id ?? ""}
      data-door-prompt={doorPrompt?.targetWorldId ?? ""}
    >
      <div ref={mountRef} className="world-viewport" aria-label={`${world.name} interactive 3D world`} />
      <div className="world-viewport-overlay">
        <div className="world-viewport-actions" aria-label="3D world controls">
          <button type="button" onClick={enterWorld} disabled={!worldReady}>
            <DoorOpen aria-hidden="true" />
            <span>Enter World</span>
          </button>
          <button type="button" onClick={exitWorld} disabled={!exploring}>
            <Pause aria-hidden="true" />
            <span>Exit</span>
          </button>
          <button type="button" onClick={resetSpawn} disabled={!worldReady}>
            <Sparkles aria-hidden="true" />
            <span>Reset Spawn</span>
          </button>
        </div>
        {doorPrompt ? (
          <button type="button" className="world-door-prompt" onClick={() => requestDoorTravel(doorPrompt.targetWorldId)}>
            <DoorOpen aria-hidden="true" />
            <span>Enter {doorPrompt.targetName}</span>
            <small>E</small>
          </button>
        ) : null}
        <div className="world-player-hud" aria-label="Player combat status">
          {hudState.controlMode === "character" ? (
            <>
              <div className="hud-health-heading">
                <span>{hudState.playerName}</span>
                <strong>
                  {hudState.health}/{hudState.maxHealth}
                </strong>
              </div>
              <div className="hud-health-track" aria-label="Player health bar">
                <span style={{ width: `${healthRatio * 100}%` }} />
              </div>
              <div className="hud-cooldowns" aria-label="Attack cooldowns">
                <span>L {hudState.cooldowns.primary.toFixed(1)}</span>
                <span>R {hudState.cooldowns.secondary.toFixed(1)}</span>
                <span>Space {hudState.cooldowns.special.toFixed(1)}</span>
              </div>
            </>
          ) : (
            <div className="hud-free-camera">
              <Camera aria-hidden="true" />
              <span>Free camera</span>
            </div>
          )}
        </div>
        <div className="world-viewport-status" aria-label="3D world status">
          <span>
            <Box aria-hidden="true" />
            {worldStatus}
          </span>
          <span>
            <Crosshair aria-hidden="true" />
            {hudState.label}
          </span>
          <span>
            <ShieldCheck aria-hidden="true" />
            {hudState.enemiesAlive} enemies
          </span>
          <span>
            <Package aria-hidden="true" />
            {world.placements.length}
          </span>
          <span>
            <Grid2X2 aria-hidden="true" />
            {columns} x {rows}
          </span>
        </div>
      </div>
    </div>
  );
}

function IconButton({ label, children, onClick, href, download }) {
  const className = "icon-button";
  if (href) {
    return (
      <a className={className} href={href} download={download} aria-label={label} title={label}>
        {children}
      </a>
    );
  }
  return (
    <button className={className} type="button" onClick={onClick} aria-label={label} title={label}>
      {children}
    </button>
  );
}

function ExportMenu({ asset }) {
  return (
    <details className="export-menu">
      <summary aria-label={`Download ${asset.shortName} exports`} title={`Download ${asset.shortName} exports`}>
        <Download aria-hidden="true" />
        <ChevronDown aria-hidden="true" />
        <span className="sr-only">Exports</span>
      </summary>
      <div className="export-menu-list">
        {asset.exports.map((item) => (
          <a
            key={item.id}
            href={item.href}
            download={item.downloadName}
            aria-label={`Download ${item.label}`}
          >
            <span>{item.label}</span>
            <small>{item.detail}</small>
          </a>
        ))}
      </div>
    </details>
  );
}

function InspectorMetric({ label, value }) {
  return (
    <div className="metric">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function AnimationSelector({ clips, activeClipName, onSelect }) {
  if (!clips?.length) return null;
  return (
    <div className="animation-control" aria-label="Animation clip selector">
      <div className="animation-control-heading">
        <Film aria-hidden="true" />
        <span>Animation</span>
      </div>
      <div className="animation-options">
        {clips.map((clip) => (
          <button
            key={clip.name}
            type="button"
            aria-label={`Select ${clip.label} animation`}
            aria-pressed={activeClipName === clip.name}
            className={activeClipName === clip.name ? "active" : ""}
            onClick={() => onSelect(clip.name)}
          >
            {clip.label}
          </button>
        ))}
      </div>
    </div>
  );
}

function AssetPicker({ assets, selectedId, onSelect }) {
  return (
    <aside className="asset-browser" aria-label="Asset viewer">
      <div className="asset-browser-heading">
        <span>Assets</span>
        <small>{assets.length} available</small>
      </div>
      <div className="asset-list">
        {assets.map((item) => (
          <button
            key={item.id}
            type="button"
            className={`asset-card${selectedId === item.id ? " active" : ""}`}
            aria-pressed={selectedId === item.id}
            aria-label={`Select ${item.shortName}`}
            onClick={() => onSelect(item.id)}
          >
            <img src={item.previewUrl} alt="" loading="lazy" />
            <span>
              <strong>{item.shortName}</strong>
              <small>{item.authored.family}</small>
            </span>
          </button>
        ))}
      </div>
    </aside>
  );
}

function Brand() {
  return (
    <div className="brand">
      <Paintbrush aria-hidden="true" />
      <span>Artomata Asset Viewer</span>
    </div>
  );
}

function PageNav({ activeTab, onNavigate }) {
  return (
    <nav className="page-nav" aria-label="App pages">
      {pageTabs.map(({ id, label, Icon }) => (
        <button
          key={id}
          type="button"
          className={activeTab === id ? "active" : ""}
          aria-current={activeTab === id ? "page" : undefined}
          onClick={() => onNavigate(id)}
        >
          <Icon aria-hidden="true" />
          <span>{label}</span>
        </button>
      ))}
    </nav>
  );
}

function AssetViewerPage({ activeTab, onNavigate }) {
  const [selectedAssetId, setSelectedAssetId] = useState(defaultAssetId);
  const [autoSpin, setAutoSpin] = useState(false);
  const [activeClipName, setActiveClipName] = useState("");
  const [exposure, setExposure] = useState(1.05);
  const [mode, setMode] = useState("studio");
  const selectedAsset = useMemo(
    () => assetRegistry.find((item) => item.id === selectedAssetId) ?? assetRegistry[0],
    [selectedAssetId],
  );
  const activeAnimationLabel = useMemo(
    () => selectedAsset.animationClips?.find((clip) => clip.name === activeClipName)?.label ?? "Still",
    [activeClipName, selectedAsset],
  );
  const [modelInfo, setModelInfo] = useState({ status: "loading", url: selectedAsset.modelUrl });
  const [authored, setAuthored] = useState(selectedAsset.metadataFallback);
  const [fileSize, setFileSize] = useState(0);
  const commandRef = useRef(null);

  useEffect(() => {
    setActiveClipName(selectedAsset.defaultAnimation ?? selectedAsset.animationClips?.[0]?.name ?? "");
  }, [selectedAsset]);

  useEffect(() => {
    let cancelled = false;
    setModelInfo({ status: "loading", url: selectedAsset.modelUrl });
    setAuthored(selectedAsset.metadataFallback);
    setFileSize(0);

    if (selectedAsset.metadataUrl) {
      fetchJson(selectedAsset.metadataUrl)
        .then((metadata) => {
          if (!cancelled) setAuthored(metadata);
        })
        .catch(() => {
          if (!cancelled) setAuthored(selectedAsset.metadataFallback);
        });
    }
    fetchFileSize(selectedAsset.modelUrl)
      .then((size) => {
        if (!cancelled) setFileSize(size);
      })
      .catch(() => {
        if (!cancelled) setFileSize(0);
      });

    return () => {
      cancelled = true;
    };
  }, [selectedAsset]);

  const metrics = useMemo(
    () => [
      {
        label: "Geometry parts",
        value:
          (authored?.counts?.geometry_objects ?? authored?.counts?.mesh_objects ?? modelInfo.meshes)?.toLocaleString?.() ??
          "...",
      },
      { label: "Triangles", value: (authored?.counts?.triangles ?? modelInfo.triangles)?.toLocaleString?.() ?? "..." },
      { label: "Materials", value: (authored?.counts?.materials ?? modelInfo.materials)?.toLocaleString?.() ?? "..." },
      { label: "Rig bones", value: authored?.counts?.bones?.toLocaleString?.() ?? "..." },
      {
        label: "Animations",
        value: (authored?.counts?.animations ?? modelInfo.animations?.length)?.toLocaleString?.() ?? "...",
      },
      { label: "GLB size", value: formatBytes(authored?.file_sizes?.glb_bytes ?? fileSize) },
      { label: "Bounds", value: formatBounds(authored?.bounds, modelInfo.dimensions) },
    ],
    [authored, fileSize, modelInfo],
  );

  function saveSnapshot() {
    const dataUrl = commandRef.current?.snapshot?.();
    if (!dataUrl) return;
    const link = document.createElement("a");
    link.href = dataUrl;
    link.download = selectedAsset.snapshotName;
    link.click();
  }

  return (
    <>
      <header className="topbar viewer-topbar">
        <Brand />
        <PageNav activeTab={activeTab} onNavigate={onNavigate} />
        <nav className="view-tabs" aria-label="Lighting mode">
          {Object.entries(sceneModes).map(([key, item]) => (
            <button key={key} type="button" className={mode === key ? "active" : ""} onClick={() => setMode(key)}>
              {item.label}
            </button>
          ))}
        </nav>
        <div className="toolbar">
          <IconButton label={autoSpin ? "Pause spin" : "Play spin"} onClick={() => setAutoSpin((value) => !value)}>
            {autoSpin ? <Pause /> : <Play />}
          </IconButton>
          <IconButton label="Reset view" onClick={() => commandRef.current?.reset?.()}>
            <RotateCcw />
          </IconButton>
          <ExportMenu asset={selectedAsset} />
        </div>
      </header>

      <AssetPicker assets={assetRegistry} selectedId={selectedAsset.id} onSelect={setSelectedAssetId} />

      <section
        className="stage"
        aria-label={`${selectedAsset.name} viewer`}
        data-active-asset={selectedAsset.id}
        data-model-status={modelInfo.status}
      >
        <SceneViewport
          key={selectedAsset.id}
          asset={selectedAsset}
          activeClipName={activeClipName}
          autoSpin={autoSpin}
          exposure={exposure}
          mode={mode}
          onLoaded={setModelInfo}
          commandRef={commandRef}
        />
        <div className="canvas-tools" aria-label="Viewport controls">
          <IconButton label="Zoom in" onClick={() => commandRef.current?.zoomIn?.()}>
            <ZoomIn />
          </IconButton>
          <IconButton label="Zoom out" onClick={() => commandRef.current?.zoomOut?.()}>
            <ZoomOut />
          </IconButton>
          <IconButton label={`Focus ${selectedAsset.shortName}`} onClick={() => commandRef.current?.focus?.()}>
            <Crosshair />
          </IconButton>
          <IconButton label="Snapshot" onClick={saveSnapshot}>
            <Camera />
          </IconButton>
        </div>
        <div className="status-strip">
          <span>{modelInfo.error ? "Model load issue" : modelInfo.status === "ready" ? "GLB loaded" : "Loading GLB"}</span>
          <span>{autoSpin ? "Spin on" : "Spin off"}</span>
          <span>{activeAnimationLabel} clip</span>
          <span>{sceneModes[mode].label} light</span>
        </div>
      </section>

      <aside className="inspector" aria-label="Model inspector">
        <div className="inspector-heading">
          <div>
            <span>{selectedAsset.shortName}</span>
            <small>{selectedAsset.authored.target}</small>
          </div>
        </div>
        <div className="metric-grid">
          {metrics.map((metric) => (
            <InspectorMetric key={metric.label} label={metric.label} value={metric.value} />
          ))}
        </div>
        <AnimationSelector
          clips={selectedAsset.animationClips}
          activeClipName={activeClipName}
          onSelect={setActiveClipName}
        />
        <div className="control-group">
          <label htmlFor="exposure">
            <SunMedium aria-hidden="true" />
            Exposure
          </label>
          <input
            id="exposure"
            type="range"
            min="0.72"
            max="1.45"
            step="0.01"
            value={exposure}
            onChange={(event) => setExposure(Number(event.target.value))}
          />
          <output>{exposure.toFixed(2)}</output>
        </div>
        <dl className="asset-facts">
          <div>
            <dt>
              <Palette aria-hidden="true" />
              Effects
            </dt>
            <dd>{selectedAsset.authored.effects}</dd>
          </div>
          <div>
            <dt>
              <Maximize aria-hidden="true" />
              Source
            </dt>
            <dd>{selectedAsset.sourceLabel}</dd>
          </div>
        </dl>
      </aside>
    </>
  );
}

function AssetGeneratorPage({ activeTab, onNavigate }) {
  const [form, setForm] = useState(defaultAssetGeneratorForm);
  const [outputView, setOutputView] = useState("brief");
  const [copyStatus, setCopyStatus] = useState("");
  const [apiStatus, setApiStatus] = useState(null);
  const [apiError, setApiError] = useState("");
  const [job, setJob] = useState(null);
  const [isAdvancedOpen, setIsAdvancedOpen] = useState(false);
  const spec = useMemo(() => buildGeneratorSpec(form), [form]);
  const brief = useMemo(() => buildAssetGenerationBrief(form, spec), [form, spec]);
  const command = useMemo(() => buildAssetAgentCommand(form, brief), [form, brief]);
  const specJson = useMemo(() => JSON.stringify(spec, null, 2), [spec]);
  const validation = useMemo(() => validateGeneratorSpec(spec), [spec]);
  const isVfx = form.type === "vfx";
  const outputValue = outputView === "spec" ? specJson : outputView === "command" ? command : brief;
  const isGenerating = isGeneratorJobActive(job);
  const openAiReady = Boolean(apiStatus?.openai?.hasApiKey);
  const blenderReady = Boolean(apiStatus?.blender?.ready);
  const canGenerate = Boolean(apiStatus) && !apiError && openAiReady && blenderReady && !isGenerating;
  const timeline = job?.steps?.length
    ? job.steps
    : Object.entries(generatorStepLabels).map(([id, label]) => ({ id, label, status: id === "queue" ? "ready" : "pending", detail: "" }));
  const resultFiles = job?.result?.files ?? [];
  const statusDetail = apiError
    ? `Asset API offline at ${getAssetApiBase()}`
    : !apiStatus
      ? "Checking local asset service"
      : !openAiReady
        ? "Add OPENAI_API_KEY in .env. OPENAI-KEY is also supported."
        : !blenderReady
          ? apiStatus.blender?.setupHint || "Start Blender MCP or configure BLENDER_PATH."
          : isGenerating
            ? "Generation is running locally."
            : job?.status === "completed"
              ? "Asset generated and registered."
              : job?.status === "failed"
                ? "Generation failed. Check the timeline for details."
                : "Ready for one-click generation.";
  const readiness = [
    {
      ok: openAiReady,
      label: "OpenAI",
      detail: apiStatus?.openai?.model ? `${apiStatus.openai.model} via local API` : "Waiting for local API.",
    },
    {
      ok: blenderReady,
      label: "Blender",
      detail: getBlenderStatusLabel(apiStatus?.blender),
    },
    { ok: validation.every((item) => item.ok), label: "Form", detail: `${spec.pipelineId}, ${spec.rigTarget}` },
  ];

  const refreshStatus = useCallback(async () => {
    try {
      const body = await assetApiRequest("/api/assets/status");
      setApiStatus(body);
      setApiError("");
      if (body.currentJob) setJob(body.currentJob);
    } catch (error) {
      setApiError(error.message || "Unable to reach the local asset API.");
    }
  }, []);

  useEffect(() => {
    refreshStatus();
  }, [refreshStatus]);

  useEffect(() => {
    if (!job?.id || !isGeneratorJobActive(job)) return undefined;
    const timer = window.setInterval(async () => {
      try {
        const body = await assetApiRequest(`/api/assets/jobs/${job.id}`);
        setJob(body.job);
      } catch (error) {
        setApiError(error.message || "Unable to poll the asset generation job.");
      }
    }, 1800);
    return () => window.clearInterval(timer);
  }, [job?.id, job?.status]);

  function updateField(field, value) {
    setForm((current) => {
      const next = { ...current, [field]: value };
      if (field === "type") {
        if (value === "character") next.rigging = "humanoid Mixamo best-effort";
        if (value === "furniture" || value === "prop") {
          next.rigging = "none";
          next.animations = "none";
        }
        if (value === "plant") {
          next.rigging = "simple transform rig";
          next.animations = "default";
        }
        if (value === "vfx") {
          next.rigging = "simple transform rig";
          next.animations = "default";
        }
      }
      return next;
    });
  }

  async function copyText(text, label) {
    try {
      if (navigator.clipboard?.writeText) {
        await navigator.clipboard.writeText(text);
      } else {
        const textarea = document.createElement("textarea");
        textarea.value = text;
        textarea.setAttribute("readonly", "");
        textarea.style.position = "fixed";
        textarea.style.opacity = "0";
        document.body.appendChild(textarea);
        textarea.select();
        document.execCommand("copy");
        document.body.removeChild(textarea);
      }
      setCopyStatus(`${label} copied`);
    } catch {
      setCopyStatus(`Unable to copy ${label.toLowerCase()}`);
    }
    window.setTimeout(() => setCopyStatus(""), 2200);
  }

  async function startGeneration() {
    try {
      setCopyStatus("");
      const body = await assetApiRequest("/api/assets/generate", {
        method: "POST",
        body: JSON.stringify({ family: form.type, form, brief }),
      });
      setJob(body.job);
      setApiError("");
      window.setTimeout(refreshStatus, 600);
    } catch (error) {
      setApiError(error.message || "Unable to start asset generation.");
    }
  }

  return (
    <>
      <header className="topbar generator-topbar">
        <Brand />
        <PageNav activeTab={activeTab} onNavigate={onNavigate} />
        <div className="toolbar">
          <IconButton label="Refresh generator status" onClick={refreshStatus}>
            <RefreshCw />
          </IconButton>
          <IconButton label="Copy asset spec" onClick={() => copyText(specJson, "Asset spec")}>
            <ClipboardCheck />
          </IconButton>
        </div>
      </header>

      <section className="asset-generator" aria-label="Asset Generator">
        <aside className="generator-panel generator-form-panel">
          <div className="panel-heading">
            <div>
              <span>Asset Brief</span>
              <small>{assetGeneratorTypes.find((item) => item.id === form.type)?.label}</small>
            </div>
            <Package aria-hidden="true" />
          </div>

          <div className="generator-form-grid">
            <label>
              <span>Type</span>
              <select value={form.type} onChange={(event) => updateField("type", event.target.value)}>
                {assetGeneratorTypes.map((type) => (
                  <option key={type.id} value={type.id}>
                    {type.label}
                  </option>
                ))}
              </select>
            </label>
            <label>
              <span>Name</span>
              <input
                value={form.name}
                placeholder="Village healer NPC"
                onChange={(event) => updateField("name", event.target.value)}
              />
            </label>
            <label>
              <span>Style</span>
              <input
                value={form.style}
                placeholder="Stylized warm hand-painted fantasy"
                onChange={(event) => updateField("style", event.target.value)}
              />
            </label>
            {!isVfx ? (
              <label>
                <span>Rigging</span>
                <select value={form.rigging} onChange={(event) => updateField("rigging", event.target.value)}>
                  <option value="none">none</option>
                  <option value="simple transform rig">simple</option>
                  <option value="deformation rig">deformation</option>
                  <option value="humanoid Mixamo best-effort">humanoid Mixamo best-effort</option>
                </select>
              </label>
            ) : (
              <label>
                <span>VFX Family</span>
                <select value={form.vfxFamily} onChange={(event) => updateField("vfxFamily", event.target.value)}>
                  {vfxFamilies.map((family) => (
                    <option key={family} value={family}>
                      {family}
                    </option>
                  ))}
                </select>
              </label>
            )}
            <label>
              <span>Animations</span>
              <select value={form.animations} onChange={(event) => updateField("animations", event.target.value)}>
                <option value="default">default</option>
                <option value="none">none</option>
                <option value="specific">specific clips</option>
              </select>
            </label>
          </div>

          <label className="full-field">
            <span>
              <Package aria-hidden="true" />
              Required Parts
            </span>
            <textarea
              value={form.requiredParts}
              placeholder="Readable silhouette, clear face, tool belt, display base"
              onChange={(event) => updateField("requiredParts", event.target.value)}
              rows="4"
            />
          </label>
          <label className="full-field">
            <span>
              <Palette aria-hidden="true" />
              Materials / Colors
            </span>
            <textarea
              value={form.materials}
              placeholder="Teal cloth, warm leather, ivory accents, soft cyan glow"
              onChange={(event) => updateField("materials", event.target.value)}
              rows="4"
            />
          </label>
          <label className="full-field">
            <span>
              <Film aria-hidden="true" />
              Animation Notes
            </span>
            <textarea
              value={form.animationNotes}
              placeholder="Leave blank for useful defaults, or list clips such as Idle, Walk, Attack"
              onChange={(event) => updateField("animationNotes", event.target.value)}
              rows="3"
            />
          </label>

          {isVfx ? (
            <div className="generator-vfx-fields">
              <div className="generator-form-grid">
                <label>
                  <span>Loop</span>
                  <select value={form.loopMode} onChange={(event) => updateField("loopMode", event.target.value)}>
                    <option value="looping">looping</option>
                    <option value="one-shot">one-shot</option>
                  </select>
                </label>
                <label>
                  <span>Seconds</span>
                  <input
                    type="number"
                    min="0.25"
                    max="30"
                    step="0.25"
                    value={form.durationSeconds}
                    onChange={(event) => updateField("durationSeconds", event.target.value)}
                  />
                </label>
                <label>
                  <span>Emission</span>
                  <select value={form.emissionSource} onChange={(event) => updateField("emissionSource", event.target.value)}>
                    {emissionSources.map((source) => (
                      <option key={source} value={source}>
                        {source}
                      </option>
                    ))}
                  </select>
                </label>
                <label>
                  <span>Transparency</span>
                  <select value={form.transparencyStyle} onChange={(event) => updateField("transparencyStyle", event.target.value)}>
                    {transparencyStyles.map((style) => (
                      <option key={style} value={style}>
                        {style}
                      </option>
                    ))}
                  </select>
                </label>
              </div>
              <label className="full-field">
                <span>
                  <Sparkles aria-hidden="true" />
                  Motion Behavior
                </span>
                <textarea value={form.motionBehavior} onChange={(event) => updateField("motionBehavior", event.target.value)} rows="3" />
              </label>
              <label className="full-field">
                <span>
                  <SlidersHorizontal aria-hidden="true" />
                  Implementation
                </span>
                <textarea
                  value={form.implementationPreference}
                  onChange={(event) => updateField("implementationPreference", event.target.value)}
                  rows="3"
                />
              </label>
            </div>
          ) : null}

          <label className="full-field">
            <span>
              <Maximize aria-hidden="true" />
              Viewer Framing
            </span>
            <textarea
              value={form.viewerFraming}
              placeholder="Centered front-quarter framing, feet visible, readable face"
              onChange={(event) => updateField("viewerFraming", event.target.value)}
              rows="3"
            />
          </label>
          <label className="full-field">
            <span>
              <TextCursorInput aria-hidden="true" />
              Asset Brief
            </span>
            <textarea
              value={form.freeformBrief}
              placeholder="Optional extra intent, gameplay role, or details the form does not cover"
              onChange={(event) => updateField("freeformBrief", event.target.value)}
              rows="4"
            />
          </label>

          <button
            type="button"
            className={`generate-asset-button${isGenerating ? " generating" : ""}`}
            disabled={!canGenerate}
            onClick={startGeneration}
          >
            {isGenerating ? <RefreshCw aria-hidden="true" /> : <WandSparkles aria-hidden="true" />}
            <span>{isGenerating ? "Generating" : "Generate Asset"}</span>
          </button>
          <div className={`generator-inline-status${canGenerate ? " ready" : ""}${apiError || job?.status === "failed" ? " error" : ""}`}>
            {statusDetail}
          </div>
        </aside>

        <section className="generator-stage-panel generator-workflow-panel">
          <div className="world-stage-heading">
            <div>
              <h1>{spec.name}</h1>
              <span>{job?.status ? `${job.status} · ${spec.pipelineId}` : spec.pipelineId}</span>
            </div>
            <div className="world-stats" aria-label="Asset spec stats">
              <span>
                <Package aria-hidden="true" />
                {spec.assetFamily}
              </span>
              <span>
                <Film aria-hidden="true" />
                {spec.animationClips.length}
              </span>
            </div>
          </div>

          <div className="generator-workflow-body">
            <div className="generator-status-card">
              <div>
                <span>Local Generation</span>
                <strong>{getBlenderStatusLabel(apiStatus?.blender)}</strong>
              </div>
              <small>{statusDetail}</small>
            </div>

            <div className="generator-timeline" aria-label="Asset generation progress">
              {timeline.map((step) => (
                <div key={step.id} className={`generator-step ${step.status || "pending"}`}>
                  <span>{step.status === "running" ? <RefreshCw aria-hidden="true" /> : <CheckCircle2 aria-hidden="true" />}</span>
                  <div>
                    <strong>{step.label || generatorStepLabels[step.id] || step.id}</strong>
                    <small>{step.detail || (step.status === "pending" ? "Waiting" : step.status)}</small>
                  </div>
                </div>
              ))}
            </div>

            {job?.status === "completed" && job.result ? (
              <div className="generator-result">
                <div className="generator-preview-card">
                  <img src={`/renders/${job.result.slug}-preview.png`} alt="" loading="lazy" />
                  <div>
                    <span>Generated Asset</span>
                    <strong>{job.result.spec?.name || spec.name}</strong>
                    <small>{job.result.pipelineId}</small>
                  </div>
                </div>
                <div className="generator-output-cards">
                  {resultFiles.map((file) => (
                    <a key={file.id} href={getPublicHref(file)} target="_blank" rel="noreferrer">
                      <Download aria-hidden="true" />
                      <span>
                        <strong>{file.label}</strong>
                        <small>{file.path}</small>
                      </span>
                    </a>
                  ))}
                </div>
                <button type="button" className="wide-action generator-viewer-action" onClick={() => onNavigate("viewer")}>
                  <Box aria-hidden="true" />
                  <span>Open Asset Viewer</span>
                </button>
              </div>
            ) : (
              <div className="generator-empty-result">
                <WandSparkles aria-hidden="true" />
                <strong>{isGenerating ? "Blender is building the asset" : "Ready to create a Blender asset"}</strong>
                <span>{isGenerating ? "This can take a few minutes while Blender renders and exports." : "Generated files will appear here after the run finishes."}</span>
              </div>
            )}

            <details className="generator-advanced" open={isAdvancedOpen} onToggle={(event) => setIsAdvancedOpen(event.currentTarget.open)}>
              <summary>
                <SlidersHorizontal aria-hidden="true" />
                <span>Advanced</span>
              </summary>
              <nav className="schema-tabs generator-debug-tabs" aria-label="Asset generator debug output">
                {[
                  ["brief", "Brief"],
                  ["spec", "Spec"],
                  ["command", "Command"],
                ].map(([id, label]) => (
                  <button key={id} type="button" className={outputView === id ? "active" : ""} onClick={() => setOutputView(id)}>
                    {label}
                  </button>
                ))}
              </nav>
              <textarea className="schema-output generator-output" readOnly value={outputValue} />
              <div className="agent-actions">
                <button type="button" onClick={() => copyText(outputValue, outputView)}>
                  <Copy aria-hidden="true" />
                  <span>Copy</span>
                </button>
              </div>
            </details>
          </div>

          <div className="creator-status-strip generator-status-strip">
            <span>{copyStatus || statusDetail}</span>
            <span>{spec.slug}</span>
            <span>{spec.rigTarget}</span>
          </div>
        </section>

        <aside className="generator-panel generator-review-panel">
          <div className="panel-heading">
            <div>
              <span>Readiness</span>
              <small>{apiStatus?.openai?.model || "local API"}</small>
            </div>
            <WandSparkles aria-hidden="true" />
          </div>
          <div className="asset-facts generator-facts">
            <div>
              <dt>
                <ShieldCheck aria-hidden="true" />
                Secret handling
              </dt>
              <dd>OpenAI requests run only through the local asset API. The browser never receives the API key.</dd>
            </div>
            <div>
              <dt>
                <Maximize aria-hidden="true" />
                Output paths
              </dt>
              <dd>{`public/models/${spec.slug}.blend, public/models/${spec.slug}.glb, public/renders/${spec.slug}-preview.png`}</dd>
            </div>
          </div>
          <div className="validation-list">
            {[...readiness, ...validation].map((item) => (
              <div key={item.label} className={item.ok ? "ready" : "needs-work"}>
                <CheckCircle2 aria-hidden="true" />
                <span>
                  <strong>{item.label}</strong>
                  <small>{item.detail}</small>
                </span>
              </div>
            ))}
          </div>
          <div className="agent-actions">
            <button type="button" onClick={refreshStatus}>
              <RefreshCw aria-hidden="true" />
              <span>Status</span>
            </button>
            <button type="button" onClick={() => copyText(specJson, "Asset spec")}>
              <ClipboardCheck aria-hidden="true" />
              <span>Spec</span>
            </button>
          </div>
        </aside>
      </section>
    </>
  );
}

function WorldPaletteButton({ item, active, onSelect }) {
  const Icon = item.Icon ?? Package;
  return (
    <button
      type="button"
      className={`palette-tile${active ? " active" : ""}${item.type === "asset" ? " asset-palette-tile" : ""}`}
      aria-pressed={active}
      onClick={() => onSelect(item.id)}
    >
      {item.previewUrl ? <img src={item.previewUrl} alt="" loading="lazy" /> : <Icon aria-hidden="true" />}
      <span>
        <strong>{item.label}</strong>
        <small>{item.family}</small>
      </span>
    </button>
  );
}

function WorldCell({ cell, x, y, selected, onClick }) {
  const structurePlacement = cell?.type === "structure" ? cell : cell?.structure;
  const occupantPlacement = cell?.type === "asset" ? cell : cell?.occupant;
  const primaryPlacement = occupantPlacement ?? structurePlacement;
  const structure = structurePlacement ? findStructure(structurePlacement.itemId) : null;
  const Icon = structure?.Icon ?? Package;
  const cellLabel = occupantPlacement && structurePlacement
    ? `${occupantPlacement.label} on ${structurePlacement.label}`
    : primaryPlacement?.label;
  const className = [
    "world-cell",
    primaryPlacement ? "occupied" : "",
    structurePlacement ? "has-structure" : "",
    occupantPlacement ? "has-occupant" : "",
    structurePlacement?.className ?? "",
    structurePlacement?.targetWorldId ? "linked-door" : "",
    occupantPlacement?.combat?.role ?? "",
    selected ? "selected" : "",
  ]
    .filter(Boolean)
    .join(" ");

  return (
    <button
      type="button"
      className={className}
      style={{
        "--cell-accent": primaryPlacement?.color ?? "#28e0ea",
        "--cell-rotation": `${occupantPlacement?.rotation ?? structurePlacement?.rotation ?? 0}deg`,
        "--cell-scale": occupantPlacement?.scale ?? structurePlacement?.scale ?? 1,
      }}
      aria-label={cellLabel ? `${cellLabel} at ${x}, ${y}` : `Empty cell ${x}, ${y}`}
      aria-pressed={selected}
      onClick={onClick}
    >
      <span className="cell-coordinates">
        {x + 1}.{y + 1}
      </span>
      {primaryPlacement ? (
        <span className="cell-content layered-cell-content">
          {structurePlacement ? (
            <span className="cell-structure-mark">
              <Icon aria-hidden="true" />
            </span>
          ) : null}
          {occupantPlacement ? <img src={occupantPlacement.previewUrl} alt="" loading="lazy" /> : null}
        </span>
      ) : null}
      {cellLabel ? <strong>{cellLabel}</strong> : null}
    </button>
  );
}

function getInitialWorldView() {
  return window.location.hash.replace("#", "") === "world-3d" ? "view3d" : "grid";
}

function WorldCreatorPage({ activeTab, onNavigate }) {
  const [initialEditorState] = useState(() => {
    const library = loadWorldLibrary();
    const activeRecord = library.worlds.find((world) => world.id === library.activeWorldId) ?? library.worlds[0];
    const activeCells = getCellsFromWorldRecord(activeRecord);
    return {
      library,
      worldMeta: activeRecord.meta,
      cells: activeCells,
      selectedKey: getDefaultSelectedKey(activeCells),
    };
  });
  const [worldLibrary, setWorldLibrary] = useState(initialEditorState.library);
  const [worldMeta, setWorldMeta] = useState(initialEditorState.worldMeta);
  const [cells, setCells] = useState(initialEditorState.cells);
  const [selectedPaletteId, setSelectedPaletteId] = useState(defaultAssetId);
  const [brushMode, setBrushMode] = useState("place");
  const [worldView, setWorldView] = useState(getInitialWorldView);
  const [selectedKey, setSelectedKey] = useState(initialEditorState.selectedKey);
  const [importText, setImportText] = useState("");
  const [copyStatus, setCopyStatus] = useState("");
  const [schemaView, setSchemaView] = useState("json");
  const [worldPrompt, setWorldPrompt] = useState(defaultWorldGenerationPrompt);
  const [worldApiStatus, setWorldApiStatus] = useState(null);
  const [worldApiError, setWorldApiError] = useState("");
  const [isGeneratingWorld, setIsGeneratingWorld] = useState(false);
  const activeWorldId = worldLibrary.activeWorldId;
  const activeWorldRecord = worldLibrary.worlds.find((world) => world.id === activeWorldId) ?? worldLibrary.worlds[0];

  const paletteItems = useMemo(
    () => [
      ...structurePalette.map((item) => ({ ...item, type: "structure" })),
      ...assetRegistry.map((asset) => ({
        id: asset.id,
        type: "asset",
        label: asset.shortName,
        family: asset.authored.family,
        previewUrl: asset.previewUrl,
        agentHint: asset.description,
      })),
    ],
    [],
  );
  const selectedPalette = paletteItems.find((item) => item.id === selectedPaletteId) ?? paletteItems[0];
  const worldTargets = useMemo(
    () => worldLibrary.worlds.map((world) => ({ id: world.id, name: world.meta.name })),
    [worldLibrary.worlds],
  );
  const worldDocument = useMemo(() => serializeWorld(worldMeta, cells, activeWorldId), [activeWorldId, cells, worldMeta]);
  const worldJson = useMemo(() => JSON.stringify(worldDocument, null, 2), [worldDocument]);
  const agentBrief = useMemo(() => buildAgentBrief(worldDocument), [worldDocument]);
  const validation = useMemo(() => validateWorld(worldDocument), [worldDocument]);
  const schemaOutputValue = schemaView === "json" ? worldJson : schemaView === "brief" ? agentBrief : worldPrompt;
  const selectedCellRecord = selectedKey ? cells[selectedKey] : null;
  const selectedCell = getSelectedCellPlacement(selectedCellRecord, selectedPalette, brushMode);
  const selectedLayer = selectedCell?.layer ?? getPaletteLayer(selectedPalette);
  const selectedAsset = selectedCell?.type === "asset" ? findAsset(selectedCell.itemId) : null;
  const selectedCombatStats = selectedAsset && selectedCell?.combat ? getResolvedCombatStats(selectedAsset, selectedCell.combat) : null;
  const selectedDoorTargetId = selectedCell?.type === "structure" && selectedCell.itemId === "door" ? selectedCell.targetWorldId ?? "" : "";
  const selectedDoorTargetMissing = selectedDoorTargetId && !worldLibrary.worlds.some((world) => world.id === selectedDoorTargetId);
  const availableDoorTargets = worldLibrary.worlds.filter((world) => world.id !== activeWorldId);
  const worldOpenAiReady = Boolean(worldApiStatus?.openai?.hasApiKey);
  const canGenerateWorld = Boolean(worldApiStatus) && !worldApiError && worldOpenAiReady && !isGeneratingWorld;
  const worldGenerationStatus = worldApiError
    ? `World API offline at ${getAssetApiBase()}`
    : !worldApiStatus
      ? "Checking local world generation service"
      : !worldOpenAiReady
        ? "Add OPENAI_API_KEY in .env. OPENAI-KEY is also supported."
        : isGeneratingWorld
          ? "OpenAI is drafting a world grid."
          : "Ready to generate a saved world.";

  const gridCells = useMemo(
    () =>
      Array.from({ length: worldMeta.columns * worldMeta.rows }, (_, index) => {
        const x = index % worldMeta.columns;
        const y = Math.floor(index / worldMeta.columns);
        return { x, y, key: getCellKey(x, y), cell: cells[getCellKey(x, y)] };
      }),
    [cells, worldMeta.columns, worldMeta.rows],
  );

  const refreshWorldStatus = useCallback(async () => {
    try {
      const body = await assetApiRequest("/api/worlds/status");
      setWorldApiStatus(body);
      setWorldApiError("");
    } catch (error) {
      setWorldApiError(error.message || "Unable to reach the local world generation API.");
    }
  }, []);

  useEffect(() => {
    refreshWorldStatus();
  }, [refreshWorldStatus]);

  useEffect(() => {
    saveWorldLibrary(worldLibrary);
  }, [worldLibrary]);

  useEffect(() => {
    setWorldLibrary((current) => {
      const activeIndex = current.worlds.findIndex((world) => world.id === activeWorldId);
      if (activeIndex < 0) return current;
      const nextWorlds = [...current.worlds];
      nextWorlds[activeIndex] = {
        ...nextWorlds[activeIndex],
        updatedAt: new Date().toISOString(),
        meta: normaliseWorldMeta(worldMeta),
        placements: getSerializedWorldPlacements(cells),
      };
      return { ...current, worlds: nextWorlds };
    });
  }, [activeWorldId, cells, worldMeta]);

  const activateWorld = useCallback(
    (worldId, statusMessage) => {
      const record = worldLibrary.worlds.find((world) => world.id === worldId);
      if (!record) return;
      const nextCells = getCellsFromWorldRecord(record);
      setWorldMeta(record.meta);
      setCells(nextCells);
      setSelectedKey(getDefaultSelectedKey(nextCells));
      setWorldLibrary((current) => ({ ...current, activeWorldId: record.id }));
      setCopyStatus(statusMessage ?? `${record.meta.name} loaded`);
      window.setTimeout(() => setCopyStatus(""), 2200);
    },
    [worldLibrary.worlds],
  );

  function createNewWorld() {
    const meta = {
      ...defaultWorldMeta,
      name: getUniqueWorldName("New World", worldLibrary.worlds),
    };
    const nextCells = createStarterWorldCells(meta.columns, meta.rows);
    const record = createWorldRecord({ meta, cells: nextCells });
    setWorldMeta(record.meta);
    setCells(nextCells);
    setSelectedKey(getDefaultSelectedKey(nextCells));
    setWorldLibrary((current) => ({
      ...current,
      activeWorldId: record.id,
      worlds: [...current.worlds, record],
    }));
    setCopyStatus("New world created");
    window.setTimeout(() => setCopyStatus(""), 2200);
  }

  function duplicateWorld() {
    const meta = {
      ...worldMeta,
      name: getUniqueWorldName(`${worldMeta.name} Copy`, worldLibrary.worlds),
    };
    const nextCells = createCellsFromPlacements(getSerializedWorldPlacements(cells), meta.columns, meta.rows);
    const record = createWorldRecord({ meta, cells: nextCells });
    setWorldMeta(record.meta);
    setCells(nextCells);
    setSelectedKey(getDefaultSelectedKey(nextCells));
    setWorldLibrary((current) => ({
      ...current,
      activeWorldId: record.id,
      worlds: [...current.worlds, record],
    }));
    setCopyStatus("World duplicated");
    window.setTimeout(() => setCopyStatus(""), 2200);
  }

  function deleteActiveWorld() {
    if (worldLibrary.worlds.length <= 1) {
      setCopyStatus("Keep at least one world");
      window.setTimeout(() => setCopyStatus(""), 2200);
      return;
    }
    const activeIndex = Math.max(0, worldLibrary.worlds.findIndex((world) => world.id === activeWorldId));
    const remainingWorlds = worldLibrary.worlds.filter((world) => world.id !== activeWorldId);
    const fallbackWorld = remainingWorlds[Math.max(0, activeIndex - 1)] ?? remainingWorlds[0];
    const nextCells = getCellsFromWorldRecord(fallbackWorld);
    setWorldMeta(fallbackWorld.meta);
    setCells(nextCells);
    setSelectedKey(getDefaultSelectedKey(nextCells));
    setWorldLibrary((current) => ({
      ...current,
      activeWorldId: fallbackWorld.id,
      worlds: current.worlds.filter((world) => world.id !== activeWorldId),
    }));
    setCopyStatus("World deleted");
    window.setTimeout(() => setCopyStatus(""), 2200);
  }

  function navigate(page) {
    onNavigate(page);
  }

  useEffect(() => {
    function handleWorldHashChange() {
      setWorldView(getInitialWorldView());
    }
    window.addEventListener("hashchange", handleWorldHashChange);
    return () => window.removeEventListener("hashchange", handleWorldHashChange);
  }, []);

  function updateWorldView(nextView) {
    setWorldView(nextView);
    const nextHash = nextView === "view3d" ? "#world-3d" : "#world";
    if (window.location.hash !== nextHash) {
      window.location.hash = nextHash;
    }
  }

  function updateWorldField(field, value) {
    setWorldMeta((current) => ({ ...current, [field]: value }));
  }

  function updateGridDimension(field, value) {
    const nextValue = clampGridValue(value, field === "columns" ? 6 : 5, field === "columns" ? 16 : 12);
    const nextMeta = { ...worldMeta, [field]: nextValue };
    setWorldMeta(nextMeta);
    setCells((current) => resizeWorldCells(current, nextMeta.columns, nextMeta.rows));
    setSelectedKey((currentKey) => {
      if (!currentKey) return null;
      const [x, y] = currentKey.split(":").map(Number);
      if (x >= nextMeta.columns || y >= nextMeta.rows) return null;
      return currentKey;
    });
  }

  function handleCellAction(x, y) {
    const key = getCellKey(x, y);
    const layer = getPaletteLayer(selectedPalette);
    setSelectedKey(key);
    if (brushMode === "inspect") return;
    if (brushMode === "erase") {
      setCells((current) => {
        const next = { ...current };
        removeCellLayer(next, x, y, layer);
        return next;
      });
      return;
    }
    setCells((current) => {
      const next = { ...current };
      const currentCell = current[key];
      const previousPlacement = currentCell?.type ? currentCell : currentCell?.[layer];
      setCellLayer(next, createPalettePlacement(selectedPalette, x, y, previousPlacement));
      return next;
    });
  }

  function updateSelectedCell(patch) {
    if (!selectedKey || !selectedCell) return;
    setCells((current) => {
      const currentCell = current[selectedKey];
      const currentPlacement = currentCell?.type ? currentCell : currentCell?.[selectedLayer];
      if (!currentPlacement) return current;
      const next = { ...current };
      setCellLayer(next, { ...currentPlacement, ...patch });
      return next;
    });
  }

  function updateSelectedDoorTarget(targetWorldId) {
    updateSelectedCell({ targetWorldId: targetWorldId || undefined });
  }

  function updateSelectedCombatRole(role) {
    if (!selectedCell?.combat) return;
    updateSelectedCell({ combat: { ...selectedCell.combat, role } });
  }

  function updateSelectedCombatStat(field, value) {
    if (!selectedCell?.combat) return;
    updateSelectedCell({
      combat: {
        ...selectedCell.combat,
        statOverrides: {
          ...selectedCell.combat.statOverrides,
          [field]: Number(value),
        },
      },
    });
  }

  function resetSelectedCombatDefaults() {
    if (!selectedAsset) return;
    updateSelectedCell({ combat: createCombatState(selectedAsset, {}) });
  }

  function clearWorld() {
    setCells({});
    setSelectedKey(null);
  }

  function resetStarterWorld() {
    const seedRecord = getSeedWorldRecord(activeWorldId);
    if (seedRecord) {
      const nextCells = getCellsFromWorldRecord(seedRecord);
      setWorldMeta(seedRecord.meta);
      setCells(nextCells);
      setSelectedKey(getDefaultSelectedKey(nextCells));
      setCopyStatus(`${seedRecord.meta.name} reset`);
      window.setTimeout(() => setCopyStatus(""), 2200);
      return;
    }
    const nextCells = createStarterWorldCells(worldMeta.columns, worldMeta.rows);
    setCells(nextCells);
    setSelectedKey(getDefaultSelectedKey(nextCells));
    setCopyStatus("Starter world reset");
    window.setTimeout(() => setCopyStatus(""), 2200);
  }

  async function copyText(text, label) {
    try {
      if (navigator.clipboard?.writeText) {
        await navigator.clipboard.writeText(text);
      } else {
        const textarea = document.createElement("textarea");
        textarea.value = text;
        textarea.setAttribute("readonly", "");
        textarea.style.position = "fixed";
        textarea.style.opacity = "0";
        document.body.appendChild(textarea);
        textarea.select();
        document.execCommand("copy");
        document.body.removeChild(textarea);
      }
      setCopyStatus(`${label} copied`);
    } catch {
      setCopyStatus(`Unable to copy ${label.toLowerCase()}`);
    }
    window.setTimeout(() => setCopyStatus(""), 2200);
  }

  async function generateWorldFromPrompt() {
    try {
      setIsGeneratingWorld(true);
      setWorldApiError("");
      setCopyStatus("Generating world grid");
      const body = await assetApiRequest("/api/worlds/generate", {
        method: "POST",
        body: JSON.stringify({
          prompt: worldPrompt,
          currentWorld: worldDocument,
        }),
      });
      const generatedWorld = body.world ?? {};
      const meta = normaliseWorldMeta(generatedWorld);
      const record = createWorldRecord({
        meta: {
          ...meta,
          name: getUniqueWorldName(meta.name || "Generated World", worldLibrary.worlds),
        },
        placements: Array.isArray(generatedWorld.placements) ? generatedWorld.placements : [],
      });
      const nextCells = getCellsFromWorldRecord(record);
      setWorldMeta(record.meta);
      setCells(nextCells);
      setSelectedKey(getDefaultSelectedKey(nextCells));
      setWorldLibrary((current) => ({
        ...current,
        activeWorldId: record.id,
        worlds: [...current.worlds, record],
      }));
      setSchemaView("json");
      setCopyStatus(`${record.meta.name} generated`);
    } catch (error) {
      setWorldApiError(error.message || "Unable to generate a world grid.");
      setCopyStatus("World generation failed");
    } finally {
      setIsGeneratingWorld(false);
      window.setTimeout(() => setCopyStatus(""), 2600);
    }
  }

  function downloadWorldJson() {
    const slug = worldMeta.name.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/(^-|-$)/g, "") || "world";
    const blob = new Blob([worldJson], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `${slug}.world.json`;
    link.click();
    URL.revokeObjectURL(url);
    setCopyStatus("World JSON saved");
    window.setTimeout(() => setCopyStatus(""), 2200);
  }

  function applyImportedWorld() {
    try {
      const parsed = JSON.parse(importText);
      const columns = clampGridValue(parsed.grid?.columns ?? parsed.columns ?? worldMeta.columns, 6, 16);
      const rows = clampGridValue(parsed.grid?.rows ?? parsed.rows ?? worldMeta.rows, 5, 12);
      const placements = Array.isArray(parsed.placements) ? parsed.placements : [];
      const nextCells = {};
      placements.forEach((placement) => {
        const x = Number(placement.x);
        const y = Number(placement.y);
        if (!Number.isInteger(x) || !Number.isInteger(y) || x < 0 || y < 0 || x >= columns || y >= rows) return;
        setCellLayer(nextCells, normaliseImportedPlacement(placement));
      });
      setWorldMeta({
        name: parsed.name || worldMeta.name,
        theme: parsed.theme || worldMeta.theme,
        columns,
        rows,
        cellSize: parsed.grid?.cellSize || worldMeta.cellSize,
        rules: parsed.rules || worldMeta.rules,
      });
      const importedCells = placements.length ? nextCells : createStarterWorldCells(columns, rows);
      setCells(importedCells);
      setSelectedKey(getDefaultSelectedKey(importedCells));
      setCopyStatus("World JSON imported");
    } catch {
      setCopyStatus("Import JSON has a syntax issue");
    }
    window.setTimeout(() => setCopyStatus(""), 2600);
  }

  return (
    <>
      <header className="topbar creator-topbar">
        <Brand />
        <PageNav activeTab={activeTab} onNavigate={navigate} />
        <nav className="view-tabs creator-mode-tabs" aria-label="World brush mode">
          {Object.entries(brushModes).map(([key, item]) => {
            const Icon = item.Icon;
            return (
              <button key={key} type="button" className={brushMode === key ? "active" : ""} onClick={() => setBrushMode(key)}>
                <Icon aria-hidden="true" />
                <span>{item.label}</span>
              </button>
            );
          })}
        </nav>
        <div className="toolbar">
          <IconButton label="Reset starter world" onClick={resetStarterWorld}>
            <RefreshCw />
          </IconButton>
          <IconButton label="Copy world JSON" onClick={() => copyText(worldJson, "World JSON")}>
            <Copy />
          </IconButton>
          <IconButton label="Download world JSON" onClick={downloadWorldJson}>
            <Save />
          </IconButton>
          <IconButton label="Clear world" onClick={clearWorld}>
            <Trash2 />
          </IconButton>
        </div>
      </header>

      <section className={`world-creator${worldView === "view3d" ? " world-creator-3d" : ""}`} aria-label="World Creator">
        <aside className="creator-panel palette-panel" aria-label="World palette">
          <div className="world-library-panel" aria-label="Saved worlds">
            <div className="panel-heading">
              <div>
                <span>Worlds</span>
                <small>{worldLibrary.worlds.length} saved</small>
              </div>
              <MapIcon aria-hidden="true" />
            </div>
            <label className="world-select-field">
              <span>Active World</span>
              <select value={activeWorldId} onChange={(event) => activateWorld(event.target.value)}>
                {worldLibrary.worlds.map((world) => (
                  <option key={world.id} value={world.id}>
                    {world.meta.name}
                  </option>
                ))}
              </select>
            </label>
            <div className="world-library-actions">
              <button type="button" onClick={createNewWorld}>
                <Plus aria-hidden="true" />
                <span>New</span>
              </button>
              <button type="button" onClick={duplicateWorld}>
                <Copy aria-hidden="true" />
                <span>Duplicate</span>
              </button>
              <button type="button" onClick={deleteActiveWorld} disabled={worldLibrary.worlds.length <= 1}>
                <Trash2 aria-hidden="true" />
                <span>Delete</span>
              </button>
            </div>
          </div>

          <div className="panel-heading">
            <div>
              <span>Palette</span>
              <small>{selectedPalette.label}</small>
            </div>
            <Box aria-hidden="true" />
          </div>
          <div className="palette-section">
            <h2>Build Pieces</h2>
            <div className="palette-grid">
              {paletteItems
                .filter((item) => item.type === "structure")
                .map((item) => (
                  <WorldPaletteButton
                    key={item.id}
                    item={item}
                    active={selectedPaletteId === item.id}
                    onSelect={setSelectedPaletteId}
                  />
                ))}
            </div>
          </div>
          <div className="palette-section">
            <h2>Assets</h2>
            <div className="palette-grid">
              {paletteItems
                .filter((item) => item.type === "asset")
                .map((item) => (
                  <WorldPaletteButton
                    key={item.id}
                    item={item}
                    active={selectedPaletteId === item.id}
                    onSelect={setSelectedPaletteId}
                  />
                ))}
            </div>
          </div>
        </aside>

        <section className={`world-stage-panel${worldView === "view3d" ? " world-3d-active" : ""}`} aria-label="World editor stage">
          <div className="world-stage-heading">
            <div>
              <h1>World Creator</h1>
              <span>{worldMeta.name}</span>
            </div>
            <div className="world-stage-actions">
              <nav className="world-view-tabs" aria-label="World view mode">
                {Object.entries(worldViewModes).map(([key, item]) => {
                  const Icon = item.Icon;
                  return (
                    <button key={key} type="button" className={worldView === key ? "active" : ""} onClick={() => updateWorldView(key)}>
                      <Icon aria-hidden="true" />
                      <span>{item.label}</span>
                    </button>
                  );
                })}
              </nav>
              <div className="world-stats" aria-label="World stats">
                <span>
                  <Grid2X2 aria-hidden="true" />
                  {worldMeta.columns} x {worldMeta.rows}
                </span>
                <span>
                  <Package aria-hidden="true" />
                  {worldDocument.placements.length}
                </span>
                <span>
                  <ShieldCheck aria-hidden="true" />
                  {validation.filter((item) => item.ok).length}/{validation.length}
                </span>
              </div>
            </div>
          </div>

          {worldView === "grid" ? (
            <div className="world-grid-frame">
              <div
                className="world-grid"
                style={{
                  "--world-columns": worldMeta.columns,
                  "--world-rows": worldMeta.rows,
                }}
              >
                {gridCells.map(({ key, x, y, cell }) => (
                  <WorldCell
                    key={key}
                    x={x}
                    y={y}
                    cell={cell}
                    selected={selectedKey === key}
                    onClick={() => handleCellAction(x, y)}
                  />
                ))}
              </div>
            </div>
          ) : (
            <div className="world-viewport-frame">
              <WorldViewport key={activeWorldId} world={worldDocument} worldTargets={worldTargets} onTravel={activateWorld} />
            </div>
          )}
          <div className="creator-status-strip">
            <span>{worldView === "grid" ? `${brushModes[brushMode].label} brush` : "3D preview"}</span>
            <span>{selectedPalette.label}</span>
            <span>{copyStatus || "Autosynced schema"}</span>
          </div>
        </section>

        <aside className="creator-panel world-inspector" aria-label="World inspector">
          <div className="panel-heading">
            <div>
              <span>World Setup</span>
              <small>{worldThemes.find((item) => item.id === worldMeta.theme)?.label}</small>
            </div>
            <MapIcon aria-hidden="true" />
          </div>

          <div className="form-grid">
            <label>
              <span>Name</span>
              <input value={worldMeta.name} onChange={(event) => updateWorldField("name", event.target.value)} />
            </label>
            <label>
              <span>Theme</span>
              <select value={worldMeta.theme} onChange={(event) => updateWorldField("theme", event.target.value)}>
                {worldThemes.map((theme) => (
                  <option key={theme.id} value={theme.id}>
                    {theme.label}
                  </option>
                ))}
              </select>
            </label>
            <label>
              <span>Columns</span>
              <input
                type="number"
                min="6"
                max="16"
                value={worldMeta.columns}
                onChange={(event) => updateGridDimension("columns", event.target.value)}
              />
            </label>
            <label>
              <span>Rows</span>
              <input
                type="number"
                min="5"
                max="12"
                value={worldMeta.rows}
                onChange={(event) => updateGridDimension("rows", event.target.value)}
              />
            </label>
            <label>
              <span>Cell Size</span>
              <input value={worldMeta.cellSize} onChange={(event) => updateWorldField("cellSize", event.target.value)} />
            </label>
          </div>

          <label className="full-field">
            <span>
              <TextCursorInput aria-hidden="true" />
              Rules
            </span>
            <textarea value={worldMeta.rules} onChange={(event) => updateWorldField("rules", event.target.value)} rows="3" />
          </label>

          <div className="panel-heading compact-heading">
            <div>
              <span>{selectedCell ? selectedCell.label : "No cell selected"}</span>
              <small>{selectedCell ? `${selectedCell.layer} ${selectedCell.x + 1}.${selectedCell.y + 1}` : "Select a grid cell"}</small>
            </div>
            <ClipboardCheck aria-hidden="true" />
          </div>

          <div className="selected-cell-tools">
            <div className="segmented-icon-row" aria-label="Cell rotation controls">
              <button type="button" disabled={!selectedCell} onClick={() => updateSelectedCell({ rotation: (selectedCell.rotation + 270) % 360 })}>
                <RotateCcw aria-hidden="true" />
                <span>-90</span>
              </button>
              <button type="button" disabled={!selectedCell} onClick={() => updateSelectedCell({ rotation: (selectedCell.rotation + 90) % 360 })}>
                <RotateCw aria-hidden="true" />
                <span>+90</span>
              </button>
            </div>
            <label>
              <span>Scale</span>
              <input
                type="range"
                min="0.5"
                max="1.75"
                step="0.05"
                disabled={!selectedCell}
                value={selectedCell?.scale ?? 1}
                onChange={(event) => updateSelectedCell({ scale: Number(event.target.value) })}
              />
            </label>
            <label>
              <span>Elevation</span>
              <input
                type="number"
                step="0.25"
                disabled={!selectedCell}
                value={selectedCell?.elevation ?? 0}
                onChange={(event) => updateSelectedCell({ elevation: Number(event.target.value) || 0 })}
              />
            </label>
            {selectedCell?.type === "structure" && selectedCell.itemId === "door" ? (
              <label className="door-link-field">
                <span>
                  <DoorOpen aria-hidden="true" />
                  Door Destination
                </span>
                <select value={selectedDoorTargetId} onChange={(event) => updateSelectedDoorTarget(event.target.value)}>
                  <option value="">Unlinked</option>
                  {selectedDoorTargetMissing ? (
                    <option value={selectedDoorTargetId}>Missing saved world</option>
                  ) : null}
                  {availableDoorTargets.length ? (
                    availableDoorTargets.map((world) => (
                      <option key={world.id} value={world.id}>
                        {world.meta.name}
                      </option>
                    ))
                  ) : (
                    <option value="" disabled>
                      Create another world to link
                    </option>
                  )}
                </select>
              </label>
            ) : null}
            {selectedAsset && isCharacterAsset(selectedAsset) ? (
              <div className="combat-editor" aria-label="Character combat settings">
                <label>
                  <span>
                    <ShieldCheck aria-hidden="true" />
                    Role
                  </span>
                  <select
                    value={selectedCell?.combat?.role ?? selectedAsset.combat?.role ?? "neutral"}
                    onChange={(event) => updateSelectedCombatRole(event.target.value)}
                  >
                    {combatRoles.map((role) => (
                      <option key={role.id} value={role.id}>
                        {role.label}
                      </option>
                    ))}
                  </select>
                </label>
                <div className="combat-stat-grid">
                  {combatStatFields.map((field) => (
                    <label key={field.id}>
                      <span>{field.label}</span>
                      <input
                        type="number"
                        min={field.min}
                        max={field.max}
                        step={field.step}
                        value={selectedCombatStats?.[field.id] ?? getDefaultCombatStats(selectedAsset)[field.id]}
                        onChange={(event) => updateSelectedCombatStat(field.id, event.target.value)}
                      />
                    </label>
                  ))}
                </div>
                <button type="button" className="wide-action subtle-action" onClick={resetSelectedCombatDefaults}>
                  <RefreshCw aria-hidden="true" />
                  <span>Reset Character Defaults</span>
                </button>
              </div>
            ) : null}
            <label>
              <span>
                <Tags aria-hidden="true" />
                Tags
              </span>
              <input
                disabled={!selectedCell}
                value={selectedCell?.tags?.join(", ") ?? ""}
                onChange={(event) =>
                  updateSelectedCell({
                    tags: event.target.value
                      .split(",")
                      .map((tag) => tag.trim())
                      .filter(Boolean),
                  })
                }
              />
            </label>
            <label>
              <span>
                <StickyNote aria-hidden="true" />
                Notes
              </span>
              <textarea
                disabled={!selectedCell}
                rows="3"
                value={selectedCell?.notes ?? ""}
                onChange={(event) => updateSelectedCell({ notes: event.target.value })}
              />
            </label>
          </div>
        </aside>

        <aside className="creator-panel agent-panel" aria-label="Agent handoff">
          <div className="panel-heading">
            <div>
              <span>Agent Handoff</span>
              <small>{schemaView === "json" ? "World JSON" : schemaView === "brief" ? "Generation brief" : "OpenAI prompt"}</small>
            </div>
            <WandSparkles aria-hidden="true" />
          </div>

          <div className="schema-tabs" aria-label="Schema view">
            <button type="button" className={schemaView === "json" ? "active" : ""} onClick={() => setSchemaView("json")}>
              JSON
            </button>
            <button type="button" className={schemaView === "brief" ? "active" : ""} onClick={() => setSchemaView("brief")}>
              Brief
            </button>
            <button type="button" className={schemaView === "generate" ? "active" : ""} onClick={() => setSchemaView("generate")}>
              Generate
            </button>
          </div>

          {schemaView === "generate" ? (
            <>
              <textarea
                className="schema-output world-prompt-output"
                aria-label="World generation prompt"
                value={worldPrompt}
                onChange={(event) => setWorldPrompt(event.target.value)}
              />
              <div className={`world-generator-status${canGenerateWorld ? " ready" : ""}${worldApiError ? " error" : ""}`}>
                {worldGenerationStatus}
              </div>
            </>
          ) : (
            <textarea className="schema-output" readOnly value={schemaOutputValue} />
          )}

          {schemaView === "generate" ? (
            <div className="agent-actions">
              <button type="button" disabled={!canGenerateWorld} onClick={generateWorldFromPrompt}>
                {isGeneratingWorld ? <RefreshCw aria-hidden="true" /> : <WandSparkles aria-hidden="true" />}
                <span>{isGeneratingWorld ? "Generating" : "Generate World"}</span>
              </button>
              <button type="button" onClick={refreshWorldStatus}>
                <RefreshCw aria-hidden="true" />
                <span>Status</span>
              </button>
            </div>
          ) : (
            <div className="agent-actions">
              <button type="button" onClick={() => copyText(worldJson, "World JSON")}>
                <Copy aria-hidden="true" />
                <span>Copy JSON</span>
              </button>
              <button type="button" onClick={() => copyText(agentBrief, "Agent brief")}>
                <ClipboardCheck aria-hidden="true" />
                <span>Copy Brief</span>
              </button>
            </div>
          )}

          <div className="validation-list">
            {validation.map((item) => (
              <div key={item.label} className={item.ok ? "ready" : "needs-work"}>
                <CheckCircle2 aria-hidden="true" />
                <span>
                  <strong>{item.label}</strong>
                  <small>{item.detail}</small>
                </span>
              </div>
            ))}
          </div>

          <label className="full-field import-field">
            <span>
              <Upload aria-hidden="true" />
              Import JSON
            </span>
            <textarea value={importText} rows="5" onChange={(event) => setImportText(event.target.value)} />
          </label>
          <button type="button" className="wide-action" onClick={applyImportedWorld}>
            <Upload aria-hidden="true" />
            <span>Apply Import</span>
          </button>
        </aside>
      </section>
    </>
  );
}

function getNavigationState() {
  const currentHash = window.location.hash.replace("#", "");
  const activeTab = pageTabs.find((tab) => tab.id === currentHash);
  if (activeTab) return { page: activeTab.page, tab: activeTab.id };
  if (currentHash.startsWith("world")) return { page: "world", tab: "world" };
  return { page: "viewer", tab: "viewer" };
}

function App() {
  const [navigationState, setNavigationState] = useState(getNavigationState);

  useEffect(() => {
    function handleHashChange() {
      setNavigationState(getNavigationState());
    }
    window.addEventListener("hashchange", handleHashChange);
    return () => window.removeEventListener("hashchange", handleHashChange);
  }, []);

  function navigate(tabId) {
    const nextTab = pageTabs.find((tab) => tab.id === tabId) ?? pageTabs[0];
    if (window.location.hash !== nextTab.hash) {
      window.location.hash = nextTab.hash;
    }
    setNavigationState(getNavigationState());
  }

  const activePage = navigationState.page;
  const activeTab = navigationState.tab;

  return (
    <main
      className={`app-shell ${
        activePage === "world" ? "world-shell" : activePage === "generator" ? "generator-shell" : "viewer-shell"
      }`}
    >
      <div className="ambient-lines" aria-hidden="true" />
      {activePage === "world" ? (
        <WorldCreatorPage activeTab={activeTab} onNavigate={navigate} />
      ) : activePage === "generator" ? (
        <AssetGeneratorPage activeTab={activeTab} onNavigate={navigate} />
      ) : (
        <AssetViewerPage activeTab={activeTab} onNavigate={navigate} />
      )}
    </main>
  );
}

createRoot(document.getElementById("root")).render(<App />);
