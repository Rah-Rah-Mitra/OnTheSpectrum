import React from "react";
import {
  AbsoluteFill,
  Easing,
  Img,
  Sequence,
  interpolate,
  spring,
  staticFile,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import { Audio } from "@remotion/media";
import {
  Box,
  CheckCircle2,
  ClipboardCheck,
  Download,
  Film,
  Grid2X2,
  LayoutGrid,
  Map,
  Package,
  Palette,
  Play,
  Save,
  ShieldCheck,
  Sparkles,
  WandSparkles,
} from "lucide-react";
import {
  VIDEO,
  handoffTabs,
  outputFiles,
  pipelineSteps,
  previewAssets,
  scenes,
  worldNames,
} from "./demoData.js";
import voiceoverManifest from "./voiceoverManifest.generated.json";
import captureManifest from "./captureManifest.generated.json";
import "./styles.css";

const frameForSecond = (seconds) => Math.round(seconds * VIDEO.fps);

const clamp = (value, min, max) => Math.min(max, Math.max(min, value));

const useSceneProgress = (durationSeconds) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  return clamp(frame / (durationSeconds * fps), 0, 1);
};

const captureFor = (name) => captureManifest.captures?.[name]?.src;

function VoiceoverTrack() {
  if (!voiceoverManifest.generated) return null;
  return scenes.map((scene) => {
    const clip = voiceoverManifest.clips?.[scene.id];
    if (!clip?.src) return null;
    return (
      <Sequence key={scene.id} from={frameForSecond(scene.start)} durationInFrames={frameForSecond(scene.duration)}>
        <Audio src={staticFile(clip.src)} volume={0.98} />
      </Sequence>
    );
  });
}

