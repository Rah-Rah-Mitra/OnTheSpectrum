export const assetFamilies = ["character", "furniture", "plant", "prop", "vfx"];

export const rigTargets = [
  "none",
  "simple transform rig",
  "deformation rig",
  "humanoid Mixamo best-effort",
  "curve or emitter controls",
];

export const stylePresets = ["studio teal", "warm fantasy", "forest natural", "violet arcane", "custom"];

export const colorTokenPattern = "^#[0-9A-Fa-f]{6}$";

export const characterHairTypes = ["short", "bob", "long", "ponytail", "spiky", "curly", "bald"];
export const characterBodyTypes = ["standard", "chibi", "slim", "sturdy"];
export const furnitureCategories = ["chair", "table", "workbench", "bed", "shelf", "stall", "cabinet", "custom"];
export const furnitureWoodStyles = ["warm oak", "dark walnut", "painted wood", "metal frame", "stone", "custom"];
export const propCategories = ["orb", "tool", "weapon", "container", "beacon", "machine", "treasure", "custom"];

export const pipelineCatalog = {
  "character.humanoid_basic": {
    family: "character",
    module: "character",
    label: "Humanoid character with basic named armature",
    defaultRig: "humanoid Mixamo best-effort",
    defaultClips: [
      { name: "Idle_Stationary", label: "Idle" },
      { name: "Walk_InPlace", label: "Walk" },
    ],
  },
  "character.chibi_mascot": {
    family: "character",
    module: "character",
    label: "Chibi mascot character with simple humanoid rig",
    defaultRig: "humanoid Mixamo best-effort",
    defaultClips: [
      { name: "Idle_Stationary", label: "Idle" },
      { name: "Walk_InPlace", label: "Walk" },
    ],
  },
  "furniture.static_or_mechanical": {
    family: "furniture",
    module: "furniture",
    label: "Static or transform-animated furniture",
    defaultRig: "none",
    defaultClips: [],
  },
  "plant.swaying_botanical": {
    family: "plant",
    module: "plant",
    label: "Botanical asset with optional transform sway",
    defaultRig: "simple transform rig",
    defaultClips: [{ name: "Sway_Gentle", label: "Sway" }],
  },
  "prop.static_or_turntable": {
    family: "prop",
    module: "prop",
    label: "Static prop with optional display turntable",
    defaultRig: "none",
    defaultClips: [],
  },
  "vfx.baked_mesh_curve": {
    family: "vfx",
    module: "vfx",
    label: "GLB-safe baked mesh and curve VFX",
    defaultRig: "simple transform rig",
    defaultClips: [{ name: "Loop_Effect", label: "Loop" }],
  },
};

export const pipelineIds = Object.keys(pipelineCatalog);

const animationClipSchema = {
  type: "object",
  additionalProperties: false,
  properties: {
    name: { type: "string", pattern: "^[A-Za-z][A-Za-z0-9_]*$" },
    label: { type: "string" },
  },
  required: ["name", "label"],
};

const nullableObject = (properties, required = []) => ({
  anyOf: [
    { type: "null" },
    {
      type: "object",
      additionalProperties: false,
      properties,
      required,
    },
  ],
});

const styleColorSchema = {
  type: "object",
  additionalProperties: false,
  properties: {
    primary: { type: "string", pattern: colorTokenPattern },
    secondary: { type: "string", pattern: colorTokenPattern },
    accent: { type: "string", pattern: colorTokenPattern },
    neutral: { type: "string", pattern: colorTokenPattern },
    emission: { type: "string", pattern: colorTokenPattern },
  },
  required: ["primary", "secondary", "accent", "neutral", "emission"],
};

const styleConfigSchema = {
  type: "object",
  additionalProperties: false,
  properties: {
    preset: { type: "string", enum: stylePresets },
    colors: styleColorSchema,
  },
  required: ["preset", "colors"],
};

const rigPlanSchema = {
  type: "object",
  additionalProperties: false,
  properties: {
    preset: { type: "string", enum: rigTargets },
    exportMixamo: { type: "boolean" },
    controls: {
      type: "array",
      items: { type: "string" },
    },
  },
  required: ["preset", "exportMixamo", "controls"],
};

