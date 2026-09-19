import React from "react";
import { AbsoluteFill, Audio, Sequence, interpolate, staticFile } from "remotion";
import { Accroche } from "./Accroche";
import { Plan } from "./Plan";
import { SousTitre } from "./SousTitre";
import type { Timeline } from "./types";

/** Plays back 06-timeline.json. It computes nothing: every cut, every camera
 *  move and every subtitle window was decided by the Python pipeline from the
 *  real word timings. See CLAUDE.md. */
export const Documentaire: React.FC<Timeline> = (timeline) => {
  const { clips, sons, musique, sous_titres, style, audio, duree_frames } = timeline;
  const { palette, typographie, traitement, motion, transitions } = style;

  return (
    <AbsoluteFill style={{ backgroundColor: palette.fond }}>
      {audio ? <Audio src={staticFile(audio)} /> : null}

      {/* Le lit sonore, bouclé sur toute la durée. Il monte et redescend :
          un fond qui démarre sec s'entend, et c'est précisément ce qu'on ne
          veut pas d'un lit sonore. */}
      {musique ? (
        <Audio
          src={staticFile(musique.fichier)}
          loop
          volume={(frame) =>
            musique.gain *
            interpolate(
              frame,
              [
                0,
                musique.fondu_frames,
                Math.max(duree_frames - musique.fondu_frames, musique.fondu_frames + 1),
                duree_frames,
              ],
              [0, 1, 1, 0],
              { extrapolateLeft: "clamp", extrapolateRight: "clamp" },
            )
          }
        />
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
