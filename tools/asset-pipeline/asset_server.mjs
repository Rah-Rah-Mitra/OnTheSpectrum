import http from "node:http";
import { randomUUID } from "node:crypto";
import {
  generateAsset,
  getOpenAISettings,
  hasBackgroundBlender,
  loadDotEnv,
  runPreflight,
} from "./asset_agent.mjs";
import { generateWorld } from "./world_agent.mjs";
import { probeBlenderMcp } from "./blender_mcp_client.mjs";

const host = process.env.ASSET_API_HOST || "127.0.0.1";
const port = Number(process.env.ASSET_API_PORT || 5174);
const maxBodyBytes = 1024 * 1024;

const stepTemplate = [
  { id: "queue", label: "Queue request" },
  { id: "normalize", label: "Normalize spec" },
  { id: "write", label: "Write generator" },
  { id: "preflight", label: "Blender preflight" },
  { id: "generate", label: "Generate in Blender" },
  { id: "validate", label: "Validate GLB" },
  { id: "register", label: "Register asset" },
];

const jobs = new Map();

function json(res, status, payload) {
  res.writeHead(status, {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Headers": "Content-Type",
    "Access-Control-Allow-Methods": "GET,POST,OPTIONS",
    "Content-Type": "application/json; charset=utf-8",
    "Cache-Control": "no-store",
  });
  res.end(JSON.stringify(payload, null, 2));
}

function readJson(req) {
  return new Promise((resolve, reject) => {
    const chunks = [];
    let size = 0;
    req.on("data", (chunk) => {
      size += chunk.length;
      if (size > maxBodyBytes) {
        reject(new Error("Request body is too large."));
        req.destroy();
        return;
      }
      chunks.push(chunk);
    });
    req.on("end", () => {
      const text = Buffer.concat(chunks).toString("utf8").trim();
      if (!text) {
        resolve({});
        return;
      }
      try {
        resolve(JSON.parse(text));
      } catch {
        reject(new Error("Request body must be valid JSON."));
      }
    });
    req.on("error", reject);
  });
}

function text(value, fallback = "") {
  return String(value ?? fallback).trim();
}

function listText(value, fallback) {
  const items = String(value || "")
    .split(/\n|,/)
    .map((item) => item.trim())
    .filter(Boolean);
  return (items.length ? items : fallback).join(", ");
}

function buildBriefFromForm(form = {}) {
  const family = text(form.type, "prop");
  const name = text(form.name, `${family === "vfx" ? "VFX" : family} concept`);
  const lines = [
    `Type: ${family === "vfx" ? "VFX" : family}`,
    family === "vfx" ? `VFX family: ${text(form.vfxFamily, "custom")}` : null,
    `Name: ${name}`,
    `Style: ${text(form.style, "Stylized Artomata procedural asset")}`,
    `Required parts: ${listText(form.requiredParts, ["primary silhouette", "detail accents", "display base"])}`,
    `Materials/colors: ${listText(form.materials, ["matte primary color", "secondary accent", "soft contact shadow"])}`,
    `Rigging: ${family === "vfx" ? "simple transform rig" : text(form.rigging, "none")}`,
    `Animations: ${text(form.animations, "default")}${text(form.animationNotes) ? `, ${text(form.animationNotes)}` : ""}`,
    family === "vfx" ? `Motion behavior: ${text(form.motionBehavior, "Looping transform motion with baked mesh accents")}` : null,
    family === "vfx" ? `Duration and loop: ${text(form.loopMode, "looping")}, ${text(form.durationSeconds, "4")} seconds` : null,
    family === "vfx" ? `Emission source: ${text(form.emissionSource, "free-floating")}` : null,
    family === "vfx" ? `Transparency style: ${text(form.transparencyStyle, "additive glow")}` : null,
    family === "vfx" ? `Implementation preference: ${text(form.implementationPreference, "GLB-compatible baked mesh/curve animation")}` : null,
    `Viewer framing notes: ${text(form.viewerFraming, "Centered front-quarter viewer framing")}`,
    "Performance budget: keep under 100k triangles, 16 materials, 12 MB GLB unless explicitly approved",
  ].filter(Boolean);
  return [text(form.freeformBrief), lines.join("\n")].filter(Boolean).join("\n\n");
}

function getRequestBrief(body) {
  const form = body.form && typeof body.form === "object" ? body.form : body;
  return {
    family: text(body.family || form.type, "prop"),
    brief: text(body.brief) || buildBriefFromForm(form),
    name: text(form.name, "Generated Asset"),
  };
}

async function preflightPayload() {
  const preflight = runPreflight();
  const report = preflight.report || {};
  const backgroundAvailable = hasBackgroundBlender(report);
  const mcpListening = Boolean(report.mcp_bridge?.listening);
  const mcpProbe = mcpListening ? await probeBlenderMcp() : { ok: false };
  const mcpExecutable = Boolean(mcpListening && mcpProbe.ok);
  return {
    status: preflight.status,
    ready: mcpExecutable || backgroundAvailable,
    output: preflight.output,
    report,
    mcpBridge: {
      host: report.mcp_bridge?.host || "127.0.0.1",
      port: report.mcp_bridge?.port || 9876,
      listening: mcpListening,
      executable: mcpExecutable,
      probe: mcpProbe,
    },
    background: report.background_blender || {},
    backgroundAvailable,
    setupHint: mcpExecutable || backgroundAvailable
      ? ""
      : mcpListening
        ? "Blender MCP is listening but execute_code did not respond. Restart Blender with the MCP add-on server enabled, or configure BLENDER_PATH."
        : "Start Blender with the MCP add-on server on 127.0.0.1:9876, or configure BLENDER_PATH for background generation.",
  };
}