export const assetSpecJsonSchema = {
  type: "object",
  additionalProperties: false,
  properties: {
    slug: {
      type: "string",
      pattern: "^[a-z0-9]+(?:-[a-z0-9]+)*$",
    },
    assetFamily: {
      type: "string",
      enum: assetFamilies,
    },
    pipelineId: {
      type: "string",
      enum: pipelineIds,
    },
    name: { type: "string" },
    subject: { type: "string" },
    visualStyle: { type: "string" },
    requiredParts: {
      type: "array",
      items: { type: "string" },
    },
    materialPalette: {
      type: "array",
      items: { type: "string" },
    },
    styleConfig: styleConfigSchema,
    rigTarget: {
      type: "string",
      enum: rigTargets,
    },
    rigPlan: rigPlanSchema,
    animationClips: {
      type: "array",
      items: animationClipSchema,
    },
    viewerFraming: { type: "string" },
    budget: {
      type: "object",
      additionalProperties: false,
      properties: {
        maxTriangles: { type: "integer", minimum: 1000, maximum: 250000 },
        maxMaterials: { type: "integer", minimum: 1, maximum: 64 },
        maxGlbMb: { type: "number", minimum: 0.1, maximum: 64 },
        approvedOverBudget: { type: "boolean" },
      },
      required: ["maxTriangles", "maxMaterials", "maxGlbMb", "approvedOverBudget"],
    },
    vfx: nullableObject(
      {
        family: {
          type: "string",
          enum: [
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
          ],
        },
        motionBehavior: { type: "string" },
        durationSeconds: { type: "number", minimum: 0.25, maximum: 30 },
        loop: { type: "boolean" },
        emissionSource: {
          type: "string",
          enum: ["point", "ring", "object-bound", "ground plane", "character-bound", "free-floating"],
        },
        transparencyStyle: {
          type: "string",
          enum: ["additive glow", "alpha-blended smoke", "opaque stylized mesh", "mixed"],
        },
        implementationPreference: { type: "string" },
      },
      [
        "family",
        "motionBehavior",
        "durationSeconds",
        "loop",
        "emissionSource",
        "transparencyStyle",
        "implementationPreference",
      ],
    ),
    character: nullableObject(
      {
        silhouette: { type: "string" },
        hairType: { type: "string", enum: characterHairTypes },
        hairColor: { type: "string", pattern: colorTokenPattern },
        bodyType: { type: "string", enum: characterBodyTypes },
        skinTone: { type: "string", pattern: colorTokenPattern },
        outfit: { type: "string" },
        outfitStyle: { type: "string" },
        accessories: {
          type: "array",
          items: { type: "string" },
        },
      },
      ["silhouette", "hairType", "hairColor", "bodyType", "skinTone", "outfit", "outfitStyle", "accessories"],
    ),
    furniture: nullableObject(
      {
        category: { type: "string", enum: furnitureCategories },
        woodStyle: { type: "string", enum: furnitureWoodStyles },
        upholstery: { type: "string" },
        mechanicalParts: {
          type: "array",
          items: { type: "string" },
        },
      },
      ["category", "woodStyle", "upholstery", "mechanicalParts"],
    ),
    plant: nullableObject(
      {
        botanicalType: { type: "string" },
        leafShape: { type: "string" },
        blossomStyle: { type: "string" },
        swayIntensity: { type: "string" },
      },
      ["botanicalType", "leafShape", "blossomStyle", "swayIntensity"],
    ),
    prop: nullableObject(
      {
        category: { type: "string", enum: propCategories },
        shapeLanguage: { type: "string" },
        displayMotion: { type: "string" },
      },
      ["category", "shapeLanguage", "displayMotion"],
    ),
  },
  required: [
    "slug",
    "assetFamily",
    "pipelineId",
    "name",
    "subject",
    "visualStyle",
    "requiredParts",
    "materialPalette",
    "styleConfig",
    "rigTarget",
    "rigPlan",
    "animationClips",
    "viewerFraming",
    "budget",
    "vfx",
    "character",
    "furniture",
    "plant",
    "prop",
  ],
};

export function defaultPipelineForFamily(family, brief = "") {
  const normalized = String(family || "").toLowerCase();
  if (normalized === "character" && /chibi|mascot/i.test(brief)) return "character.chibi_mascot";
  if (normalized === "character") return "character.humanoid_basic";
  if (normalized === "furniture") return "furniture.static_or_mechanical";
  if (normalized === "plant") return "plant.swaying_botanical";
  if (normalized === "vfx") return "vfx.baked_mesh_curve";
  return "prop.static_or_turntable";
}
