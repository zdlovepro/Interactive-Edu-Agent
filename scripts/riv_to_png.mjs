#!/usr/bin/env node

import { spawn } from "node:child_process";
import {
  appendFileSync,
  existsSync,
  mkdirSync,
  mkdtempSync,
  readFileSync,
  readdirSync,
  rmSync,
  statSync,
  writeFileSync,
} from "node:fs";
import http from "node:http";
import { tmpdir } from "node:os";
import { dirname, extname, join, resolve } from "node:path";
import { pathToFileURL } from "node:url";
import { extname as pathExtname, join as pathJoin, normalize } from "node:path";

const DEBUG = process.env.RIV_DEBUG === "1";
const DEBUG_FILE = process.env.RIV_DEBUG_FILE || "";
const RIVE_VERSION = "2.38.0";
const RIVE_PACKAGE = "@rive-app/canvas-lite";

function debugLog(message) {
  if (DEBUG) {
    console.error(`[riv_to_png][debug] ${message}`);
    if (DEBUG_FILE) {
      try {
        appendFileSync(DEBUG_FILE, `[riv_to_png][debug] ${message}\n`, "utf8");
      } catch (error) {
        // ignore debug file write failures
      }
    }
  }
}

function parseArgs(argv) {
  const args = {
    input: null,
    output: null,
    width: 1024,
    height: 1024,
    waitMs: 15000,
    captureMs: 400,
    artboard: null,
    stateMachine: null,
    animation: null,
    background: "transparent",
    browser: null,
  };

  for (let i = 0; i < argv.length; i += 1) {
    const value = argv[i];
    if (!value.startsWith("-")) {
      if (args.input) {
        throw new Error(`Unexpected extra argument: ${value}`);
      }
      args.input = value;
      continue;
    }

    const next = argv[i + 1];
    switch (value) {
      case "--output":
      case "-o":
        args.output = next;
        i += 1;
        break;
      case "--width":
        args.width = Number(next);
        i += 1;
        break;
      case "--height":
        args.height = Number(next);
        i += 1;
        break;
      case "--wait-ms":
        args.waitMs = Number(next);
        i += 1;
        break;
      case "--capture-ms":
      case "--play-ms":
        args.captureMs = Number(next);
        i += 1;
        break;
      case "--artboard":
        args.artboard = next;
        i += 1;
        break;
      case "--state-machine":
        args.stateMachine = next;
        i += 1;
        break;
      case "--animation":
        args.animation = next;
        i += 1;
        break;
      case "--background":
        args.background = next;
        i += 1;
        break;
      case "--browser":
        args.browser = next;
        i += 1;
        break;
      case "--help":
      case "-h":
        printHelp();
        process.exit(0);
      default:
        throw new Error(`Unknown option: ${value}`);
    }
  }

  if (!Number.isFinite(args.width) || args.width <= 0) {
    throw new Error(`Invalid --width value: ${args.width}`);
  }
  if (!Number.isFinite(args.height) || args.height <= 0) {
    throw new Error(`Invalid --height value: ${args.height}`);
  }
  if (!Number.isFinite(args.waitMs) || args.waitMs <= 0) {
    throw new Error(`Invalid --wait-ms value: ${args.waitMs}`);
  }
  if (!Number.isFinite(args.captureMs) || args.captureMs < 0) {
    throw new Error(`Invalid --capture-ms value: ${args.captureMs}`);
  }

  return args;
}

function printHelp() {
  console.log(`Usage: node scripts/riv_to_png.mjs [input.riv] [options]

Options:
  -o, --output <path>          Output PNG path. Defaults to <input-stem>.png
  --width <px>                 Output width. Default: 1024
  --height <px>                Output height. Default: 1024
  --wait-ms <ms>               Max wait for page render. Default: 15000
  --capture-ms <ms>            Scrub into the selected animation. Default: 400
  --artboard <name>            Optional artboard name
  --state-machine <name>       Optional state machine name
  --animation <name>           Optional animation name
  --background <color>         transparent or e.g. #ffffff
  --browser <path>             Optional Edge/Chrome executable path
`);
}

function resolveInputPath(inputArg) {
  if (inputArg) {
    const full = resolve(inputArg);
    if (extname(full).toLowerCase() !== ".riv") {
      throw new Error(`Input must be a .riv file: ${full}`);
    }
    return full;
  }

  const candidates = readdirSync(process.cwd())
    .filter((name) => name.toLowerCase().endsWith(".riv"))
    .filter((name) => statSync(resolve(name)).isFile())
    .sort();

  if (candidates.length === 1) {
    return resolve(candidates[0]);
  }
  if (candidates.length === 0) {
    throw new Error("No .riv file found in the current directory.");
  }
  throw new Error(`Multiple .riv files found. Please specify one: ${candidates.join(", ")}`);
}

