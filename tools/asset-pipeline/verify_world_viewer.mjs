import os from "node:os";
import path from "node:path";
import { pathToFileURL } from "node:url";

const url = process.argv[2] || "http://127.0.0.1:5173/#world-3d";
const chromePath =
  process.env.CHROME_PATH ||
  "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe";
const expectedSeedWorlds = [
  { id: "seed-atelier-nexus", name: "Atelier Nexus" },
  { id: "seed-garden-circuit", name: "Garden Circuit" },
  { id: "seed-market-concourse", name: "Market Concourse" },
  { id: "seed-forge-yard", name: "Forge Yard" },
  { id: "seed-rift-arena", name: "Rift Arena" },
];

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
  await page.addInitScript(() => {
    window.localStorage.removeItem("on_the_spectrum.world-library.v1");
  });
  await page.goto(url, { waitUntil: "load", timeout: 30000 });
  await waitForWorldReady(page);
  return { browser, page, consoleIssues, requestFailures };
}

async function waitForWorldReady(page) {
  await page.waitForFunction(
    () => {
      const shell = document.querySelector(".world-viewport-shell");
      if (!shell || shell.dataset.worldStatus !== "ready") return false;
      const [loaded, total] = String(shell.dataset.worldAssets || "0/0").split("/").map(Number);
      return Number.isFinite(loaded) && Number.isFinite(total) && loaded === total;
    },
    null,
    { timeout: 45000 },
  );
}

function readHealthValue(value) {
  return Number(String(value || "0").split("/")[0]);
}

async function readWorldOptions(page) {
  return page.$$eval('[aria-label="Saved worlds"] select option', (options) =>
    options.map((option) => ({ value: option.value, name: option.textContent?.trim() || "" })),
  );
}

async function readSeedLoadStates(page, activeWorldSelect) {
  const states = [];
  for (const seed of expectedSeedWorlds) {
    await activeWorldSelect.selectOption(seed.id);
    await waitForWorldReady(page);
    states.push({
      expected: seed,
      ...(await readWorldState(page)),
    });
  }
  return states;
}

async function deleteUntilOnlyWorld(page, activeWorldSelect, keepWorldId) {
  let options = await readWorldOptions(page);
  while (options.length > 1) {
    const deleteTarget = options.find((option) => option.value !== keepWorldId);
    if (!deleteTarget) break;
    await activeWorldSelect.selectOption(deleteTarget.value);
    await page.getByRole("button", { name: "Delete" }).click();
    await page.waitForFunction(
      (expectedCount) => document.querySelectorAll('[aria-label="Saved worlds"] option').length === expectedCount,
      options.length - 1,
      { timeout: 10000 },
    );
    options = await readWorldOptions(page);
  }
  await activeWorldSelect.selectOption(keepWorldId);
}

async function readWorldState(page) {
  for (let attempt = 0; attempt < 3; attempt += 1) {
    try {
      return await page.evaluate(() => ({
        title: document.title,
        hash: window.location.hash,
        activeView: document.querySelector('[aria-label="World view mode"] button.active')?.textContent?.trim() || "",
        statusData: document.querySelector(".world-viewport-shell")?.dataset.worldStatus || "",
        statusText: document.querySelector(".world-viewport-status")?.innerText || "",
        assets: document.querySelector(".world-viewport-shell")?.dataset.worldAssets || "",
        controlMode: document.querySelector(".world-viewport-shell")?.dataset.controlMode || "",
        gameActive: document.querySelector(".world-viewport-shell")?.dataset.gameActive || "",
        playerHealth: document.querySelector(".world-viewport-shell")?.dataset.playerHealth || "",
        enemiesAlive: Number(document.querySelector(".world-viewport-shell")?.dataset.enemiesAlive || 0),
        enemyHealth: Number(document.querySelector(".world-viewport-shell")?.dataset.enemyHealth || 0),
        activeWorldId: document.querySelector(".world-viewport-shell")?.dataset.activeWorldId || "",
        doorPrompt: document.querySelector(".world-viewport-shell")?.dataset.doorPrompt || "",
        savedWorldCount: document.querySelectorAll('[aria-label="Saved worlds"] option').length,
        activeWorldName: document.querySelector('[aria-label="Saved worlds"] select option:checked')?.textContent?.trim() || "",
        hasPlayerHud: Boolean(document.querySelector(".world-player-hud")),
        hasHealthBar: Boolean(document.querySelector('[aria-label="Player health bar"]')),
        canvasLength: document.querySelector(".world-viewport canvas")?.toDataURL("image/png").length || 0,
        horizontalOverflow: document.documentElement.scrollWidth > window.innerWidth + 1,
        frameworkOverlay: document.body.innerText.includes("Internal server error") || document.body.innerText.includes("Failed to compile"),
      }));
    } catch (error) {
      if (!String(error.message || "").includes("Execution context was destroyed") || attempt === 2) throw error;
      await page.waitForLoadState("load").catch(() => undefined);
      await page.waitForTimeout(250);
    }
  }
}

