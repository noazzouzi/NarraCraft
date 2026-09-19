import React from "react";
import { AbsoluteFill, Easing, interpolate } from "remotion";
import type { MotionStyle } from "./types";

/** Le socle commun des panneaux graphiques.
 *
 *  Il vivait dans Motion.tsx tant qu'il n'y avait que trois panneaux. À
 *  partir du moment où d'autres fichiers en ont besoin, le laisser là
 *  imposait un import circulaire — Motion connaît les panneaux, les
 *  panneaux connaîtraient Motion. */

export const EASE_OUT = Easing.bezier(0.16, 1, 0.3, 1);

/** Apparition en cascade : l'élément `index` démarre `cascade` secondes
 *  après le précédent. Renvoie 0 → 1 et le décalage vertical qui va avec.
 *
 *  Tout qui apparaît d'un coup se lit comme une diapositive. Un par un,
 *  l'œil suit la narration, qui arrive au même rythme.
 *
 *  Une fonction, pas un hook : les panneaux révèlent leurs éléments dans un
 *  `.map()`, et appeler un hook là-dedans enfreint les règles des hooks. */
export function reveal(
  frame: number, fps: number, index: number, cascade: number, delay = 0,
) {
  const start = (delay + index * cascade) * fps;
  const progress = interpolate(frame, [start, start + fps * 0.5], [0, 1], {
    easing: EASE_OUT,
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  return { progress, lift: (1 - progress) * 18 };
}

/** Progression continue de 0 à 1 sur une durée, sans cascade. Pour ce qui
 *  se remplit plutôt que ce qui apparaît : une barre, un trait, une part. */
export function croissance(
  frame: number, fps: number, duree_s: number, delay_s = 0,
) {
  return interpolate(
    frame, [delay_s * fps, (delay_s + duree_s) * fps], [0, 1],
    { easing: EASE_OUT, extrapolateLeft: "clamp", extrapolateRight: "clamp" },
  );
}

export const Fond: React.FC<{
  style: MotionStyle;
  titre?: string;
  children: React.ReactNode;
}> = ({ style, titre, children }) => (
  <AbsoluteFill
    style={{
      backgroundColor: style.fond,
      fontFamily: style.famille,
      padding: "0 140px",
      justifyContent: "center",
    }}
  >
    {titre ? (
      <div
        style={{
          color: style.attenue,
          fontSize: 30,
          letterSpacing: "0.18em",
          textTransform: "uppercase",
          marginBottom: 56,
        }}
      >
        {titre}
      </div>
    ) : null}
    {children}
  </AbsoluteFill>
);
