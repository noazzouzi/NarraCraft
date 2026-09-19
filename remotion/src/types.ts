/** Mirrors 06-timeline.json. That file is the contract between the Python
 *  pipeline and this renderer — nothing else crosses the boundary. */

export type Etat = { scale: number; x: number; y: number };

export type Mouvement = {
  kind: string;
  easing: string;
  rotation_deg: number;
  debut: Etat;
  fin: Etat;
};

export type Clip = {
  id: string;
  beat: string;
  type: "archive" | "generated" | "motion";
  debut_frame: number;
  duree_frames: number;
  image: string | null;
  ratio: number | null;
  mouvement: Mouvement;
  motion: Record<string, unknown> | null;
  intention: string;
};

export type SousTitre = {
  texte: string;
  debut_frame: number;
  duree_frames: number;
};

export type Timeline = {
  version: number;
  fps: number;
  width: number;
  height: number;
  duree_frames: number;
  duree_s: number;
  source_timings: string;
  audio: string | null;
  traitement: { grain?: number; vignette?: number };
  clips: Clip[];
  sous_titres: SousTitre[];
  credits: { asset: string; credit: string; url: string; licence: string }[];
};
