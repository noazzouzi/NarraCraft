import React from "react";
import {
  AbsoluteFill,
  interpolate,
  interpolateColors,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import type { MotSousTitre, Palette, SurlignageStyle, Typographie } from "./types";

/** La chaleur d'un mot : 0 quand la voix ne l'a pas encore dit, 1 pendant,
 *  et retour à 0 après.
 *
 *  Le fondu est la raison d'être de cette fonction. Une bascule sèche d'un
 *  mot au suivant clignote ; mesuré chez Frontier, le surlignage passe de
 *  l'un à l'autre en deux à trois images. Comme les fenêtres sont
 *  contiguës — un mot reste surligné jusqu'à ce que le suivant commence —
 *  la descente de l'un et la montée de l'autre se chevauchent exactement
 *  sur la frontière, ce qui est l'effet recherché. */
const chaleur = (frame: number, debut: number, fin: number, fondu: number) => {
  const f = Math.max(fondu, 1);
  // `interpolate` exige une plage strictement croissante. Les fenêtres ont
  // déjà un plancher côté Python, mais une plage est moins chère à garantir
  // ici qu'un rendu qui casse à la millième image.
  const haut = Math.max(fin, debut + 1);
  return interpolate(
    frame,
    [debut - f, debut, haut, haut + f],
    [0, 1, 1, 0],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" },
  );
};

/** Subtitles sit on a soft gradient rather than a solid box: a hard black bar
 *  across a documentary frame reads as a player overlay, not as part of the
 *  film. The fade is short — long fades feel sluggish against speech.
 *
 *  Every colour and every metric comes from the template. This component
 *  chooses nothing — pas même la fenêtre de chaque mot, qui est calculée en
 *  Python comme tout le reste du temps. */
export const SousTitre: React.FC<{
  texte: string;
  mots?: MotSousTitre[];
  depuis: number;
  palette: Palette;
  typographie: Typographie;
  surlignage?: SurlignageStyle;
  ligneDeBasePct?: number;
  voile?: boolean;
}> = ({
  texte,
  mots,
  depuis,
  palette,
  typographie,
  surlignage,
  ligneDeBasePct = 90.8,
  voile = true,
}) => {
  const frame = useCurrentFrame();
  const { durationInFrames, height } = useVideoConfig();
  const fade = Math.min(4, Math.floor(durationInFrames / 3));

  const opacity = interpolate(
    frame,
    [0, fade, Math.max(durationInFrames - fade, fade + 1), durationInFrames],
    [0, 1, 1, 0],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" },
  );

  const blanc = palette.sous_titre;
  const actif = surlignage?.actif && mots && mots.length > 0;
  const dore = surlignage?.couleur ?? blanc;
  const fondu = surlignage?.fondu_frames ?? 3;

  const style: React.CSSProperties = {
    maxWidth: "78%",
    textAlign: "center",
    color: blanc,
    fontFamily: typographie.famille,
    fontSize: typographie.taille,
    lineHeight: typographie.interligne,
    fontWeight: typographie.graisse,
    letterSpacing: typographie.interlettrage,
    textShadow: `0 2px 18px ${palette.ombre}`,
  };

  return (
    <AbsoluteFill style={{ justifyContent: "flex-end", alignItems: "center", opacity }}>
      <div
        style={{
          width: "100%",
          // La ligne de base est un pourcentage du cadre, pas un nombre de
          // pixels : le même réglage tient en 1080p et en 720p.
          paddingBottom: (height * (100 - ligneDeBasePct)) / 100,
          paddingTop: 140,
          display: "flex",
          justifyContent: "center",
          background: voile
            ? `linear-gradient(to top, ${palette.voile}, rgba(0,0,0,0))`
            : undefined,
        }}
      >
        <span style={style}>
          {actif
            ? mots!.map((mot, index) => (
                <span
                  key={index}
                  style={{
                    color: interpolateColors(
                      chaleur(
                        frame + depuis,
                        mot.debut_frame,
                        mot.fin_frame,
                        fondu,
                      ),
                      [0, 1],
                      [blanc, dore],
                    ),
                  }}
                >
                  {index > 0 ? " " : ""}
                  {mot.tx}
                </span>
              ))
            : texte}
        </span>
      </div>
    </AbsoluteFill>
  );
};
