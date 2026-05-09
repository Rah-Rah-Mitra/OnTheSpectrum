import React, { useEffect, useMemo, useRef, useState } from "react";
import { createRoot } from "react-dom/client";
import {
  Camera,
  ChevronDown,
  Crosshair,
  Download,
  Film,
  Maximize,
  Paintbrush,
  Palette,
  Pause,
  Play,
  RotateCcw,
  SunMedium,
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

function App() {
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
    <main className="app-shell">
      <div className="ambient-lines" aria-hidden="true" />
      <header className="topbar">
        <div className="brand">
          <Paintbrush aria-hidden="true" />
          <span>Artomata Asset Viewer</span>
        </div>
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
    </main>
  );
}

createRoot(document.getElementById("root")).render(<App />);
