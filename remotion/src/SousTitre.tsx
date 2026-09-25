import React from "react";
import {
  AbsoluteFill,
  interpolate,
  interpolateColors,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import type {
  MotSousTitre,
  Palette,
  SousTitreStyle,
  SurlignageStyle,
  Typographie,
} from "./types";

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

/** Quatre familles de sous-titres, et rien d'autre.
 *
 *  La liste est close et connue du pipeline (`timeline.FAMILLES_SOUS_TITRES`),
 *  qui refuse un nom inconnu avant le rendu. Un template en choisit une,
 *  un projet peut la changer, l'interface la propose — personne n'en
 *  invente : c'est la même règle que les sept mouvements de caméra et les
 *  treize panneaux.
 *
 *  Toutes les couleurs et toutes les mesures viennent du template. Ce
 *  composant ne choisit rien, pas même la fenêtre de chaque mot, qui est
 *  calculée en Python comme tout le reste du temps. */
export const SousTitre: React.FC<{
  texte: string;
  mots?: MotSousTitre[];
  depuis: number;
  palette: Palette;
  typographie: Typographie;
  surlignage?: SurlignageStyle;
  reglages?: SousTitreStyle;
}> = ({ texte, mots, depuis, palette, typographie, surlignage, reglages }) => {
  const frame = useCurrentFrame();
  const { durationInFrames, height } = useVideoConfig();
  const fade = Math.min(4, Math.floor(durationInFrames / 3));

  const famille = reglages?.style ?? "surligne";
  const position = reglages?.position ?? "bas";
  const ligneDeBase = reglages?.ligne_de_base_pct ?? 90.8;
  const voile = reglages?.voile ?? true;

  // Une couleur vide retombe sur la palette : c'est ce qui fait qu'un
  // template repeint ses sous-titres sans avoir à les régler.
  const texteCouleur = reglages?.couleur_texte || palette.sous_titre;
  const motCouleur = reglages?.couleur_mot || surlignage?.couleur || texteCouleur;
  const fondCouleur = reglages?.couleur_fond || palette.voile;
  // Ce que le mot devient quand il est posé SUR le marqueur. Le fond du
  // film fait une encre correcte : il contraste avec tout ce que le
  // template met dessus, puisque c'est ce sur quoi le template travaille.
  const encreMarqueur = reglages?.couleur_fond || palette.fond;

  const opacity = interpolate(
    frame,
    [0, fade, Math.max(durationInFrames - fade, fade + 1), durationInFrames],
    [0, 1, 1, 0],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" },
  );

  const parMot = surlignage?.actif && mots && mots.length > 0;
  const fondu = surlignage?.fondu_frames ?? 3;
  const casse = reglages?.majuscules ? ("uppercase" as const) : undefined;

  const corps: React.CSSProperties = {
    maxWidth: "78%",
    textAlign: "center",
    color: texteCouleur,
    fontFamily: typographie.famille,
    // La famille « mot » n'affiche qu'un mot : il peut donc être bien plus
    // grand sans déborder, et c'est tout l'intérêt du format.
    fontSize: famille === "mot" ? typographie.taille * 1.8 : typographie.taille,
    lineHeight: typographie.interligne,
    fontWeight: typographie.graisse,
    letterSpacing: typographie.interlettrage,
    textTransform: casse,
    textShadow: famille === "bloc" ? undefined : `0 2px 18px ${palette.ombre}`,
  };

  /** Le mot que la voix dit maintenant. Utilisé par la famille « mot ». */
  const courant = parMot
    ? mots!.reduce((retenu, mot) =>
        mot.debut_frame <= frame + depuis ? mot : retenu, mots![0])
    : null;

  const contenu = () => {
    if (famille === "mot") {
      return <span style={corps}>{courant?.tx ?? texte.split(" ")[0]}</span>;
    }
    if (famille === "bloc") {
      return (
        <span
          style={{
            ...corps,
            backgroundColor: fondCouleur,
            padding: "0.18em 0.6em",
            borderRadius: 6,
            boxDecorationBreak: "clone",
            WebkitBoxDecorationBreak: "clone",
          }}
        >
          {parMot ? mots!.map((mot, index) => (
            <span
              key={index}
              style={{
                color: interpolateColors(
                  chaleur(frame + depuis, mot.debut_frame, mot.fin_frame, fondu),
                  [0, 1],
                  [texteCouleur, motCouleur],
                ),
              }}
            >
              {index > 0 ? " " : ""}
              {mot.tx}
            </span>
          )) : texte}
        </span>
      );
    }
    // `surligne` et `marqueur` partagent la même mise en page : toute la
    // phrase est là, et seul change ce que reçoit le mot dit — une couleur
    // de texte, ou un bloc derrière lui.
    return (
      <span style={corps}>
        {parMot
          ? mots!.map((mot, index) => {
              const chaud = chaleur(
                frame + depuis, mot.debut_frame, mot.fin_frame, fondu);
              const marqueur = famille === "marqueur";
              return (
                <span key={index}>
                  {index > 0 ? " " : ""}
                  <span
                    style={
                      marqueur
                        ? {
                            // Le bloc arrive et repart avec le mot, en
                            // fondu comme la couleur de `surligne` : une
                            // bascule sèche clignoterait.
                            backgroundColor: interpolateColors(
                              chaud, [0, 1], ["rgba(0,0,0,0)", motCouleur]),
                            boxShadow: `0 0 0 0.14em ${interpolateColors(
                              chaud, [0, 1], ["rgba(0,0,0,0)", motCouleur])}`,
                            borderRadius: 3,
                            // De l'encre sur le marqueur. Du texte clair
                            // sur un aplat clair ne se lit pas.
                            color: interpolateColors(
                              chaud, [0, 1], [texteCouleur, encreMarqueur]),
                          }
                        : {
                            color: interpolateColors(
                              chaud, [0, 1], [texteCouleur, motCouleur]),
                          }
                    }
                  >
                    {mot.tx}
                  </span>
                </span>
              );
            })
          : texte}
      </span>
    );
  };

  return (
    <AbsoluteFill
      style={{
        justifyContent: position === "centre" ? "center" : "flex-end",
        alignItems: "center",
        opacity,
      }}
    >
      <div
        style={{
          width: "100%",
          // La ligne de base est un pourcentage du cadre, pas un nombre de
          // pixels : le même réglage tient en 1080p et en 720p.
          paddingBottom:
            position === "centre" ? 0 : (height * (100 - ligneDeBase)) / 100,
          paddingTop: position === "centre" ? 0 : 140,
          display: "flex",
          justifyContent: "center",
          // Le voile n'a de sens que sous un texte posé sur l'image. La
          // famille `bloc` porte déjà son fond, le voile ferait double.
          background:
            voile && position === "bas" && famille !== "bloc"
              ? `linear-gradient(to top, ${palette.voile}, rgba(0,0,0,0))`
              : undefined,
        }}
      >
        {contenu()}
      </div>
    </AbsoluteFill>
  );
};
