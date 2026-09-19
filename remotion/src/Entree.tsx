import React from "react";
import { AbsoluteFill, Easing, interpolate, useCurrentFrame } from "remotion";
import type { Entree as EntreeSpec } from "./types";

const EASE_OUT = Easing.bezier(0.16, 1, 0.3, 1);

/** How a shot arrives.
 *
 *  These are entry effects, not cross-dissolves: clips are contiguous,
 *  non-overlapping sequences, and keeping them that way is what lets the
 *  timeline be read by something that is not Remotion. A hard cut with a
 *  whoosh under it is also more alive than a dissolve.
 *
 *  Which effect goes where was decided by the pipeline from the shot's place
 *  in the story. This component chooses nothing — it draws. */

/** The part that has to wrap the image, because it moves or scales it. */
export const enveloppe = (
  entree: EntreeSpec | undefined,
  frame: number,
): React.CSSProperties => {
  if (!entree) return {};
  const n = Math.max(entree.duree_frames, 1);
  const t = interpolate(frame, [0, n], [0, 1], {
    easing: EASE_OUT,
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  switch (entree.type) {
    case "flash":
      // A small punch outwards that settles. Under a quarter of a second it
      // is felt as impact rather than seen as a zoom.
      return { transform: `scale(${1 + (1 - t) * 0.05})` };
    case "glisse":
      // The incoming frame slides in and the blur sells the speed. Without
      // the blur it reads as a slideshow control, with it as a whip pan.
      return {
        transform: `translateX(${(1 - t) * 9}%)`,
        filter: `blur(${(1 - t) * 14}px)`,
      };
    default:
      return {};
  }
};

/** The part that sits on top of the image. */
export const Entree: React.FC<{ entree?: EntreeSpec }> = ({ entree }) => {
  const frame = useCurrentFrame();
  if (!entree || entree.type === "coupe" || entree.type === "glisse") {
    return null;
  }

  const n = Math.max(entree.duree_frames, 1);

  if (entree.type === "flash") {
    // Decays much faster than the transition's nominal length: a flash you
    // can watch is a fault, not an edit.
    const opacity = interpolate(frame, [0, n * 0.45], [0.55, 0], {
      extrapolateLeft: "clamp",
      extrapolateRight: "clamp",
    });
    return <AbsoluteFill style={{ backgroundColor: "#ffffff", opacity }} />;
  }

  // fondu_noir and ouverture: the shot comes up out of black. The act break
  // earns the pause; the opening earns it twice over.
  const opacity = interpolate(frame, [0, n], [1, 0], {
    easing: EASE_OUT,
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  return <AbsoluteFill style={{ backgroundColor: "#000000", opacity }} />;
};
