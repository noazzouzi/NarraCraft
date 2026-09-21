import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api, type Projet, type Template } from "../api";
import Rail from "./Rail";

export default function Projets() {
  const [projets, setProjets] = useState<Projet[] | null>(null);
  const [erreur, setErreur] = useState<string | null>(null);

  useEffect(() => {
    api.projets().then(setProjets).catch((e) => setErreur(String(e)));
  }, []);

  return (
    <div className="atelier">
      <Rail actif="projets" />
      <main>
        <header className="entete">
          <div>
            <h1>Documentaires</h1>
            <p className="chapeau">
              {projets ? `${projets.length} projets. Chacun reprend là où il s'est arrêté.` : "Lecture des fichiers…"}
            </p>
          </div>
        </header>

        <Barre surErreur={setErreur} />

        {erreur && <div className="erreur">{erreur}</div>}

        <div className="liste">
          {projets?.map((p) => (
            <Link key={p.slug} to={`/projets/${p.slug}`} className="carte">
              {p.vignette ? (
                <img className="vignette" src={api.media(p.slug, p.vignette)} alt="" />
              ) : (
                <div className="vignette" />
              )}
              <div className="corps">
                <div className="titre">
                  <h2>{p.titre}</h2>
                  {p.template && <span className="etiquette">{p.template}</span>}
                </div>
                <Chaine etapes={p.etapes} />
                <div className="mesures">
                  {p.mesures.map(([nom, valeur]) => (
                    <span key={nom}>
                      <b>{valeur}</b> {nom}
                    </span>
                  ))}
                  {p.mesures.length === 0 && <span>pas encore de montage</span>}
                </div>
              </div>
            </Link>
          ))}
          {projets?.length === 0 && (
            <p className="vide">Aucun projet dans <span className="mono">projects/</span>.</p>
          )}
        </div>
      </main>
    </div>
  );
}

// Le seul texte que l'utilisateur tape dans toute l'application. Il part
// au serveur, qui crée le dossier puis lance l'exploration — et on saute
// sur la page du projet, où le journal se déroule en direct.
function Barre({ surErreur }: { surErreur: (message: string | null) => void }) {
  const [sujet, setSujet] = useState("");
  const [template, setTemplate] = useState("");
  const [templates, setTemplates] = useState<Template[]>([]);
  const [occupe, setOccupe] = useState(false);
  const naviguer = useNavigate();

  useEffect(() => {
    api.templates().then((liste) => {
      setTemplates(liste);
      setTemplate((actuel) => actuel || liste[0]?.nom || "");
    }).catch(() => {});
  }, []);

  async function partir(evenement: React.FormEvent) {
    evenement.preventDefault();
    if (!sujet.trim() || occupe) return;
    setOccupe(true);
    surErreur(null);
    try {
      const { slug } = await api.creer(sujet.trim(), template || null);
      naviguer(`/projets/${slug}`);
    } catch (e) {
      surErreur(String(e));
      setOccupe(false);
    }
  }

  return (
    <form className="barre" onSubmit={partir}>
      <input
        value={sujet}
        onChange={(e) => setSujet(e.target.value)}
        placeholder="Un sujet, quelques mots-clés — « la faillite de Subway »"
        aria-label="Sujet du documentaire"
      />
      <select value={template} onChange={(e) => setTemplate(e.target.value)}>
        {templates.map((t) => (
          <option key={t.nom} value={t.nom}>{t.titre}</option>
        ))}
      </select>
      <button type="submit" disabled={!sujet.trim() || occupe}>
        {occupe ? "Exploration…" : "Explorer"}
      </button>
    </form>
  );
}

export function Chaine({ etapes }: { etapes: [string, boolean][] }) {
  return (
    <div className="chaine">
      <span className="bout">{etapes[0]?.[0]}</span>
      {etapes.map(([nom, faite]) => (
        <span key={nom} className={faite ? "segment faite" : "segment"} title={nom} />
      ))}
      <span className="bout fin">{etapes[etapes.length - 1]?.[0]}</span>
    </div>
  );
}
