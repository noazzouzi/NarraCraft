import React from "react";
import { AbsoluteFill, random, useCurrentFrame } from "remotion";

const NOISE =
  "data:image/svg+xml;utf8," +
  encodeURIComponent(
    `<svg xmlns="http://www.w3.org/2000/svg" width="180" height="180">
       <filter id="n"><feTurbulence type="fractalNoise" baseFrequency="0.85" numOctaves="3"/></filter>
       <rect width="180" height="180" filter="url(#n)" opacity="0.55"/>
     </svg>`,
  );

/** Grain and vignette. Both are deliberately subtle: the point is to stop the
 *  image reading as a flat, freshly-rendered digital still, not to look like a
 *  filter. The grain pattern is re-seeded every frame — a static grain looks
 *  like a dirty lens rather than film. */
export const Traitement: React.FC<{ grain?: number; vignette?: number }> = ({
  grain = 0,
  vignette = 0,
}) => {
  const frame = useCurrentFrame();
  const offsetX = Math.floor(random(`gx${frame}`) * 180);
  const offsetY = Math.floor(random(`gy${frame}`) * 180);

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
        <AbsoluteFill
          style={{
            backgroundImage: `url("${NOISE}")`,
            backgroundPosition: `${offsetX}px ${offsetY}px`,
            opacity: grain,
            mixBlendMode: "overlay",
          }}
        />
      )}
    </AbsoluteFill>
  );
};
