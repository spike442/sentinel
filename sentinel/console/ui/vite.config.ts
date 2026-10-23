import { createHash } from "node:crypto";
import { readFileSync, readdirSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { defineConfig, type Plugin } from "vite";
import react from "@vitejs/plugin-react";

const uiRoot = dirname(fileURLToPath(import.meta.url));
const sentinelApi = process.env.SENTINEL_API_URL ?? "http://127.0.0.1:8070";
const stonksApi = process.env.STONKS_API_URL ?? "http://127.0.0.1:8090";
const local = {
  host: "127.0.0.1",
  port: 8080,
  strictPort: true,
  proxy: {
    "/api/stonks": { target: stonksApi, changeOrigin: true },
    "/api": { target: sentinelApi, changeOrigin: true },
  },
};

function serviceWorker(): Plugin {
  return {
    name: "sentinel-service-worker",
    apply: "build",
    writeBundle({ dir }, bundle) {
      const outDir = dir ?? join(uiRoot, "dist");
      const publicFiles = readdirSync(join(uiRoot, "public"));
      const files = [...Object.keys(bundle), ...publicFiles]
        .filter((file) => !file.endsWith(".woff") && file !== "domains.json")
        .sort();
      const digest = createHash("sha256");
      for (const file of files) digest.update(file).update(readFileSync(join(outDir, file)));
      const shell = files.map((file) => `/${file}`);
      const template = readFileSync(join(uiRoot, "service-worker.js"), "utf8");
      const cacheName = `sentinel-${digest.digest("hex").slice(0, 16)}`;
      const header = `const CACHE_NAME = ${JSON.stringify(cacheName)};\nconst SHELL = ${JSON.stringify(shell)};\n`;
      writeFileSync(join(outDir, "sw.js"), header + template);
    },
  };
}

export default defineConfig({
  root: uiRoot,
  plugins: [react(), serviceWorker()],
  server: local,
  preview: local,
});
