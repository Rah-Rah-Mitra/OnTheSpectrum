import React from "react";
import { Composition } from "remotion";
import { OnTheSpectrumFullDemo } from "./OnTheSpectrumFullDemo.jsx";
import { VIDEO } from "./demoData.js";

export const RemotionRoot = () => {
  return (
    <Composition
      id={VIDEO.compositionId}
      component={OnTheSpectrumFullDemo}
      durationInFrames={VIDEO.durationSeconds * VIDEO.fps}
      fps={VIDEO.fps}
      width={VIDEO.width}
      height={VIDEO.height}
      defaultProps={{
        renderMode: "auto",
      }}
    />
  );
};
