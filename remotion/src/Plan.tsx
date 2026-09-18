import React from "react";
import { AbsoluteFill, Easing, Img, interpolate, staticFile, useCurrentFrame, useVideoConfig } from "remotion";
import type { Clip } from "./types";

const EASINGS: Record<string, (t: number) => number> = {
  easeInOutCubic: Easing.bezier(0.65, 0, 0.35, 1),
  easeOutCubic: Easing.bezier(0.33, 1, 0.68, 1),
  linear: Easing.linear,
};

/** One shot: a still image given a slow, authored-looking camera move.
 *
 *  The move is fully described by the timeline, so this component decides
 *  nothing — it only plays back what the pipeline computed. */
export const Plan: React.FC<{ clip: Clip }> = ({ clip }) => {
  const frame = useCurrentFrame();
  const { durationInFrames } = useVideoConfig();
  const { debut, fin, rotation_deg, easing } = clip.mouvement;

  const ease = EASINGS[easing] ?? EASINGS.easeInOutCubic;
  const at = (from: number, to: number) =>
    interpolate(frame, [0, Math.max(durationInFrames - 1, 1)], [from, to], {
      easing: ease,
      extrapolateLeft: "clamp",
      extrapolateRight: "clamp",
    });

  const scale = at(debut.scale, fin.scale);
  const x = at(debut.x, fin.x) * 100;
  const y = at(debut.y, fin.y) * 100;
  const rotation = at(0, rotation_deg);

  if (!clip.image) {
    return (
      <AbsoluteFill style={{ backgroundColor: "#12151b", alignItems: "center", justifyContent: "center" }}>
        <div style={{ color: "#5b6373", fontSize: 40, fontFamily: "sans-serif" }}>
          {clip.id} · {clip.type}
        </div>
      </AbsoluteFill>
    );
  }

  return (
    <AbsoluteFill style={{ backgroundColor: "#000", overflow: "hidden" }}>
      <Img
        src={staticFile(clip.image)}
        style={{
          width: "100%",
          height: "100%",
          objectFit: "cover",
          transform: `translate(${x}%, ${y}%) scale(${scale}) rotate(${rotation}deg)`,
          transformOrigin: "center center",
        }}
      />
    </AbsoluteFill>
  );
};
