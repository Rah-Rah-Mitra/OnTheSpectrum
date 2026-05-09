import { existsSync, mkdirSync, readFileSync, writeFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { scenes, VIDEO } from "../src/demoData.js";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const projectRoot = path.resolve(__dirname, "..");
const repoRoot = path.resolve(projectRoot, "..");
const voiceoverDir = path.join(projectRoot, "public", "voiceover", VIDEO.mediaFolder);
const manifestPath = path.join(projectRoot, "src", "voiceoverManifest.generated.json");

function loadEnvFile(filePath) {
  if (!existsSync(filePath)) return;
  const contents = readFileSync(filePath, "utf8");
  for (const rawLine of contents.split(/\r?\n/)) {
    const line = rawLine.trim();
    if (!line || line.startsWith("#")) continue;
    const index = line.indexOf("=");
    if (index < 0) continue;
    const key = line.slice(0, index).trim();
    const value = line.slice(index + 1).trim().replace(/^['"]|['"]$/g, "");
    if (key && !(key in process.env)) process.env[key] = value;
  }
}

loadEnvFile(path.join(projectRoot, ".env"));
loadEnvFile(path.join(repoRoot, ".env"));

const apiKey = process.env.ELEVENLABS_API_KEY;
const voiceId = process.env.ELEVENLABS_VOICE_ID || "21m00Tcm4TlvDq8ikWAM";
const modelId = process.env.ELEVENLABS_MODEL_ID || "eleven_multilingual_v2";

if (!apiKey) {
  throw new Error("ELEVENLABS_API_KEY is not set. Set it in the environment or an ignored .env file, then rerun npm run voiceover.");
}

mkdirSync(voiceoverDir, { recursive: true });

const clips = {};

for (const scene of scenes) {
  const outputName = `${scene.id}.mp3`;
  const outputPath = path.join(voiceoverDir, outputName);
  const response = await fetch(`https://api.elevenlabs.io/v1/text-to-speech/${voiceId}`, {
    method: "POST",
    headers: {
      "xi-api-key": apiKey,
      "Content-Type": "application/json",
      Accept: "audio/mpeg",
    },
    body: JSON.stringify({
      text: scene.narration,
      model_id: modelId,
      voice_settings: {
        stability: 0.54,
        similarity_boost: 0.78,
        style: 0.24,
        use_speaker_boost: true,
      },
    }),
  });

  if (!response.ok) {
    const body = await response.text().catch(() => "");
    throw new Error(`ElevenLabs request failed for scene ${scene.id}: ${response.status} ${body.slice(0, 240)}`);
  }

  const audioBuffer = Buffer.from(await response.arrayBuffer());
  writeFileSync(outputPath, audioBuffer);
  clips[scene.id] = {
    src: `voiceover/${VIDEO.mediaFolder}/${outputName}`,
    start: scene.start,
    duration: scene.duration,
  };
  console.log(`Generated ${outputName}`);
}

writeFileSync(
  manifestPath,
  `${JSON.stringify(
    {
      generated: true,
      generatedAt: new Date().toISOString(),
      provider: "elevenlabs",
      clips,
    },
    null,
    2,
  )}\n`,
);

console.log(`Voiceover manifest written to ${path.relative(projectRoot, manifestPath)}`);
