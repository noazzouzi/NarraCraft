// L'API de l'atelier. Une fonction par route, rien de plus : pas de cache,
// pas d'état global. Chaque écran relit ce dont il a besoin, comme le
// serveur relit les fichiers.

export type Etape = [string, boolean];

export type Projet = {
  slug: string;
  titre: string;
  template: string | null;
  etapes: Etape[];
  avancement: number;
  mesures: [string, string][];
  vignette: string | null;
};

export type Fichier = {
  etape: string;
  fichier: string;
  existe: boolean;
  octets: number | null;
};

export type Execution = {
  id: string;
  commande: string;
  debut: number;
  fin?: number;
  code: number | null;
  vivant: boolean;
};

export type ProjetDetail = Projet & {
  fichiers: Fichier[];
  journaux: Execution[];
  composition: Record<string, number>;
};

export type Option = {
  nom: string;
  libelle: string;
  type: "drapeau" | "nombre" | "texte";
  defaut: string;
};

export type Commande = {
  nom: string;
  libelle: string;
  exige: string;
  produit: string;
  depense: boolean;
  longue: boolean;
  // Celle qui accomplit vraiment l'étape, quand plusieurs écrivent
  // le même fichier. `align` estime, `voice` synthétise.
  principale: boolean;
  options: Option[];
};

export type Template = {
  nom: string;
  titre: string;
  description: string;
};

// `pistes.md`, relu par le serveur. Un titre cite toujours la preuve qui
// le tient : c'est ce qui sépare une accroche d'une invention.
export type Preuve = { numero: number; texte: string; source: string; url: string };
export type Titre = { texte: string; preuve: number };

export type Piste = {
  numero: number;
  resume: string;
  angle: string;
  pivot: string;
  risque: string;
  preuves: Preuve[];
  titres: Titre[];
};

export type Catalogue = {
  sujet: string;
  pistes: Piste[];
  retenue: number | null;
};

// Le premier beat du script. On le lit et on l'écoute côte à côte : il ne
// sera jamais lu par personne d'autre, il sera entendu une seule fois.
export type Hook = {
  beat: string;
  texte: string;
  intention: string;
  mots: number;
  fichier: string | null;
};

export type HookDit = { fichier: string; mesure: string; alerte: string };

// Un élément du montage. C'est ce que la galerie montre, et ce que le
// bouton « Remplacer » remplace.
export type Visuel = {
  id: string;
  beat: string;
  type: "archive" | "collage" | "video" | "motion" | "generated" | string;
  intention: string;
  requete: string;
  accroche: string;
  panneau: string;
  fichier: string | null;
  titre: string;
  auteur: string;
  licence: string;
  source: string;
  url: string;
  largeur: number | null;
  relachee: boolean;
};

export type Galerie = { plans: Visuel[]; manquants: number };

// La bibliothèque de voix. Les trois fournisseurs décrivent leur catalogue
// de façon incompatible ; le serveur les normalise, l'interface n'en
// connaît qu'une forme.
export type VoixItem = {
  id: string;
  nom: string;
  langue: string;
  genre: "homme" | "femme" | "inconnu" | string;
  detail: string;
};

export type Bibliotheque = {
  provider: string;
  total: number;
  langues: string[];
  voix: VoixItem[];
};

export type Fournisseur = { nom: string; titre: string; note: string };
export type ChoixVoix = { provider: string; voix: string };

// La piste voix. `estime` distingue une vraie synthèse d'un alignement
// estimé : les deux écrivent le même fichier, et les confondre fait croire
// qu'un film a du son quand il n'en a pas.
export type PisteAudio = {
  fichier: string | null;
  octets: number | null;
  beats: number | null;
  mots: number | null;
  duree_s: number | null;
  source: string;
  estime: boolean;
  voix: Record<string, string | number>;
};

export type EtatJournal = {
  texte: string;
  offset: number;
  vivant: boolean;
  code: number | null;
  interrompu: boolean;
};

async function lire<T>(route: string): Promise<T> {
  const reponse = await fetch(route);
  if (!reponse.ok) {
    const detail = await reponse.text();
    throw new Error(`${reponse.status} — ${detail}`);
  }
  return reponse.json() as Promise<T>;
}

async function poster<T>(route: string, corps: unknown): Promise<T> {
  const reponse = await fetch(route, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(corps),
  });
  if (!reponse.ok) throw new Error(await reponse.text());
  return reponse.json() as Promise<T>;
}