function resolveOutputPath(inputPath, outputArg) {
  if (outputArg) {
    return resolve(outputArg);
  }
  return inputPath.replace(/\.riv$/i, ".png");
}

function fileExists(path) {
  return existsSync(path);
}

function resolveBrowserPath(explicitBrowser) {
  const candidates = [
    explicitBrowser,
    process.env.RIV_BROWSER,
    "C:\\Program Files\\Microsoft\\Edge\\Application\\msedge.exe",
    "C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe",
    "C:\\Users\\user\\AppData\\Local\\Google\\Chrome\\Application\\chrome.exe",
    "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",
    "C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe",
  ].filter(Boolean);

  for (const candidate of candidates) {
    const full = resolve(String(candidate));
    if (fileExists(full)) {
      return full;
    }
  }

  throw new Error("No supported browser found. Pass --browser <path> or set RIV_BROWSER.");
}

function escapeForHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

function jsStringLiteral(value) {
  if (value === null || value === undefined) {
    return "null";
  }
  return JSON.stringify(String(value));
}

function buildHtml(rivBase64, args) {
  return `<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>Rive Snapshot</title>
    <style>
      html, body {
        margin: 0;
        width: 100%;
        height: 100%;
        overflow: hidden;
        background: ${escapeForHtml(args.background)};
      }
      body {
        display: flex;
        align-items: center;
        justify-content: center;
      }
      #rive-canvas {
        width: 100vw;
        height: 100vh;
        display: block;
        background: transparent;
      }
    </style>
    <script src="./rive.js"></script>
  </head>
  <body data-ready="booting" data-error-message="">
    <canvas id="rive-canvas" width="${args.width}" height="${args.height}"></canvas>
    <script>
      const requestedArtboard = ${jsStringLiteral(args.artboard)};
      const requestedStateMachine = ${jsStringLiteral(args.stateMachine)};
      const requestedAnimation = ${jsStringLiteral(args.animation)};
      const captureMs = ${Number(args.captureMs)};

      const canvas = document.getElementById("rive-canvas");
      const binaryString = atob("${rivBase64}");
      const rivBytes = new Uint8Array(binaryString.length);
      for (let i = 0; i < binaryString.length; i += 1) {
        rivBytes[i] = binaryString.charCodeAt(i);
      }

      function markError(message) {
        const text = typeof message === "string" ? message : String(message ?? "Unknown error");
        document.body.dataset.ready = "error";
        document.body.dataset.errorMessage = text;
        console.error(text);
      }

      window.addEventListener("error", (event) => {
        markError(event?.message || event?.error?.message || "Window error");
      });

      window.addEventListener("unhandledrejection", (event) => {
        const reason = event?.reason;
        markError(reason?.message || String(reason ?? "Unhandled rejection"));
      });

      function choosePlayback(contents) {
        const artboards = Array.isArray(contents?.artboards) ? contents.artboards : [];
        const artboard = artboards.find((item) => item.name === requestedArtboard) || artboards[0] || null;
        const stateMachine = requestedStateMachine || null;
        const animation = requestedAnimation || (!stateMachine ? artboard?.animations?.[0] || null : null);
        return {
          artboard: artboard?.name || null,
          stateMachine,
          animation,
        };
      }

      function syncCanvasSize(instance) {
        canvas.width = window.innerWidth;
        canvas.height = window.innerHeight;
        if (instance) {
          instance.resizeDrawingSurfaceToCanvas();
        }
      }

      let riveInstance = null;
      try {
        rive.RuntimeLoader.setWasmUrl("./rive.wasm");
        rive.RuntimeLoader.setWasmFallbackUrl("./rive_fallback.wasm");
        riveInstance = new rive.Rive({
          buffer: rivBytes.buffer,
          canvas,
          autoplay: false,
          layout: new rive.Layout({
            fit: rive.Fit.Contain,
            alignment: rive.Alignment.Center,
          }),
          onLoad: () => {
            const selection = choosePlayback(riveInstance.contents);
            const resetParams = {
              artboard: selection.artboard || undefined,
              autoplay: false,
            };
            if (selection.stateMachine) {
              resetParams.stateMachines = selection.stateMachine;
            }
            if (selection.animation) {
              resetParams.animations = selection.animation;
            }
            riveInstance.reset(resetParams);
            syncCanvasSize(riveInstance);
            if (selection.animation && captureMs > 0) {
              riveInstance.scrub(selection.animation, captureMs / 1000);
            }
            riveInstance.drawFrame();
            window.__RIVE_SELECTION__ = selection;
            document.body.dataset.ready = "true";
          },
          onLoadError: (event) => {
            markError(event?.message || event?.data || "Failed to load Rive file.");
          },
        });
      } catch (error) {
        markError(error?.message || String(error));
      }

      window.addEventListener("resize", () => syncCanvasSize(riveInstance));
      syncCanvasSize(riveInstance);
    </script>
  </body>
</html>`;
}

