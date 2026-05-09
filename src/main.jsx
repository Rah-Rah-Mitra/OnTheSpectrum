import React, { useEffect, useMemo, useRef, useState } from "react";
import { createRoot } from "react-dom/client";
import {
  Box,
  BrickWall,
  Camera,
  ChevronDown,
  CheckCircle2,
  ClipboardCheck,
  Copy,
  Crosshair,
  DoorOpen,
  Download,
  Eraser,
  Film,
  Grid2X2,
  Home,
  LayoutGrid,
  Lightbulb,
  Map as MapIcon,
  Maximize,
  MousePointer2,
  Package,
  Paintbrush,
  Palette,
  Pause,
  Play,
  RefreshCw,
  RotateCcw,
  RotateCw,
  Save,
  ShieldCheck,
  SlidersHorizontal,
  Sparkles,
  StickyNote,
  SunMedium,
  Tags,
  TextCursorInput,
  Trash2,
  Upload,
  WandSparkles,
  ZoomIn,
  ZoomOut,
} from "lucide-react";
import * as THREE from "three";
import { GLTFLoader } from "three/examples/jsm/loaders/GLTFLoader.js";
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls.js";
import { assetRegistry, defaultAssetId } from "./assets/assetRegistry.js";
import "./styles.css";

const sceneModes = {
  studio: {
    label: "Studio",
    backgroundTop: "#182023",
    backgroundBottom: "#050708",
    key: 3.1,
    fill: 1.25,
    rim: 2.4,
    accent: "#28e0ea",
  },
  toon: {
    label: "Toon",
    backgroundTop: "#222133",
    backgroundBottom: "#07070d",
    key: 3.75,
    fill: 1.7,
    rim: 2.7,
    accent: "#f47d69",
  },
  inspect: {
    label: "Inspect",
    backgroundTop: "#252b2c",
    backgroundBottom: "#0b0f10",
    key: 4.2,
    fill: 2.1,
    rim: 1.7,
    accent: "#e4cf9b",
  },
};

const pageTabs = [
  { id: "viewer", label: "Asset Viewer", Icon: Home },
  { id: "world", label: "World Creator", Icon: LayoutGrid },
];

const brushModes = {
  place: { label: "Place", Icon: MousePointer2 },
  erase: { label: "Erase", Icon: Eraser },
  inspect: { label: "Inspect", Icon: SlidersHorizontal },
};

const worldThemes = [
  { id: "studio-atrium", label: "Studio Atrium", mood: "polished indoor set with practical lighting and display zones" },
  { id: "toon-lab", label: "Toon Lab", mood: "bright experimental room for animated characters and prop testing" },
  { id: "garden-room", label: "Garden Room", mood: "soft botanical interior with paths, blooms, and quiet staging pockets" },
  { id: "training-floor", label: "Training Floor", mood: "clear traversal lanes for action character blocking and animation tests" },
];

const structurePalette = [
  {
    id: "floor",
    label: "Floor",
    family: "Structure",
    className: "floor",
    color: "#2e4241",
    Icon: Grid2X2,
    agentHint: "walkable tile",
  },
  {
    id: "wall",
    label: "Wall",
    family: "Structure",
    className: "wall",
    color: "#e4cf9b",
    Icon: BrickWall,
    agentHint: "blocking boundary wall",
  },
  {
    id: "door",
    label: "Door",
    family: "Structure",
    className: "door",
    color: "#f47d69",
    Icon: DoorOpen,
    agentHint: "entry or transition point",
  },
  {
    id: "light",
    label: "Light",
    family: "Utility",
    className: "light",
    color: "#28e0ea",
    Icon: Lightbulb,
    agentHint: "motivated scene light",
  },
  {
    id: "spawn",
    label: "Spawn",
    family: "Utility",
    className: "spawn",
    color: "#91f0a8",
    Icon: Sparkles,
    agentHint: "default character start point",
  },
];

const defaultWorldMeta = {
  name: "Painter Atelier Grid",
  theme: "studio-atrium",
  columns: 10,
  rows: 8,
  cellSize: "1m",
  rules: "Keep at least one door or spawn, keep characters reachable, and use walls only where they clarify room boundaries.",
};

function getCellKey(x, y) {
  return `${x}:${y}`;
}

function clampGridValue(value, min, max) {
  const parsed = Number(value);
  if (!Number.isFinite(parsed)) return min;
  return Math.min(max, Math.max(min, Math.round(parsed)));
}

function findStructure(id) {
  return structurePalette.find((item) => item.id === id) ?? structurePalette[0];
}

function findAsset(id) {
  return assetRegistry.find((item) => item.id === id) ?? assetRegistry[0];
}

function createStructureCell(item, x, y, overrides = {}) {
  return {
    id: `${item.id}-${x}-${y}`,
    type: "structure",
    itemId: item.id,
    label: item.label,
    family: item.family,
    x,
    y,
    rotation: overrides.rotation ?? 0,
    scale: overrides.scale ?? 1,
    elevation: overrides.elevation ?? 0,
    color: item.color,
    className: item.className,
    agentHint: item.agentHint,
    tags: overrides.tags ?? [item.family.toLowerCase()],
    notes: overrides.notes ?? "",
  };
}

function createAssetCell(asset, x, y, overrides = {}) {
  return {
    id: `${asset.id}-${x}-${y}`,
    type: "asset",
    itemId: asset.id,
    label: asset.shortName,
    family: asset.authored.family,
    x,
    y,
    rotation: overrides.rotation ?? 0,
    scale: overrides.scale ?? 1,
    elevation: overrides.elevation ?? 0,
    previewUrl: asset.previewUrl,
    modelUrl: asset.modelUrl,
    blendUrl: asset.blendUrl,
    agentHint: asset.description,
    tags: overrides.tags ?? [asset.authored.family.toLowerCase()],
    notes: overrides.notes ?? "",
  };
}

function createPaletteCell(paletteItem, x, y, previousCell) {
  const overrides = previousCell
    ? {
        rotation: previousCell.rotation,
        scale: previousCell.scale,
        elevation: previousCell.elevation,
        tags: previousCell.tags,
        notes: previousCell.notes,
      }
    : {};
  if (paletteItem.type === "asset") {
    return createAssetCell(findAsset(paletteItem.id), x, y, overrides);
  }
  return createStructureCell(findStructure(paletteItem.id), x, y, overrides);
}

