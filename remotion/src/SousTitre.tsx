import React from "react";
import { AbsoluteFill, interpolate, useCurrentFrame, useVideoConfig } from "remotion";

/** Subtitles sit on a soft gradient rather than a solid box: a hard black bar
 *  across a documentary frame reads as a player overlay, not as part of the
 *  film. The fade is short — long fades feel sluggish against speech. */
export const SousTitre: React.FC<{ texte: string }> = ({ texte }) => {
  const frame = useCurrentFrame();
  const { durationInFrames } = useVideoConfig();
  const fade = Math.min(4, Math.floor(durationInFrames / 3));

  const opacity = interpolate(
    frame,
    [0, fade, Math.max(durationInFrames - fade, fade + 1), durationInFrames],
    [0, 1, 1, 0],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" },
  );

  return (
    <AbsoluteFill style={{ justifyContent: "flex-end", alignItems: "center", opacity }}>
      <div
        style={{
          width: "100%",
          paddingBottom: 72,
          paddingTop: 140,
          display: "flex",
          justifyContent: "center",
          background: "linear-gradient(to top, rgba(0,0,0,0.72), rgba(0,0,0,0))",
        }}
      >
        <span
          style={{
            maxWidth: "78%",
            textAlign: "center",
            color: "#f4f6fa",
            fontFamily: "'Inter', 'Helvetica Neue', Arial, sans-serif",
            fontSize: 52,
            lineHeight: 1.28,
            fontWeight: 500,
            letterSpacing: "-0.01em",
            textShadow: "0 2px 18px rgba(0,0,0,0.55)",
          }}
        >
          {texte}
        </span>
      </div>
    </AbsoluteFill>
  );
};