async function main() {
  const { chromium } = await loadPlaywright();
  const desktop = await openWorldPage(chromium, { viewport: { width: 1440, height: 900 }, deviceScaleFactor: 1 });
  try {
    const activeWorldSelect = desktop.page.getByLabel("Active World");
    const initialWorldOptions = await readWorldOptions(desktop.page);
    const seedLoadStates = await readSeedLoadStates(desktop.page, activeWorldSelect);
    await activeWorldSelect.selectOption(expectedSeedWorlds[0].id);
    await waitForWorldReady(desktop.page);
    const desktopState = await readWorldState(desktop.page);
    const enemyHealthBefore = desktopState.enemyHealth;
    const playerHealthBefore = readHealthValue(desktopState.playerHealth);
    await desktop.page.waitForTimeout(1500);
    const preEnterIdleState = await readWorldState(desktop.page);
    await desktop.page.getByRole("button", { name: "Enter World" }).click();
    await desktop.page
      .waitForFunction(() => document.querySelector(".world-viewport-shell")?.dataset.exploring === "true", null, {
        timeout: 3000,
      })
      .catch(() => undefined);
    const entered = await desktop.page.evaluate(() => ({
      exploring: document.querySelector(".world-viewport-shell")?.dataset.exploring || "",
      gameActive: document.querySelector(".world-viewport-shell")?.dataset.gameActive || "",
      pointerLocked: Boolean(document.pointerLockElement),
      fullscreen: Boolean(document.fullscreenElement),
    }));
    await desktop.page.mouse.click(720, 450, { button: "right" });
    await desktop.page.keyboard.press("KeyK");
    await desktop.page
      .waitForFunction((before) => Number(document.querySelector(".world-viewport-shell")?.dataset.enemyHealth || 0) < before, enemyHealthBefore, {
        timeout: 3500,
      })
      .catch(() => undefined);
    const afterPlayerAttack = await readWorldState(desktop.page);
    await desktop.page
      .waitForFunction((before) => Number(String(document.querySelector(".world-viewport-shell")?.dataset.playerHealth || "0").split("/")[0]) < before, playerHealthBefore, {
        timeout: 5500,
      })
      .catch(() => undefined);
    const afterEnemyAttack = await readWorldState(desktop.page);
    await desktop.page.keyboard.press("Escape");
    await desktop.page.evaluate(() => {
      document.exitPointerLock?.();
      if (document.fullscreenElement) document.exitFullscreen?.().catch(() => undefined);
    });
    await desktop.page
      .waitForFunction(() => document.querySelector(".world-viewport-shell")?.dataset.exploring === "false", null, {
        timeout: 3000,
      })
      .catch(() => undefined);
    const exited = await desktop.page.evaluate(() => ({
      exploring: document.querySelector(".world-viewport-shell")?.dataset.exploring || "",
      gameActive: document.querySelector(".world-viewport-shell")?.dataset.gameActive || "",
      pointerLocked: Boolean(document.pointerLockElement),
      fullscreen: Boolean(document.fullscreenElement),
    }));
    await desktop.page.getByRole("button", { name: "Reset Spawn" }).click();
    await desktop.page.waitForTimeout(400);
    const afterReset = await readWorldState(desktop.page);

    await desktop.page.getByRole("button", { name: "Grid" }).click({ force: true });
    const initialWorldCount = (await readWorldOptions(desktop.page)).length;
    const initialWorldId = await activeWorldSelect.inputValue();
    await desktop.page.getByRole("button", { name: "New" }).click();
    await desktop.page.waitForFunction(
      (expectedCount) => document.querySelectorAll('[aria-label="Saved worlds"] option').length === expectedCount,
      initialWorldCount + 1,
    );
    const createdWorldId = await activeWorldSelect.inputValue();
    await desktop.page.getByRole("button", { name: "Place" }).click({ force: true });
    await desktop.page.locator('[aria-label="Empty cell 2, 2"]').click();
    await desktop.page.waitForSelector('[aria-label="Painter Chibi at 2, 2"]', { timeout: 10000 });
    await activeWorldSelect.selectOption(initialWorldId);
    await desktop.page.waitForTimeout(200);
    const editMissingInOriginal = (await desktop.page.locator('[aria-label="Painter Chibi at 2, 2"]').count()) === 0;
    await activeWorldSelect.selectOption(createdWorldId);
    await desktop.page.waitForSelector('[aria-label="Painter Chibi at 2, 2"]', { timeout: 10000 });
    const editPersistedAfterSwitch = (await desktop.page.locator('[aria-label="Painter Chibi at 2, 2"]').count()) === 1;
    await desktop.page.getByRole("button", { name: "Duplicate" }).click();
    await desktop.page.waitForFunction(
      (expectedCount) => document.querySelectorAll('[aria-label="Saved worlds"] option').length === expectedCount,
      initialWorldCount + 2,
    );
    const duplicateWorldId = await activeWorldSelect.inputValue();
    await desktop.page.getByRole("button", { name: "Clear world" }).click();
    await desktop.page.waitForFunction(() => document.querySelectorAll(".world-cell.occupied").length === 0);
    const duplicateCleared = (await desktop.page.locator(".world-cell.occupied").count()) === 0;
    await activeWorldSelect.selectOption(createdWorldId);
    await desktop.page.waitForSelector('[aria-label="Painter Chibi at 2, 2"]', { timeout: 10000 });
    const duplicateIndependent = (await desktop.page.locator('[aria-label="Painter Chibi at 2, 2"]').count()) === 1;
    await activeWorldSelect.selectOption(duplicateWorldId);
    await desktop.page.getByRole("button", { name: "Delete" }).click();
    await desktop.page.waitForFunction(
      (expectedCount) => document.querySelectorAll('[aria-label="Saved worlds"] option').length === expectedCount,
      initialWorldCount + 1,
    );
    await deleteUntilOnlyWorld(desktop.page, activeWorldSelect, createdWorldId);
    await desktop.page.waitForSelector('[aria-label="Painter Chibi at 2, 2"]', { timeout: 10000 });
    const deleteDisabledAtOne = await desktop.page.getByRole("button", { name: "Delete" }).isDisabled();
    const sourceWorldId = await activeWorldSelect.inputValue();
    await desktop.page.getByRole("button", { name: "New" }).click();
    await desktop.page.waitForFunction(() => document.querySelectorAll('[aria-label="Saved worlds"] option').length === 2);
    const targetWorldId = await activeWorldSelect.inputValue();
    const targetWorldName = await desktop.page.locator('[aria-label="Saved worlds"] select option:checked').textContent();
    await activeWorldSelect.selectOption(sourceWorldId);
    await desktop.page.waitForSelector('[aria-label="Painter Chibi at 2, 2"]', { timeout: 10000 });
    await desktop.page.getByRole("button", { name: "Place" }).click({ force: true });
    await desktop.page.locator(".palette-tile").filter({ hasText: "Door" }).click();
    await desktop.page.locator('[aria-label="Empty cell 2, 1"]').click();
    await desktop.page.getByLabel("Door Destination").selectOption(targetWorldId);
    const linkedDoorSelectValue = await desktop.page.getByLabel("Door Destination").inputValue();
    await desktop.page.getByRole("button", { name: "3D", exact: true }).click({ force: true });
    await waitForWorldReady(desktop.page);
    await desktop.page.waitForFunction(
      (expectedWorldId) => document.querySelector(".world-viewport-shell")?.dataset.doorPrompt === expectedWorldId,
      targetWorldId,
      { timeout: 5000 },
    );
    const linkedDoorPromptState = await readWorldState(desktop.page);
    await desktop.page.locator(".world-door-prompt").click();
    await desktop.page.waitForFunction(
      (expectedWorldId) => document.querySelector(".world-viewport-shell")?.dataset.activeWorldId === expectedWorldId,
      targetWorldId,
      { timeout: 10000 },
    );
    await waitForWorldReady(desktop.page);
    const afterDoorTravel = await readWorldState(desktop.page);

    await desktop.page.getByRole("button", { name: "Grid" }).click({ force: true });
    await desktop.page.getByRole("button", { name: "Inspect" }).click({ force: true });
    await desktop.page.locator('[aria-label^="Goblin Grunt"]').click();
    const enemyRoleValue = await desktop.page.locator('[aria-label="Character combat settings"] select').inputValue();
    const hasStatInputs = (await desktop.page.locator(".combat-stat-grid input").count()) >= 5;
    await desktop.page.getByRole("button", { name: "Erase" }).click({ force: true });
    await desktop.page.locator('[aria-label^="Painter Chibi on Spawn"]').click();
    await desktop.page.evaluate(() => {
      [...document.querySelectorAll('[aria-label="World view mode"] button')]
        .find((button) => button.textContent?.trim() === "3D")
        ?.click();
      if (window.location.hash !== "#world-3d") window.location.hash = "#world-3d";
    });
    await waitForWorldReady(desktop.page);
    const freeCameraState = await readWorldState(desktop.page);

    await desktop.page.setViewportSize({ width: 390, height: 844 });
    await desktop.page.waitForTimeout(600);
    const mobileState = await readWorldState(desktop.page);

    const relevantConsoleIssues = desktop.consoleIssues.filter(
      (issue) =>
        !issue.includes("ReadPixels") &&
        !issue.includes("favicon.ico") &&
        !issue.includes("Too many active WebGL contexts"),
    );
    const requestFailures = desktop.requestFailures;
    const result = {
      url,
      initialWorldOptions,
      seedLoadStates,
      desktopState,
      preEnterIdleState,
      entered,
      afterPlayerAttack,
      afterEnemyAttack,
      exited,
      afterReset,
      multiWorldState: {
        editMissingInOriginal,
        editPersistedAfterSwitch,
        duplicateCleared,
        duplicateIndependent,
        deleteDisabledAtOne,
        sourceWorldId,
        targetWorldId,
        targetWorldName: targetWorldName?.trim() || "",
        linkedDoorSelectValue,
        linkedDoorPromptState,
        afterDoorTravel,
      },
      inspectorState: { enemyRoleValue, hasStatInputs },
      freeCameraState,
      mobileState,
      requestFailures,
      consoleIssues: relevantConsoleIssues,
      checks: {
        seededFiveWorldLibrary:
          initialWorldOptions.length === expectedSeedWorlds.length &&
          expectedSeedWorlds.every((seed) =>
            initialWorldOptions.some((option) => option.value === seed.id && option.name === seed.name),
          ),
        seedWorldsLoad3d: seedLoadStates.every(
          (state) =>
            state.statusData === "ready" &&
            state.activeWorldId === state.expected.id &&
            state.activeWorldName === state.expected.name &&
            state.canvasLength > 5000,
        ),
        pageIdentity: desktopState.title === "OnTheSpectrum Asset Viewer" && desktopState.hash === "#world-3d",
        desktop3dReady:
          desktopState.activeView === "3D" &&
          desktopState.statusData === "ready" &&
          desktopState.controlMode === "character" &&
          desktopState.gameActive === "false" &&
          desktopState.hasPlayerHud &&
          desktopState.hasHealthBar &&
          desktopState.enemiesAlive >= 2 &&
          desktopState.canvasLength > 5000,
        navigationEntryAndExit:
          entered.exploring === "true" &&
          entered.gameActive === "true" &&
          entered.pointerLocked === true &&
          exited.exploring === "false" &&
          exited.gameActive === "false" &&
          exited.pointerLocked === false &&
          exited.fullscreen === false,
        gameStartsAfterEnter:
          preEnterIdleState.gameActive === "false" &&
          readHealthValue(preEnterIdleState.playerHealth) === playerHealthBefore &&
          preEnterIdleState.enemyHealth === enemyHealthBefore,
        playerDamagesEnemy: afterPlayerAttack.enemyHealth < enemyHealthBefore,
        enemyDamagesPlayer:
          readHealthValue(afterPlayerAttack.playerHealth) < playerHealthBefore ||
          readHealthValue(afterEnemyAttack.playerHealth) < playerHealthBefore,
        resetRestoresEncounter:
          readHealthValue(afterReset.playerHealth) === playerHealthBefore &&
          afterReset.enemyHealth === enemyHealthBefore,
        unlinkedDoorDoesNotPrompt: desktopState.doorPrompt === "",
        multiWorldCreateSwitchAndPersist:
          editMissingInOriginal === true &&
          editPersistedAfterSwitch === true &&
          linkedDoorPromptState.savedWorldCount === 2,
        duplicateCreatesIndependentCopy:
          duplicateCleared === true &&
          duplicateIndependent === true,
        deletePreservesLastWorld: deleteDisabledAtOne === true,
        linkedDoorTravelsWorlds:
          linkedDoorSelectValue === targetWorldId &&
          linkedDoorPromptState.doorPrompt === targetWorldId &&
          afterDoorTravel.activeWorldId === targetWorldId &&
          afterDoorTravel.activeWorldName === targetWorldName?.trim(),
        inspectorCombatControls: enemyRoleValue === "enemy-melee" && hasStatInputs,
        spawnLayerFallbackToFreeCamera:
          freeCameraState.statusData === "ready" &&
          freeCameraState.controlMode === "free" &&
          freeCameraState.statusText.includes("Free camera") &&
          freeCameraState.canvasLength > 5000,
        mobile3dReady:
          mobileState.activeView === "3D" &&
          mobileState.statusData === "ready" &&
          mobileState.controlMode === "free" &&
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
