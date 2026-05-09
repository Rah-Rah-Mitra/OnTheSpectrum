# OnTheSpectrum Remotion Demo

This sidecar project renders the 2-minute OnTheSpectrum application demo. It does not change the application runtime.

## Workflow

```powershell
cd D:\OnTheSpectrum\video-demo
npm install
npm run voiceover
npm run capture
npm run render
```

`npm run voiceover` reads `ELEVENLABS_API_KEY` from the environment, `video-demo/.env`, or the repository `.env`. The key is never written to source files or shown in the video.

`npm run capture` starts the app with `npm run dev`, captures deterministic browser screenshots for the generator, viewer, world creator, Agent Handoff tabs, saved world navigation, and World 3D preview, then writes a capture manifest used by the composition. It demonstrates the Agent Handoff Generate tab but does not click **Generate World**.

If captures or voiceover are not generated yet, the Remotion composition still renders using built-in animated panels and captions.

## Output

- Composition ID: `OnTheSpectrumFullDemo`
- Duration: 120 seconds
- Size: 1920 x 1080
- FPS: 30
- Main output: `out/onthe-spectrum-full-demo.mp4`
