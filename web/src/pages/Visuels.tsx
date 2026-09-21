import { useCallback, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api, type Galerie, type Visuel } from "../api";

// Tout ce qui entrera dans le film, avant qu'il soit monté. C'est le seul
// moment où remplacer une image coûte trois secondes plutôt qu'un rendu.
export default function Visuels() {
  const { slug = "" } = useParams();
  const [galerie, setGalerie] = useState<Galerie | null>(null);
  const [erreur, setErreur] = useState<string | null>(null);
  const [filtre, setFiltre] = useState("tous");
  const [occupe, setOccupe] = useState<string | null>(null);

  const recharger = useCallback(() => {
    api.visuels(slug).then(setGalerie).catch((e) => setErreur(String(e)));
  }, [slug]);

  useEffect(recharger, [recharger]);

  async function remplacer(plan: Visuel) {
    const raison = window.prompt(
      `Pourquoi refuser ce visuel ?\n${plan.titre || plan.requete}`,
      "",
    );
    if (raison === null) return;
    setOccupe(plan.id);
    setErreur(null);
    try {
      await api.remplacer(slug, plan.id, raison);
      recharger();
    } catch (e) {
      setErreur(String(e));
    } finally {
      setOccupe(null);
    }
  }

  if (erreur) return <div className="erreur" style={{ margin: 40 }}>{erreur}</div>;
  if (!galerie) return <p className="vide" style={{ padding: 40 }}>Lecture des fichiers…</p>;

  const comptes = new Map<string, number>();
  for (const plan of galerie.plans) {
    comptes.set(plan.type, (comptes.get(plan.type) ?? 0) + 1);
  }
  const visibles = galerie.plans.filter(
    (p) => filtre === "tous" || p.type === filtre,
  );

  return (
    <div className="galerie">
      <header className="entete">
        <div>
          <Link to={`/projets/${slug}`} className="leger">← {slug}</Link>
          <h1 style={{ fontSize: 28, marginTop: 8 }}>Les éléments</h1>
          <p className="chapeau">
            {galerie.plans.length} plans
            {galerie.manquants > 0 && ` · ${galerie.manquants} sans visuel`}
          </p>
        </div>
        <div className="filtres">
          <button
            className={filtre === "tous" ? "choisi" : undefined}
            onClick={() => setFiltre("tous")}
          >
            tous <span className="leger">{galerie.plans.length}</span>
          </button>
          {[...comptes.entries()].sort().map(([type, compte]) => (
            <button
              key={type}
              className={filtre === type ? "choisi" : undefined}
              onClick={() => setFiltre(type)}
            >
              {type} <span className="leger">{compte}</span>
            </button>
          ))}
        </div>
      </header>

      <div className="grille">
        {visibles.map((plan) => (
          <Carte
            key={plan.id}
            slug={slug}
            plan={plan}
            occupe={occupe === plan.id}
            surRemplacement={() => remplacer(plan)}
          />
        ))}
      </div>
    </div>
  );
}

function Carte({
  slug,
  plan,
  occupe,
  surRemplacement,
}: {
  slug: string;
  plan: Visuel;
  occupe: boolean;
  surRemplacement: () => void;
}) {
  // Un panneau graphique n'a pas de fichier : il est construit au rendu,
  // depuis les données du plan. Il n'y a rien à remplacer, seulement son
  // contenu à corriger dans `03-shots.json`.
  const construit = plan.type === "motion";

  return (
    <article className={plan.fichier || construit ? "visuel" : "visuel manquant"}>
      <div className="cadre">
        {plan.fichier ? (
          plan.type === "video" ? (
            <video src={api.media(slug, plan.fichier)} muted preload="metadata" />
          ) : (
            <img src={api.media(slug, plan.fichier)} alt={plan.titre} loading="lazy" />
          )
        ) : (
          <div className="rien">{construit ? plan.panneau : "pas de visuel"}</div>
        )}
        <span className="type">{construit ? plan.panneau || "motion" : plan.type}</span>
        {plan.relachee && <span className="alerte" title="requête élargie">élargie</span>}
      </div>

      <div className="corps">
        <div className="ligne">
          <b className="mono">{plan.id}</b>
          <span className="leger mono">{plan.beat}</span>
        </div>
        <p className="intention">{plan.intention}</p>
        {plan.titre && (
          <p className="leger">
            {plan.url ? (
              <a href={plan.url} target="_blank" rel="noreferrer">{plan.titre}</a>
            ) : plan.titre}
          </p>
        )}
        {plan.licence && (
          <p className="leger mono">
            {plan.licence}{plan.auteur && ` · ${plan.auteur}`}
          </p>
        )}
        {!construit && (
          <button onClick={surRemplacement} disabled={occupe}>
            {occupe ? "Recherche…" : "Remplacer"}
          </button>
        )}
      </div>
    </article>
  );
}
