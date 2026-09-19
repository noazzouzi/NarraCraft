import React from "react";
import { AbsoluteFill, Easing, interpolate, useCurrentFrame, useVideoConfig } from "remotion";
import type { MotionStyle } from "./types";

const EASE_OUT = Easing.bezier(0.16, 1, 0.3, 1);

const FAMILLES: Record<string, string> = {
  // A monospaced face reads as "typed" without needing a font file: every
  // system has one, and the even spacing is the whole signal.
  dactylographie: "'Courier New', Courier, monospace",
  officiel: "Georgia, 'Times New Roman', serif",
};

/** An archive document, with one passage picked out.
 *
 *  On a judicial or administrative subject this is often the strongest shot
 *  available: the wording of a ruling is the evidence, and no photograph of
 *  a courthouse says what one sentence of the judgment says.
 *
 *  The highlighter sweep exists because a viewer cannot read a full page in
 *  eight seconds. It tells them where to look before they have finished
 *  deciding for themselves. */
export const Document: React.FC<{
  entete?: string;
  reference?: string;
  lignes: string[];
  surligne?: number;
  ecriture?: string;
  style: MotionStyle;
}> = ({ entete, reference, lignes, surligne, ecriture, style }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const famille = FAMILLES[ecriture ?? "dactylographie"] ?? FAMILLES.dactylographie;
  const papier = "#efe9dc";
  const encre = "#1d1c1a";

  const pose = interpolate(frame, [0, fps * 0.8], [0, 1], {
    easing: EASE_OUT, extrapolateLeft: "clamp", extrapolateRight: "clamp",
  });

  // A slow drift downwards, the way a document is actually filmed. Small
  // enough that it never becomes the subject.
  const derive = interpolate(frame, [0, fps * 12], [0, -26], {
    extrapolateRight: "clamp",
  });

  // The sweep starts once the page has settled, so the eye has somewhere to
  // land first.
  const balayage = interpolate(
    frame, [fps * 1.2, fps * 2.1], [0, 1],
    { easing: EASE_OUT, extrapolateLeft: "clamp", extrapolateRight: "clamp" },
  );

  return (
    <AbsoluteFill
      style={{
        backgroundColor: style.fond,
        alignItems: "center",
        justifyContent: "center",
        overflow: "hidden",
      }}
    >
      <div
        style={{
          width: 1140,
          backgroundColor: papier,
          // Aged paper: warmer towards the edges, never uniform.
          backgroundImage:
            "radial-gradient(ellipse at 50% 40%, rgba(255,255,255,0.55), rgba(196,183,156,0.30))",
          padding: "70px 92px 86px",
          boxShadow: "0 46px 130px rgba(0,0,0,0.7)",
          opacity: pose,
          transform: `translateY(${(1 - pose) * 34 + derive}px) rotate(${(1 - pose) * -0.5}deg)`,
          fontFamily: famille,
          color: encre,
        }}
      >
        {entete ? (
          <div
            style={{
              fontSize: 27,
              letterSpacing: "0.22em",
              textTransform: "uppercase",
              textAlign: "center",
              paddingBottom: 20,
              borderBottom: `2px solid ${encre}`,
            }}
          >
            {entete}
          </div>
        ) : null}

        {reference ? (
          <div style={{ fontSize: 25, marginTop: 26, opacity: 0.72 }}>
            {reference}
          </div>
        ) : null}

        <div style={{ marginTop: entete || reference ? 40 : 0 }}>
          {lignes.map((ligne, index) => {
            const vedette = index === surligne;
            return (
              <div key={index} style={{ position: "relative", marginBottom: 26 }}>
                {vedette ? (
                  <div
                    style={{
                      position: "absolute",
                      left: -10,
                      top: -4,
                      bottom: -4,
                      width: `${balayage * 100}%`,
                      maxWidth: "calc(100% + 20px)",
                      backgroundColor: style.accent,
                      opacity: 0.32,
                    }}
                  />
                ) : null}
                <div
                  style={{
                    position: "relative",
                    fontSize: 32,
                    lineHeight: 1.62,
                    opacity: vedette ? 1 : 0.78,
                    fontWeight: vedette ? 700 : 400,
                  }}
                >
                  {ligne}
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </AbsoluteFill>
  );
};
