import { getOpenAISettings, loadDotEnv } from "./asset_agent.mjs";

const worldSchemaVersion = "artomata.world-grid.v2";
const worldThemes = ["studio-atrium", "toon-lab", "garden-room", "training-floor"];
const structureLayer = "structure";
const occupantLayer = "occupant";
const placementTypes = ["asset", "structure"];
const combatRoles = ["neutral", "player", "enemy-melee", "enemy-ranged"];
const rotations = [0, 90, 180, 270];

function extractResponseText(responseJson) {
  if (typeof responseJson.output_text === "string") return responseJson.output_text;
  const chunks = [];
  for (const item of responseJson.output || []) {
    for (const content of item.content || []) {
      if (content.type === "output_text" && typeof content.text === "string") chunks.push(content.text);
      if (content.type === "refusal") throw new Error(`OpenAI refused the world prompt: ${content.refusal}`);
    }
  }
  return chunks.join("");
}

function paletteItems(currentWorld, key) {
  return Array.isArray(currentWorld?.palette?.[key])
    ? currentWorld.palette[key].filter((item) => typeof item?.id === "string" && item.id.trim())
    : [];
}

function getPaletteContext(currentWorld = {}) {
  const structures = paletteItems(currentWorld, "structures");
  const assets = paletteItems(currentWorld, "assets");
  if (!structures.length || !assets.length) {
    throw new Error("currentWorld.palette.assets and currentWorld.palette.structures are required for world generation.");
  }
  const structureIds = structures.map((item) => item.id);
  const assetIds = assets.map((item) => item.id);
  return {
    structures,
    assets,
    structureIds,
    assetIds,
    itemIds: [...structureIds, ...assetIds],
    itemTypes: new Map([...structureIds.map((id) => [id, "structure"]), ...assetIds.map((id) => [id, "asset"])]),
  };
}

function worldGridJsonSchema(palette) {
  return {
    type: "object",
    additionalProperties: false,
    properties: {
      schemaVersion: { type: "string", enum: [worldSchemaVersion] },
      name: { type: "string" },
      theme: { type: "string", enum: worldThemes },
      grid: {
        type: "object",
        additionalProperties: false,
        properties: {
          columns: { type: "integer", minimum: 6, maximum: 16 },
          rows: { type: "integer", minimum: 5, maximum: 12 },
          cellSize: { type: "string" },
        },
        required: ["columns", "rows", "cellSize"],
      },
      rules: { type: "string" },
      placements: {
        type: "array",
        items: {
          type: "object",
          additionalProperties: false,
          properties: {
            type: { type: "string", enum: placementTypes },
            layer: { type: "string", enum: [structureLayer, occupantLayer] },
            itemId: { type: "string", enum: palette.itemIds },
            x: { type: "integer", minimum: 0, maximum: 15 },
            y: { type: "integer", minimum: 0, maximum: 11 },
            rotation: { type: "integer", enum: rotations },
            scale: { type: "number", minimum: 0.5, maximum: 1.75 },
            elevation: { type: "number", minimum: -5, maximum: 5 },
            tags: {
              type: "array",
              items: { type: "string" },
            },
            notes: { type: "string" },
            combat: {
              anyOf: [
                { type: "null" },
                {
                  type: "object",
                  additionalProperties: false,
                  properties: {
                    role: { type: "string", enum: combatRoles },
                  },
                  required: ["role"],
                },
              ],
            },
            targetWorldId: { type: "null" },
          },
          required: [
            "type",
            "layer",
            "itemId",
            "x",
            "y",
            "rotation",
            "scale",
            "elevation",
            "tags",
            "notes",
            "combat",
            "targetWorldId",
          ],
        },
      },
    },
    required: ["schemaVersion", "name", "theme", "grid", "rules", "placements"],
  };
}

function clampInteger(value, min, max, fallback) {
  const parsed = Number(value);
  if (!Number.isFinite(parsed)) return fallback;
  return Math.min(max, Math.max(min, Math.round(parsed)));
}

function clampNumber(value, min, max, fallback) {
  const parsed = Number(value);
  if (!Number.isFinite(parsed)) return fallback;
  return Math.min(max, Math.max(min, parsed));
}

function nearestRotation(value) {
  const parsed = clampInteger(value, 0, 359, 0);
  return rotations.reduce((best, rotation) => (Math.abs(rotation - parsed) < Math.abs(best - parsed) ? rotation : best), 0);
}

function stringList(value, fallback = []) {
  if (!Array.isArray(value)) return fallback;
  return value
    .map((item) => String(item || "").trim())
    .filter(Boolean)
    .slice(0, 8);
}

