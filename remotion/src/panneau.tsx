import React from "react";
import {
  AbsoluteFill, Easing, Img, interpolate, staticFile, useCurrentFrame,
  useVideoConfig,
} from "remotion";
import { Traitement } from "./Traitement";
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

/** La scène derrière un panneau.
 *
 *  Sans elle, un panneau est un rectangle noir avec du texte : il se lit
 *  comme une diapositive posée À CÔTÉ du film, pas comme un plan du film.
 *  Ce qui le rattache au reste, c'est de garder sous lui l'image du plan
 *  qui le précède — assombrie, floutée, désaturée jusqu'à n'être qu'une
 *  texture. Le spectateur ne l'identifie pas, mais il ne voit pas non plus
 *  le fond changer de nature.
 *
 *  Le choix de l'image est fait par le pipeline, pas ici : le moteur
 *  applique, il ne décide pas. Et tout ce qui suit — opacité, flou,
 *  saturation, filet, grain, vignette — vient du template, ce qui est la
 *  condition pour qu'un documentaire criminel ne ressemble pas à un
 *  portrait d'entreprise. */
export const Scene: React.FC<{
  style: MotionStyle;
  image?: string | null;
  children: React.ReactNode;
}> = ({ style, image, children }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const scene = style.scene ?? {};
  const filet = croissance(frame, fps, 0.9, 0.1);

  // Une dérive très lente sur l'image de fond. Immobile, elle se lit comme
  // un papier peint ; en mouvement, comme un plan.
  const derive = interpolate(frame, [0, fps * 12], [0, 1], {
    extrapolateRight: "clamp",
  });
  const echelle = scene.echelle ?? 1.12;

  return (
    <AbsoluteFill style={{ backgroundColor: style.fond, overflow: "hidden" }}>
      {image && (scene.opacite ?? 0) > 0 ? (
        <Img
          src={staticFile(image)}
          style={{
            width: "100%",
            height: "100%",
            objectFit: "cover",
            opacity: scene.opacite,
            filter: `blur(${scene.flou_px ?? 26}px) saturate(${scene.saturation ?? 0.35})`,
            transform: `scale(${echelle + derive * 0.05})`,
            transformOrigin: "center center",
          }}
        />
      ) : null}

      {/* Un dégradé qui creuse le bas du cadre : les sous-titres s'y posent,
          et le texte du panneau garde son contraste en haut. */}
      <AbsoluteFill
        style={{
          background:
            `linear-gradient(to bottom, ${style.fond}00 0%, ${style.fond}00 42%, ${style.fond}cc 100%)`,
        }}
      />

      {scene.filet ? (
        <div
          style={{
            position: "absolute",
            top: 0,
            left: 0,
            height: 4,
            width: `${filet * 100}%`,
            backgroundColor: style.accent,
          }}
        />
      ) : null}

      <AbsoluteFill style={{ fontFamily: style.famille }}>{children}</AbsoluteFill>

      <Traitement grain={scene.grain} vignette={scene.vignette} />
    </AbsoluteFill>
  );
};
