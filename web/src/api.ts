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

export const api = {
  projets: () => lire<Projet[]>("/api/projets"),
  projet: (slug: string) => lire<ProjetDetail>(`/api/projets/${slug}`),
  commandes: () => lire<Record<string, Commande>>("/api/commandes"),
  templates: () => lire<Template[]>("/api/templates"),
  pistes: (slug: string) => lire<Catalogue>(`/api/projets/${slug}/pistes`),

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
