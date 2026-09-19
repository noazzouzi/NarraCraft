import React from "react";
import { AbsoluteFill, interpolate, useCurrentFrame, useVideoConfig } from "remotion";
import type { Palette, Typographie } from "./types";

/** Subtitles sit on a soft gradient rather than a solid box: a hard black bar
 *  across a documentary frame reads as a player overlay, not as part of the
 *  film. The fade is short — long fades feel sluggish against speech.
 *
 *  Every colour and every metric comes from the template. This component
 *  chooses nothing. */
export const SousTitre: React.FC<{
  texte: string;
  palette: Palette;
  typographie: Typographie;
}> = ({ texte, palette, typographie }) => {
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
          background: `linear-gradient(to top, ${palette.voile}, rgba(0,0,0,0))`,
        }}
      >
        <span
          style={{
            maxWidth: "78%",
            textAlign: "center",
            color: palette.sous_titre,
            fontFamily: typographie.famille,
            fontSize: typographie.taille,
            lineHeight: typographie.interligne,
            fontWeight: typographie.graisse,
            letterSpacing: typographie.interlettrage,
            textShadow: `0 2px 18px ${palette.ombre}`,
          }}
        >
          {texte}
        </span>
      </div>
    </AbsoluteFill>
  );
};