function createStarterWorldCells(columns = defaultWorldMeta.columns, rows = defaultWorldMeta.rows) {
  const cells = {};
  const wall = findStructure("wall");
  for (let y = 0; y < rows; y += 1) {
    for (let x = 0; x < columns; x += 1) {
      if (x === 0 || y === 0 || x === columns - 1 || y === rows - 1) {
        cells[getCellKey(x, y)] = createStructureCell(wall, x, y, { tags: ["boundary", "wall"] });
      }
    }
  }

  const door = findStructure("door");
  const spawn = findStructure("spawn");
  const light = findStructure("light");
  cells[getCellKey(Math.floor(columns / 2), rows - 1)] = createStructureCell(door, Math.floor(columns / 2), rows - 1, {
    tags: ["entry", "south"],
    notes: "Primary entrance for generated scene traversal.",
  });
  cells[getCellKey(1, 1)] = createStructureCell(spawn, 1, 1, {
    tags: ["start", "agent"],
    notes: "Default spawn point for character placement.",
  });
  cells[getCellKey(columns - 2, 1)] = createStructureCell(light, columns - 2, 1, {
    tags: ["lighting", "key"],
    notes: "Key light anchor for the first generated room.",
  });

  const character = assetRegistry.find((asset) => asset.authored.family === "Character") ?? assetRegistry[0];
  const table = assetRegistry.find((asset) => asset.id === "table");
  const chair = assetRegistry.find((asset) => asset.id === "chair");
  const flower = assetRegistry.find((asset) => asset.id === "flower");
  cells[getCellKey(3, 3)] = createAssetCell(character, 3, 3, { tags: ["hero", "character"] });
  if (table) cells[getCellKey(5, 4)] = createAssetCell(table, 5, 4, { rotation: 90, tags: ["furniture", "anchor"] });
  if (chair) cells[getCellKey(5, 5)] = createAssetCell(chair, 5, 5, { rotation: 180, tags: ["furniture", "seat"] });
  if (flower) cells[getCellKey(columns - 3, rows - 3)] = createAssetCell(flower, columns - 3, rows - 3, {
    scale: 0.85,
    tags: ["botanical", "accent"],
  });

  return cells;
}

function resizeWorldCells(cells, columns, rows) {
  const next = {};
  Object.values(cells).forEach((cell) => {
    if (cell.x < columns && cell.y < rows) {
      next[getCellKey(cell.x, cell.y)] = cell;
    }
  });

  const wall = findStructure("wall");
  for (let y = 0; y < rows; y += 1) {
    for (let x = 0; x < columns; x += 1) {
      const key = getCellKey(x, y);
      if ((x === 0 || y === 0 || x === columns - 1 || y === rows - 1) && !next[key]) {
        next[key] = createStructureCell(wall, x, y, { tags: ["boundary", "wall"] });
      }
    }
  }
  return next;
}

function normaliseImportedCell(placement) {
  const x = Number(placement.x);
  const y = Number(placement.y);
  const overrides = {
    rotation: Number(placement.rotation) || 0,
    scale: Number(placement.scale) || 1,
    elevation: Number(placement.elevation) || 0,
    tags: Array.isArray(placement.tags) ? placement.tags : [],
    notes: typeof placement.notes === "string" ? placement.notes : "",
  };
  if (placement.type === "asset") {
    return createAssetCell(findAsset(placement.itemId ?? placement.assetId), x, y, overrides);
  }
  return createStructureCell(findStructure(placement.itemId ?? placement.structureId), x, y, overrides);
}

function serializeWorld(meta, cells) {
  const theme = worldThemes.find((item) => item.id === meta.theme) ?? worldThemes[0];
  return {
    schemaVersion: "artomata.world-grid.v1",
    name: meta.name,
    theme: meta.theme,
    mood: theme.mood,
    grid: {
      columns: meta.columns,
      rows: meta.rows,
      cellSize: meta.cellSize,
      coordinateSystem: "zero-based x,y from top-left",
    },
    rules: meta.rules,
    palette: {
      assets: assetRegistry.map((asset) => ({
        id: asset.id,
        label: asset.shortName,
        family: asset.authored.family,
        modelUrl: asset.modelUrl,
      })),
      structures: structurePalette.map((item) => ({
        id: item.id,
        label: item.label,
        family: item.family,
        agentHint: item.agentHint,
      })),
    },
    placements: Object.values(cells)
      .sort((a, b) => a.y - b.y || a.x - b.x)
      .map(({ type, itemId, label, family, x, y, rotation, scale, elevation, tags, notes, agentHint }) => ({
        type,
        itemId,
        label,
        family,
        x,
        y,
        rotation,
        scale,
        elevation,
        tags,
        notes,
        agentHint,
      })),
    agentContract: {
      oneOccupantPerCell: true,
      validPlacementTypes: ["asset", "structure"],
      preferredWorkflow: "Edit placements, keep x/y inside grid bounds, then import JSON through the World Creator panel.",
    },
  };
}

function buildAgentBrief(world) {
  const characterCount = world.placements.filter((item) => item.family === "Character").length;
  const structureCount = world.placements.filter((item) => item.type === "structure").length;
  return [
    `World: ${world.name}`,
    `Theme: ${world.theme} (${world.mood})`,
    `Grid: ${world.grid.columns} x ${world.grid.rows}, ${world.grid.cellSize} cells, coordinates are ${world.grid.coordinateSystem}.`,
    `Current contents: ${world.placements.length} placements, ${characterCount} character placement(s), ${structureCount} structure placement(s).`,
    `Rules: ${world.rules}`,
    "Agent task contract: use itemId values from the palette, place at integer x/y coordinates inside the grid, use rotation in 90-degree increments when possible, add tags and notes for generation intent, and keep one occupant per cell.",
  ].join("\n");
}

function validateWorld(world) {
  const placements = world.placements;
  const hasCharacter = placements.some((item) => item.family === "Character");
  const hasEntry = placements.some((item) => item.itemId === "door" || item.itemId === "spawn");
  const hasStructure = placements.some((item) => item.type === "structure");
  const occupiedKeys = new Set();
  let duplicate = false;
  placements.forEach((item) => {
    const key = getCellKey(item.x, item.y);
    if (occupiedKeys.has(key)) duplicate = true;
    occupiedKeys.add(key);
  });
  return [
    { ok: hasCharacter, label: "Character anchor", detail: hasCharacter ? "Ready" : "Place at least one character asset." },
    { ok: hasEntry, label: "Entry point", detail: hasEntry ? "Ready" : "Add a door or spawn tile." },
    { ok: hasStructure, label: "Room structure", detail: hasStructure ? "Ready" : "Add walls, floors, lights, or spawn markers." },
    { ok: !duplicate, label: "Cell uniqueness", detail: duplicate ? "Resolve duplicate coordinates." : "Ready" },
  ];
}

