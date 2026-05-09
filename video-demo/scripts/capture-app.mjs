import { mkdirSync, writeFileSync } from "node:fs";
import http from "node:http";
import path from "node:path";
import { spawn } from "node:child_process";
import { fileURLToPath } from "node:url";
import { chromium } from "playwright-core";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const projectRoot = path.resolve(__dirname, "..");
const repoRoot = path.resolve(projectRoot, "..");
const captureDir = path.join(projectRoot, "public", "captures");
const manifestPath = path.join(projectRoot, "src", "captureManifest.generated.json");
const appUrl = process.env.APP_URL || "http://127.0.0.1:5173";
const noServer = process.argv.includes("--no-server");

mkdirSync(captureDir, { recursive: true });

function waitForHttp(url, timeoutMs = 90000) {
  const started = Date.now();
  return new Promise((resolve, reject) => {
    const check = () => {
      const request = http.get(url, (response) => {
        response.resume();
        if (response.statusCode && response.statusCode < 500) {
          resolve();
        } else if (Date.now() - started > timeoutMs) {
          reject(new Error(`Timed out waiting for ${url}`));
        } else {
          setTimeout(check, 1000);
        }
      });
      request.on("error", () => {
        if (Date.now() - started > timeoutMs) {
          reject(new Error(`Timed out waiting for ${url}`));
        } else {
          setTimeout(check, 1000);
        }
      });
      request.setTimeout(2500, () => request.destroy());
    };
    check();
  });
}

async function launchBrowser() {
  const common = {
    headless: true,
    args: ["--disable-gpu", "--disable-dev-shm-usage", "--hide-scrollbars"],
  };
  if (process.env.CHROME_PATH) {
    return chromium.launch({ ...common, executablePath: process.env.CHROME_PATH });
  }
  try {
    return await chromium.launch({ ...common, channel: process.env.PLAYWRIGHT_CHROME_CHANNEL || "chrome" });
  } catch {
    return chromium.launch({ ...common, channel: "msedge" });
  }
}

async function settle(page, ms = 1800) {
  await page.waitForLoadState("domcontentloaded");
  await page.waitForTimeout(ms);
}

async function screenshot(page, name) {
  const src = `captures/${name}.png`;
  await page.screenshot({
    path: path.join(captureDir, `${name}.png`),
    fullPage: false,
  });
  return { src };
}

async function panelScreenshot(page, name, selector) {
  const src = `captures/${name}.png`;
  const panel = page.locator(selector).last();
  if ((await panel.count()) === 0) return screenshot(page, name);
  await panel.screenshot({
    path: path.join(captureDir, `${name}.png`),
  });
  return { src };
}

let serverProcess = null;
if (!noServer) {
  const command = process.platform === "win32" ? "npm run dev" : "npm";
  const args = process.platform === "win32" ? [] : ["run", "dev"];
  serverProcess = spawn(command, args, {
    cwd: repoRoot,
    shell: process.platform === "win32",
    stdio: ["ignore", "ignore", "ignore"],
    env: { ...process.env },
  });
}

const captures = {};

try {
  await waitForHttp(appUrl);
  const browser = await launchBrowser();
  const page = await browser.newPage({ viewport: { width: 1920, height: 1080 }, deviceScaleFactor: 1 });

  await page.goto(`${appUrl}/#generator`);
  await settle(page, 2600);
  captures.generator = await screenshot(page, "generator");

  await page.goto(`${appUrl}/#viewer`);
  await settle(page, 2600);
  captures.viewer = await screenshot(page, "viewer");

  await page.goto(`${appUrl}/#world`);
  await settle(page, 2600);
  captures["world-grid"] = await screenshot(page, "world-grid");

  const jsonTab = page.getByRole("button", { name: /^JSON$/ });
  const briefTab = page.getByRole("button", { name: /^Brief$/ });
  const generateTab = page.getByRole("button", { name: /^Generate$/ });

  await jsonTab.click().catch(() => undefined);
  await settle(page, 900);
  captures["agent-handoff-json"] = await panelScreenshot(page, "agent-handoff-json", ".agent-panel");

  await briefTab.click().catch(() => undefined);
  await settle(page, 900);
  captures["agent-handoff-brief"] = await panelScreenshot(page, "agent-handoff-brief", ".agent-panel");

  await generateTab.click().catch(() => undefined);
  await settle(page, 1200);
  captures["agent-handoff-generate"] = await panelScreenshot(page, "agent-handoff-generate", ".agent-panel");

  const activeWorldSelect = page.locator(".world-select-field select");
  const options = await activeWorldSelect.locator("option").evaluateAll((nodes) =>
    nodes.map((node) => ({ value: node.value, label: node.textContent || "" })),
  );
  for (const option of options.slice(0, 4)) {
    await activeWorldSelect.selectOption(option.value).catch(() => undefined);
    await settle(page, 450);
  }
  captures["world-switch"] = await screenshot(page, "world-switch");

  await page.goto(`${appUrl}/#world-3d`);
  await settle(page, 3600);
  captures["world-3d"] = await screenshot(page, "world-3d");

  await browser.close();
} finally {
  if (serverProcess) serverProcess.kill();
}

writeFileSync(
  manifestPath,
  `${JSON.stringify(
    {
      generated: true,
      generatedAt: new Date().toISOString(),
      appUrl,
      captures,
    },
    null,
    2,
  )}\n`,
);

console.log(`Capture manifest written to ${path.relative(projectRoot, manifestPath)}`);
