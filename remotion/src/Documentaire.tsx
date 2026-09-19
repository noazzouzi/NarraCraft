import React from "react";
import { AbsoluteFill, Audio, Sequence, interpolate, staticFile } from "remotion";
import { Accroche } from "./Accroche";
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
  const { clips, sons, musique, sous_titres, style, audio, duree_frames } = timeline;
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
            traitement={traitement}
            transitions={transitions}
          />
          {clip.accroche ? (
            <Accroche
              texte={clip.accroche}
              typographie={typographie}
              style={motion}
            />
          ) : null}
        </Sequence>
      ))}

      {sous_titres.map((line, index) => (
        <Sequence
          key={`st-${index}`}
          from={line.debut_frame}
          durationInFrames={line.duree_frames}
          name={`ST ${index}`}
        >
          <SousTitre
            texte={line.texte}
            palette={palette}
            typographie={typographie}
          />
        </Sequence>
      ))}
    </AbsoluteFill>
  );
};
