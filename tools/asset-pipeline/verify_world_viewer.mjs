import os from "node:os";
import path from "node:path";
import { pathToFileURL } from "node:url";

const url = process.argv[2] || "http://127.0.0.1:5173/#world-3d";
const chromePath =
  process.env.CHROME_PATH ||
  "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe";

async function loadPlaywright() {
  try {
    return await import("playwright");
  } catch {
    const bundledPlaywright = path.join(
      os.homedir(),
      ".cache",
      "codex-runtimes",
      "codex-primary-runtime",
      "dependencies",
      "node",
      "node_modules",
      "playwright",
      "index.mjs",
    );
    return import(pathToFileURL(bundledPlaywright).href);
  }
}

async function openWorldPage(chromium, viewport) {
  const browser = await chromium.launch({
    headless: true,
    executablePath: chromePath,
    args: ["--disable-gpu", "--enable-unsafe-swiftshader", "--use-angle=swiftshader"],
  });
  const page = await browser.newPage(viewport);
  const consoleIssues = [];
  const requestFailures = [];
  page.on("console", (message) => {
    if (["warning", "error"].includes(message.type())) consoleIssues.push(`${message.type()}: ${message.text()}`);
  });
  page.on("pageerror", (error) => consoleIssues.push(`exception: ${error.message}`));
  page.on("requestfailed", (request) => requestFailures.push(`${request.url()} :: ${request.failure()?.errorText}`));
  await page.goto(url, { waitUntil: "load", timeout: 30000 });
  await page.waitForFunction(() => document.querySelector(".world-viewport-shell")?.dataset.worldAssets === "4/4", null, {
    timeout: 45000,
  });
  return { browser, page, consoleIssues, requestFailures };
}

async function readWorldState(page) {
  return page.evaluate(() => ({
    title: document.title,
    hash: window.location.hash,
    activeView: document.querySelector('[aria-label="World view mode"] button.active')?.textContent?.trim() || "",
    statusData: document.querySelector(".world-viewport-shell")?.dataset.worldStatus || "",
    statusText: document.querySelector(".world-viewport-status")?.innerText || "",
    assets: document.querySelector(".world-viewport-shell")?.dataset.worldAssets || "",
    canvasLength: document.querySelector(".world-viewport canvas")?.toDataURL("image/png").length || 0,
    horizontalOverflow: document.documentElement.scrollWidth > window.innerWidth + 1,
    frameworkOverlay: document.body.innerText.includes("Internal server error") || document.body.innerText.includes("Failed to compile"),
  }));
}

async function main() {
  const { chromium } = await loadPlaywright();
  const desktop = await openWorldPage(chromium, { viewport: { width: 1440, height: 900 }, deviceScaleFactor: 1 });
  try {
    const desktopState = await readWorldState(desktop.page);
    await desktop.page.getByRole("button", { name: "Enter World" }).click();
    await desktop.page
      .waitForFunction(() => document.querySelector(".world-viewport-shell")?.dataset.exploring === "true", null, {
        timeout: 3000,
      })
      .catch(() => undefined);
    const entered = await desktop.page.evaluate(() => ({
      exploring: document.querySelector(".world-viewport-shell")?.dataset.exploring || "",
      pointerLocked: Boolean(document.pointerLockElement),
      fullscreen: Boolean(document.fullscreenElement),
    }));
    await desktop.page.keyboard.press("Escape");
    await desktop.page
      .waitForFunction(() => document.querySelector(".world-viewport-shell")?.dataset.exploring === "false", null, {
        timeout: 3000,
      })
      .catch(() => undefined);
    const exited = await desktop.page.evaluate(() => ({
      exploring: document.querySelector(".world-viewport-shell")?.dataset.exploring || "",
      pointerLocked: Boolean(document.pointerLockElement),
      fullscreen: Boolean(document.fullscreenElement),
    }));

    await desktop.page.getByRole("button", { name: "Grid" }).click();
    const occupiedBefore = await desktop.page.locator(".world-cell.occupied").count();
    await desktop.page.locator('[aria-label="Empty cell 2, 2"]').click();
    await desktop.page.waitForSelector('[aria-label="Painter Chibi at 2, 2"]', { timeout: 10000 });
    const occupiedAfter = await desktop.page.locator(".world-cell.occupied").count();
    await desktop.page.getByRole("button", { name: "3D" }).click();
    await desktop.page.waitForFunction(() => document.querySelector(".world-viewport-shell")?.dataset.worldAssets === "5/5", null, {
      timeout: 45000,
    });
    const updated3dState = await readWorldState(desktop.page);

    await desktop.page.setViewportSize({ width: 390, height: 844 });
    await desktop.page.waitForTimeout(600);
    const mobileState = await readWorldState(desktop.page);

    const relevantConsoleIssues = desktop.consoleIssues.filter(
      (issue) => !issue.includes("ReadPixels") && !issue.includes("favicon.ico"),
    );
    const requestFailures = desktop.requestFailures;
    const result = {
      url,
      desktopState,
      entered,
      exited,
      gridEditState: { occupiedBefore, occupiedAfter },
      updated3dState,
      mobileState,
      requestFailures,
      consoleIssues: relevantConsoleIssues,
      checks: {
        pageIdentity: desktopState.title === "Artomata Asset Viewer" && desktopState.hash === "#world-3d",
        desktop3dReady:
          desktopState.activeView === "3D" &&
          desktopState.statusData === "ready" &&
          desktopState.assets === "4/4" &&
          desktopState.canvasLength > 5000,
        navigationEntryAndExit:
          entered.exploring === "true" &&
          entered.pointerLocked === true &&
          exited.exploring === "false" &&
          exited.pointerLocked === false &&
          exited.fullscreen === false,
        gridEditLiveUpdate:
          occupiedAfter === occupiedBefore + 1 &&
          updated3dState.statusData === "ready" &&
          updated3dState.assets === "5/5" &&
          updated3dState.canvasLength > 5000,
        mobile3dReady:
          mobileState.activeView === "3D" &&
          mobileState.statusData === "ready" &&
          mobileState.canvasLength > 5000,
        mobileNoHorizontalOverflow: mobileState.horizontalOverflow === false,
        noFrameworkOverlay: !desktopState.frameworkOverlay && !mobileState.frameworkOverlay,
        consoleHealth: relevantConsoleIssues.length === 0 && requestFailures.length === 0,
      },
    };
    console.log(JSON.stringify(result, null, 2));
    process.exit(Object.values(result.checks).every(Boolean) ? 0 : 1);
  } finally {
    await desktop.browser.close();
  }
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
