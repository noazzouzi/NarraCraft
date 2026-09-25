import React from "react";
import { AbsoluteFill, random, useCurrentFrame, useVideoConfig } from "remotion";

const NOISE =
  "data:image/svg+xml;utf8," +
  encodeURIComponent(
    `<svg xmlns="http://www.w3.org/2000/svg" width="140" height="140">
       <filter id="n"><feTurbulence type="fractalNoise" baseFrequency="0.9" numOctaves="2"/></filter>
       <rect width="140" height="140" filter="url(#n)" opacity="0.6"/>
     </svg>`,
  );

/** Grain and vignette. Both are deliberately subtle: the point is to stop the
 *  image reading as a flat digital still, not to look like a filter.
 *
 *  Performance matters here — this layer covers every pixel of every frame.
 *  Two decisions keep it close to free:
 *
 *  1. The grain moves by `transform`, not `background-position`. A transform
 *     is composited on the GPU; a background shift repaints the whole surface.
 *  2. It steps at 12 fps rather than every frame. That is how film grain is
 *     actually emulated, and it cuts the number of distinct paints by more
 *     than half at 30 fps. */
export const Traitement: React.FC<{ grain?: number; vignette?: number }> = ({
  grain = 0,
  vignette = 0,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const step = Math.max(1, Math.round(fps / 12));
  const tick = Math.floor(frame / step);
  const dx = (random(`gx${tick}`) - 0.5) * 140;
  const dy = (random(`gy${tick}`) - 0.5) * 140;

  return (
    <AbsoluteFill style={{ pointerEvents: "none" }}>
      {vignette > 0 && (
        <AbsoluteFill
          style={{
            background: `radial-gradient(ellipse at center, rgba(0,0,0,0) 45%, rgba(0,0,0,${vignette}) 100%)`,
          }}
        />
      )}
      {grain > 0 && (
        <AbsoluteFill style={{ overflow: "hidden" }}>
          <div
            style={{
              position: "absolute",
              inset: "-160px",
              backgroundImage: `url("${NOISE}")`,
              backgroundRepeat: "repeat",
              opacity: grain * 1.6,
              transform: `translate3d(${dx}px, ${dy}px, 0)`,
              willChange: "transform",
            }}
          />
        </AbsoluteFill>
      )}
    </AbsoluteFill>
  );
};