export const api = {
  projets: () => lire<Projet[]>("/api/projets"),
  projet: (slug: string) => lire<ProjetDetail>(`/api/projets/${slug}`),
  commandes: () => lire<Record<string, Commande>>("/api/commandes"),
  templates: () => lire<Template[]>("/api/templates"),
  pistes: (slug: string) => lire<Catalogue>(`/api/projets/${slug}/pistes`),
  hook: (slug: string) => lire<Hook>(`/api/projets/${slug}/hook`),
  visuels: (slug: string) => lire<Galerie>(`/api/projets/${slug}/visuels`),
  fournisseurs: () => lire<Fournisseur[]>("/api/fournisseurs"),
  audio: (slug: string) => lire<PisteAudio>(`/api/projets/${slug}/audio`),
  choixVoix: (slug: string) => lire<ChoixVoix>(`/api/projets/${slug}/voix`),

  bibliotheque: (provider: string, langue: string, genre: string) =>
    lire<Bibliotheque>(
      `/api/voix?provider=${provider}` +
        `&langue=${encodeURIComponent(langue)}&genre=${encodeURIComponent(genre)}`,
    ),

  // Écouter une voix ne la retient pas : écouter et décider sont deux
  // gestes, et deux routes.
  async essayerVoix(slug: string, provider: string, voix: string) {
    return poster<{ fichier: string; mesure: string }>(
      `/api/projets/${slug}/voix/essai`, { provider, voix });
  },

  async choisirVoix(slug: string, provider: string, voix: string) {
    return poster<ChoixVoix>(`/api/projets/${slug}/voix`, { provider, voix });
  },

  // Refuser un visuel et en chercher un autre. Le refus est gardé, donc
  // deux clics ne rendent jamais la même image.
  async remplacer(slug: string, plan: string, raison = "") {
    const reponse = await fetch(
      `/api/projets/${slug}/visuels/${plan}/remplacer`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ raison }),
      },
    );
    if (!reponse.ok) throw new Error(await reponse.text());
    return (await reponse.json()) as { sortie: string };
  },

  // Trois secondes de voix, pas quinze minutes. L'appel est synchrone :
  // le serveur attend la synthèse et rend le chemin du fichier.
  async direLeHook(slug: string) {
    const reponse = await fetch(`/api/projets/${slug}/hook`, { method: "POST" });
    if (!reponse.ok) throw new Error(await reponse.text());
    return (await reponse.json()) as HookDit;
  },

  // La barre de saisie : le sujet part, le dossier est créé et
  // l'exploration démarre. On récupère le slug et le journal à suivre.
  async creer(sujet: string, template: string | null) {
    const reponse = await fetch("/api/projets", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ sujet, template }),
    });
    if (!reponse.ok) throw new Error(await reponse.text());
    return (await reponse.json()) as { slug: string; id: string };
  },

  // Le choix d'une piste. Il n'y a pas de route dédiée : choisir, c'est
  // lancer la recherche sur cette piste — et le numéro est vérifié contre
  // `pistes.md` côté serveur avant d'entrer dans un argv.
  choisir: (slug: string, numero: number) =>
    api.lancer(slug, "recherche", { piste: String(numero) }),

  async lancer(slug: string, nom: string, options: Record<string, string> = {}) {
    const reponse = await fetch(`/api/projets/${slug}/lancer`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ nom, options }),
    });
    if (!reponse.ok) throw new Error(await reponse.text());
    return (await reponse.json()) as { id: string };
  },

  async arreter(identifiant: string) {
    await fetch(`/api/journaux/${identifiant}/arreter`, { method: "POST" });
  },

  media: (slug: string, chemin: string) => `/api/projets/${slug}/media/${chemin}`,

  // La sortie d'une commande arrive par SSE. Le serveur relit le journal et
  // n'envoie que ce qui s'y est ajouté ; fermer l'onglet n'interrompt rien.
  suivre(
    slug: string,
    identifiant: string,
    surEtat: (etat: EtatJournal) => void,
  ): () => void {
    const source = new EventSource(`/api/projets/${slug}/flux/${identifiant}`);
    source.onmessage = (evenement) => {
      const etat = JSON.parse(evenement.data) as EtatJournal;
      surEtat(etat);
      if (!etat.vivant && (etat.code !== null || etat.interrompu)) source.close();
    };
    source.onerror = () => source.close();
    return () => source.close();
  },
};
