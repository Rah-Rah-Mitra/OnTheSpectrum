import fs from "node:fs";
import path from "node:path";

export function inspectGlb(filePath) {
  const buffer = fs.readFileSync(filePath);
  if (buffer.toString("utf8", 0, 4) !== "glTF") {
    throw new Error(`${filePath} is not a binary GLB file`);
  }
  let offset = 12;
  let json = null;
  while (offset < buffer.length) {
    const chunkLength = buffer.readUInt32LE(offset);
    const chunkType = buffer.toString("utf8", offset + 4, offset + 8);
    const chunkStart = offset + 8;
    if (chunkType === "JSON") {
      json = JSON.parse(buffer.toString("utf8", chunkStart, chunkStart + chunkLength));
      break;
    }
    offset = chunkStart + chunkLength;
  }
  if (!json) throw new Error("GLB JSON chunk was not found");

  const accessors = json.accessors || [];
  let meshPrimitives = 0;
  let triangles = 0;
  const materialIndexes = new Set();
  const nodeNames = [];
  const boneNames = [];

  for (const node of json.nodes || []) {
    if (node.name) nodeNames.push(node.name);
    if (node.skin !== undefined && node.name) boneNames.push(node.name);
  }

  for (const mesh of json.meshes || []) {
    for (const primitive of mesh.primitives || []) {
      meshPrimitives += 1;
      if (primitive.material !== undefined) materialIndexes.add(primitive.material);
      const mode = primitive.mode ?? 4;
      const indexAccessor = primitive.indices !== undefined ? accessors[primitive.indices] : null;
      const positionAccessor =
        primitive.attributes?.POSITION !== undefined ? accessors[primitive.attributes.POSITION] : null;
      const count = indexAccessor?.count ?? positionAccessor?.count ?? 0;
      if (mode === 4) triangles += Math.floor(count / 3);
      if (mode === 5 || mode === 6) triangles += Math.max(0, count - 2);
    }
  }

  const materialNames = (json.materials || []).map((material) => material.name || "Unnamed material");
  const animationNames = (json.animations || []).map((animation, index) => animation.name || `Animation_${index + 1}`);
  return {
    file: path.normalize(filePath),
    bytes: buffer.length,
    scenes: json.scenes?.length || 0,
    nodes: json.nodes?.length || 0,
    meshes: json.meshes?.length || 0,
    meshPrimitives,
    triangles,
    materials: materialNames.length,
    materialNames,
    skins: json.skins?.length || 0,
    animations: animationNames.length,
    animationNames,
    nodeNames,
    boneNodeHints: boneNames,
  };
}

if (process.argv[1] && import.meta.url.endsWith(path.basename(process.argv[1]))) {
  const target = process.argv[2] || "public/models/on_the_spectrum-painter-chibi.glb";
  console.log(JSON.stringify(inspectGlb(target), null, 2));
}
