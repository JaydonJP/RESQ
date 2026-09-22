import { copyFileSync, mkdirSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const webRoot = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const assets = resolve(webRoot, "dist", "assets");
mkdirSync(assets, { recursive: true });
copyFileSync(
  resolve(webRoot, "node_modules", "maplibre-gl", "dist", "maplibre-gl-shared.mjs"),
  resolve(assets, "maplibre-gl-shared.mjs"),
);
