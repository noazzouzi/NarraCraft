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

/** Une pièce de papier d'une planche de collage. Tout y est déjà décidé par
 *  `fresque.collage` : le moteur place, découpe et dessine, il ne choisit ni
 *  la forme ni la place. */
export type Piece = {
  role: "bloc" | "photo" | "accent" | "ruban";
  /** Ce que le moteur dessine : `papier`, `ruban`, ou une forme d'accent. */
  forme: string;
  /** Feuille déchirée ou coupée aux ciseaux. Absent sur un accent. */
  bords?: "dechire" | "coupe";
  /** Quelle encre du template, quand la pièce en porte une. */
  couleur?: "accent" | "encre" | "adhesif";
  /** Centre et taille, en fraction du cadre. */
  x: number;
  y: number;
  w: number;
  h: number;
  rotation_deg: number;
  /** 0 au fond, 1 devant. Décide de la part du mouvement de caméra que la
   *  pièce reçoit — c'est toute la parallaxe. */
  profondeur: number;
  /** Graine du bord déchiré. Stable, donc deux rendus sont identiques. */
  graine: string;
};

export type Planche = {
  /** Hauteur réservée en haut du cadre pour l'accroche, en fraction. Zéro
   *  quand le plan n'en porte pas. */
  bande_titre: number;
  /** Du fond vers l'avant. L'ordre de la liste EST l'ordre de superposition :
   *  le moteur ne trie rien, sans quoi une correction à la main dans
   *  `06-timeline.json` ne servirait à rien. */
  pieces: Piece[];
};

export type Clip = {
  id: string;
  beat: string;
  acte: string;
  type: "archive" | "collage" | "generated" | "motion" | "video";
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
  /** Pour un plan `collage` : la mise en page de la planche. */
  collage: Planche | null;
  /** Pour un panneau graphique : l'image du plan voisin, posée derrière lui
   *  en texture. Choisie par le pipeline, jamais par le moteur. */
  fond_image: string | null;
  intention: string;
  /** A sentence burned over the shot — the hook, and chapter cards. Read
   *  while the voice says something else, so it is never a subtitle. */
  accroche: string | null;
};

export type MotSousTitre = {
  tx: string;
  /** Frames absolues, comme partout ailleurs dans le fichier : le composant
   *  les ramène au début de sa séquence. */
  debut_frame: number;
  fin_frame: number;
};

export type SurlignageStyle = {
  actif: boolean;
  couleur: string;
  fondu_frames: number;
};

/** La famille de sous-titres, et ce qui se combine avec elle.
 *
 *  Liste close, connue du pipeline, qui refuse un nom inconnu avant le
 *  rendu : une famille inventée donnerait un film sans sous-titres,
 *  découvert après vingt minutes. Un template en choisit une, un projet
 *  peut la changer, l'interface la propose. */
export type FamilleSousTitre = "surligne" | "marqueur" | "bloc" | "mot";

export type SousTitreStyle = {
  style?: FamilleSousTitre;
  majuscules?: boolean;
  position?: "bas" | "centre";
  /** Vides, ces couleurs retombent sur la palette du template. */
  couleur_texte?: string;
  couleur_mot?: string;
  couleur_fond?: string;
  ligne_de_base_pct?: number;
  voile?: boolean;
};

export type SousTitre = {
  texte: string;
  debut_frame: number;
  duree_frames: number;
  mots?: MotSousTitre[];
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
  /** Corps de l'accroche incrustée. Séparé de `taille`, qui est celui des
   *  sous-titres : les deux ne sont pas du même ordre et ne se règlent pas
   *  ensemble. */
  accroche?: number;
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
  /** Le papier et l'encre des panneaux qui représentent un imprimé — une
   *  une de journal, un document. Facultatifs : chaque composant garde sa
   *  valeur en repli, parce qu'un journal et un document n'ont pas le même
   *  blanc. Un template qui les pose repeint les deux. */
  papier?: string;
  encre?: string;
  /** La scène derrière le panneau : ce qui le rattache au film au lieu de
   *  le poser à côté. Entièrement décidée par le template. */
  scene?: {
    opacite?: number;
    flou_px?: number;
    saturation?: number;
    echelle?: number;
    filet?: boolean;
    grain?: number;
    vignette?: number;
  };
};

/** How hard the transitions hit. Set by the template, applied by the
 *  renderer, decided by neither. */
export type StyleTransitions = {
  flash_opacite: number;
  glisse_pct: number;
  punch_pct: number;
};

/** La direction artistique d'une planche de collage. Entièrement donnée par
 *  le template : c'est ce qui fait qu'une deuxième thématique est un fichier
 *  YAML et non un deuxième composant. */
export type CollageStyle = {
  papier: string;
  encre: string;
  accent: string;
  lisere: string;
  adhesif: string;
  /** Voile posé sous l'accroche. Déclaré par le template, jamais dérivé du
   *  papier — une transparence concaténée à une couleur casse dès qu'elle
   *  n'est pas écrite en hexadécimal. */
  voile_titre: string;
  ombre: string;
  /** Force de la trame d'impression posée sur les aplats. */
  trame: number;
  /** Fibre du papier, sous les pièces. */
  grain: number;
  photo: "duotone" | "gris" | "brut";
  /** Part du mouvement de caméra que reçoit la pièce la plus au fond. À 1,0
   *  toutes les pièces bougent ensemble et la planche redevient plate. */
  parallaxe_min: number;
  cascade_s: number;
  lisere_px: number;
};

export type Style = {
  palette: Palette;
  typographie: Typographie;
  traitement: { grain?: number; vignette?: number };
  motion: MotionStyle;
  transitions: StyleTransitions;
  surlignage?: SurlignageStyle;
  sous_titres?: SousTitreStyle;
  collage?: CollageStyle;
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
  musique: {
    fichier: string;
    gain: number;
    fondu_entree_frames: number;
    fondu_sortie_frames: number;
  } | null;
  sous_titres: SousTitre[];
  credits: {
    asset: string;
    credit: string;
    url: string;
    licence: string;
    auteur?: string;
    source?: string;
  }[];
  /** Le carton de fin. Absent quand le film n'utilise rien qui exige une
   *  attribution, ou quand le template l'a désactivé. */
  generique?: Generique | null;
};

/** Le carton de fin, groupé par licence. Tout est décidé par
 *  `timeline.generique` : le composant met en page et ne compte rien. */
export type Generique = {
  debut_frame: number;
  duree_frames: number;
  titre: string;
  groupes: {
    licence: string;
    nombre: number;
    auteurs: string[];
    fonds: string[];
    reste: number;
  }[];
  libres: number;
  mention: string;
};
