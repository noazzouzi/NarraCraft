import { useCallback, useEffect, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api, type Bibliotheque, type Fournisseur, type VoixItem } from "../api";

// La bibliothèque. On choisit un fournisseur, on filtre par langue et par
// sexe, on écoute, puis on retient. Écouter et retenir sont deux gestes :
// une voix essayée n'entre dans `projet.yaml` que si on clique « Choisir ».
export default function Voix() {
  const { slug = "" } = useParams();
  const [fournisseurs, setFournisseurs] = useState<Fournisseur[]>([]);
  const [provider, setProvider] = useState("edge");
  const [langue, setLangue] = useState("fr");
  const [genre, setGenre] = useState("");
  const [biblio, setBiblio] = useState<Bibliotheque | null>(null);
  const [retenue, setRetenue] = useState("");
  const [erreur, setErreur] = useState<string | null>(null);
  const [occupe, setOccupe] = useState<string | null>(null);
  const [mesure, setMesure] = useState("");
  const [source, setSource] = useState<string | null>(null);
  const lecteur = useRef<HTMLAudioElement>(null);

  useEffect(() => {
    api.fournisseurs().then(setFournisseurs).catch(() => {});
    api.choixVoix(slug)
      .then((c) => {
        if (c.provider) setProvider(c.provider);
        setRetenue(c.voix);
      })
      .catch(() => {});
  }, [slug]);

  const charger = useCallback(() => {
    setBiblio(null);
    setErreur(null);
    api.bibliotheque(provider, langue, genre)
      .then(setBiblio)
      .catch((e) => setErreur(String(e)));
  }, [provider, langue, genre]);

  useEffect(charger, [charger]);

  async function ecouter(voix: VoixItem) {
    setOccupe(voix.id);
    setErreur(null);
    try {
      const dit = await api.essayerVoix(slug, provider, voix.id);
      setMesure(dit.mesure);
      // Le nom de fichier ne change pas d'un essai à l'autre pour une même
      // voix : sans ce paramètre, le navigateur rejoue le précédent.
      setSource(`${api.media(slug, dit.fichier)}?t=${Date.now()}`);
      requestAnimationFrame(() => lecteur.current?.play().catch(() => {}));
    } catch (e) {
      setErreur(String(e));
    } finally {
      setOccupe(null);
    }
  }

  async function choisir(voix: VoixItem) {
    setOccupe(voix.id);
    try {
      await api.choisirVoix(slug, provider, voix.id);
      setRetenue(voix.id);
    } catch (e) {
      setErreur(String(e));
    } finally {
      setOccupe(null);
    }
  }

  return (
    <div className="voix">
      <header className="entete">
        <div>
          <Link to={`/projets/${slug}`} className="leger">← {slug}</Link>
          <h1 style={{ fontSize: 28, marginTop: 8 }}>La voix</h1>
          <p className="chapeau">
            {biblio
              ? `${biblio.voix.length} voix sur ${biblio.total} chez ${biblio.provider}`
              : "Lecture du catalogue…"}
          </p>
        </div>
      </header>

      <div className="reglages">
        <div className="filtres">
          {fournisseurs.map((f) => (
            <button
              key={f.nom}
              className={provider === f.nom ? "choisi" : undefined}
              onClick={() => setProvider(f.nom)}
              title={f.note}
            >
              {f.titre}
            </button>
          ))}
        </div>

        <div className="filtres">
          <select value={langue} onChange={(e) => setLangue(e.target.value)}>
            <option value="">toutes les langues</option>
            {(biblio?.langues ?? []).map((l) => (
              <option key={l} value={l}>{l}</option>
            ))}
            {!biblio?.langues.includes("fr-FR") && <option value="fr">fr</option>}
          </select>
          <select value={genre} onChange={(e) => setGenre(e.target.value)}>
            <option value="">les deux</option>
            <option value="homme">homme</option>
            <option value="femme">femme</option>
          </select>
        </div>
      </div>

      {erreur && <div className="erreur">{erreur}</div>}

      {source && (
        <div className="ecoute">
          <audio ref={lecteur} controls src={source} />
          {mesure && <span className="leger mono">{mesure}</span>}
        </div>
      )}

      <div className="catalogue">
        {biblio?.voix.map((v) => (
          <article key={v.id} className={v.id === retenue ? "voix-item retenue" : "voix-item"}>
            <div className="quoi">
              <div className="nom">
                {v.nom}
                {v.id === retenue && <span className="etiquette">retenue</span>}
              </div>
              <div className="sous mono">
                {v.id} · {v.langue || "—"} · {v.genre}
                {v.detail && ` · ${v.detail}`}
              </div>
            </div>
            <button onClick={() => ecouter(v)} disabled={occupe !== null}>
              {occupe === v.id ? "…" : "Écouter"}
            </button>
            <button
              className="principal"
              onClick={() => choisir(v)}
              disabled={occupe !== null || v.id === retenue}
            >
              Choisir
            </button>
          </article>
        ))}
        {biblio?.voix.length === 0 && (
          <p className="vide">Aucune voix pour ces filtres.</p>
        )}
      </div>
    </div>
  );
}
