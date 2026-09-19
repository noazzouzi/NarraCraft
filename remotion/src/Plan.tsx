import React from "react";
import { AbsoluteFill, Easing, Img, interpolate, staticFile, useCurrentFrame, useVideoConfig } from "remotion";
import type { Clip } from "./types";

const EASINGS: Record<string, (t: number) => number> = {
  easeInOutCubic: Easing.bezier(0.65, 0, 0.35, 1),
  easeOutCubic: Easing.bezier(0.33, 1, 0.68, 1),
  linear: Easing.linear,
};

/** Below this, filling the frame would crop the source to a vertical slice.
 *  Archives are full of tall scans — book pages, posters, portrait plates —
 *  and they are often the only image of a given subject. */
const MIN_FILL_RATIO = 1.15;

/** One shot: a still image given a slow, authored-looking camera move.
 *
 *  The move is fully described by the timeline, so this component decides
 *  nothing about pacing — it only plays back what the pipeline computed. */
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

  const src = staticFile(clip.image);
  const tall = clip.ratio !== null && clip.ratio < MIN_FILL_RATIO;
  const transform = `translate(${x}%, ${y}%) scale(${scale}) rotate(${rotation}deg)`;

  // A tall document is shown whole, over a blurred blow-up of itself. That is
  // how a documentary presents an archive page, and it reads as a deliberate
  // choice rather than as a framing accident.
  if (tall) {
    return (
      <AbsoluteFill style={{ backgroundColor: "#0a0c10", overflow: "hidden" }}>
        <Img
          src={src}
          style={{
            width: "100%",
            height: "100%",
            objectFit: "cover",
            filter: "blur(38px) saturate(0.6) brightness(0.45)",
            transform: `scale(${1.25 * scale})`,
            transformOrigin: "center center",
          }}
        />
        <AbsoluteFill style={{ alignItems: "center", justifyContent: "center" }}>
          <Img
            src={src}
            style={{
              height: "100%",
              width: "auto",
              maxWidth: "100%",
              objectFit: "contain",
              transform,
              transformOrigin: "center center",
              boxShadow: "0 24px 90px rgba(0,0,0,0.75)",
            }}
          />
        </AbsoluteFill>
      </AbsoluteFill>
    );
  }

  return (
    <AbsoluteFill style={{ backgroundColor: "#000", overflow: "hidden" }}>
      <Img
        src={src}
        style={{
          width: "100%",
          height: "100%",
          objectFit: "cover",
          transform,
          transformOrigin: "center center",
        }}
      />
    </AbsoluteFill>
  );
};
