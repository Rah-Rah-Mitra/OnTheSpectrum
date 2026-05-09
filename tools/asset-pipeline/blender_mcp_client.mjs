import net from "node:net";
import path from "node:path";

const defaultHost = process.env.BLENDER_MCP_HOST || process.env.BLENDER_HOST || "127.0.0.1";
const defaultPort = Number(process.env.BLENDER_MCP_PORT || process.env.BLENDER_PORT || 9876);
const responseDelimiter = "\0";

export function checkBlenderMcp({ host = defaultHost, port = defaultPort, timeoutMs = 1000 } = {}) {
  return new Promise((resolve) => {
    const socket = net.createConnection({ host, port });
    let settled = false;
    const finish = (value) => {
      if (settled) return;
      settled = true;
      socket.destroy();
      resolve(value);
    };
    socket.setTimeout(timeoutMs);
    socket.once("connect", () => finish(true));
    socket.once("timeout", () => finish(false));
    socket.once("error", () => finish(false));
  });
}

export function sendBlenderCommand(type, params = {}, { host = defaultHost, port = defaultPort, timeoutMs = 600000 } = {}) {
  return new Promise((resolve, reject) => {
    const socket = net.createConnection({ host, port });
    let buffer = Buffer.alloc(0);
    let settled = false;

    const finish = (error, value) => {
      if (settled) return;
      settled = true;
      socket.destroy();
      if (error) reject(error);
      else resolve(value);
    };

    socket.setTimeout(timeoutMs);
    socket.once("connect", () => {
      socket.write(`${JSON.stringify({ type, ...params })}${responseDelimiter}`, "utf8");
    });
    socket.on("data", (chunk) => {
      buffer = Buffer.concat([buffer, chunk]);
      const delimiterIndex = buffer.indexOf(0);
      if (delimiterIndex < 0) return;
      const text = buffer.subarray(0, delimiterIndex).toString("utf8");
      try {
        const payload = JSON.parse(text);
        finish(null, payload);
      } catch (error) {
        finish(new Error(`Blender MCP returned invalid JSON: ${error.message}`));
      }
    });
    socket.once("timeout", () => finish(new Error(`Timed out waiting for Blender MCP ${type} response.`)));
    socket.once("error", (error) => finish(error));
    socket.once("end", () => {
      if (settled) return;
      const text = buffer.toString("utf8").replace(/\0.*$/s, "").trim();
      if (!text) finish(new Error("Blender MCP closed the connection without a response."));
      try {
        finish(null, JSON.parse(text));
      } catch {
        finish(new Error(`Blender MCP returned invalid JSON: ${text.slice(0, 500)}`));
      }
    });
  });
}

export async function executeBlenderCode(code, options) {
  const payload = await sendBlenderCommand("execute", { code, strict_json: false }, options);
  if (payload.status === "error") throw new Error(payload.message || "Blender MCP execute failed.");
  return payload.result ?? payload;
}

export async function probeBlenderMcp(options) {
  try {
    const result = await executeBlenderCode("result = {'ok': True}", { timeoutMs: 5000, ...options });
    return { ok: Boolean(result?.ok), result };
  } catch (error) {
    return { ok: false, error: error?.message || String(error) };
  }
}

export async function runGeneratorViaMcp(generatorPath, repoRoot, options) {
  const moduleName = `artomata_generated_${path.basename(generatorPath).replace(/[^A-Za-z0-9_]/g, "_")}`;
  const code = `
import importlib.util
import json
import os
import sys
from pathlib import Path

repo_root = Path(${JSON.stringify(repoRoot)})
generator_path = Path(${JSON.stringify(generatorPath)})
asset_pipeline = repo_root / "tools" / "asset-pipeline"
os.chdir(str(repo_root))
if str(asset_pipeline) not in sys.path:
    sys.path.insert(0, str(asset_pipeline))

spec = importlib.util.spec_from_file_location(${JSON.stringify(moduleName)}, str(generator_path))
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)
asset_result = module.main()
result = {"ok": True, "asset_result": asset_result}
`;
  return executeBlenderCode(code, options);
}
