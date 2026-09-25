import React from "react";
import { Composition } from "remotion";
import { Documentaire } from "./Documentaire";
import type { Timeline } from "./types";
import vide from "./timeline-vide.json";

/** Dimensions, fps and duration all come from the timeline passed in with
 *  --props, so changing the config never means editing this file. */
export const Root: React.FC = () => (
  <Composition
    id="Documentaire"
    component={Documentaire}
    defaultProps={vide as unknown as Timeline}
    // Placeholder metadata, immediately overridden by calculateMetadata.
    durationInFrames={60}
    fps={30}
    width={1920}
    height={1080}
    calculateMetadata={({ props }) => ({
      durationInFrames: Math.max(props.duree_frames ?? 60, 1),
      fps: props.fps ?? 30,
      width: props.width ?? 1920,
      height: props.height ?? 1080,
    })}
  />
);
