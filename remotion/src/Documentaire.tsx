import React from "react";
import { AbsoluteFill, Audio, Sequence, staticFile } from "remotion";
import { Accroche } from "./Accroche";
import { Plan } from "./Plan";
import { SousTitre } from "./SousTitre";
import type { Timeline } from "./types";

/** Plays back 06-timeline.json. It computes nothing: every cut, every camera
 *  move and every subtitle window was decided by the Python pipeline from the
 *  real word timings. See CLAUDE.md. */
export const Documentaire: React.FC<Timeline> = (timeline) => {
  const { clips, sons, sous_titres, style, audio } = timeline;
  const { palette, typographie, traitement, motion } = style;

  return (
    <AbsoluteFill style={{ backgroundColor: palette.fond }}>
      {audio ? <Audio src={staticFile(audio)} /> : null}

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