function getFreePort() {
  return new Promise((resolvePort, reject) => {
    const server = http.createServer();
    server.listen(0, "127.0.0.1", () => {
      const address = server.address();
      server.close(() => {
        if (!address || typeof address === "string") {
          reject(new Error("Failed to allocate a debug port."));
          return;
        }
        resolvePort(address.port);
      });
    });
    server.on("error", reject);
  });
}

function contentTypeFor(filePath) {
  switch (pathExtname(filePath).toLowerCase()) {
    case ".html":
      return "text/html; charset=utf-8";
    case ".js":
      return "application/javascript; charset=utf-8";
    case ".wasm":
      return "application/wasm";
    default:
      return "application/octet-stream";
  }
}

async function startStaticServer(rootDir) {
  return await new Promise((resolveServer, rejectServer) => {
    const server = http.createServer((request, response) => {
      try {
        const url = new URL(request.url || "/", "http://127.0.0.1");
        const requestPath = decodeURIComponent(url.pathname === "/" ? "/index.html" : url.pathname);
        const filePath = normalize(pathJoin(rootDir, requestPath));
        if (!filePath.startsWith(normalize(rootDir))) {
          response.writeHead(403);
          response.end("Forbidden");
          return;
        }
        const body = readFileSync(filePath);
        response.writeHead(200, { "Content-Type": contentTypeFor(filePath) });
        response.end(body);
      } catch (error) {
        response.writeHead(404);
        response.end("Not found");
      }
    });

    server.listen(0, "127.0.0.1", () => {
      const address = server.address();
      if (!address || typeof address === "string") {
        rejectServer(new Error("Failed to start the temporary HTTP server."));
        return;
      }
      resolveServer({ server, port: address.port });
    });

    server.on("error", rejectServer);
  });
}

function sleep(ms) {
  return new Promise((resolveSleep) => setTimeout(resolveSleep, ms));
}

async function fetchJson(url, timeoutMs = 3000) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const response = await fetch(url, { signal: controller.signal });
    if (!response.ok) {
      throw new Error(`HTTP ${response.status} when requesting ${url}`);
    }
    return await response.json();
  } finally {
    clearTimeout(timer);
  }
}

async function downloadBinary(url, timeoutMs = 15000) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const response = await fetch(url, { signal: controller.signal });
    if (!response.ok) {
      throw new Error(`HTTP ${response.status} when requesting ${url}`);
    }
    return Buffer.from(await response.arrayBuffer());
  } finally {
    clearTimeout(timer);
  }
}

async function killProcessTree(pid) {
  if (!pid) {
    return;
  }

  if (process.platform === "win32") {
    await new Promise((resolveKill) => {
      const killer = spawn("taskkill", ["/PID", String(pid), "/T", "/F"], {
        stdio: "ignore",
        windowsHide: true,
      });
      killer.on("exit", () => resolveKill());
      killer.on("error", () => resolveKill());
    });
    return;
  }

  try {
    process.kill(pid, "SIGTERM");
  } catch (error) {
    // ignore
  }
}

async function waitForPageWebSocketUrl(debugPort, timeoutMs) {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    try {
      debugLog(`Polling DevTools target list on port ${debugPort}`);
      const targets = await fetchJson(`http://127.0.0.1:${debugPort}/json/list`);
      const pageTarget = targets.find((target) => target.type === "page" && target.webSocketDebuggerUrl);
      if (pageTarget?.webSocketDebuggerUrl) {
        debugLog(`Found page target: ${pageTarget.webSocketDebuggerUrl}`);
        return pageTarget.webSocketDebuggerUrl;
      }
    } catch (error) {
      // Browser not ready yet.
    }
    await sleep(200);
  }
  throw new Error("Timed out while waiting for the browser DevTools endpoint.");
}

