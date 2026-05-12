import assert from "node:assert/strict";
import { normalizeSpec, validateSpec } from "./asset_agent.mjs";
import { normalizeGeneratedWorld, worldGridJsonSchema } from "./world_agent.mjs";

function verifyAssetFixture(label, rawSpec, expectations) {
  const spec = normalizeSpec(rawSpec, rawSpec.subject || rawSpec.name || label);
  validateSpec(spec);
  for (const [path, expected] of Object.entries(expectations)) {
    const actual = path.split(".").reduce((value, key) => value?.[key], spec);
    assert.deepEqual(actual, expected, `${label}: expected ${path} to be ${JSON.stringify(expected)}, got ${JSON.stringify(actual)}`);
  }
  return spec;
}

const characterSpec = verifyAssetFixture(
  "character prompt",
  {
    slug: "azure-ponytail-ranger",
    assetFamily: "character",
    pipelineId: "character.humanoid_basic",
    name: "Azure Ponytail Ranger",
    subject: "stylized ranger NPC with a bow",
    visualStyle: "Stylized forest adventure character",
    requiredParts: ["hooded cloak", "bow", "quiver", "belt pouch"],
    materialPalette: ["deep green cloth", "warm leather", "cyan accent"],
    styleConfig: {
      preset: "forest natural",
      colors: {
        primary: "#4f8d55",
        secondary: "#9f6f3e",
        accent: "#9ee26d",
        neutral: "#26342b",
        emission: "#9dff9f",
      },
    },
    rigTarget: "humanoid Mixamo best-effort",
    rigPlan: { preset: "humanoid Mixamo best-effort", exportMixamo: true, controls: ["root", "spine", "head"] },
    animationClips: [
      { name: "Idle_Stationary", label: "Idle" },
      { name: "Walk_InPlace", label: "Walk" },
      { name: "Attack_Bow", label: "Bow Attack" },
    ],
    viewerFraming: "front quarter",
    budget: { maxTriangles: 100000, maxMaterials: 16, maxGlbMb: 12, approvedOverBudget: false },
    vfx: null,
    character: {
      silhouette: "slim ranger",
      hairType: "ponytail",
      hairColor: "#243027",
      bodyType: "slim",
      skinTone: "#c99068",
      outfit: "hooded cloak and leather belt",
      outfitStyle: "forest ranger cloak",
      accessories: ["bow", "quiver"],
    },
    furniture: null,
    plant: null,
    prop: null,
  },
  {
    "styleConfig.colors.primary": "#4f8d55",
    "rigPlan.exportMixamo": true,
    "character.hairType": "ponytail",
    "character.bodyType": "slim",
    "animationClips.2.name": "Attack_Bow",
  },
);

const furnitureSpec = verifyAssetFixture(
  "furniture prompt",
  {
    name: "Clockwork Reading Chair",
    assetFamily: "furniture",
    subject: "compact animated reading chair",
    requiredParts: ["padded seat", "tilting back", "brass lever"],
    materialPalette: ["dark walnut", "teal cushion", "brass accent"],
    styleConfig: {
      preset: "warm fantasy",
      colors: {
        primary: "#7a4c2c",
        secondary: "#2e8f92",
        accent: "#d9a84e",
        neutral: "#28211e",
        emission: "#ffc65c",
      },
    },
    animationClips: [{ name: "Recline_Test", label: "Recline" }],
    furniture: {
      category: "chair",
      woodStyle: "dark walnut",
      upholstery: "teal cushion",
      mechanicalParts: ["tilting back", "brass lever"],
    },
  },
  {
    assetFamily: "furniture",
    rigTarget: "simple transform rig",
    "furniture.category": "chair",
    "furniture.woodStyle": "dark walnut",
    "rigPlan.controls": ["root"],
  },
);