function createGradientTexture(top, bottom) {
  const canvas = document.createElement("canvas");
  canvas.width = 2;
  canvas.height = 256;
  const context = canvas.getContext("2d");
  const gradient = context.createLinearGradient(0, 0, 0, canvas.height);
  gradient.addColorStop(0, top);
  gradient.addColorStop(1, bottom);
  context.fillStyle = gradient;
  context.fillRect(0, 0, canvas.width, canvas.height);
  const texture = new THREE.CanvasTexture(canvas);
  texture.colorSpace = THREE.SRGBColorSpace;
  return texture;
}

function readPose(pose) {
  return {
    position: new THREE.Vector3(...pose.position),
    target: new THREE.Vector3(...pose.target),
  };
}

function setCameraPose(camera, controls, pose) {
  const next = readPose(pose);
  camera.position.copy(next.position);
  controls.target.copy(next.target);
  controls.update();
}

function setCameraHome(camera, controls, asset, width) {
  setCameraPose(camera, controls, width < 700 ? asset.camera.mobile : asset.camera.desktop);
}

function formatBytes(bytes) {
  if (!bytes) return "...";
  if (bytes < 1024 * 1024) return `${Math.round(bytes / 1024).toLocaleString()} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function formatBounds(bounds, dimensions) {
  const size = bounds?.size ?? dimensions;
  if (!size) return "...";
  return `${size.map((value) => Number(value).toFixed(2)).join(" x ")} m`;
}

function placeLoadedModel(model, asset) {
  model.rotation.set(...asset.initialTransform.rotation);
  model.scale.setScalar(asset.initialTransform.scale);
  model.updateMatrixWorld(true);

  const box = new THREE.Box3().setFromObject(model);
  const center = box.getCenter(new THREE.Vector3());
  if (asset.placement?.mode === "center") {
    model.position.sub(center);
  } else {
    model.position.x -= center.x;
    model.position.z -= center.z;
    model.position.y -= box.min.y;
  }

  const offset = asset.placement?.offset;
  if (offset) model.position.add(new THREE.Vector3(...offset));
}

function disposeModel(model) {
  model.traverse((child) => {
    if (!child.isMesh) return;
    child.geometry?.dispose?.();
    const materialList = Array.isArray(child.material) ? child.material : [child.material];
    for (const material of materialList) {
      material?.dispose?.();
    }
  });
}

function extractModelMetadata(model, animations = []) {
  let meshes = 0;
  let triangles = 0;
  const materials = new Set();
  model.traverse((child) => {
    if (!child.isMesh) return;
    meshes += 1;
    const geometry = child.geometry;
    const indexCount = geometry.index?.count;
    const vertexCount = geometry.attributes.position?.count ?? 0;
    triangles += Math.round((indexCount ?? vertexCount) / 3);
    const materialList = Array.isArray(child.material) ? child.material : [child.material];
    for (const material of materialList) {
      if (material?.name) materials.add(material.name);
    }
  });

  const box = new THREE.Box3().setFromObject(model);
  const size = box.getSize(new THREE.Vector3());
  return {
    meshes,
    triangles,
    materials: materials.size,
    dimensions: [size.x, size.y, size.z],
    animations: animations.map((clip) => clip.name),
  };
}

async function fetchJson(url) {
  const response = await fetch(url);
  if (!response.ok) throw new Error(`Unable to load ${url}`);
  return response.json();
}

async function fetchFileSize(url) {
  const head = await fetch(url, { method: "HEAD" });
  const length = head.headers.get("content-length");
  if (length) return Number(length);
  const response = await fetch(url);
  const blob = await response.blob();
  return blob.size;
}

function SceneViewport({ asset, activeClipName, autoSpin, exposure, mode, onLoaded, commandRef }) {
  const mountRef = useRef(null);
  const stateRef = useRef({
    renderer: null,
    scene: null,
    camera: null,
    controls: null,
    model: null,
    mixer: null,
    animations: [],
    activeAction: null,
    activeClipName,
    playClip: null,
    lights: null,
    animationId: 0,
    autoSpin,
  });

  useEffect(() => {
    const mount = mountRef.current;
    let disposed = false;
    const scene = new THREE.Scene();
    const clock = new THREE.Clock();
    scene.background = createGradientTexture(sceneModes[mode].backgroundTop, sceneModes[mode].backgroundBottom);
    scene.fog = new THREE.Fog(sceneModes[mode].backgroundBottom, 7.2, 13.5);

    const camera = new THREE.PerspectiveCamera(35, mount.clientWidth / mount.clientHeight, 0.05, 100);
    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: false, preserveDrawingBuffer: true });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.setSize(mount.clientWidth, mount.clientHeight);
    renderer.outputColorSpace = THREE.SRGBColorSpace;
    renderer.toneMapping = THREE.ACESFilmicToneMapping;
    renderer.toneMappingExposure = exposure;
    mount.appendChild(renderer.domElement);

    const controls = new OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true;
    controls.dampingFactor = 0.06;
    controls.minDistance = 1.9;
    controls.maxDistance = 8.2;
    setCameraHome(camera, controls, asset, mount.clientWidth);

    const hemi = new THREE.HemisphereLight("#fcf5e5", "#101820", 0.85);
    const key = new THREE.DirectionalLight("#ffe6d3", sceneModes[mode].key);
    key.position.set(-3.2, 4.8, 4.2);
    const fill = new THREE.DirectionalLight("#8feaf0", sceneModes[mode].fill);
    fill.position.set(3.3, 2.3, 2.0);
    const rim = new THREE.DirectionalLight(sceneModes[mode].accent, sceneModes[mode].rim);
    rim.position.set(3.1, 2.7, -3.2);
    scene.add(hemi, key, fill, rim);

    function playClip(name, fadeDuration = 0.16) {
      const current = stateRef.current;
      if (!current.mixer || !current.animations.length) return;
      const clip = current.animations.find((item) => item.name === name) ?? current.animations[0];
      if (!clip) return;
      const nextAction = current.mixer.clipAction(clip);
      if (current.activeAction === nextAction && nextAction.isRunning()) return;
      if (current.activeAction) {
        current.activeAction.fadeOut(fadeDuration);
      }
      nextAction.reset().setLoop(THREE.LoopRepeat, Infinity).fadeIn(fadeDuration).play();
      current.activeAction = nextAction;
      current.activeClipName = clip.name;
    }

    const loader = new GLTFLoader();
    loader.load(
      asset.modelUrl,
      (gltf) => {
        if (disposed) {
          disposeModel(gltf.scene);
          return;
        }
        const model = gltf.scene;
        placeLoadedModel(model, asset);

        model.traverse((child) => {
          if (!child.isMesh) return;
          child.castShadow = true;
          child.receiveShadow = true;
          const materialList = Array.isArray(child.material) ? child.material : [child.material];
          for (const material of materialList) {
            if (!material) continue;
            material.envMapIntensity = 0.55;
            material.needsUpdate = true;
          }
        });
        scene.add(model);
        stateRef.current.model = model;
        stateRef.current.animations = gltf.animations || [];
        stateRef.current.mixer = gltf.animations?.length ? new THREE.AnimationMixer(model) : null;
        stateRef.current.playClip = playClip;
        playClip(stateRef.current.activeClipName || activeClipName, 0);
        onLoaded({ ...extractModelMetadata(model, gltf.animations), url: asset.modelUrl, status: "ready" });
      },
      undefined,
      (error) => {
        if (disposed) return;
        onLoaded({ error: error.message || "Unable to load model", url: asset.modelUrl, status: "error" });
      },
    );

    function resize() {
      const width = mount.clientWidth;
      const height = mount.clientHeight;
      camera.aspect = width / height;
      camera.updateProjectionMatrix();
      renderer.setSize(width, height);
    }

    function animate() {
      const delta = clock.getDelta();
      if (stateRef.current.mixer) {
        stateRef.current.mixer.update(delta);
      }
      const loadedModel = stateRef.current.model;
      if (loadedModel && stateRef.current.autoSpin) {
        loadedModel.rotation.y += 0.0042;
      }
      controls.update();
      renderer.render(scene, camera);
      stateRef.current.animationId = requestAnimationFrame(animate);
    }

    window.addEventListener("resize", resize);
    stateRef.current = {
      renderer,
      scene,
      camera,
      controls,
      model: null,
      mixer: null,
      animations: [],
      activeAction: null,
      activeClipName,
      playClip,
      lights: { key, fill, rim },
      animationId: 0,
      autoSpin,
    };
    animate();

    commandRef.current = {
      reset: () => {
        const loadedModel = stateRef.current.model;
        if (loadedModel) loadedModel.rotation.set(...asset.initialTransform.rotation);
        setCameraHome(camera, controls, asset, mount.clientWidth);
      },
      focus: () => setCameraPose(camera, controls, asset.camera.focus),
      zoomIn: () => {
        camera.position.lerp(controls.target, 0.18);
        controls.update();
      },
      zoomOut: () => {
        camera.position.lerpVectors(controls.target, camera.position, 1.18);
        controls.update();
      },
      snapshot: () => renderer.domElement.toDataURL("image/png"),
    };

    return () => {
      disposed = true;
      window.removeEventListener("resize", resize);
      cancelAnimationFrame(stateRef.current.animationId);
      commandRef.current = null;
      stateRef.current.mixer?.stopAllAction();
      if (stateRef.current.model) disposeModel(stateRef.current.model);
      controls.dispose();
      renderer.dispose();
      if (renderer.domElement.parentNode === mount) {
        mount.removeChild(renderer.domElement);
      }
    };
  }, [asset, commandRef, onLoaded]);

  useEffect(() => {
    stateRef.current.autoSpin = autoSpin;
  }, [autoSpin]);

  useEffect(() => {
    stateRef.current.activeClipName = activeClipName;
    stateRef.current.playClip?.(activeClipName);
  }, [activeClipName]);

  useEffect(() => {
    const current = stateRef.current;
    if (!current.renderer) return;
    current.renderer.toneMappingExposure = exposure;
    if (current.lights) {
      current.lights.key.intensity = sceneModes[mode].key;
      current.lights.fill.intensity = sceneModes[mode].fill;
      current.lights.rim.intensity = sceneModes[mode].rim;
      current.lights.rim.color.set(sceneModes[mode].accent);
    }
    const oldBackground = current.scene.background;
    current.scene.background = createGradientTexture(sceneModes[mode].backgroundTop, sceneModes[mode].backgroundBottom);
    current.scene.fog.color.set(sceneModes[mode].backgroundBottom);
    if (oldBackground?.dispose) oldBackground.dispose();
  }, [exposure, mode]);

  return <div className="viewport" ref={mountRef} aria-label={`${asset.name} interactive 3D model viewport`} />;
}

function IconButton({ label, children, onClick, href, download }) {
  const className = "icon-button";
  if (href) {
    return (
      <a className={className} href={href} download={download} aria-label={label} title={label}>
        {children}
      </a>
    );
  }
  return (
    <button className={className} type="button" onClick={onClick} aria-label={label} title={label}>
      {children}
    </button>
  );
}

function ExportMenu({ asset }) {
  return (
    <details className="export-menu">
      <summary aria-label={`Download ${asset.shortName} exports`} title={`Download ${asset.shortName} exports`}>
        <Download aria-hidden="true" />
        <ChevronDown aria-hidden="true" />
        <span className="sr-only">Exports</span>
      </summary>
      <div className="export-menu-list">
        {asset.exports.map((item) => (
          <a
            key={item.id}
            href={item.href}
            download={item.downloadName}
            aria-label={`Download ${item.label}`}
          >
            <span>{item.label}</span>
            <small>{item.detail}</small>
          </a>
        ))}
      </div>
    </details>
  );
}

function InspectorMetric({ label, value }) {
  return (
    <div className="metric">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function AnimationSelector({ clips, activeClipName, onSelect }) {
  if (!clips?.length) return null;
  return (
    <div className="animation-control" aria-label="Animation clip selector">
      <div className="animation-control-heading">
        <Film aria-hidden="true" />
        <span>Animation</span>
      </div>
      <div className="animation-options">
        {clips.map((clip) => (
          <button
            key={clip.name}
            type="button"
            aria-label={`Select ${clip.label} animation`}
            aria-pressed={activeClipName === clip.name}
            className={activeClipName === clip.name ? "active" : ""}
            onClick={() => onSelect(clip.name)}
          >
            {clip.label}
          </button>
        ))}
      </div>
    </div>
  );
}

function AssetPicker({ assets, selectedId, onSelect }) {
  return (
    <aside className="asset-browser" aria-label="Asset viewer">
      <div className="asset-browser-heading">
        <span>Assets</span>
        <small>{assets.length} available</small>
      </div>
      <div className="asset-list">
        {assets.map((item) => (
          <button
            key={item.id}
            type="button"
            className={`asset-card${selectedId === item.id ? " active" : ""}`}
            aria-pressed={selectedId === item.id}
            aria-label={`Select ${item.shortName}`}
            onClick={() => onSelect(item.id)}
          >
            <img src={item.previewUrl} alt="" loading="lazy" />
            <span>
              <strong>{item.shortName}</strong>
              <small>{item.authored.family}</small>
            </span>
          </button>
        ))}
      </div>
    </aside>
  );
}

function Brand() {
  return (
    <div className="brand">
      <Paintbrush aria-hidden="true" />
      <span>Artomata Asset Viewer</span>
    </div>
  );
}

function PageNav({ activePage, onNavigate }) {
  return (
    <nav className="page-nav" aria-label="App pages">
      {pageTabs.map(({ id, label, Icon }) => (
        <button
          key={id}
          type="button"
          className={activePage === id ? "active" : ""}
          aria-current={activePage === id ? "page" : undefined}
          onClick={() => onNavigate(id)}
        >
          <Icon aria-hidden="true" />
          <span>{label}</span>
        </button>
      ))}
    </nav>
  );
}

function AssetViewerPage({ activePage, onNavigate }) {
  const [selectedAssetId, setSelectedAssetId] = useState(defaultAssetId);
  const [autoSpin, setAutoSpin] = useState(false);
  const [activeClipName, setActiveClipName] = useState("");
  const [exposure, setExposure] = useState(1.05);
  const [mode, setMode] = useState("studio");
  const selectedAsset = useMemo(
    () => assetRegistry.find((item) => item.id === selectedAssetId) ?? assetRegistry[0],
    [selectedAssetId],
  );
  const activeAnimationLabel = useMemo(
    () => selectedAsset.animationClips?.find((clip) => clip.name === activeClipName)?.label ?? "Still",
    [activeClipName, selectedAsset],
  );
  const [modelInfo, setModelInfo] = useState({ status: "loading", url: selectedAsset.modelUrl });
  const [authored, setAuthored] = useState(selectedAsset.metadataFallback);
  const [fileSize, setFileSize] = useState(0);
  const commandRef = useRef(null);

  useEffect(() => {
    setActiveClipName(selectedAsset.defaultAnimation ?? selectedAsset.animationClips?.[0]?.name ?? "");
  }, [selectedAsset]);

  useEffect(() => {
    let cancelled = false;
    setModelInfo({ status: "loading", url: selectedAsset.modelUrl });
    setAuthored(selectedAsset.metadataFallback);
    setFileSize(0);

    if (selectedAsset.metadataUrl) {
      fetchJson(selectedAsset.metadataUrl)
        .then((metadata) => {
          if (!cancelled) setAuthored(metadata);
        })
        .catch(() => {
          if (!cancelled) setAuthored(selectedAsset.metadataFallback);
        });
    }
    fetchFileSize(selectedAsset.modelUrl)
      .then((size) => {
        if (!cancelled) setFileSize(size);
      })
      .catch(() => {
        if (!cancelled) setFileSize(0);
      });

    return () => {
      cancelled = true;
    };
  }, [selectedAsset]);

  const metrics = useMemo(
    () => [
      {
        label: "Geometry parts",
        value:
          (authored?.counts?.geometry_objects ?? authored?.counts?.mesh_objects ?? modelInfo.meshes)?.toLocaleString?.() ??
          "...",
      },
      { label: "Triangles", value: (authored?.counts?.triangles ?? modelInfo.triangles)?.toLocaleString?.() ?? "..." },
      { label: "Materials", value: (authored?.counts?.materials ?? modelInfo.materials)?.toLocaleString?.() ?? "..." },
      { label: "Rig bones", value: authored?.counts?.bones?.toLocaleString?.() ?? "..." },
      {
        label: "Animations",
        value: (authored?.counts?.animations ?? modelInfo.animations?.length)?.toLocaleString?.() ?? "...",
      },
      { label: "GLB size", value: formatBytes(authored?.file_sizes?.glb_bytes ?? fileSize) },
      { label: "Bounds", value: formatBounds(authored?.bounds, modelInfo.dimensions) },
    ],
    [authored, fileSize, modelInfo],
  );

  function saveSnapshot() {
    const dataUrl = commandRef.current?.snapshot?.();
    if (!dataUrl) return;
    const link = document.createElement("a");
    link.href = dataUrl;
    link.download = selectedAsset.snapshotName;
    link.click();
  }

  return (
    <>
      <header className="topbar viewer-topbar">
        <Brand />
        <PageNav activePage={activePage} onNavigate={onNavigate} />
        <nav className="view-tabs" aria-label="Lighting mode">
          {Object.entries(sceneModes).map(([key, item]) => (
            <button key={key} type="button" className={mode === key ? "active" : ""} onClick={() => setMode(key)}>
              {item.label}
            </button>
          ))}
        </nav>
        <div className="toolbar">
          <IconButton label={autoSpin ? "Pause spin" : "Play spin"} onClick={() => setAutoSpin((value) => !value)}>
            {autoSpin ? <Pause /> : <Play />}
          </IconButton>
          <IconButton label="Reset view" onClick={() => commandRef.current?.reset?.()}>
            <RotateCcw />
          </IconButton>
          <ExportMenu asset={selectedAsset} />
        </div>
      </header>

      <AssetPicker assets={assetRegistry} selectedId={selectedAsset.id} onSelect={setSelectedAssetId} />

      <section
        className="stage"
        aria-label={`${selectedAsset.name} viewer`}
        data-active-asset={selectedAsset.id}
        data-model-status={modelInfo.status}
      >
        <SceneViewport
          key={selectedAsset.id}
          asset={selectedAsset}
          activeClipName={activeClipName}
          autoSpin={autoSpin}
          exposure={exposure}
          mode={mode}
          onLoaded={setModelInfo}
          commandRef={commandRef}
        />
        <div className="canvas-tools" aria-label="Viewport controls">
          <IconButton label="Zoom in" onClick={() => commandRef.current?.zoomIn?.()}>
            <ZoomIn />
          </IconButton>
          <IconButton label="Zoom out" onClick={() => commandRef.current?.zoomOut?.()}>
            <ZoomOut />
          </IconButton>
          <IconButton label={`Focus ${selectedAsset.shortName}`} onClick={() => commandRef.current?.focus?.()}>
            <Crosshair />
          </IconButton>
          <IconButton label="Snapshot" onClick={saveSnapshot}>
            <Camera />
          </IconButton>
        </div>
        <div className="status-strip">
          <span>{modelInfo.error ? "Model load issue" : modelInfo.status === "ready" ? "GLB loaded" : "Loading GLB"}</span>
          <span>{autoSpin ? "Spin on" : "Spin off"}</span>
          <span>{activeAnimationLabel} clip</span>
          <span>{sceneModes[mode].label} light</span>
        </div>
      </section>

      <aside className="inspector" aria-label="Model inspector">
        <div className="inspector-heading">
          <div>
            <span>{selectedAsset.shortName}</span>
            <small>{selectedAsset.authored.target}</small>
          </div>
        </div>
        <div className="metric-grid">
          {metrics.map((metric) => (
            <InspectorMetric key={metric.label} label={metric.label} value={metric.value} />
          ))}
        </div>
        <AnimationSelector
          clips={selectedAsset.animationClips}
          activeClipName={activeClipName}
          onSelect={setActiveClipName}
        />
        <div className="control-group">
          <label htmlFor="exposure">
            <SunMedium aria-hidden="true" />
            Exposure
          </label>
          <input
            id="exposure"
            type="range"
            min="0.72"
            max="1.45"
            step="0.01"
            value={exposure}
            onChange={(event) => setExposure(Number(event.target.value))}
          />
          <output>{exposure.toFixed(2)}</output>
        </div>
        <dl className="asset-facts">
          <div>
            <dt>
              <Palette aria-hidden="true" />
              Effects
            </dt>
            <dd>{selectedAsset.authored.effects}</dd>
          </div>
          <div>
            <dt>
              <Maximize aria-hidden="true" />
              Source
            </dt>
            <dd>{selectedAsset.sourceLabel}</dd>
          </div>
        </dl>
      </aside>
    </>
  );
}

function WorldPaletteButton({ item, active, onSelect }) {
  const Icon = item.Icon ?? Package;
  return (
    <button
      type="button"
      className={`palette-tile${active ? " active" : ""}${item.type === "asset" ? " asset-palette-tile" : ""}`}
      aria-pressed={active}
      onClick={() => onSelect(item.id)}
    >
      {item.previewUrl ? <img src={item.previewUrl} alt="" loading="lazy" /> : <Icon aria-hidden="true" />}
      <span>
        <strong>{item.label}</strong>
        <small>{item.family}</small>
      </span>
    </button>
  );
}

function WorldCell({ cell, x, y, selected, onClick }) {
  const structure = cell?.type === "structure" ? findStructure(cell.itemId) : null;
  const Icon = structure?.Icon ?? Package;
  const className = [
    "world-cell",
    cell ? "occupied" : "",
    cell?.type ?? "",
    cell?.className ?? "",
    selected ? "selected" : "",
  ]
    .filter(Boolean)
    .join(" ");

  return (
    <button
      type="button"
      className={className}
      style={{
        "--cell-accent": cell?.color ?? "#28e0ea",
        "--cell-rotation": `${cell?.rotation ?? 0}deg`,
        "--cell-scale": cell?.scale ?? 1,
      }}
      aria-label={cell ? `${cell.label} at ${x}, ${y}` : `Empty cell ${x}, ${y}`}
      aria-pressed={selected}
      onClick={onClick}
    >
      <span className="cell-coordinates">
        {x + 1}.{y + 1}
      </span>
      {cell ? (
        <span className="cell-content">
          {cell.previewUrl ? <img src={cell.previewUrl} alt="" loading="lazy" /> : <Icon aria-hidden="true" />}
        </span>
      ) : null}
      {cell ? <strong>{cell.label}</strong> : null}
    </button>
  );
}

function WorldCreatorPage({ activePage, onNavigate }) {
  const [worldMeta, setWorldMeta] = useState(defaultWorldMeta);
  const [cells, setCells] = useState(() => createStarterWorldCells());
  const [selectedPaletteId, setSelectedPaletteId] = useState(defaultAssetId);
  const [brushMode, setBrushMode] = useState("place");
  const [selectedKey, setSelectedKey] = useState(getCellKey(3, 3));
  const [importText, setImportText] = useState("");
  const [copyStatus, setCopyStatus] = useState("");
  const [schemaView, setSchemaView] = useState("json");

  const paletteItems = useMemo(
    () => [
      ...structurePalette.map((item) => ({ ...item, type: "structure" })),
      ...assetRegistry.map((asset) => ({
        id: asset.id,
        type: "asset",
        label: asset.shortName,
        family: asset.authored.family,
        previewUrl: asset.previewUrl,
        agentHint: asset.description,
      })),
    ],
    [],
  );
  const selectedPalette = paletteItems.find((item) => item.id === selectedPaletteId) ?? paletteItems[0];
  const worldDocument = useMemo(() => serializeWorld(worldMeta, cells), [cells, worldMeta]);
  const worldJson = useMemo(() => JSON.stringify(worldDocument, null, 2), [worldDocument]);
  const agentBrief = useMemo(() => buildAgentBrief(worldDocument), [worldDocument]);
  const validation = useMemo(() => validateWorld(worldDocument), [worldDocument]);
  const selectedCell = selectedKey ? cells[selectedKey] : null;

  const gridCells = useMemo(
    () =>
      Array.from({ length: worldMeta.columns * worldMeta.rows }, (_, index) => {
        const x = index % worldMeta.columns;
        const y = Math.floor(index / worldMeta.columns);
        return { x, y, key: getCellKey(x, y), cell: cells[getCellKey(x, y)] };
      }),
    [cells, worldMeta.columns, worldMeta.rows],
  );

  function navigate(page) {
    onNavigate(page);
  }

  function updateWorldField(field, value) {
    setWorldMeta((current) => ({ ...current, [field]: value }));
  }

  function updateGridDimension(field, value) {
    const nextValue = clampGridValue(value, field === "columns" ? 6 : 5, field === "columns" ? 16 : 12);
    const nextMeta = { ...worldMeta, [field]: nextValue };
    setWorldMeta(nextMeta);
    setCells((current) => resizeWorldCells(current, nextMeta.columns, nextMeta.rows));
    setSelectedKey((currentKey) => {
      const currentCell = currentKey ? cells[currentKey] : null;
      if (!currentCell || currentCell.x >= nextMeta.columns || currentCell.y >= nextMeta.rows) return null;
      return currentKey;
    });
  }

  function handleCellAction(x, y) {
    const key = getCellKey(x, y);
    setSelectedKey(key);
    if (brushMode === "inspect") return;
    if (brushMode === "erase") {
      setCells((current) => {
        const next = { ...current };
        delete next[key];
        return next;
      });
      return;
    }
    setCells((current) => ({
      ...current,
      [key]: createPaletteCell(selectedPalette, x, y, current[key]),
    }));
  }

  function updateSelectedCell(patch) {
    if (!selectedKey || !cells[selectedKey]) return;
    setCells((current) => ({
      ...current,
      [selectedKey]: { ...current[selectedKey], ...patch },
    }));
  }

  function clearWorld() {
    setCells({});
    setSelectedKey(null);
  }

  function resetStarterWorld() {
    setCells(createStarterWorldCells(worldMeta.columns, worldMeta.rows));
    setSelectedKey(getCellKey(3, 3));
  }

  async function copyText(text, label) {
    try {
      if (navigator.clipboard?.writeText) {
        await navigator.clipboard.writeText(text);
      } else {
        const textarea = document.createElement("textarea");
        textarea.value = text;
        textarea.setAttribute("readonly", "");
        textarea.style.position = "fixed";
        textarea.style.opacity = "0";
        document.body.appendChild(textarea);
        textarea.select();
        document.execCommand("copy");
        document.body.removeChild(textarea);
      }
      setCopyStatus(`${label} copied`);
    } catch {
      setCopyStatus(`Unable to copy ${label.toLowerCase()}`);
    }
    window.setTimeout(() => setCopyStatus(""), 2200);
  }

  function downloadWorldJson() {
    const slug = worldMeta.name.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/(^-|-$)/g, "") || "world";
    const blob = new Blob([worldJson], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `${slug}.world.json`;
    link.click();
    URL.revokeObjectURL(url);
    setCopyStatus("World JSON saved");
    window.setTimeout(() => setCopyStatus(""), 2200);
  }

  function applyImportedWorld() {
    try {
      const parsed = JSON.parse(importText);
      const columns = clampGridValue(parsed.grid?.columns ?? parsed.columns ?? worldMeta.columns, 6, 16);
      const rows = clampGridValue(parsed.grid?.rows ?? parsed.rows ?? worldMeta.rows, 5, 12);
      const placements = Array.isArray(parsed.placements) ? parsed.placements : [];
      const nextCells = {};
      placements.forEach((placement) => {
        const x = Number(placement.x);
        const y = Number(placement.y);
        if (!Number.isInteger(x) || !Number.isInteger(y) || x < 0 || y < 0 || x >= columns || y >= rows) return;
        nextCells[getCellKey(x, y)] = normaliseImportedCell(placement);
      });
      setWorldMeta({
        name: parsed.name || worldMeta.name,
        theme: parsed.theme || worldMeta.theme,
        columns,
        rows,
        cellSize: parsed.grid?.cellSize || worldMeta.cellSize,
        rules: parsed.rules || worldMeta.rules,
      });
      setCells(placements.length ? nextCells : createStarterWorldCells(columns, rows));
      setSelectedKey(Object.keys(nextCells)[0] ?? null);
      setCopyStatus("World JSON imported");
    } catch {
      setCopyStatus("Import JSON has a syntax issue");
    }
    window.setTimeout(() => setCopyStatus(""), 2600);
  }

  return (
    <>
      <header className="topbar creator-topbar">
        <Brand />
        <PageNav activePage={activePage} onNavigate={navigate} />
        <nav className="view-tabs creator-mode-tabs" aria-label="World brush mode">
          {Object.entries(brushModes).map(([key, item]) => {
            const Icon = item.Icon;
            return (
              <button key={key} type="button" className={brushMode === key ? "active" : ""} onClick={() => setBrushMode(key)}>
                <Icon aria-hidden="true" />
                <span>{item.label}</span>
              </button>
            );
          })}
        </nav>
        <div className="toolbar">
          <IconButton label="Reset starter world" onClick={resetStarterWorld}>
            <RefreshCw />
          </IconButton>
          <IconButton label="Copy world JSON" onClick={() => copyText(worldJson, "World JSON")}>
            <Copy />
          </IconButton>
          <IconButton label="Download world JSON" onClick={downloadWorldJson}>
            <Save />
          </IconButton>
          <IconButton label="Clear world" onClick={clearWorld}>
            <Trash2 />
          </IconButton>
        </div>
      </header>

      <section className="world-creator" aria-label="World Creator">
        <aside className="creator-panel palette-panel" aria-label="World palette">
          <div className="panel-heading">
            <div>
              <span>Palette</span>
              <small>{selectedPalette.label}</small>
            </div>
            <Box aria-hidden="true" />
          </div>
          <div className="palette-section">
            <h2>Build Pieces</h2>
            <div className="palette-grid">
              {paletteItems
                .filter((item) => item.type === "structure")
                .map((item) => (
                  <WorldPaletteButton
                    key={item.id}
                    item={item}
                    active={selectedPaletteId === item.id}
                    onSelect={setSelectedPaletteId}
                  />
                ))}
            </div>
          </div>
          <div className="palette-section">
            <h2>Assets</h2>
            <div className="palette-grid">
              {paletteItems
                .filter((item) => item.type === "asset")
                .map((item) => (
                  <WorldPaletteButton
                    key={item.id}
                    item={item}
                    active={selectedPaletteId === item.id}
                    onSelect={setSelectedPaletteId}
                  />
                ))}
            </div>
          </div>
        </aside>

        <section className="world-stage-panel" aria-label="Placement grid">
          <div className="world-stage-heading">
            <div>
              <h1>World Creator</h1>
              <span>{worldMeta.name}</span>
            </div>
            <div className="world-stats" aria-label="World stats">
              <span>
                <Grid2X2 aria-hidden="true" />
                {worldMeta.columns} x {worldMeta.rows}
              </span>
              <span>
                <Package aria-hidden="true" />
                {worldDocument.placements.length}
              </span>
              <span>
                <ShieldCheck aria-hidden="true" />
                {validation.filter((item) => item.ok).length}/{validation.length}
              </span>
            </div>
          </div>

          <div className="world-grid-frame">
            <div
              className="world-grid"
              style={{
                "--world-columns": worldMeta.columns,
                "--world-rows": worldMeta.rows,
              }}
            >
              {gridCells.map(({ key, x, y, cell }) => (
                <WorldCell
                  key={key}
                  x={x}
                  y={y}
                  cell={cell}
                  selected={selectedKey === key}
                  onClick={() => handleCellAction(x, y)}
                />
              ))}
            </div>
          </div>
          <div className="creator-status-strip">
            <span>{brushModes[brushMode].label} brush</span>
            <span>{selectedPalette.label}</span>
            <span>{copyStatus || "Autosynced schema"}</span>
          </div>
        </section>

        <aside className="creator-panel world-inspector" aria-label="World inspector">
          <div className="panel-heading">
            <div>
              <span>World Setup</span>
              <small>{worldThemes.find((item) => item.id === worldMeta.theme)?.label}</small>
            </div>
            <MapIcon aria-hidden="true" />
          </div>

          <div className="form-grid">
            <label>
              <span>Name</span>
              <input value={worldMeta.name} onChange={(event) => updateWorldField("name", event.target.value)} />
            </label>
            <label>
              <span>Theme</span>
              <select value={worldMeta.theme} onChange={(event) => updateWorldField("theme", event.target.value)}>
                {worldThemes.map((theme) => (
                  <option key={theme.id} value={theme.id}>
                    {theme.label}
                  </option>
                ))}
              </select>
            </label>
            <label>
              <span>Columns</span>
              <input
                type="number"
                min="6"
                max="16"
                value={worldMeta.columns}
                onChange={(event) => updateGridDimension("columns", event.target.value)}
              />
            </label>
            <label>
              <span>Rows</span>
              <input
                type="number"
                min="5"
                max="12"
                value={worldMeta.rows}
                onChange={(event) => updateGridDimension("rows", event.target.value)}
              />
            </label>
            <label>
              <span>Cell Size</span>
              <input value={worldMeta.cellSize} onChange={(event) => updateWorldField("cellSize", event.target.value)} />
            </label>
          </div>

          <label className="full-field">
            <span>
              <TextCursorInput aria-hidden="true" />
              Rules
            </span>
            <textarea value={worldMeta.rules} onChange={(event) => updateWorldField("rules", event.target.value)} rows="3" />
          </label>

          <div className="panel-heading compact-heading">
            <div>
              <span>{selectedCell ? selectedCell.label : "No cell selected"}</span>
              <small>{selectedCell ? `${selectedCell.x + 1}.${selectedCell.y + 1}` : "Select a grid cell"}</small>
            </div>
            <ClipboardCheck aria-hidden="true" />
          </div>

          <div className="selected-cell-tools">
            <div className="segmented-icon-row" aria-label="Cell rotation controls">
              <button type="button" disabled={!selectedCell} onClick={() => updateSelectedCell({ rotation: (selectedCell.rotation + 270) % 360 })}>
                <RotateCcw aria-hidden="true" />
                <span>-90</span>
              </button>
              <button type="button" disabled={!selectedCell} onClick={() => updateSelectedCell({ rotation: (selectedCell.rotation + 90) % 360 })}>
                <RotateCw aria-hidden="true" />
                <span>+90</span>
              </button>
            </div>
            <label>
              <span>Scale</span>
              <input
                type="range"
                min="0.5"
                max="1.75"
                step="0.05"
                disabled={!selectedCell}
                value={selectedCell?.scale ?? 1}
                onChange={(event) => updateSelectedCell({ scale: Number(event.target.value) })}
              />
            </label>
            <label>
              <span>Elevation</span>
              <input
                type="number"
                step="0.25"
                disabled={!selectedCell}
                value={selectedCell?.elevation ?? 0}
                onChange={(event) => updateSelectedCell({ elevation: Number(event.target.value) || 0 })}
              />
            </label>
            <label>
              <span>
                <Tags aria-hidden="true" />
                Tags
              </span>
              <input
                disabled={!selectedCell}
                value={selectedCell?.tags?.join(", ") ?? ""}
                onChange={(event) =>
                  updateSelectedCell({
                    tags: event.target.value
                      .split(",")
                      .map((tag) => tag.trim())
                      .filter(Boolean),
                  })
                }
              />
            </label>
            <label>
              <span>
                <StickyNote aria-hidden="true" />
                Notes
              </span>
              <textarea
                disabled={!selectedCell}
                rows="3"
                value={selectedCell?.notes ?? ""}
                onChange={(event) => updateSelectedCell({ notes: event.target.value })}
              />
            </label>
          </div>
        </aside>

        <aside className="creator-panel agent-panel" aria-label="Agent handoff">
          <div className="panel-heading">
            <div>
              <span>Agent Handoff</span>
              <small>{schemaView === "json" ? "World JSON" : "Generation brief"}</small>
            </div>
            <WandSparkles aria-hidden="true" />
          </div>

          <div className="schema-tabs" aria-label="Schema view">
            <button type="button" className={schemaView === "json" ? "active" : ""} onClick={() => setSchemaView("json")}>
              JSON
            </button>
            <button type="button" className={schemaView === "brief" ? "active" : ""} onClick={() => setSchemaView("brief")}>
              Brief
            </button>
          </div>

          <textarea className="schema-output" readOnly value={schemaView === "json" ? worldJson : agentBrief} />

          <div className="agent-actions">
            <button type="button" onClick={() => copyText(worldJson, "World JSON")}>
              <Copy aria-hidden="true" />
              <span>Copy JSON</span>
            </button>
            <button type="button" onClick={() => copyText(agentBrief, "Agent brief")}>
              <ClipboardCheck aria-hidden="true" />
              <span>Copy Brief</span>
            </button>
          </div>

          <div className="validation-list">
            {validation.map((item) => (
              <div key={item.label} className={item.ok ? "ready" : "needs-work"}>
                <CheckCircle2 aria-hidden="true" />
                <span>
                  <strong>{item.label}</strong>
                  <small>{item.detail}</small>
                </span>
              </div>
            ))}
          </div>

          <label className="full-field import-field">
            <span>
              <Upload aria-hidden="true" />
              Import JSON
            </span>
            <textarea value={importText} rows="5" onChange={(event) => setImportText(event.target.value)} />
          </label>
          <button type="button" className="wide-action" onClick={applyImportedWorld}>
            <Upload aria-hidden="true" />
            <span>Apply Import</span>
          </button>
        </aside>
      </section>
    </>
  );
}

function getInitialPage() {
  if (window.location.hash.replace("#", "") === "world") return "world";
  return "viewer";
}

function App() {
  const [activePage, setActivePage] = useState(getInitialPage);

  useEffect(() => {
    function handleHashChange() {
      setActivePage(getInitialPage());
    }
    window.addEventListener("hashchange", handleHashChange);
    return () => window.removeEventListener("hashchange", handleHashChange);
  }, []);

  function navigate(page) {
    setActivePage(page);
    const nextHash = page === "world" ? "#world" : "#viewer";
    if (window.location.hash !== nextHash) {
      window.location.hash = nextHash;
    }
  }

  return (
    <main className={`app-shell ${activePage === "world" ? "world-shell" : "viewer-shell"}`}>
      <div className="ambient-lines" aria-hidden="true" />
      {activePage === "world" ? (
        <WorldCreatorPage activePage={activePage} onNavigate={navigate} />
      ) : (
        <AssetViewerPage activePage={activePage} onNavigate={navigate} />
      )}
    </main>
  );
}

createRoot(document.getElementById("root")).render(<App />);
