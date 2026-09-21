import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, type ChoixVoix, type PisteAudio } from "../api";

// `voice` imprime « 12/168 beats · 1 min 04 s » à chaque beat synthétisé.
// C'est la seule mesure d'avancement qui existe, et elle est dans le
// journal : on la relit plutôt que d'en inventer une deuxième.
const AVANCEMENT = /(\d+)\/(\d+) beats/g;

function progression(journal: string): [number, number] | null {
  let dernier: RegExpExecArray | null = null;
  let trouve: RegExpExecArray | null;
  AVANCEMENT.lastIndex = 0;
  while ((trouve = AVANCEMENT.exec(journal)) !== null) dernier = trouve;
  return dernier ? [Number(dernier[1]), Number(dernier[2])] : null;
}

function duree(secondes: number): string {
  const m = Math.floor(secondes / 60);
  const s = Math.round(secondes % 60);
  return m ? `${m} min ${String(s).padStart(2, "0")} s` : `${s} s`;
}

// La voix du film. Le bouton, l'avancement pendant qu'elle se fabrique,
// et la piste quand elle existe — au même endroit.
export default function Audio({
  slug,
  journal,
  vivant,
  surLancement,
}: {
  slug: string;
  journal: string;
  vivant: boolean;
  surLancement: (identifiant: string) => void;
}) {
  const [piste, setPiste] = useState<PisteAudio | null>(null);
  const [choix, setChoix] = useState<ChoixVoix | null>(null);
  const [erreur, setErreur] = useState<string | null>(null);

  const recharger = useCallback(() => {
    api.audio(slug).then(setPiste).catch((e) => setErreur(String(e)));
    api.choixVoix(slug).then(setChoix).catch(() => {});
  }, [slug]);

  useEffect(recharger, [recharger]);

  // Quand la commande se termine, la piste vient d'apparaître.
  useEffect(() => {
    if (!vivant) recharger();
  }, [vivant, recharger]);

  async function generer() {
    setErreur(null);
    try {
      const { id } = await api.lancer(slug, "voice");
      surLancement(id);
    } catch (e) {
      setErreur(String(e));
    }
  }

  if (!piste) return null;

  const avance = vivant ? progression(journal) : null;
  const moteur = Object.entries(piste.voix);

  return (
    <section className="audio">
      <header>
        <div>
          <h3>L'audio</h3>
          <p className="sous">
            {choix?.voix
              ? `${choix.provider} · ${choix.voix}`
              : "voix par défaut de la configuration"}
            {" · "}
            <Link to={`/projets/${slug}/voix`}>changer</Link>
          </p>
        </div>
        <button onClick={generer} disabled={vivant} className="principal">
          {vivant ? "Synthèse…" : piste.fichier ? "Refaire l'audio" : "Générer l'audio"}
        </button>
      </header>

      {erreur && <div className="erreur">{erreur}</div>}

      {avance && (
        <div className="avancement">
          <div className="barre">
            <span style={{ width: `${(avance[0] / avance[1]) * 100}%` }} />
          </div>
          <span className="leger mono">
            {avance[0]} / {avance[1]} beats
          </span>
        </div>
      )}

      {piste.fichier && (
        <audio controls src={api.media(slug, piste.fichier)} />
      )}

      {/* Une estimation n'est pas une voix : `align` et `voice` écrivent le
          même fichier, et confondre les deux fait croire qu'un film a du
          son quand il n'en a pas. */}
      {piste.estime && (
        <p className="alerte">
          Durées estimées, aucun son. Le montage tombera à côté.
        </p>
      )}

      {piste.duree_s !== null && !piste.estime && (
        <p className="mesure mono">
          {duree(piste.duree_s)} · {piste.beats} beats · {piste.mots} mots
          {piste.duree_s > 0 &&
            ` · ${Math.round((piste.mots ?? 0) / piste.duree_s * 60)} mots/min`}
          {moteur.length > 0 &&
            ` · ${moteur.map(([c, v]) => `${c} ${v}`).join(" · ")}`}
        </p>
      )}
    </section>
  );
}
