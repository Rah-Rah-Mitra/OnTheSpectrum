export const VIDEO = {
  compositionId: "OnTheSpectrumFullDemo",
  mediaFolder: "onthe-spectrum-full-demo",
  width: 1920,
  height: 1080,
  fps: 30,
  durationSeconds: 120,
};

export const scenes = [
  {
    id: "hook",
    title: "OnTheSpectrum",
    eyebrow: "Full application demo",
    start: 0,
    duration: 8,
    narration:
      "OnTheSpectrum turns a game asset idea into a generated model, a viewer-ready export, and a playable world.",
    caption:
      "OnTheSpectrum turns a game asset idea into a generated model, a viewer-ready export, and a playable world.",
  },
  {
    id: "asset-brief",
    title: "Asset Generator",
    eyebrow: "Brief to asset spec",
    start: 8,
    duration: 20,
    narration:
      "Start with a structured brief: family, rigging, materials, animations, and framing become a clean asset spec.",
    caption:
      "A structured brief becomes a clean asset spec: family, rigging, materials, animations, and framing.",
  },
  {
    id: "asset-pipeline",
    title: "Local Generation Pipeline",
    eyebrow: "OpenAI, Blender, validation",
    start: 28,
    duration: 20,
    narration:
      "The local pipeline drafts the spec, runs Blender, validates budgets, and registers source, GLB, preview, and metadata outputs.",
    caption:
      "The local pipeline drafts the spec, runs Blender, validates budgets, and registers every output.",
  },
  {
    id: "asset-viewer",
    title: "Asset Viewer",
    eyebrow: "Inspect, animate, export",
    start: 48,
    duration: 20,
    narration:
      "The viewer proves assets load, animate, measure cleanly, and are ready for export or capture.",
    caption:
      "The viewer proves assets load, animate, measure cleanly, and are ready for export or capture.",
  },
  {
    id: "world-creator",
    title: "World Creator",
    eyebrow: "Palette to saved worlds",
    start: 68,
    duration: 28,
    narration:
      "Registered assets become a world palette. Worlds can be edited, saved, duplicated, and switched without leaving the creator.",
    caption:
      "Registered assets become a world palette with editing, saved worlds, duplication, and switching.",
  },
  {
    id: "agent-handoff",
    title: "Agent Handoff",
    eyebrow: "JSON, Brief, Generate",
    start: 96,
    duration: 14,
    narration:
      "Agent Handoff gives both machine-readable JSON and a human-readable brief, plus a Generate tab for drafting a new world from a prompt.",
    caption:
      "Agent Handoff shows JSON, Brief, and the Generate tab without running world generation.",
  },
  {
    id: "world-navigation",
    title: "Saved World Navigation",
    eyebrow: "Reusable world library",
    start: 110,
    duration: 6,
    narration:
      "The demo moves across multiple saved worlds to show this is a reusable world library, not a single static map.",
    caption:
      "Saved worlds can be switched before opening the 3D preview.",
  },
  {
    id: "close",
    title: "OnTheSpectrum",
    eyebrow: "Prompt to playable scene",
    start: 116,
    duration: 4,
    narration: "OnTheSpectrum: from prompt to asset to playable scene.",
    caption: "OnTheSpectrum: from prompt to asset to playable scene.",
  },
];

export const previewAssets = [
  {
    id: "painter",
    name: "Painter Chibi",
    family: "Character",
    src: "assets/on_the_spectrum-painter-chibi-preview.png",
    accent: "#28e0ea",
  },
  {
    id: "runner",
    name: "Blaster Runner",
    family: "Character",
    src: "assets/toon-blaster-runner-preview.png",
    accent: "#f47d69",
  },
  {
    id: "ranger",
    name: "Ranger NPC",
    family: "Character",
    src: "assets/forest-ranger-npc-preview.png",
    accent: "#91f0a8",
  },
  {
    id: "blacksmith",
    name: "Blacksmith NPC",
    family: "Character",
    src: "assets/village-blacksmith-npc-preview.png",
    accent: "#e4cf9b",
  },
  {
    id: "portal",
    name: "Violet Rift",
    family: "VFX",
    src: "assets/violet-rift-portal-preview.png",
    accent: "#b58cff",
  },
  {
    id: "beacon",
    name: "Smoke Beacon",
    family: "Prop",
    src: "assets/codex-smoke-beacon-prop-preview.png",
    accent: "#28e0ea",
  },
  {
    id: "workbench",
    name: "Forge Workbench",
    family: "Furniture",
    src: "assets/blacksmith-forge-workbench-preview.png",
    accent: "#f2b56b",
  },
  {
    id: "market",
    name: "Market Stall",
    family: "Furniture",
    src: "assets/village-market-stall-preview.png",
    accent: "#f47d69",
  },
];

export const pipelineSteps = [
  "Queue request",
  "Normalize spec",
  "Write generator",
  "Blender preflight",
  "Generate in Blender",
  "Validate GLB",
  "Register asset",
];

export const outputFiles = [
  { label: "Blender source", path: "public/models/<slug>.blend" },
  { label: "Web GLB", path: "public/models/<slug>.glb" },
  { label: "Preview render", path: "public/renders/<slug>-preview.png" },
  { label: "Metadata", path: "public/models/<slug>.metadata.json" },
];

export const worldNames = [
  "Atelier Nexus",
  "Garden Circuit",
  "Market Concourse",
  "Forge Yard",
  "Rift Arena",
];

export const handoffTabs = [
  {
    id: "json",
    label: "JSON",
    lines: [
      '{',
      '  "schemaVersion": "world-grid.v2",',
      '  "name": "Forge Yard",',
      '  "placements": [ ... ]',
      "}",
    ],
  },
  {
    id: "brief",
    label: "Brief",
    lines: [
      "World: Forge Yard",
      "Use readable combat lanes, one spawn tile, linked doors, cover walls, lights, and workshop props.",
      "Keep all item IDs from the current palette.",
    ],
  },
  {
    id: "generate",
    label: "Generate",
    lines: [
      "Use a 12 x 9 grid with boundary walls, one spawn tile layered with a non-enemy character, one door, readable combat lanes, two enemies, cover walls, three lights, and a few workshop props.",
    ],
  },
];
