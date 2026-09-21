import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, type Projet } from "../api";
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
