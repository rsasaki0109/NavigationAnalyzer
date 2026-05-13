import { access, mkdir } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import { chromium } from "playwright";

const url = process.env.NAV_ANALYZER_WEB_URL ?? "http://127.0.0.1:5173/";
const chrome = process.env.NAV_ANALYZER_CHROME ?? "/usr/bin/google-chrome";
const outputDir = new URL("../../outputs/frontend-check/", import.meta.url);
const benchmarkFile = process.env.NAV_ANALYZER_BENCHMARK_FILE
  ?? fileURLToPath(new URL("../../outputs/demo_sample/benchmark.json", import.meta.url));

const viewports = [
  { name: "desktop", width: 1440, height: 960 },
  { name: "mobile", width: 390, height: 844 },
];

await mkdir(outputDir, { recursive: true });

const browser = await chromium.launch({
  executablePath: chrome,
  headless: true,
  args: ["--no-sandbox", "--disable-dev-shm-usage"],
});

try {
  for (const viewport of viewports) {
    const page = await browser.newPage({ viewport });
    await page.goto(url, { waitUntil: "networkidle" });
    await page.waitForSelector("canvas", { timeout: 20_000 });
    if (await exists(benchmarkFile)) {
      await page.locator('label:has-text("Open benchmark.json") input').setInputFiles(benchmarkFile);
      await page.waitForSelector("text=Benchmark Comparison", { timeout: 10_000 });
    }
    await page.waitForTimeout(750);

    const canvasStats = await page.evaluate(() => {
      const canvas = document.querySelector("canvas");
      if (!canvas) return null;
      const width = canvas.width;
      const height = canvas.height;
      const probe = document.createElement("canvas");
      probe.width = width;
      probe.height = height;
      const context = probe.getContext("2d");
      if (!context) return { width, height, unique: 0, nonBackground: 0 };
      context.drawImage(canvas, 0, 0);
      const data = context.getImageData(0, 0, width, height).data;
      const unique = new Set();
      let nonBackground = 0;
      for (let i = 0; i < data.length; i += 64) {
        const r = data[i];
        const g = data[i + 1];
        const b = data[i + 2];
        unique.add(`${r},${g},${b}`);
        if (!(r > 235 && g > 235 && b > 235)) nonBackground += 1;
      }
      return { width, height, unique: unique.size, nonBackground };
    });

    if (!canvasStats || canvasStats.unique < 4 || canvasStats.nonBackground < 40) {
      throw new Error(`${viewport.name} canvas appears blank: ${JSON.stringify(canvasStats)}`);
    }

    await page.screenshot({ path: fileURLToPath(new URL(`${viewport.name}.png`, outputDir)), fullPage: true });
    console.log(`${viewport.name}: ${JSON.stringify(canvasStats)}`);
    await page.close();
  }
} finally {
  await browser.close();
}

async function exists(path) {
  try {
    await access(path);
    return true;
  } catch {
    return false;
  }
}