function Captions() {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const second = frame / fps;
  const active = scenes.find((scene) => second >= scene.start && second < scene.start + scene.duration) ?? scenes[0];
  const local = second - active.start;
  const opacity = interpolate(local, [0, 0.35, active.duration - 0.35, active.duration], [0, 1, 1, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  return (
    <div className="caption-safe">
      <div className="caption-box" style={{ opacity }}>
        {active.caption}
      </div>
    </div>
  );
}

function SceneChrome({ scene, children, kind = "default" }) {
  return (
    <AbsoluteFill className={`scene scene-${kind}`}>
      <div className="scene-grid" />
      <div className="scene-header">
        <div>
          <span className="eyebrow">{scene.eyebrow}</span>
          <h1>{scene.title}</h1>
        </div>
        <div className="timecode">
          {String(scene.start).padStart(2, "0")}s
          <span>{scene.duration}s</span>
        </div>
      </div>
      {children}
    </AbsoluteFill>
  );
}

function CaptureFrame({ name, className = "", children }) {
  const src = captureFor(name);
  if (!src) return children;
  return (
    <div className={`capture-shell ${className}`}>
      <Img src={staticFile(src)} className="capture-image" />
    </div>
  );
}

function AssetTile({ asset, index, large = false }) {
  const frame = useCurrentFrame();
  const lift = Math.sin((frame + index * 18) / 26) * (large ? 10 : 5);
  return (
    <div className={`asset-tile${large ? " asset-tile-large" : ""}`} style={{ "--asset-accent": asset.accent, transform: `translateY(${lift}px)` }}>
      <Img src={staticFile(asset.src)} />
      <div>
        <strong>{asset.name}</strong>
        <span>{asset.family}</span>
      </div>
    </div>
  );
}

function HookScene({ scene }) {
  const progress = useSceneProgress(scene.duration);
  const titleScale = spring({
    frame: useCurrentFrame(),
    fps: VIDEO.fps,
    config: { damping: 18, stiffness: 90, mass: 0.8 },
  });

  return (
    <SceneChrome scene={scene} kind="hook">
      <div className="hook-layout">
        <div className="hook-copy" style={{ transform: `scale(${interpolate(titleScale, [0, 1], [0.94, 1])})` }}>
          <span className="product-mark">
            <Sparkles size={28} />
            OnTheSpectrum
          </span>
          <h2>Prompt to asset to playable scene</h2>
          <p>Two minutes across generation, inspection, export, world building, Agent Handoff, and 3D preview.</p>
          <div className="hook-pills">
            <span>Asset Generator</span>
            <span>Viewer</span>
            <span>World Creator</span>
            <span>World 3D</span>
          </div>
        </div>
        <div className="asset-mosaic" style={{ transform: `translateX(${interpolate(progress, [0, 1], [42, -16])}px)` }}>
          {previewAssets.slice(0, 8).map((asset, index) => (
            <AssetTile key={asset.id} asset={asset} index={index} large={index === 0 || index === 4} />
          ))}
        </div>
      </div>
    </SceneChrome>
  );
}

function BriefForm() {
  return (
    <div className="app-panel generator-form">
      <div className="panel-title">
        <Package />
        <div>
          <strong>Asset Brief</strong>
          <span>Character</span>
        </div>
      </div>
      <div className="form-grid">
        <Field label="Type" value="Character" />
        <Field label="Name" value="Forge Runner NPC" />
        <Field label="Style" value="Stylized hand-painted fantasy" wide />
        <Field label="Rigging" value="Humanoid Mixamo best-effort" />
        <Field label="Animations" value="Idle, Walk, Attack" />
      </div>
      <TextBlock icon={<Palette />} label="Materials / Colors" lines={["teal cloth", "warm leather", "brass accents", "soft cyan glow"]} />
      <TextBlock icon={<Film />} label="Animation Notes" lines={["Readable idle", "short walk loop", "single attack pose"]} />
    </div>
  );
}

function Field({ label, value, wide = false }) {
  return (
    <div className={`field${wide ? " field-wide" : ""}`}>
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function TextBlock({ icon, label, lines }) {
  return (
    <div className="text-block">
      <div>
        {icon}
        <span>{label}</span>
      </div>
      <p>{lines.join(", ")}</p>
    </div>
  );
}

function SpecPreview() {
  const frame = useCurrentFrame();
  const highlighted = Math.floor(frame / 28) % 5;
  const rows = [
    ["family", "character"],
    ["pipelineId", "character.humanoid_basic"],
    ["rigTarget", "humanoid Mixamo best-effort"],
    ["maxTriangles", "100000"],
    ["viewerFraming", "front-quarter"],
  ];
  return (
    <div className="spec-preview">
      <div className="panel-title">
        <ClipboardCheck />
        <div>
          <strong>Asset Spec</strong>
          <span>ready for local generation</span>
        </div>
      </div>
      <div className="code-card">
        {rows.map(([key, value], index) => (
          <div key={key} className={highlighted === index ? "active" : ""}>
            <span>{key}</span>
            <strong>{value}</strong>
          </div>
        ))}
      </div>
      <div className="readiness-list">
        {["OpenAI local API", "Blender runtime", "Form validation", "Budget limits"].map((item) => (
          <span key={item}>
            <CheckCircle2 size={18} />
            {item}
          </span>
        ))}
      </div>
    </div>
  );
}

function AssetBriefScene({ scene }) {
  const progress = useSceneProgress(scene.duration);
  return (
    <SceneChrome scene={scene} kind="generator">
      <CaptureFrame name="generator">
        <div className="two-column-layout" style={{ transform: `translateY(${interpolate(progress, [0, 1], [20, -10])}px)` }}>
          <BriefForm />
          <SpecPreview />
        </div>
      </CaptureFrame>
      <Callout label="Asset Spec" x={1160} y={318} delay={0.22} />
    </SceneChrome>
  );
}

function PipelineScene({ scene }) {
  const frame = useCurrentFrame();
  const progress = useSceneProgress(scene.duration);
  const activeStep = Math.min(pipelineSteps.length - 1, Math.floor(progress * pipelineSteps.length));
  return (
    <SceneChrome scene={scene} kind="pipeline">
      <div className="pipeline-layout">
        <div className="pipeline-card">
          <div className="panel-title">
            <WandSparkles />
            <div>
              <strong>Generation Timeline</strong>
              <span>fast playback of the local pipeline</span>
            </div>
          </div>
          <div className="pipeline-steps">
            {pipelineSteps.map((step, index) => {
              const complete = index < activeStep;
              const active = index === activeStep;
              return (
                <div key={step} className={`pipeline-step${complete ? " complete" : ""}${active ? " active" : ""}`}>
                  <span>{complete || active ? <CheckCircle2 /> : index + 1}</span>
                  <div>
                    <strong>{step}</strong>
                    <small>{complete ? "Completed" : active ? "Running" : "Waiting"}</small>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
        <div className="result-card">
          <AssetTile asset={previewAssets[5]} index={2} large />
          <div className="output-list">
            {outputFiles.map((file, index) => (
              <div key={file.label} style={{ opacity: interpolate(frame, [80 + index * 18, 106 + index * 18], [0, 1], { extrapolateRight: "clamp" }) }}>
                <Download size={20} />
                <span>
                  <strong>{file.label}</strong>
                  <small>{file.path}</small>
                </span>
              </div>
            ))}
          </div>
        </div>
      </div>
      <Callout label="Blender Preflight" x={560} y={580} delay={0.3} />
      <Callout label="GLB Validated" x={1190} y={704} delay={0.62} />
    </SceneChrome>
  );
}

function ViewerScene({ scene }) {
  const frame = useCurrentFrame();
  const activeAsset = previewAssets[frame < 230 ? 0 : frame < 420 ? 4 : 2];
  return (
    <SceneChrome scene={scene} kind="viewer">
      <CaptureFrame name="viewer">
        <div className="viewer-layout">
          <div className="asset-browser">
            {previewAssets.slice(0, 6).map((asset) => (
              <div key={asset.id} className={asset.id === activeAsset.id ? "selected" : ""}>
                <Img src={staticFile(asset.src)} />
                <span>{asset.name}</span>
              </div>
            ))}
          </div>
          <div className="viewer-stage">
            <Img src={staticFile(activeAsset.src)} />
            <div className="viewport-toolbar">
              <span>Studio</span>
              <span>Toon</span>
              <span>Inspect</span>
            </div>
            <div className="status-strip">
              <span>GLB loaded</span>
              <span>Idle clip</span>
              <span>Studio light</span>
            </div>
          </div>
          <div className="inspector-panel">
            <strong>{activeAsset.name}</strong>
            <div className="metric-grid">
              <Metric label="Triangles" value="30,724" />
              <Metric label="Materials" value="16" />
              <Metric label="Animations" value="2" />
              <Metric label="GLB size" value="1.1 MB" />
            </div>
            <div className="export-card">
              <Save />
              <span>Web GLB, Blender source, Mixamo export, snapshot</span>
            </div>
          </div>
        </div>
      </CaptureFrame>
    </SceneChrome>
  );
}

function Metric({ label, value }) {
  return (
    <div>
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function WorldGrid({ activeWorldIndex = 0 }) {
  const cells = Array.from({ length: 96 }, (_, index) => {
    const x = index % 12;
    const y = Math.floor(index / 12);
    const boundary = x === 0 || y === 0 || x === 11 || y === 7;
    const spawn = x === 2 && y === 5;
    const light = (x === 3 && y === 2) || (x === 8 && y === 2) || (x === 9 && y === 6);
    const asset = (x === 4 && y === 4) || (x === 7 && y === 5) || (x === 9 && y === 3);
    const cover = (x === 5 && y === 2) || (x === 6 && y === 2) || (x === 5 && y === 5);
    return { boundary, spawn, light, asset, cover, key: `${x}-${y}` };
  });
  return (
    <div className="world-grid-demo" style={{ "--world-shift": activeWorldIndex }}>
      {cells.map((cell) => (
        <div
          key={cell.key}
          className={[
            cell.boundary ? "wall" : "",
            cell.spawn ? "spawn" : "",
            cell.light ? "light" : "",
            cell.asset ? "asset" : "",
            cell.cover ? "cover" : "",
          ].join(" ")}
        />
      ))}
    </div>
  );
}

function WorldCreatorScene({ scene }) {
  const frame = useCurrentFrame();
  const activeWorldIndex = Math.floor(frame / 120) % worldNames.length;
  return (
    <SceneChrome scene={scene} kind="world">
      <CaptureFrame name="world-grid">
        <div className="world-layout">
          <div className="world-sidebar">
            <div className="panel-title">
              <Map />
              <div>
                <strong>Worlds</strong>
                <span>{worldNames.length} saved</span>
              </div>
            </div>
            {worldNames.map((name, index) => (
              <div key={name} className={`world-row${index === activeWorldIndex ? " active" : ""}`}>
                <span>{name}</span>
                <small>{index === activeWorldIndex ? "active" : "saved"}</small>
              </div>
            ))}
            <div className="palette-mini">
              <span>Build Pieces</span>
              <div>
                <Grid2X2 />
                <Box />
                <Sparkles />
              </div>
            </div>
          </div>
          <div className="world-center">
            <div className="world-toolbar">
              <strong>World Creator</strong>
              <span>12 x 8</span>
              <span>42 placements</span>
              <span>validated</span>
            </div>
            <WorldGrid activeWorldIndex={activeWorldIndex} />
          </div>
          <div className="world-inspector-demo">
            <strong>Cell Inspector</strong>
            <Metric label="Brush" value="Place" />
            <Metric label="Layer" value="Occupant" />
            <Metric label="Role" value="Player" />
            <div className="json-preview">schemaVersion: world-grid.v2</div>
          </div>
        </div>
      </CaptureFrame>
      <Callout label="Saved Worlds" x={315} y={340} delay={0.18} />
      <Callout label="World JSON" x={1320} y={704} delay={0.52} />
    </SceneChrome>
  );
}

function AgentHandoffPanel() {
  const frame = useCurrentFrame();
  const tabIndex = frame < 130 ? 0 : frame < 260 ? 1 : 2;
  const active = handoffTabs[tabIndex];
  return (
    <div className="handoff-panel">
      <div className="panel-title">
        <WandSparkles />
        <div>
          <strong>Agent Handoff</strong>
          <span>{active.label === "Generate" ? "OpenAI prompt" : active.label === "Brief" ? "Generation brief" : "World JSON"}</span>
        </div>
      </div>
      <div className="handoff-tabs">
        {handoffTabs.map((tab) => (
          <span key={tab.id} className={tab.id === active.id ? "active" : ""}>
            {tab.label}
          </span>
        ))}
      </div>
      <div className={`handoff-output ${active.id}`}>
        {active.lines.map((line) => (
          <p key={line}>{line}</p>
        ))}
      </div>
      {active.id === "generate" ? (
        <div className="handoff-actions">
          <button type="button" disabled>
            <WandSparkles size={18} />
            Generate World
          </button>
          <button type="button">
            <Play size={18} />
            Status
          </button>
        </div>
      ) : (
        <div className="handoff-actions">
          <button type="button">
            <ClipboardCheck size={18} />
            Copy
          </button>
          <button type="button">
            <Download size={18} />
            Export
          </button>
        </div>
      )}
    </div>
  );
}

function AgentHandoffScene({ scene }) {
  return (
    <SceneChrome scene={scene} kind="handoff">
      <CaptureFrame name="agent-handoff-generate" className="capture-handoff">
        <div className="handoff-layout">
          <div className="handoff-context">
            <span className="eyebrow">Deterministic demo path</span>
            <h2>Show the Generate tab without starting generation</h2>
            <p>
              The panel moves through JSON, Brief, and Generate. The Generate World action stays disabled in the recording path so the video stays repeatable.
            </p>
            <div className="handoff-callouts">
              <span>JSON</span>
              <span>Brief</span>
              <span>Generate Tab</span>
            </div>
          </div>
          <AgentHandoffPanel />
        </div>
      </CaptureFrame>
      <Callout label="Agent Handoff" x={1032} y={250} delay={0.15} />
      <Callout label="Generate Tab" x={1310} y={372} delay={0.6} />
    </SceneChrome>
  );
}

function WorldNavigationScene({ scene }) {
  const frame = useCurrentFrame();
  const active = Math.min(worldNames.length - 1, Math.floor(frame / 36));
  const showing3d = frame >= 96;
  return (
    <SceneChrome scene={scene} kind="navigation">
      {showing3d ? (
        <CaptureFrame name="world-3d">
          <ThreeDPreviewFallback />
        </CaptureFrame>
      ) : (
        <CaptureFrame name="world-switch">
          <div className="navigation-layout">
            <div className="select-demo">
              <span>Active World</span>
              <strong>{worldNames[active]}</strong>
              <div>
                {worldNames.map((name, index) => (
                  <p key={name} className={index === active ? "active" : ""}>
                    {name}
                  </p>
                ))}
              </div>
            </div>
            <div className="world-preview-stack">
              {worldNames.slice(0, 4).map((name, index) => (
                <div key={name} className={index === active % 4 ? "front" : ""}>
                  <WorldGrid activeWorldIndex={index} />
                  <span>{name}</span>
                </div>
              ))}
            </div>
          </div>
        </CaptureFrame>
      )}
      <Callout label={showing3d ? "3D Preview" : "Saved Worlds"} x={1180} y={230} delay={0.12} />
    </SceneChrome>
  );
}

function ThreeDPreviewFallback() {
  return (
    <div className="three-d-fallback">
      <div className="world-perspective">
        <WorldGrid activeWorldIndex={3} />
      </div>
      <div className="hud-demo">
        <strong>World 3D</strong>
        <span>Free camera</span>
        <span>Player 110/110</span>
        <span>L 0.0 R 0.0 Space 0.0</span>
      </div>
    </div>
  );
}

function CloseScene({ scene }) {
  const frame = useCurrentFrame();
  const fade = interpolate(frame, [0, 30, 100, 120], [0, 1, 1, 0.95], { extrapolateRight: "clamp" });
  return (
    <SceneChrome scene={scene} kind="close">
      <div className="close-layout" style={{ opacity: fade }}>
        <div className="close-grid">
          {previewAssets.slice(0, 6).map((asset, index) => (
            <AssetTile key={asset.id} asset={asset} index={index} />
          ))}
        </div>
        <div className="close-title">
          <span className="product-mark">
            <Sparkles size={30} />
            OnTheSpectrum
          </span>
          <h2>From prompt to asset to playable scene</h2>
          <p>Generator, viewer, world editor, Agent Handoff, and 3D preview in one workflow.</p>
        </div>
      </div>
    </SceneChrome>
  );
}

function Callout({ label, x, y, delay = 0 }) {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const opacity = interpolate(frame / fps, [delay, delay + 0.35], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  return (
    <div className="callout" style={{ left: x, top: y, opacity }}>
      <span />
      {label}
    </div>
  );
}

function SceneLayer({ scene }) {
  switch (scene.id) {
    case "hook":
      return <HookScene scene={scene} />;
    case "asset-brief":
      return <AssetBriefScene scene={scene} />;
    case "asset-pipeline":
      return <PipelineScene scene={scene} />;
    case "asset-viewer":
      return <ViewerScene scene={scene} />;
    case "world-creator":
      return <WorldCreatorScene scene={scene} />;
    case "agent-handoff":
      return <AgentHandoffScene scene={scene} />;
    case "world-navigation":
      return <WorldNavigationScene scene={scene} />;
    default:
      return <CloseScene scene={scene} />;
  }
}

export function OnTheSpectrumFullDemo() {
  return (
    <AbsoluteFill className="demo-root">
      {scenes.map((scene) => (
        <Sequence key={scene.id} from={frameForSecond(scene.start)} durationInFrames={frameForSecond(scene.duration)} premountFor={VIDEO.fps}>
          <SceneLayer scene={scene} />
        </Sequence>
      ))}
      <VoiceoverTrack />
      <Captions />
      <div className="progress-rail">
        {scenes.map((scene) => (
          <span key={scene.id} style={{ width: `${(scene.duration / VIDEO.durationSeconds) * 100}%` }} />
        ))}
      </div>
    </AbsoluteFill>
  );
}
