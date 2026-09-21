import { useCallback, useEffect, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api, type Commande, type ProjetDetail } from "../api";

const CHECKPOINTS: Record<string, string> = {
  "02-script.md": "CHECKPOINT 1",
  "03-shots.json": "CHECKPOINT 2",
};

// Un mp4 de dix-sept minutes fait huit cent mille kilo-octets : l'unité
// doit suivre, sinon le chiffre ne veut plus rien dire.
function taille(octets: number): string {
  if (octets >= 1e9) return `${(octets / 1e9).toFixed(1)} Go`;
  if (octets >= 1e6) return `${Math.round(octets / 1e6)} Mo`;
  return `${Math.max(1, Math.round(octets / 1e3))} Ko`;
}

export default function Projet() {
  const { slug = "" } = useParams();
  const [projet, setProjet] = useState<ProjetDetail | null>(null);
  const [commandes, setCommandes] = useState<Record<string, Commande>>({});
  const [erreur, setErreur] = useState<string | null>(null);

  const [suivi, setSuivi] = useState<string | null>(null);
  const [texte, setTexte] = useState("");
  const [vivant, setVivant] = useState(false);
  const [code, setCode] = useState<number | null>(null);
  const fermer = useRef<(() => void) | null>(null);
  const bas = useRef<HTMLPreElement>(null);

  const recharger = useCallback(() => {
    api.projet(slug).then(setProjet).catch((e) => setErreur(String(e)));
  }, [slug]);

  useEffect(() => {
    recharger();
    api.commandes().then(setCommandes).catch(() => {});
  }, [recharger]);

  // Une exécution suivie : on repart de l'offset zéro, donc le premier
  // événement porte tout le journal et les suivants n'en portent que la
  // suite. Rien n'est gardé en mémoire ici que l'affichage.
  useEffect(() => {
    if (!suivi) return;
    setTexte("");
    setCode(null);
    setVivant(true);
    fermer.current?.();
    fermer.current = api.suivre(slug, suivi, (etat) => {
      setTexte((avant) => avant + etat.texte);
      setVivant(etat.vivant);
      setCode(etat.code);
      if (!etat.vivant && (etat.code !== null || etat.interrompu)) recharger();
    });
    return () => fermer.current?.();
  }, [slug, suivi, recharger]);

  useEffect(() => {
    bas.current?.scrollTo(0, bas.current.scrollHeight);
  }, [texte]);

  // Au chargement, s'il y a une commande en cours, on s'y attache.
  useEffect(() => {
    if (suivi || !projet) return;
    const en_cours = projet.journaux.find((j) => j.vivant);
    if (en_cours) setSuivi(en_cours.id);
  }, [projet, suivi]);

  async function lancer(nom: string) {
    try {
      const { id } = await api.lancer(slug, nom);
      setSuivi(id);
      recharger();
    } catch (e) {
      setErreur(String(e));
    }
  }

  if (erreur) return <div className="erreur" style={{ margin: 40 }}>{erreur}</div>;
  if (!projet) return <p className="vide" style={{ padding: 40 }}>Lecture des fichiers…</p>;

  const parProduit = new Map<string, Commande>();
  for (const c of Object.values(commandes)) if (c.produit) parProduit.set(c.produit, c);

  return (
    <div className="colonnes">
      <main>
        <header className="entete">
          <div>
            <Link to="/" className="leger">← Documentaires</Link>
            <h2 style={{ fontSize: 28, marginTop: 8 }}>{projet.titre}</h2>
            <p className="chapeau mono">
              projects/{projet.slug}
              {projet.template ? ` · ${projet.template}` : ""}
            </p>
          </div>
          <div style={{ display: "flex", flexDirection: "column", alignItems: "flex-end", gap: 12 }}>
            {projet.mesures.length > 0 && (
              <div className="mesures">
                {projet.mesures.map(([nom, valeur]) => (
                  <span key={nom}><b>{valeur}</b> {nom}</span>
                ))}
              </div>
            )}
            {projet.fichiers.find((f) => f.fichier === "06-timeline.json")?.existe && (
              <Link
                to={`/projets/${slug}/apercu`}
                style={{
                  display: "inline-flex", alignItems: "center", gap: 9, height: 44,
                  padding: "0 18px", borderRadius: 9, background: "var(--accent)",
                  color: "#17110e", fontWeight: 600, fontSize: 14.5,
                }}
              >
                ▶ Voir le montage
              </Link>
            )}
          </div>
        </header>

        <h3 style={{ marginBottom: 14 }}>La chaîne</h3>
        {projet.fichiers.map((f, i) => {
          const commande = parProduit.get(f.fichier);
          const dernier = i === projet.fichiers.length - 1;
          return (
            <div className={f.existe ? "etape faite" : "etape"} key={f.fichier}>
              <div className="rail-vertical">
                {i > 0 && <span className="trait" style={{ flexGrow: 0, height: 16 }} />}
                <span className="noeud" />
                {!dernier && <span className="trait" />}
              </div>
              <div className="fiche">
                <div className="quoi">
                  <div className="nom">
                    {f.etape}
                    {CHECKPOINTS[f.fichier] && (
                      <span className="checkpoint" style={{ marginLeft: 10 }}>
                        {CHECKPOINTS[f.fichier]}
                      </span>
                    )}
                  </div>
                  <div className="sous">
                    {f.fichier}
                    {f.octets !== null && ` · ${taille(f.octets)}`}
                    {!f.existe && " · pas encore écrit"}
                  </div>
                </div>
                {commande && (
                  <button
                    onClick={() => lancer(commande.nom)}
                    disabled={vivant}
                    className={commande.depense ? "depense" : undefined}
                  >
                    {f.existe ? "Refaire" : commande.libelle}
                  </button>
                )}
              </div>
            </div>
          );
        })}
      </main>

      <aside className="flanc">
        <section>
          <h3>Lancer</h3>
          <div className="actions" style={{ marginTop: 11 }}>
            {Object.values(commandes)
              .filter((c) => !c.produit)
              .map((c) => (
                <button key={c.nom} onClick={() => lancer(c.nom)} disabled={vivant}>
                  <span>{c.libelle}</span>
                  <span className="cout">{c.longue ? "long" : "rapide"}</span>
                </button>
              ))}
          </div>
        </section>

        <section style={{ display: "flex", flexDirection: "column", gap: 10, flexGrow: 1, minHeight: 0 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
            <h3>Sortie</h3>
            {vivant && (
              <span className="leger" style={{ color: "var(--accent)" }}>en cours</span>
            )}
            {!vivant && code !== null && (
              <span className="leger" style={{ color: code === 0 ? "var(--ok)" : "#ec8f6f" }}>
                code {code}
              </span>
            )}
            {vivant && suivi && (
              <button className="arret" style={{ marginLeft: "auto", minHeight: 32 }} onClick={() => api.arreter(suivi)}>
                Interrompre
              </button>
            )}
          </div>
          <pre className="journal" ref={bas}>
            {texte || "Aucune commande suivie."}
          </pre>
          <div className="leger mono">{suivi ? `journal/${suivi}.log` : "journal/"}</div>
        </section>

        <section>
          <h3>Exécutions</h3>
          <div className="executions" style={{ marginTop: 10 }}>
            {projet.journaux.slice(0, 6).map((j) => (
              <button
                key={j.id}
                className={j.id === suivi ? "execution choisie" : "execution"}
                onClick={() => setSuivi(j.id)}
              >
                <span style={{ color: j.vivant ? "var(--accent)" : j.code === 0 ? "var(--ok)" : "#ec8f6f" }}>
                  {j.vivant ? "•" : j.code === 0 ? "✓" : "✗"}
                </span>
                <span className="nom">{j.commande}</span>
                <span className="leger">
                  {j.fin ? `${Math.round(j.fin - j.debut)} s` : "…"}
                </span>
              </button>
            ))}
            {projet.journaux.length === 0 && <span className="leger">Rien encore lancé d'ici.</span>}
          </div>
        </section>
      </aside>
    </div>
  );
}
