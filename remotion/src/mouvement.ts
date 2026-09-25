import { Easing, interpolate } from "remotion";
import type { Mouvement } from "./types";

/** Le mouvement de caméra, lu depuis la timeline et rien de plus.
 *
 *  Les deux bornes, la vitesse et la rotation sont calculées par le pipeline
 *  (`timeline._movement`). Ici on interpole entre elles, et c'est tout — le
 *  moteur ne décide ni l'amplitude ni la durée, au même titre qu'il ne décide
 *  aucune coupe.
 *
 *  Ce fichier existe parce que deux composants en ont besoin : un plan
 *  photographique l'applique à son image, une planche de collage l'applique
 *  pièce par pièce, atténué par la profondeur. C'est la même caméra. */

export const EASINGS: Record<string, (t: number) => number> = {
  easeInOutCubic: Easing.bezier(0.65, 0, 0.35, 1),
  easeOutCubic: Easing.bezier(0.33, 1, 0.68, 1),
  linear: Easing.linear,
};

export type Camera = {
  scale: number;
  /** En pourcentage de la largeur du cadre, prêt pour un `translate`. */
  x: number;
  y: number;
  rotation: number;
};

export function camera(
  mouvement: Mouvement, frame: number, duree: number,
): Camera {
  const ease = EASINGS[mouvement.easing] ?? EASINGS.easeInOutCubic;
  const at = (from: number, to: number) =>
    interpolate(frame, [0, Math.max(duree - 1, 1)], [from, to], {
      easing: ease,
      extrapolateLeft: "clamp",
      extrapolateRight: "clamp",
    });

  return {
    scale: at(mouvement.debut.scale, mouvement.fin.scale),
    x: at(mouvement.debut.x, mouvement.fin.x) * 100,
    y: at(mouvement.debut.y, mouvement.fin.y) * 100,
    rotation: at(0, mouvement.rotation_deg),
  };
}

/** La même caméra, atténuée par la profondeur d'une pièce.
 *
 *  C'est toute la parallaxe : le fond de papier reçoit `minimum` du
 *  mouvement, l'avant-plan le reçoit entier, et l'œil en déduit des plans
 *  séparés. Une affiche générée ne peut pas faire ça — ses couches sont
 *  cuites dans les pixels — et c'est la raison d'être du moteur de
 *  composition. */
export function attenuee(vue: Camera, profondeur: number, minimum: number): Camera {
  const facteur = minimum + (1 - minimum) * profondeur;
  return {
    // L'échelle s'atténue autour de 1, pas autour de 0 : une pièce au fond
    // doit garder sa taille, pas disparaître.
    scale: 1 + (vue.scale - 1) * facteur,
    x: vue.x * facteur,
    y: vue.y * facteur,
    rotation: vue.rotation * facteur,
  };
}
