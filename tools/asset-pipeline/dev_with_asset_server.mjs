import { spawn } from "node:child_process";

const children = [];

function start(label, command, args, env = {}) {
  const child = spawn(command, args, {
    env: { ...process.env, ...env },
    stdio: "inherit",
  });
  children.push(child);
  child.on("exit", (code, signal) => {
    if (shuttingDown) return;
    console.error(`${label} exited${signal ? ` via ${signal}` : ` with code ${code}`}.`);
    shutdown(code || 1);
  });
  return child;
}

let shuttingDown = false;

function shutdown(code = 0) {
  if (shuttingDown) return;
  shuttingDown = true;
  for (const child of children) {
    if (!child.killed) child.kill();
  }
  process.exitCode = code;
}

process.on("SIGINT", () => shutdown(0));
process.on("SIGTERM", () => shutdown(0));

const assetApiHost = process.env.ASSET_API_HOST || "127.0.0.1";
const assetApiPort = process.env.ASSET_API_PORT || "5174";
const vitePort = process.env.VITE_DEV_PORT || "5173";

start("asset:server", process.execPath, ["tools/asset-pipeline/asset_server.mjs"], {
  ASSET_API_HOST: assetApiHost,
  ASSET_API_PORT: assetApiPort,
});
start("vite", process.execPath, ["node_modules/vite/bin/vite.js", "--host", "127.0.0.1", "--port", vitePort], {
  VITE_ASSET_API_BASE: `http://${assetApiHost}:${assetApiPort}`,
});
