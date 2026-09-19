import React from "react";
import { AbsoluteFill, Audio, Sequence, staticFile } from "remotion";
import { Plan } from "./Plan";
import { SousTitre } from "./SousTitre";
import type { Timeline } from "./types";

/** Plays back 06-timeline.json. It computes nothing: every cut, every camera
 *  move and every subtitle window was decided by the Python pipeline from the
 *  real word timings. See CLAUDE.md. */
export const Documentaire: React.FC<Timeline> = (timeline) => {
  const { clips, sous_titres, style, audio } = timeline;
  const { palette, typographie, traitement, motion } = style;

  return (
    <AbsoluteFill style={{ backgroundColor: palette.fond }}>
      {audio ? <Audio src={staticFile(audio)} /> : null}

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
