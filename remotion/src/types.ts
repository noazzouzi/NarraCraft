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

/** How a shot arrives. Chosen by the pipeline from the shot's place in the
 *  story, never by the renderer. */
export type Entree = {
  type: "coupe" | "flash" | "glisse" | "fondu_noir" | "ouverture";
  duree_frames: number;
};

export type Clip = {
  id: string;
  beat: string;
  acte: string;
  type: "archive" | "generated" | "motion" | "video";
  entree: Entree;
  debut_frame: number;
  duree_frames: number;
  image: string | null;
  /** Archive footage, and the second to start at inside the source file. */
  video: string | null;
  depart_s: number | null;
  /** Source aspect ratio. Lets the renderer letterbox a tall archive
   *  document instead of cropping it to a vertical slice of itself. */
  ratio: number | null;
  mouvement: Mouvement;
  motion: Record<string, unknown> | null;
  intention: string;
  /** A sentence burned over the shot — the hook, and chapter cards. Read
   *  while the voice says something else, so it is never a subtitle. */
  accroche: string | null;
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
export type MotionStyle = {
  fond: string;
  texte: string;
  accent: string;
  attenue: string;
  famille: string;
  cascade_s: number;
};

/** How hard the transitions hit. Set by the template, applied by the
 *  renderer, decided by neither. */
export type StyleTransitions = {
  flash_opacite: number;
  glisse_pct: number;
  punch_pct: number;
};

export type Style = {
  palette: Palette;
  typographie: Typographie;
  traitement: { grain?: number; vignette?: number };
  motion: MotionStyle;
  transitions: StyleTransitions;
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
  /** Transition sounds, synthesised locally by `fresque.sons`. They lead
   *  their cut rather than landing on it. */
  sons: { fichier: string; debut_frame: number; gain: number }[];
  /** The background bed, looped for the whole film. Null when the template
   *  turns it off. */
  musique: { fichier: string; gain: number; fondu_frames: number } | null;
  sous_titres: SousTitre[];
  credits: { asset: string; credit: string; url: string; licence: string }[];
};
