import React from "react";
import { AbsoluteFill, Easing, interpolate, useCurrentFrame, useVideoConfig } from "remotion";
import type { MotionStyle } from "./types";

const EASE_OUT = Easing.bezier(0.16, 1, 0.3, 1);

/** Filler lines. Real body text would be unreadable at this size and would
 *  invite the viewer to try; grey rules read immediately as "newspaper" and
 *  keep the eye on the headline, which is the only thing that matters. */
const Colonne: React.FC<{ lignes: number; couleur: string; opacite: number }> = ({
  lignes, couleur, opacite,
}) => (
  <div style={{ flex: 1, display: "flex", flexDirection: "column", gap: 9 }}>
    {Array.from({ length: lignes }, (_, i) => (
      <div
        key={i}
        style={{
          height: 7,
          backgroundColor: couleur,
          opacity: opacite,
          // A short last line per paragraph is what makes it read as prose.
          width: i % 7 === 6 ? "62%" : "100%",
        }}
      />
    ))}
  </div>
);

/** A front page, built rather than photographed.
 *
 *  Press front pages are under copyright and almost never available freely,
 *  so a documentary that needs "the paper the next morning" either pays for
 *  it or builds it. This builds it, and says so by construction: it carries
 *  the paper's name and date as stated facts, never a facsimile. */
export const Journal: React.FC<{
  journal: string;
  date: string;
  titre: string;
  chapeau?: string;
  style: MotionStyle;
}> = ({ journal, date, titre, chapeau, style }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  // The page arrives, then the headline lands on it.
  const page = interpolate(frame, [0, fps * 0.7], [0, 1], {
    easing: EASE_OUT, extrapolateLeft: "clamp", extrapolateRight: "clamp",
  });
  const gros = interpolate(
    frame, [fps * 0.55, fps * 1.25], [0, 1],
    { easing: EASE_OUT, extrapolateLeft: "clamp", extrapolateRight: "clamp" },
  );

  const encre = "#14161a";
  const papier = "#e8e3d8";

  return (
    <AbsoluteFill
      style={{
        backgroundColor: style.fond,
        fontFamily: style.famille,
        alignItems: "center",
        justifyContent: "center",
      }}
    >
      <div
        style={{
          width: 1180,
          backgroundColor: papier,
          padding: "54px 64px 64px",
          boxShadow: "0 40px 120px rgba(0,0,0,0.65)",
          opacity: page,
          transform: `translateY(${(1 - page) * 26}px) rotate(${(1 - page) * -0.6}deg)`,
        }}
      >
        <div
          style={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "baseline",
            borderBottom: `3px solid ${encre}`,
            paddingBottom: 18,
          }}
        >
          <div style={{ fontSize: 46, fontWeight: 800, letterSpacing: "-0.02em", color: encre }}>
            {journal}
          </div>
          <div style={{ fontSize: 24, color: "#5b5b55", letterSpacing: "0.06em" }}>
            {date}
          </div>
        </div>

        <div
          style={{
            fontSize: 82,
            lineHeight: 1.08,
            fontWeight: 800,
            color: encre,
            marginTop: 40,
            letterSpacing: "-0.02em",
            opacity: gros,
            transform: `translateY(${(1 - gros) * 14}px)`,
          }}
        >
          {titre}
        </div>

        {chapeau ? (
          <div
            style={{
              fontSize: 30,
              lineHeight: 1.45,
              color: "#3d3f44",
              marginTop: 26,
              opacity: gros,
            }}
          >
            {chapeau}
          </div>
        ) : null}

        <div style={{ display: "flex", gap: 42, marginTop: 44 }}>
          <Colonne lignes={13} couleur={encre} opacite={0.24 * page} />
          <Colonne lignes={13} couleur={encre} opacite={0.24 * page} />
          <Colonne lignes={13} couleur={encre} opacite={0.24 * page} />
        </div>
      </div>
    </AbsoluteFill>
  );
};
