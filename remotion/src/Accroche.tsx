import React from "react";
import { AbsoluteFill, Easing, interpolate, useCurrentFrame, useVideoConfig } from "remotion";
import type { MotionStyle, Typographie } from "./types";

const EASE_OUT = Easing.bezier(0.16, 1, 0.3, 1);

/** A sentence burned over a shot, word by word.
 *
 *  This is the hook, and it is not a subtitle: it appears while the voice is
 *  saying something else, it is set far larger, and it sits in the upper
 *  third where the eye lands first. A viewer decides in four seconds whether
 *  to keep watching, and reading is faster than listening — so the sentence
 *  that earns those four seconds has to be on screen, not only in the audio.
 *
 *  The words arrive one after another rather than all at once. A full block
 *  of text appearing at frame zero is read before the first word is spoken
 *  and then has nothing left to give; staggered, it holds the eye for its
 *  whole duration. */
/** De quoi écrire l'accroche sur une surface claire.
 *
 *  Le voile sombre par défaut creuse le haut d'une photographie, et c'est ce
 *  qui rend le texte lisible dessus. Posé sur une planche de collage en
 *  papier crème, le même voile est une bande noire en travers du papier. Les
 *  trois couleurs viennent alors du template de la planche — le moteur
 *  choisit de s'en servir, il n'en invente aucune. */
export type Surface = { texte: string; accent: string; voile: string };

export const Accroche: React.FC<{
  texte: string;
  typographie: Typographie;
  style: MotionStyle;
  surface?: Surface;
}> = ({ texte, typographie, style, surface }) => {
  const frame = useCurrentFrame();
  const { durationInFrames, fps } = useVideoConfig();

  // Codée en dur jusqu'ici, ce qui allait tant que l'accroche se posait sur
  // une photographie plein cadre. Sur une planche de collage, 104 px prennent
  // la moitié de la hauteur et poussent la planche hors du cadre : c'est donc
  // une valeur de template, comme tout le reste de la direction artistique.
  const taille = typographie.accroche ?? 104;
  const mots = texte.split(/\s+/).filter(Boolean);
  // The whole sentence lands within the first second and a half, whatever its
  // length: a hook that is still assembling itself at four seconds has lost.
  const pas = mots.length > 1 ? (fps * 1.2) / mots.length : 0;

  const sortie = interpolate(
    frame,
    [Math.max(durationInFrames - fps * 0.4, 1), durationInFrames],
    [1, 0],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" },
  );

  return (
    <AbsoluteFill
      style={{
        alignItems: "center",
        justifyContent: "flex-start",
        paddingTop: "16%",
        opacity: sortie,
        // A dark wash only under the text. Dimming the whole frame would
        // hide the face the sentence is talking about.
        background: surface
          ? `linear-gradient(to bottom, ${surface.voile} 0%, ${surface.voile} 40%, transparent 78%)`
          : "linear-gradient(to bottom, rgba(0,0,0,0.78) 0%, rgba(0,0,0,0.55) 46%, rgba(0,0,0,0) 72%)",
      }}
    >
      <div
        style={{
          maxWidth: "80%",
          textAlign: "center",
          fontFamily: typographie.famille,
          fontSize: taille,
          fontWeight: 800,
          lineHeight: 1.08,
          letterSpacing: "-0.025em",
          color: surface?.texte ?? style.texte,
          textShadow: surface ? "none" : "0 6px 42px rgba(0,0,0,0.85)",
          textWrap: "balance",
        }}
      >
        {mots.map((mot, index) => {
          const depart = index * pas;
          const pose = interpolate(frame, [depart, depart + fps * 0.34], [0, 1], {
            easing: EASE_OUT,
            extrapolateLeft: "clamp",
            extrapolateRight: "clamp",
          });
          return (
            <span
              key={index}
              style={{
                display: "inline-block",
                marginRight: "0.26em",
                opacity: pose,
                transform: `translateY(${(1 - pose) * taille * 0.25}px)`,
              }}
            >
              {mot}
            </span>
          );
        })}
      </div>

      {/* A rule that draws itself under the sentence once it is complete.
          It is the only ornament, and it says "this is a title card". */}
      <div
        style={{
          marginTop: taille * 0.37,
          height: Math.max(Math.round(taille * 0.048), 3),
          width: interpolate(
            frame, [fps * 1.2, fps * 2.0], [0, 240],
            { easing: EASE_OUT, extrapolateLeft: "clamp", extrapolateRight: "clamp" },
          ),
          backgroundColor: surface?.accent ?? style.accent,
        }}
      />
    </AbsoluteFill>
  );
};