class CdpClient {
  constructor(wsUrl) {
    this.nextId = 1;
    this.pending = new Map();
    this.eventWaiters = new Map();
    this.ws = new WebSocket(wsUrl);
  }

  async open() {
    await new Promise((resolveOpen, rejectOpen) => {
      const onOpen = () => {
        this.ws.removeEventListener("error", onError);
        resolveOpen();
      };
      const onError = (event) => {
        this.ws.removeEventListener("open", onOpen);
        rejectOpen(event.error || new Error("Failed to open CDP websocket."));
      };
      this.ws.addEventListener("open", onOpen, { once: true });
      this.ws.addEventListener("error", onError, { once: true });
    });

    this.ws.addEventListener("message", (event) => {
      const payload = JSON.parse(String(event.data));
      if (payload.id) {
        const pending = this.pending.get(payload.id);
        if (!pending) {
          return;
        }
        this.pending.delete(payload.id);
        if (payload.error) {
          pending.reject(new Error(payload.error.message || "CDP command failed."));
        } else {
          pending.resolve(payload.result || {});
        }
        return;
      }

      const waiters = this.eventWaiters.get(payload.method);
      if (waiters && waiters.length > 0) {
        const next = waiters.shift();
        next.resolve(payload.params || {});
      }
    });
  }

  send(method, params = {}, timeoutMs = 5000) {
    const id = this.nextId++;
    const message = JSON.stringify({ id, method, params });
    return new Promise((resolveSend, rejectSend) => {
      const timer = setTimeout(() => {
        this.pending.delete(id);
        rejectSend(new Error(`Timed out waiting for CDP response: ${method}`));
      }, timeoutMs);
      this.pending.set(id, { resolve: resolveSend, reject: rejectSend });
      const pending = this.pending.get(id);
      this.pending.set(id, {
        resolve: (result) => {
          clearTimeout(timer);
          resolveSend(result);
        },
        reject: (error) => {
          clearTimeout(timer);
          rejectSend(error);
        },
      });
      this.ws.send(message);
    });
  }

  waitForEvent(method, timeoutMs) {
    return new Promise((resolveEvent, rejectEvent) => {
      const timer = setTimeout(() => {
        rejectEvent(new Error(`Timed out waiting for CDP event: ${method}`));
      }, timeoutMs);

      const wrappedResolve = (payload) => {
        clearTimeout(timer);
        resolveEvent(payload);
      };

      const current = this.eventWaiters.get(method) || [];
      current.push({ resolve: wrappedResolve });
      this.eventWaiters.set(method, current);
    });
  }

  close() {
    try {
      this.ws.close();
    } catch (error) {
      // ignore
    }
  }
}

async function waitUntilRendered(cdp, timeoutMs) {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    try {
      const result = await cdp.send(
        "Runtime.evaluate",
        {
          expression: "document.body && document.body.dataset ? document.body.dataset.ready || '' : ''",
          returnByValue: true,
        },
        1500,
      );
      const value = result?.result?.value || "";
      debugLog(`document.body.dataset.ready = ${value || "<empty>"}`);
      if (value === "true") {
        return;
      }
      if (value === "error") {
        const errorResult = await cdp.send(
          "Runtime.evaluate",
          {
            expression: "document.body && document.body.dataset ? document.body.dataset.errorMessage || '' : ''",
            returnByValue: true,
          },
          1500,
        );
        const detail = errorResult?.result?.value || "Unknown browser-side error";
        throw new Error(`Rive page reported a rendering error: ${detail}`);
      }
    } catch (error) {
      debugLog(`Render probe skipped: ${error.message}`);
    }
    await sleep(200);
  }
  throw new Error("Timed out waiting for the Rive page to finish rendering.");
}

