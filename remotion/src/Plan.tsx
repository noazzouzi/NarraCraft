import React from "react";
import { AbsoluteFill, Img, OffthreadVideo, staticFile, useCurrentFrame, useVideoConfig } from "remotion";
import { Collage } from "./Collage";
import { Entree, enveloppe } from "./Entree";
import { MotionGraphic } from "./Motion";
import { camera } from "./mouvement";
import { Traitement } from "./Traitement";
import type { Clip, CollageStyle, MotionStyle, Palette, StyleTransitions } from "./types";

/** Below this, filling the frame would crop the source to a vertical slice.
 *  Archives are full of tall scans — book pages, posters, portrait plates —
 *  and they are often the only image of a given subject. */
const MIN_FILL_RATIO = 1.15;

type PlanProps = {
  clip: Clip;
  palette: Palette;
  motionStyle: MotionStyle;
  collageStyle?: CollageStyle;
  traitement: { grain?: number; vignette?: number };
  transitions: StyleTransitions;
};

/** One shot, with the way it arrives wrapped around it.
 *
 *  The wrapper is separate from the content because a slide or a punch has
 *  to move the image itself, while a flash or a fade from black sits over
 *  it. Both come from the same `entree` the pipeline computed. */
export const Plan: React.FC<PlanProps> = (props) => {
  const frame = useCurrentFrame();
  return (
    <AbsoluteFill style={{ overflow: "hidden" }}>
      <AbsoluteFill style={enveloppe(props.clip.entree, frame, props.transitions)}>
        <Contenu {...props} />
      </AbsoluteFill>
      <Entree entree={props.clip.entree} style={props.transitions} />
    </AbsoluteFill>
  );
};

/** The shot itself: a still image given a slow, authored-looking camera move.
 *
 *  The move is fully described by the timeline, so this component decides
 *  nothing about pacing — it only plays back what the pipeline computed. */
const Contenu: React.FC<PlanProps> = ({
  clip, palette, motionStyle, collageStyle, traitement,
}) => {
  const frame = useCurrentFrame();
  const { durationInFrames, fps } = useVideoConfig();
  const { scale, x, y, rotation } = camera(clip.mouvement, frame, durationInFrames);

  if (clip.type === "motion" && clip.motion) {
    return (
      <MotionGraphic
        motion={clip.motion}
        style={motionStyle}
        fond={clip.fond_image}
      />
    );
  }

  // Une planche de collage : ses pièces reçoivent la même caméra, atténuée
  // par leur profondeur. Elle est donc rendue avant tout traitement d'image —
  // ce n'est pas une photographie, c'est du papier composé.
  if (clip.type === "collage" && clip.collage && collageStyle) {
    return (
      <Collage
        planche={clip.collage}
        style={collageStyle}
        mouvement={clip.mouvement}
        image={clip.image}
        grain={traitement.grain}
        vignette={traitement.vignette}
      />
    );
  }

  // Archive footage already moves. Adding a camera move on top gives two
  // motions fighting each other, so the clip is played straight — only the
  // film treatment is kept, because the footage is film.
  if (clip.video) {
    // Archive film is almost always 4:3. Cropping it to fill a 16:9 frame
    // costs a quarter of the height and cuts heads off, so anything narrower
    // than the frame is shown whole over a blurred blow-up of itself — the
    // same treatment tall documents get.
    const source = staticFile(clip.video);
    const depart = Math.round((clip.depart_s ?? 0) * fps);
    const etroit = clip.ratio !== null && clip.ratio < 1.6;

    if (etroit) {
      return (
        <AbsoluteFill style={{ backgroundColor: palette.letterbox, overflow: "hidden" }}>
          <OffthreadVideo
            src={source}
            trimBefore={depart}
            muted
            style={{
              width: "100%", height: "100%", objectFit: "cover",
              filter: "blur(38px) saturate(0.5) brightness(0.4)",
              transform: "scale(1.25)",
            }}
          />
          <AbsoluteFill style={{ alignItems: "center", justifyContent: "center" }}>
            <OffthreadVideo
              src={source}
              trimBefore={depart}
              muted
              style={{
                height: "100%", width: "auto", maxWidth: "100%",
                objectFit: "contain",
                boxShadow: `0 24px 90px ${palette.ombre}`,
              }}
            />
          </AbsoluteFill>
          <Traitement grain={traitement.grain} vignette={traitement.vignette} />
        </AbsoluteFill>
      );
    }

    return (
      <AbsoluteFill style={{ backgroundColor: palette.fond }}>
        <OffthreadVideo
          src={source}
          trimBefore={depart}
          muted
          style={{ width: "100%", height: "100%", objectFit: "cover" }}
        />
        <Traitement grain={traitement.grain} vignette={traitement.vignette} />
      </AbsoluteFill>
    );
  }

  if (!clip.image) {
    return (
      <AbsoluteFill style={{ backgroundColor: "#12151b", alignItems: "center", justifyContent: "center" }}>
        <div style={{ color: "#5b6373", fontSize: 40, fontFamily: "sans-serif" }}>
          {clip.id} · {clip.type}
        </div>
      </AbsoluteFill>
    );
  }

  const src = staticFile(clip.image);
  const tall = clip.ratio !== null && clip.ratio < MIN_FILL_RATIO;
  const transform = `translate(${x}%, ${y}%) scale(${scale}) rotate(${rotation}deg)`;

  // A tall document is shown whole, over a blurred blow-up of itself. That is
  // how a documentary presents an archive page, and it reads as a deliberate
  // choice rather than as a framing accident.
  if (tall) {
    return (
      <AbsoluteFill style={{ backgroundColor: palette.letterbox, overflow: "hidden" }}>
        <Img
          src={src}
          style={{
            width: "100%",
            height: "100%",
            objectFit: "cover",
            filter: "blur(38px) saturate(0.6) brightness(0.45)",
            transform: `scale(${1.25 * scale})`,
            transformOrigin: "center center",
          }}
        />
        <AbsoluteFill style={{ alignItems: "center", justifyContent: "center" }}>
          <Img
            src={src}
            style={{
              height: "100%",
              width: "auto",
              maxWidth: "100%",
              objectFit: "contain",
              transform,
              transformOrigin: "center center",
              boxShadow: `0 24px 90px ${palette.ombre}`,
            }}
          />
        </AbsoluteFill>
        <Traitement grain={traitement.grain} vignette={traitement.vignette} />
      </AbsoluteFill>
    );
  }

  return (
    <AbsoluteFill style={{ backgroundColor: palette.fond, overflow: "hidden" }}>
      <Img
        src={src}
        style={{
          width: "100%",
          height: "100%",
          objectFit: "cover",
          transform,
          transformOrigin: "center center",
        }}
      />
      <Traitement grain={traitement.grain} vignette={traitement.vignette} />
    </AbsoluteFill>
  );
};
