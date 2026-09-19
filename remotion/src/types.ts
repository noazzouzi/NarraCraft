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
  /** Source aspect ratio. Lets the renderer letterbox a tall archive
   *  document instead of cropping it to a vertical slice of itself. */
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

export type Palette = {
  fond: string;
  sous_titre: string;
  voile: string;
  ombre: string;
  letterbox: string;
};

export type Typographie = {
  famille: string;
  taille: number;
  graisse: number;
  interligne: number;
  interlettrage: string;
};

/** The art direction, set by the project's template. The renderer applies
 *  it and decides none of it — which is what lets a new theme be a YAML
 *  file rather than a new set of components. */
export type Style = {
  palette: Palette;
  typographie: Typographie;
  traitement: { grain?: number; vignette?: number };
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
  template: string | null;
  style: Style;
  clips: Clip[];
  sous_titres: SousTitre[];
  credits: { asset: string; credit: string; url: string; licence: string }[];
};
