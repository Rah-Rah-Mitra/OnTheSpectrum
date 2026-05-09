import { inspectGlb } from "./inspect_glb.mjs";
import fs from "node:fs";
import path from "node:path";

const target = process.argv[2] || "public/models/artomata-painter-chibi.glb";
const info = inspectGlb(target);
const warnings = [];

function readSiblingMetadata(filePath) {
  const parsed = path.parse(filePath);
  const metadataPath = path.join(parsed.dir, `${parsed.name}.metadata.json`);
  if (!fs.existsSync(metadataPath)) return null;
  return JSON.parse(fs.readFileSync(metadataPath, "utf8"));
}

const metadata = readSiblingMetadata(target);
const intentionallyStatic =
  metadata?.export?.animations === false &&
  metadata?.counts?.animations === 0 &&
  Array.isArray(metadata?.animations?.clips) &&
  metadata.animations.clips.length === 0;

if (info.triangles > 100000) warnings.push(`Triangle count ${info.triangles} exceeds 100000 warning budget.`);
if (info.bytes > 12 * 1024 * 1024) warnings.push(`GLB size ${info.bytes} bytes exceeds 12 MB warning budget.`);
if (info.materials > 16) warnings.push(`Material count ${info.materials} is higher than the preferred 8-12 range.`);
if (info.animations === 0 && !intentionallyStatic) warnings.push("No embedded animation clips were found.");

console.log(JSON.stringify({ ...info, intentionallyStatic, warnings }, null, 2));
process.exit(warnings.length ? 1 : 0);