function createJob({ family, name, brief }) {
  const now = new Date().toISOString();
  return {
    id: randomUUID(),
    status: "queued",
    family,
    name,
    brief,
    createdAt: now,
    updatedAt: now,
    steps: stepTemplate.map((step) => ({ ...step, status: step.id === "queue" ? "completed" : "pending", detail: "" })),
    events: [],
    result: null,
    error: "",
  };
}

function summarizeJob(job) {
  if (!job) return null;
  return {
    id: job.id,
    status: job.status,
    family: job.family,
    name: job.name,
    createdAt: job.createdAt,
    updatedAt: job.updatedAt,
    steps: job.steps,
    result: job.result,
    error: job.error,
  };
}

function activeJob() {
  return [...jobs.values()].find((job) => job.status === "queued" || job.status === "running") || null;
}

function latestJob() {
  return [...jobs.values()].sort((a, b) => b.updatedAt.localeCompare(a.updatedAt))[0] || null;
}

function updateStep(job, event) {
  const now = event.at || new Date().toISOString();
  job.updatedAt = now;
  job.events.push(event);
  const step = job.steps.find((item) => item.id === event.step);
  if (step) {
    step.status = event.status;
    step.detail = event.detail || "";
    step.updatedAt = now;
    if (event.payload) step.payload = event.payload;
  }
}

function failActiveStep(job, message) {
  const active = [...job.steps].reverse().find((step) => step.status === "running");
  if (active) {
    active.status = "failed";
    active.detail = message;
    active.updatedAt = new Date().toISOString();
  }
}

function pruneJobs() {
  const ordered = [...jobs.values()].sort((a, b) => b.updatedAt.localeCompare(a.updatedAt));
  for (const stale of ordered.slice(20)) jobs.delete(stale.id);
}

async function runJob(job) {
  job.status = "running";
  job.updatedAt = new Date().toISOString();
  updateStep(job, { step: "queue", status: "completed", detail: "Generation started.", at: job.updatedAt });
  try {
    const result = await generateAsset({
      brief: job.brief,
      family: job.family,
      onProgress: (event) => updateStep(job, event),
    });
    job.status = "completed";
    job.result = result;
    job.updatedAt = new Date().toISOString();
  } catch (error) {
    const message = error?.message || String(error);
    job.status = "failed";
    job.error = message;
    job.updatedAt = new Date().toISOString();
    failActiveStep(job, message);
  } finally {
    pruneJobs();
  }
}

async function handleRequest(req, res) {
  if (req.method === "OPTIONS") {
    json(res, 204, {});
    return;
  }

  const url = new URL(req.url || "/", `http://${req.headers.host || `${host}:${port}`}`);

  if (req.method === "GET" && url.pathname === "/api/assets/status") {
    loadDotEnv();
    json(res, 200, {
      ok: true,
      openai: getOpenAISettings(),
      blender: await preflightPayload(),
      currentJob: summarizeJob(activeJob() || latestJob()),
    });
    return;
  }

  if (req.method === "GET" && url.pathname === "/api/worlds/status") {
    loadDotEnv();
    json(res, 200, {
      ok: true,
      openai: getOpenAISettings(),
    });
    return;
  }

  if (req.method === "GET" && url.pathname.startsWith("/api/assets/jobs/")) {
    const id = decodeURIComponent(url.pathname.split("/").pop() || "");
    const job = jobs.get(id);
    if (!job) {
      json(res, 404, { ok: false, error: "Unknown asset generation job." });
      return;
    }
    json(res, 200, { ok: true, job: summarizeJob(job) });
    return;
  }

  if (req.method === "POST" && url.pathname === "/api/assets/generate") {
    const current = activeJob();
    if (current) {
      json(res, 409, { ok: false, error: "Another asset generation job is already running.", currentJob: summarizeJob(current) });
      return;
    }
    const settings = getOpenAISettings();
    if (!settings.hasApiKey) {
      json(res, 400, { ok: false, error: "Missing OPENAI_API_KEY in .env. OPENAI-KEY is also supported." });
      return;
    }
    const blender = await preflightPayload();
    if (!blender.ready) {
      json(res, 400, { ok: false, error: blender.setupHint || "Blender is not ready for local asset generation.", blender });
      return;
    }
    const body = await readJson(req);
    const request = getRequestBrief(body);
    const job = createJob(request);
    jobs.set(job.id, job);
    setImmediate(() => runJob(job));
    json(res, 202, { ok: true, job: summarizeJob(job) });
    return;
  }

  if (req.method === "POST" && url.pathname === "/api/worlds/generate") {
    const settings = getOpenAISettings();
    if (!settings.hasApiKey) {
      json(res, 400, { ok: false, error: "Missing OPENAI_API_KEY in .env. OPENAI-KEY is also supported." });
      return;
    }
    const body = await readJson(req);
    const result = await generateWorld({
      prompt: text(body.prompt, "Create a compact playable training world."),
      currentWorld: body.currentWorld && typeof body.currentWorld === "object" ? body.currentWorld : {},
    });
    json(res, 200, { ok: true, world: result.world });
    return;
  }

  json(res, 404, { ok: false, error: "Not found." });
}

loadDotEnv();
const server = http.createServer((req, res) => {
  handleRequest(req, res).catch((error) => json(res, 500, { ok: false, error: error?.message || String(error) }));
});

server.listen(port, host, () => {
  console.log(`Asset generation API listening on http://${host}:${port}`);
});