async function main() {
  const args = parseArgs(process.argv.slice(2));
  const inputPath = resolveInputPath(args.input);
  const outputPath = resolveOutputPath(inputPath, args.output);
  const browserPath = resolveBrowserPath(args.browser);
  debugLog(`Input: ${inputPath}`);
  debugLog(`Output: ${outputPath}`);
  debugLog(`Browser: ${browserPath}`);

  const rivBase64 = readFileSync(inputPath).toString("base64");
  const tempDir = mkdtempSync(join(tmpdir(), "rive-to-png-"));
  const profileDir = join(tempDir, "browser-profile");
  mkdirSync(profileDir, { recursive: true });
  debugLog(`Temp dir: ${tempDir}`);

  const htmlPath = join(tempDir, "index.html");
  writeFileSync(htmlPath, buildHtml(rivBase64, args), "utf8");
  debugLog(`HTML file: ${htmlPath}`);
  debugLog("Downloading local Rive runtime assets");
  const riveJs = await downloadBinary(`https://unpkg.com/${RIVE_PACKAGE}@${RIVE_VERSION}/rive.js`);
  const riveWasm = await downloadBinary(`https://unpkg.com/${RIVE_PACKAGE}@${RIVE_VERSION}/rive.wasm`);
  const riveFallbackWasm = await downloadBinary(
    `https://unpkg.com/${RIVE_PACKAGE}@${RIVE_VERSION}/rive_fallback.wasm`,
  );
  writeFileSync(join(tempDir, "rive.js"), riveJs);
  writeFileSync(join(tempDir, "rive.wasm"), riveWasm);
  writeFileSync(join(tempDir, "rive_fallback.wasm"), riveFallbackWasm);
  debugLog("Saved local Rive runtime assets");
  const { server: assetServer, port: assetPort } = await startStaticServer(tempDir);
  const pageUrl = `http://127.0.0.1:${assetPort}/index.html`;
  debugLog(`Asset server: ${pageUrl}`);

  const debugPort = await getFreePort();
  debugLog(`Debug port: ${debugPort}`);
  const browserArgs = [
    "--headless=new",
    "--no-first-run",
    "--no-default-browser-check",
    "--hide-scrollbars",
    "--enable-webgl",
    "--use-angle=swiftshader",
    `--user-data-dir=${profileDir}`,
    `--remote-debugging-port=${debugPort}`,
    "about:blank",
  ];

  const browser = spawn(browserPath, browserArgs, {
    stdio: ["ignore", "ignore", "pipe"],
    windowsHide: true,
  });
  debugLog(`Spawned browser pid=${browser.pid}`);

  let stderrBuffer = "";
  browser.stderr.on("data", (chunk) => {
    stderrBuffer += chunk.toString();
  });

  try {
    const wsUrl = await waitForPageWebSocketUrl(debugPort, 10000);
    const cdp = new CdpClient(wsUrl);
    debugLog("Opening CDP websocket");
    await cdp.open();
    debugLog("CDP websocket opened");
    await cdp.send("Page.enable");
    await cdp.send("Runtime.enable");
    debugLog("Enabled Page and Runtime domains");
    await cdp.send("Emulation.setDeviceMetricsOverride", {
      width: args.width,
      height: args.height,
      deviceScaleFactor: 1,
      mobile: false,
    });
    debugLog("Applied device metrics override");

    if (String(args.background).toLowerCase() === "transparent") {
      await cdp.send("Emulation.setDefaultBackgroundColorOverride", {
        color: { r: 0, g: 0, b: 0, a: 0 },
      });
      debugLog("Applied transparent background override");
    }

    const loadEvent = cdp.waitForEvent("Page.loadEventFired", args.waitMs);
    debugLog("Navigating to generated HTML");
    await cdp.send("Page.navigate", { url: pageUrl });
    await loadEvent;
    debugLog("Page load event fired");
    debugLog(`Waiting ${args.waitMs}ms for Rive to settle before capture`);
    await sleep(args.waitMs);

    const screenshot = await cdp.send(
      "Page.captureScreenshot",
      {
        format: "png",
        fromSurface: true,
        clip: {
          x: 0,
          y: 0,
          width: args.width,
          height: args.height,
          scale: 1,
        },
        captureBeyondViewport: false,
      },
      5000,
    );
    debugLog("Captured screenshot");

    mkdirSync(dirname(outputPath), { recursive: true });
    writeFileSync(outputPath, Buffer.from(screenshot.data, "base64"));
    debugLog("Wrote PNG to disk");
    cdp.close();
  } finally {
    debugLog("Cleaning up browser process and temp files");
    await killProcessTree(browser.pid);
    try {
      await new Promise((resolveClose) => assetServer.close(() => resolveClose()));
    } catch (error) {
      debugLog(`Asset server cleanup skipped: ${error.message}`);
    }
    try {
      rmSync(tempDir, { recursive: true, force: true });
    } catch (error) {
      debugLog(`Temp cleanup skipped: ${error.message}`);
    }
  }

  console.log(`Rendered ${inputPath} -> ${outputPath}`);
  if (stderrBuffer.trim()) {
    console.warn(stderrBuffer.trim());
  }
}

main().catch((error) => {
  console.error(`[riv_to_png] ${error.message}`);
  process.exit(1);
});