function normalizePlacement(rawPlacement, palette, columns, rows, occupied) {
  const itemId = String(rawPlacement?.itemId || "").trim();
  const inferredType = palette.itemTypes.get(itemId);
  if (!inferredType) return null;
  const type = inferredType;
  const layer = type === "asset" ? occupantLayer : structureLayer;
  const x = Number(rawPlacement?.x);
  const y = Number(rawPlacement?.y);
  if (!Number.isInteger(x) || !Number.isInteger(y) || x < 0 || y < 0 || x >= columns || y >= rows) return null;
  const occupiedKey = `${x}:${y}:${layer}`;
  if (occupied.has(occupiedKey)) return null;
  occupied.add(occupiedKey);
  const combatRole = rawPlacement?.combat?.role;
  return {
    type,
    layer,
    itemId,
    x,
    y,
    rotation: nearestRotation(rawPlacement?.rotation),
    scale: clampNumber(rawPlacement?.scale, 0.5, 1.75, 1),
    elevation: clampNumber(rawPlacement?.elevation, -5, 5, 0),
    tags: stringList(rawPlacement?.tags, type === "asset" ? ["generated", "asset"] : ["generated", "structure"]),
    notes: String(rawPlacement?.notes || "").trim(),
    ...(type === "asset" && combatRoles.includes(combatRole) ? { combat: { role: combatRole } } : {}),
  };
}

function normalizeGeneratedWorld(rawWorld, currentWorld, palette) {
  const grid = rawWorld?.grid && typeof rawWorld.grid === "object" ? rawWorld.grid : {};
  const columns = clampInteger(grid.columns ?? rawWorld?.columns ?? currentWorld?.grid?.columns, 6, 16, 12);
  const rows = clampInteger(grid.rows ?? rawWorld?.rows ?? currentWorld?.grid?.rows, 5, 12, 9);
  const occupied = new Set();
  const placements = (Array.isArray(rawWorld?.placements) ? rawWorld.placements : [])
    .map((placement) => normalizePlacement(placement, palette, columns, rows, occupied))
    .filter(Boolean);
  if (!placements.length) {
    throw new Error("OpenAI produced no valid world placements.");
  }
  return {
    schemaVersion: worldSchemaVersion,
    name: String(rawWorld?.name || "Generated World").trim() || "Generated World",
    theme: worldThemes.includes(rawWorld?.theme) ? rawWorld.theme : currentWorld?.theme || "training-floor",
    grid: {
      columns,
      rows,
      cellSize: typeof grid.cellSize === "string" && grid.cellSize.trim() ? grid.cellSize.trim() : currentWorld?.grid?.cellSize || "1m",
    },
    rules: String(rawWorld?.rules || currentWorld?.rules || "Keep the spawn reachable and preserve readable traversal lanes.").trim(),
    placements,
  };
}

function worldPromptInput(prompt, currentWorld, palette) {
  const compactWorld = {
    name: currentWorld?.name,
    theme: currentWorld?.theme,
    grid: currentWorld?.grid,
    rules: currentWorld?.rules,
  };
  return [
    `World prompt:\n${prompt}`,
    `Current world context:\n${JSON.stringify(compactWorld, null, 2)}`,
    `Valid structures:\n${JSON.stringify(palette.structures.map(({ id, label, family, agentHint }) => ({ id, label, family, agentHint })), null, 2)}`,
    `Valid assets:\n${JSON.stringify(palette.assets.map(({ id, label, family }) => ({ id, label, family })), null, 2)}`,
  ].join("\n\n");
}

async function generateWorld({ prompt = "", currentWorld = {} } = {}) {
  loadDotEnv();
  const apiKey = process.env.OPENAI_API_KEY || process.env["OPENAI-KEY"];
  if (!apiKey) throw new Error("Missing OPENAI_API_KEY in .env. OPENAI-KEY is also supported.");
  const palette = getPaletteContext(currentWorld);
  const model = process.env.OPENAI_MODEL || "gpt-5.5";
  const requestBody = {
    model,
    input: [
      {
        role: "system",
        content:
          "You create one Artomata world-grid JSON document from a prompt. Use only the supplied palette itemIds. Structures must use type structure and layer structure; assets must use type asset and layer occupant. Keep x/y integer coordinates inside the grid. Use at most one structure and one occupant per cell. When placing a playable character on a spawn tile, set combat.role to player. Do not create linked multi-world output; always set targetWorldId to null. Return concise tags and notes that explain layout intent.",
      },
      {
        role: "user",
        content: worldPromptInput(prompt || "Create a compact playable training world.", currentWorld, palette),
      },
    ],
    text: {
      format: {
        type: "json_schema",
        name: "artomata_world_grid",
        strict: true,
        schema: worldGridJsonSchema(palette),
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
  const rawWorld = JSON.parse(outputText);
  return {
    world: normalizeGeneratedWorld(rawWorld, currentWorld, palette),
    model,
  };
}

export { generateWorld, normalizeGeneratedWorld, worldGridJsonSchema };