const vfxSpec = verifyAssetFixture(
  "vfx prompt",
  {
    name: "Amber Portal Loop",
    assetFamily: "vfx",
    subject: "looping amber portal",
    materialPalette: ["violet rim", "amber glow"],
    styleConfig: {
      preset: "violet arcane",
      colors: {
        primary: "#6f5fb8",
        secondary: "#b85fa6",
        accent: "#f0a642",
        neutral: "#201b2b",
        emission: "#ffbb55",
      },
    },
    vfx: {
      family: "portal",
      motionBehavior: "rotating ring with pulsing core",
      durationSeconds: 3,
      loop: true,
      emissionSource: "ring",
      transparencyStyle: "additive glow",
      implementationPreference: "GLB-compatible baked mesh/curve animation",
    },
  },
  {
    assetFamily: "vfx",
    rigTarget: "simple transform rig",
    "styleConfig.colors.emission": "#ffbb55",
    "vfx.family": "portal",
  },
);

const currentWorld = {
  name: "Fixture World",
  theme: "training-floor",
  grid: { columns: 8, rows: 6, cellSize: "1m" },
  rules: "Keep spawn reachable.",
};
const palette = {
  structures: [
    { id: "wall", label: "Wall", family: "Structure", agentHint: "blocking boundary wall" },
    { id: "spawn", label: "Spawn", family: "Utility", agentHint: "default character start point" },
    { id: "light", label: "Light", family: "Utility", agentHint: "motivated scene light" },
  ],
  assets: [
    { id: characterSpec.slug, label: characterSpec.name, family: "Character" },
    { id: furnitureSpec.slug, label: furnitureSpec.name, family: "Furniture" },
  ],
  itemIds: ["wall", "spawn", "light", characterSpec.slug, furnitureSpec.slug],
  itemTypes: new Map([
    ["wall", "structure"],
    ["spawn", "structure"],
    ["light", "structure"],
    [characterSpec.slug, "asset"],
    [furnitureSpec.slug, "asset"],
  ]),
};
const schema = worldGridJsonSchema(palette);
assert.equal(schema.properties.placements.items.properties.itemId.enum.includes(characterSpec.slug), true);

const generatedWorld = normalizeGeneratedWorld(
  {
    name: "Generated Fixture Yard",
    theme: "training-floor",
    grid: { columns: 8, rows: 6, cellSize: "1m" },
    rules: "Clear combat lanes.",
    placements: [
      { type: "structure", layer: "structure", itemId: "spawn", x: 1, y: 1, rotation: 0, scale: 1, elevation: 0, tags: ["spawn"], notes: "start", combat: null, targetWorldId: null },
      { type: "asset", layer: "occupant", itemId: characterSpec.slug, x: 1, y: 1, rotation: 90, scale: 1, elevation: 0, tags: ["player"], notes: "spawned hero", combat: { role: "player" }, targetWorldId: null },
      { type: "structure", layer: "structure", itemId: "wall", x: 0, y: 0, rotation: 0, scale: 1, elevation: 0, tags: ["wall"], notes: "boundary", combat: null, targetWorldId: null },
      { type: "structure", layer: "structure", itemId: "wall", x: 0, y: 0, rotation: 0, scale: 1, elevation: 0, tags: ["duplicate"], notes: "should drop", combat: null, targetWorldId: null },
      { type: "asset", layer: "occupant", itemId: "missing-asset", x: 2, y: 2, rotation: 0, scale: 1, elevation: 0, tags: [], notes: "should drop", combat: null, targetWorldId: null },
    ],
  },
  currentWorld,
  palette,
);

assert.equal(generatedWorld.placements.length, 3);
assert.equal(generatedWorld.placements.some((placement) => placement.itemId === "missing-asset"), false);
assert.equal(generatedWorld.placements.filter((placement) => placement.x === 0 && placement.y === 0 && placement.layer === "structure").length, 1);
assert.equal(generatedWorld.placements.find((placement) => placement.itemId === characterSpec.slug)?.combat.role, "player");

console.log(
  JSON.stringify(
    {
      ok: true,
      assets: [characterSpec.slug, furnitureSpec.slug, vfxSpec.slug],
      worldPlacements: generatedWorld.placements.length,
    },
    null,
    2,
  ),
);
