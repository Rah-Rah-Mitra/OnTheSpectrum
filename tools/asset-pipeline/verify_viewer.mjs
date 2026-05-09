import crypto from "node:crypto";
import fs from "node:fs/promises";
import net from "node:net";
import os from "node:os";
import path from "node:path";
import { spawn } from "node:child_process";

const url = process.argv[2] || "http://127.0.0.1:5173";
const chromePath =
  process.env.CHROME_PATH ||
  "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe";
const port = Number(process.env.CDP_PORT || 9233);

function delay(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function waitForJsonList() {
  for (let attempt = 0; attempt < 40; attempt += 1) {
    try {
      const response = await fetch(`http://127.0.0.1:${port}/json/list`);
      if (response.ok) return response.json();
    } catch {
      await delay(250);
    }
  }
  throw new Error("Chrome DevTools endpoint did not become available");
}

function encodeClientFrame(payloadText) {
  const payload = Buffer.from(payloadText);
  let header;
  if (payload.length < 126) {
    header = Buffer.alloc(2);
    header[1] = 0x80 | payload.length;
  } else if (payload.length < 65536) {
    header = Buffer.alloc(4);
    header[1] = 0x80 | 126;
    header.writeUInt16BE(payload.length, 2);
  } else {
    header = Buffer.alloc(10);
    header[1] = 0x80 | 127;
    header.writeBigUInt64BE(BigInt(payload.length), 2);
  }
  header[0] = 0x81;
  const mask = crypto.randomBytes(4);
  const masked = Buffer.alloc(payload.length);
  for (let index = 0; index < payload.length; index += 1) {
    masked[index] = payload[index] ^ mask[index % 4];
  }
  return Buffer.concat([header, mask, masked]);
}

async function connectCdp(wsUrl) {
  const target = new URL(wsUrl);
  const host = target.hostname;
  const key = crypto.randomBytes(16).toString("base64");
  let socket;
  let frameBuffer = Buffer.alloc(0);
  let fragments = [];
  let nextId = 1;
  const pending = new Map();
  const events = [];

  function handleMessage(message) {
    if (message.id && pending.has(message.id)) {
      const { resolve, reject } = pending.get(message.id);
      pending.delete(message.id);
      if (message.error) reject(new Error(JSON.stringify(message.error)));
      else resolve(message.result || {});
      return;
    }
    events.push(message);
  }

  function decodeFrames() {
    while (frameBuffer.length >= 2) {
      const first = frameBuffer[0];
      const second = frameBuffer[1];
      const fin = Boolean(first & 0x80);
      const opcode = first & 0x0f;
      const masked = Boolean(second & 0x80);
      let length = second & 0x7f;
      let offset = 2;
      if (length === 126) {
        if (frameBuffer.length < 4) return;
        length = frameBuffer.readUInt16BE(2);
        offset = 4;
      } else if (length === 127) {
        if (frameBuffer.length < 10) return;
        length = Number(frameBuffer.readBigUInt64BE(2));
        offset = 10;
      }
      const maskOffset = masked ? 4 : 0;
      const frameEnd = offset + maskOffset + length;
      if (frameBuffer.length < frameEnd) return;
      let payload = frameBuffer.subarray(offset + maskOffset, frameEnd);
      if (masked) {
        const mask = frameBuffer.subarray(offset, offset + 4);
        const unmasked = Buffer.alloc(payload.length);
        for (let index = 0; index < payload.length; index += 1) {
          unmasked[index] = payload[index] ^ mask[index % 4];
        }
        payload = unmasked;
      }
      frameBuffer = frameBuffer.subarray(frameEnd);
      if (opcode === 0x8) return;
      if (opcode === 0x9) {
        socket.write(Buffer.from([0x8a, 0]));
        continue;
      }
      if (opcode === 0x1 || opcode === 0x0) {
        fragments.push(payload);
        if (fin) {
          const text = Buffer.concat(fragments).toString("utf8");
          fragments = [];
          handleMessage(JSON.parse(text));
        }
      }
    }
  }

  await new Promise((resolve, reject) => {
    socket = net.createConnection({ host, port }, () => {
      socket.write(
        [
          `GET ${target.pathname}${target.search} HTTP/1.1`,
          `Host: ${host}:${port}`,
          "Upgrade: websocket",
          "Connection: Upgrade",
          `Sec-WebSocket-Key: ${key}`,
          "Sec-WebSocket-Version: 13",
          "",
          "",
        ].join("\r\n"),
      );
    });
    let handshake = Buffer.alloc(0);
    socket.on("data", (chunk) => {
      if (handshake !== null) {
        handshake = Buffer.concat([handshake, chunk]);
        const headerEnd = handshake.indexOf("\r\n\r\n");
        if (headerEnd === -1) return;
        const header = handshake.subarray(0, headerEnd).toString("utf8");
        if (!header.includes("101")) {
          reject(new Error(`WebSocket handshake failed: ${header}`));
          return;
        }
        frameBuffer = handshake.subarray(headerEnd + 4);
        handshake = null;
        resolve();
        decodeFrames();
        return;
      }
      frameBuffer = Buffer.concat([frameBuffer, chunk]);
      decodeFrames();
    });
    socket.on("error", reject);
  });

  function send(method, params = {}) {
    const id = nextId++;
    socket.write(encodeClientFrame(JSON.stringify({ id, method, params })));
    return new Promise((resolve, reject) => {
      pending.set(id, { resolve, reject });
      setTimeout(() => {
        if (pending.has(id)) {
          pending.delete(id);
          reject(new Error(`Timed out waiting for ${method}`));
        }
      }, 20000);
    });
  }

  return {
    send,
    events,
    close: () => socket.end(),
  };
}

async function main() {
  const qaDir = path.join(os.tmpdir(), "artomata-viewer-qa");
  await fs.mkdir(qaDir, { recursive: true });
  const userDataDir = path.join(os.tmpdir(), `artomata-chrome-${Date.now()}`);
  const chrome = spawn(chromePath, [
    "--headless=new",
    "--disable-gpu",
    "--disable-crash-reporter",
    `--remote-debugging-port=${port}`,
    `--user-data-dir=${userDataDir}`,
    "--window-size=1440,900",
    url,
  ]);

  const pages = await waitForJsonList();
  const page = pages.find((item) => item.type === "page") || pages[0];
  const cdp = await connectCdp(page.webSocketDebuggerUrl);
  await cdp.send("Page.enable");
  await cdp.send("Runtime.enable");
  await cdp.send("Log.enable");

  async function evaluate(expression) {
    const result = await cdp.send("Runtime.evaluate", { expression, awaitPromise: true, returnByValue: true });
    if (result.exceptionDetails) throw new Error(JSON.stringify(result.exceptionDetails));
    return result.result?.value;
  }

  async function waitForAsset(shortName, trianglesText) {
    return evaluate(`new Promise((resolve) => {
      const started = performance.now();
      const poll = () => {
        const canvas = document.querySelector('canvas');
        const text = document.body.innerText;
        const ready =
          text.includes('${shortName}') &&
          text.includes('${trianglesText}') &&
          document.querySelector('.stage')?.dataset.modelStatus === 'ready';
        if (canvas && ready) resolve({ ready: true, width: canvas.width, height: canvas.height });
        else if (performance.now() - started > 12000) resolve({ ready: false, text: document.body.innerText.slice(0, 500) });
        else setTimeout(poll, 150);
      };
      poll();
    })`);
  }

  async function canvasDataLength() {
    return evaluate(`document.querySelector('canvas')?.toDataURL('image/png').length || 0`);
  }

  await cdp.send("Page.navigate", { url });
  await delay(900);
  const desktopReady = await waitForAsset("Painter Chibi", "30,724");
  const chibiCanvasDataLength = await canvasDataLength();
  const initialShot = await cdp.send("Page.captureScreenshot", { format: "png", fromSurface: true });
  const desktopPath = path.join(qaDir, "artomata-assets-desktop.png");
  await fs.writeFile(desktopPath, Buffer.from(initialShot.data, "base64"));

  await evaluate(`document.querySelector('[aria-label="Play spin"]')?.click();`);
  await delay(120);
  const afterPlay = await evaluate(`Boolean(document.querySelector('[aria-label="Pause spin"]'))`);
  await evaluate(`document.querySelector('[aria-label="Pause spin"]')?.click();`);
  await evaluate(`document.querySelector('[aria-label="Reset view"]')?.click();`);
  await evaluate(`document.querySelector('[aria-label="Focus Painter Chibi"]')?.click();`);
  await evaluate(`document.querySelector('[aria-label="Zoom in"]')?.click();`);
  await evaluate(`document.querySelector('[aria-label="Zoom out"]')?.click();`);
  await evaluate(`document.querySelector('[aria-label="Snapshot"]')?.click();`);
  await evaluate(`[...document.querySelectorAll('button')].find((button) => button.textContent.trim() === 'Toon')?.click();`);
  const idleInitiallyActive = await evaluate(`Boolean(document.querySelector('[aria-label="Select Idle animation"][aria-pressed="true"]'))`);
  await evaluate(`document.querySelector('[aria-label="Select Walk animation"]')?.click();`);
  await delay(300);

  const chibiState = await evaluate(`({
    spinPaused: Boolean(document.querySelector('[aria-label="Play spin"]')),
    activeMode: document.querySelector('.view-tabs button.active')?.textContent?.trim(),
    idleInitiallyActive: ${idleInitiallyActive},
    walkActive: Boolean(document.querySelector('[aria-label="Select Walk animation"][aria-pressed="true"]')),
    statusText: document.querySelector('.status-strip')?.innerText || '',
    exports: Object.fromEntries([...document.querySelectorAll('.export-menu-list a')].map((link) => [
      link.getAttribute('aria-label'),
      { href: link.getAttribute('href'), download: link.getAttribute('download') },
    ])),
    inspectorText: document.querySelector('.inspector')?.innerText || '',
  })`);
  await evaluate(`document.querySelector('[aria-label="Select Blaster Runner"]')?.click();`);
  const blasterReady = await waitForAsset("Blaster Runner", "27,556");
  await delay(300);
  const blasterCanvasDataLength = await canvasDataLength();
  const blasterIdleInitiallyActive = await evaluate(`Boolean(document.querySelector('[aria-label="Select Idle animation"][aria-pressed="true"]'))`);
  await evaluate(`document.querySelector('[aria-label="Select Run animation"]')?.click();`);
  await delay(300);
  const blasterState = await evaluate(`({
    selected: Boolean(document.querySelector('[aria-label="Select Blaster Runner"][aria-pressed="true"]')),
    idleInitiallyActive: ${blasterIdleInitiallyActive},
    runActive: Boolean(document.querySelector('[aria-label="Select Run animation"][aria-pressed="true"]')),
    statusText: document.querySelector('.status-strip')?.innerText || '',
    exports: Object.fromEntries([...document.querySelectorAll('.export-menu-list a')].map((link) => [
      link.getAttribute('aria-label'),
      { href: link.getAttribute('href'), download: link.getAttribute('download') },
    ])),
    inspectorText: document.querySelector('.inspector')?.innerText || '',
  })`);
  await evaluate(`document.querySelector('[aria-label="Select Flower"]')?.click();`);
  const flowerReady = await waitForAsset("Flower", "60,952");
  await delay(300);
  const flowerCanvasDataLength = await canvasDataLength();
  const flowerState = await evaluate(`({
    selected: Boolean(document.querySelector('[aria-label="Select Flower"][aria-pressed="true"]')),
    swayActive: Boolean(document.querySelector('[aria-label="Select Sway animation"][aria-pressed="true"]')),
    exports: Object.fromEntries([...document.querySelectorAll('.export-menu-list a')].map((link) => [
      link.getAttribute('aria-label'),
      { href: link.getAttribute('href'), download: link.getAttribute('download') },
    ])),
    inspectorText: document.querySelector('.inspector')?.innerText || '',
  })`);
  await evaluate(`document.querySelector('[aria-label="Select Chair"]')?.click();`);
  const chairReady = await waitForAsset("Chair", "12,956");
  await delay(300);
  const chairCanvasDataLength = await canvasDataLength();
  const chairState = await evaluate(`({
    selected: Boolean(document.querySelector('[aria-label="Select Chair"][aria-pressed="true"]')),
    hasAnimationControl: Boolean(document.querySelector('.animation-control')),
    statusText: document.querySelector('.status-strip')?.innerText || '',
    exports: Object.fromEntries([...document.querySelectorAll('.export-menu-list a')].map((link) => [
      link.getAttribute('aria-label'),
      { href: link.getAttribute('href'), download: link.getAttribute('download') },
    ])),
    inspectorText: document.querySelector('.inspector')?.innerText || '',
  })`);

  await cdp.send("Emulation.setDeviceMetricsOverride", { width: 390, height: 844, deviceScaleFactor: 2, mobile: true });
  await cdp.send("Page.navigate", { url });
  await delay(900);
  const mobileReady = await waitForAsset("Painter Chibi", "30,724");
  await evaluate(`document.querySelector('[aria-label="Select Blaster Runner"]')?.click();`);
  const mobileBlasterReady = await waitForAsset("Blaster Runner", "27,556");
  const mobileBlasterCanvasDataLength = await canvasDataLength();
  await evaluate(`document.querySelector('[aria-label="Select Flower"]')?.click();`);
  const mobileFlowerReady = await waitForAsset("Flower", "60,952");
  const mobileFlowerSelected = await evaluate(`Boolean(document.querySelector('[aria-label="Select Flower"][aria-pressed="true"]'))`);
  await evaluate(`document.querySelector('[aria-label="Select Chair"]')?.click();`);
  const mobileChairReady = await waitForAsset("Chair", "12,956");
  const mobileChairCanvasDataLength = await canvasDataLength();
  const mobileState = await evaluate(`({
    horizontalOverflow: document.documentElement.scrollWidth > window.innerWidth + 1,
    bodyText: document.body.innerText.slice(0, 500),
    viewport: { width: window.innerWidth, height: window.innerHeight },
    selectedFlower: ${mobileFlowerSelected},
    selectedChair: Boolean(document.querySelector('[aria-label="Select Chair"][aria-pressed="true"]')),
  })`);
  const mobileShot = await cdp.send("Page.captureScreenshot", { format: "png", fromSurface: true });
  const mobilePath = path.join(qaDir, "artomata-assets-mobile.png");
  await fs.writeFile(mobilePath, Buffer.from(mobileShot.data, "base64"));

  const consoleIssues = cdp.events
    .filter((event) => event.method === "Runtime.exceptionThrown" || event.method === "Log.entryAdded")
    .map((event) => {
      if (event.method === "Runtime.exceptionThrown") return `exception: ${event.params?.exceptionDetails?.text || "runtime exception"}`;
      const entry = event.params?.entry;
      if (["error", "warning"].includes(entry?.level)) return `${entry.level}: ${entry.text}`;
      return "";
    })
    .filter(Boolean);
  const relevantConsoleIssues = consoleIssues.filter((issue) => !issue.includes("favicon.ico"));

  const result = {
    url,
    title: await evaluate("document.title"),
    desktopReady,
    blasterReady,
    flowerReady,
    chairReady,
    mobileReady,
    mobileBlasterReady,
    mobileFlowerReady,
    mobileChairReady,
    chibiState,
    blasterState,
    flowerState,
    chairState,
    mobileState,
    consoleIssues: relevantConsoleIssues,
    screenshots: [desktopPath, mobilePath],
    checks: {
      pageIdentity: (await evaluate("document.title")) === "Artomata Asset Viewer",
      notBlank:
        Boolean(desktopReady.ready && blasterReady.ready && flowerReady.ready && chairReady.ready && mobileReady.ready && mobileBlasterReady.ready && mobileFlowerReady.ready && mobileChairReady.ready) &&
        chibiCanvasDataLength > 5000 &&
        blasterCanvasDataLength > 5000 &&
        chairCanvasDataLength > 5000 &&
        mobileBlasterCanvasDataLength > 5000 &&
        mobileChairCanvasDataLength > 5000 &&
        flowerCanvasDataLength > 5000,
      noFrameworkOverlay: !mobileState.bodyText.includes("Internal server error"),
      spinToggle: Boolean(afterPlay && chibiState.spinPaused),
      modeSwitch: chibiState.activeMode === "Toon",
      chibiAnimationControl:
        chibiState.idleInitiallyActive &&
        chibiState.walkActive &&
        chibiState.statusText.includes("Walk clip"),
      chibiExportLinks:
        chibiState.exports["Download Web GLB"]?.href === "/models/artomata-painter-chibi.glb" &&
        chibiState.exports["Download Web GLB"]?.download === "artomata-painter-chibi.glb" &&
        chibiState.exports["Download Mixamo FBX"]?.href ===
          "/exports/artomata-painter-chibi/artomata-painter-chibi-mixamo.fbx" &&
        chibiState.exports["Download Mixamo FBX"]?.download === "artomata-painter-chibi-mixamo.fbx" &&
        chibiState.exports["Download OBJ ZIP"]?.href ===
          "/exports/artomata-painter-chibi/artomata-painter-chibi-mixamo-obj.zip" &&
        chibiState.exports["Download OBJ ZIP"]?.download === "artomata-painter-chibi-mixamo-obj.zip" &&
        chibiState.exports["Download Blender source"]?.href === "/models/artomata-painter-chibi.blend",
      blasterSelection:
        blasterState.selected &&
        blasterState.idleInitiallyActive &&
        blasterState.runActive &&
        blasterState.statusText.includes("Run clip") &&
        blasterState.inspectorText.includes("Humanoid toon action showcase"),
      blasterExportLinks:
        blasterState.exports["Download Web GLB"]?.href === "/models/toon-blaster-runner.glb" &&
        blasterState.exports["Download Web GLB"]?.download === "toon-blaster-runner.glb" &&
        blasterState.exports["Download Mixamo FBX"]?.href ===
          "/exports/toon-blaster-runner/toon-blaster-runner-mixamo.fbx" &&
        blasterState.exports["Download Mixamo FBX"]?.download === "toon-blaster-runner-mixamo.fbx" &&
        blasterState.exports["Download OBJ ZIP"]?.href ===
          "/exports/toon-blaster-runner/toon-blaster-runner-mixamo-obj.zip" &&
        blasterState.exports["Download OBJ ZIP"]?.download === "toon-blaster-runner-mixamo-obj.zip" &&
        blasterState.exports["Download Blender source"]?.href === "/models/toon-blaster-runner.blend",
      flowerSelection:
        flowerState.selected &&
        flowerState.swayActive &&
        flowerState.exports["Download Web GLB"]?.href === "/models/flower.glb" &&
        flowerState.exports["Download Web GLB"]?.download === "flower.glb" &&
        flowerState.exports["Download Blender source"]?.href === "/models/flower.blend" &&
        !flowerState.exports["Download Mixamo FBX"] &&
        flowerState.inspectorText.includes("Procedural GLB showcase"),
      chairSelection:
        chairState.selected &&
        !chairState.hasAnimationControl &&
        chairState.statusText.includes("Still clip") &&
        chairState.inspectorText.includes("Static furniture showcase") &&
        chairState.inspectorText.includes("Warm oak frame"),
      chairExportLinks:
        chairState.exports["Download Web GLB"]?.href === "/models/chair.glb" &&
        chairState.exports["Download Web GLB"]?.download === "chair.glb" &&
        chairState.exports["Download Blender source"]?.href === "/models/chair.blend" &&
        !chairState.exports["Download Mixamo FBX"] &&
        !chairState.exports["Download OBJ ZIP"],
      mobileSelection: Boolean(mobileState.selectedFlower && mobileState.selectedChair),
      mobileNoHorizontalOverflow: mobileState.horizontalOverflow === false,
      consoleHealth: relevantConsoleIssues.length === 0,
    },
  };

  cdp.close();
  chrome.kill();
  console.log(JSON.stringify(result, null, 2));
  process.exit(Object.values(result.checks).every(Boolean) ? 0 : 1);
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
