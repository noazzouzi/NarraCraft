import React from "react";
import { AbsoluteFill, Sequence } from "remotion";
import { Plan } from "./Plan";
import { SousTitre } from "./SousTitre";
import { Traitement } from "./Traitement";
import type { Timeline } from "./types";

/** Plays back 06-timeline.json. It computes nothing: every cut, every camera
 *  move and every subtitle window was decided by the Python pipeline from the
 *  real word timings. See CLAUDE.md. */
export const Documentaire: React.FC<Timeline> = (timeline) => {
  const { clips, sous_titres, traitement } = timeline;

  return (
    <AbsoluteFill style={{ backgroundColor: "#000" }}>
      {clips.map((clip) => (
        <Sequence
          key={clip.id}
          from={clip.debut_frame}
          durationInFrames={clip.duree_frames}
          name={`${clip.id} ${clip.beat}`}
        >
          <Plan clip={clip} />
        </Sequence>
      ))}

      <Traitement grain={traitement?.grain} vignette={traitement?.vignette} />

      {sous_titres.map((line, index) => (
        <Sequence
          key={`st-${index}`}
          from={line.debut_frame}
          durationInFrames={line.duree_frames}
          name={`ST ${index}`}
        >
          <SousTitre texte={line.texte} />
        </Sequence>
      ))}
    </AbsoluteFill>
  );
};
