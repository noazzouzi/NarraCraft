import React from "react";
import { AbsoluteFill, Audio, Sequence, interpolate, staticFile } from "remotion";
import { Accroche } from "./Accroche";
import { Generique } from "./Generique";
import { Plan } from "./Plan";
import { SousTitre } from "./SousTitre";
import type { Timeline } from "./types";

/** Le lit sonore et sa courbe de volume.
 *
 *  Sorti en composant parce que la courbe n'a pas toujours le même nombre
 *  de points : une entrée nulle en supprime un, et `interpolate` exige une
 *  plage strictement croissante — `[0, 0, …]` lève une erreur au premier
 *  frame rendu. */
const MusiqueDeFond: React.FC<{
  musique: NonNullable<Timeline["musique"]>;
  duree: number;
}> = ({ musique, duree }) => {
  const entree = Math.max(musique.fondu_entree_frames, 0);
  const sortie = Math.max(duree - musique.fondu_sortie_frames, entree + 1);
  const bornes = entree > 0 ? [0, entree, sortie, duree] : [0, sortie, duree];
  const niveaux = entree > 0 ? [0, 1, 1, 0] : [1, 1, 0];

  return (
    <Audio
      src={staticFile(musique.fichier)}
      loop
      volume={(frame) =>
        musique.gain *
        interpolate(frame, bornes, niveaux, {
          extrapolateLeft: "clamp",
          extrapolateRight: "clamp",
        })
      }
    />
  );
};

/** Plays back 06-timeline.json. It computes nothing: every cut, every camera
 *  move and every subtitle window was decided by the Python pipeline from the
 *  real word timings. See CLAUDE.md. */
export const Documentaire: React.FC<Timeline> = (timeline) => {
  const { clips, sons, musique, sous_titres, style, audio, duree_frames } =
    timeline;
  const generique = timeline.generique;
  const { palette, typographie, traitement, motion, transitions } = style;

  return (
    <AbsoluteFill style={{ backgroundColor: palette.fond }}>
      {audio ? <Audio src={staticFile(audio)} /> : null}

      {/* Le lit sonore, bouclé sur toute la durée. L'entrée et la sortie
          sont réglées séparément : une entrée nulle met le lit à plein
          niveau dès la première image — les quinze premières secondes
          décident du reste, leur retirer la musique n'a pas de sens — et
          la sortie reste longue, parce qu'une coupe nette à la fin
          s'entend comme une panne. */}
      {musique ? (
        <MusiqueDeFond musique={musique} duree={duree_frames} />
      ) : null}

      {/* Transition sounds. Each one starts slightly before its cut — the
          ear announces to the eye what is coming — so they are mounted at
          the composition level rather than inside a clip's sequence, whose
          window would clip the lead-in off. */}
      {(sons ?? []).map((son, index) => (
        <Sequence
          key={`son-${index}`}
          from={son.debut_frame}
          name={`♪ ${son.fichier.split("/").pop()}`}
        >
          <Audio src={staticFile(son.fichier)} volume={son.gain} />
        </Sequence>
      ))}

      {clips.map((clip) => (
        <Sequence
          key={clip.id}
          from={clip.debut_frame}
          durationInFrames={clip.duree_frames}
          name={`${clip.id} ${clip.beat}`}
        >
          <Plan
            clip={clip}
            palette={palette}
            motionStyle={motion}
            collageStyle={style.collage}
            traitement={traitement}
            transitions={transitions}
          />
          {clip.accroche ? (
            <Accroche
              texte={clip.accroche}
              typographie={typographie}
              style={motion}
              // Sur une planche de papier clair, le voile sombre de
              // l'accroche serait une bande noire en travers du collage. Les
              // couleurs de remplacement viennent du template de la planche.
              surface={
                clip.type === "collage" && style.collage
                  ? {
                      texte: style.collage.encre,
                      accent: style.collage.accent,
                      voile: style.collage.voile_titre,
                    }
                  : undefined
              }
            />
          ) : null}
        </Sequence>
      ))}

      {/* Le carton de fin. Il prolonge le film au-delà du dernier plan :
          `timeline.py` a déjà ajouté sa durée à `duree_frames`, sinon le
          rendu s'arrêterait avant lui. Les sous-titres sont montés après
          pour qu'aucune ligne ne traîne par-dessus. */}
      {generique ? (
        <Sequence
          from={generique.debut_frame}
          durationInFrames={generique.duree_frames}
          name="Générique"
        >
          <Generique
            generique={generique}
            style={style.motion}
            typographie={typographie}
          />
        </Sequence>
      ) : null}

      {sous_titres.map((line, index) => (
        <Sequence
          key={`st-${index}`}
          from={line.debut_frame}
          durationInFrames={line.duree_frames}
          name={`ST ${index}`}
        >
          <SousTitre
            texte={line.texte}
            mots={line.mots}
            depuis={line.debut_frame}
            palette={palette}
            typographie={typographie}
            surlignage={style.surlignage}
            ligneDeBasePct={style.sous_titres?.ligne_de_base_pct}
            voile={style.sous_titres?.voile}
          />
        </Sequence>
      ))}
    </AbsoluteFill>
  );
};
