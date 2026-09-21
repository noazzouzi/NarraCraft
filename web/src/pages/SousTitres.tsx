import { useCallback, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api, type SousTitres as Reglages } from "../api";

const PHRASE = ["Nicolas", "Sarkozy", "a", "été", "condamné", "à"];
const MOT_DIT = 4;

// Les sous-titres se choisissent en les voyant. L'aperçu ci-dessous est du
// HTML, pas un rendu Remotion : il emploie les mêmes couleurs et les mêmes
// proportions, mais il APPROCHE le film — il ne le remplace pas.
function Apercu({
  reglages,
  fond,
}: {
  reglages: Reglages;
  fond: string | null;
}) {
  const echelle = 0.32; // l'aperçu fait ~620 px de large pour un cadre 1920
  const corps = reglages.taille * echelle *
    (reglages.style === "mot" ? 1.8 : 1);

  const commun: React.CSSProperties = {
    fontFamily: reglages.famille_police,
    fontSize: corps,
    fontWeight: reglages.graisse,
    color: reglages.couleur_texte,
    textTransform: reglages.majuscules ? "uppercase" : undefined,
    textShadow: reglages.style === "bloc" ? undefined : "0 1px 8px rgba(0,0,0,.7)",
    textAlign: "center",
    lineHeight: 1.25,
  };

  const mot = (texte: string, index: number) => {
    const dit = index === MOT_DIT;
    if (reglages.style === "marqueur") {
      return (
        <span
          key={index}
          style={{
            backgroundColor: dit ? reglages.couleur_mot : undefined,
            boxShadow: dit ? `0 0 0 0.14em ${reglages.couleur_mot}` : undefined,
            borderRadius: 3,
            color: dit ? reglages.couleur_fond : reglages.couleur_texte,
          }}
        >
          {texte}
        </span>
      );
    }
    return (
      <span key={index} style={{ color: dit ? reglages.couleur_mot : undefined }}>
        {texte}
      </span>
    );
  };

  const ligne = () => {
    if (reglages.style === "mot") {
      return <span style={commun}>{PHRASE[MOT_DIT]}</span>;
    }
    const mots = PHRASE.flatMap((m, i) => (i ? [" ", mot(m, i)] : [mot(m, i)]));
    if (reglages.style === "bloc") {
      return (
        <span
          style={{
            ...commun,
            backgroundColor: reglages.couleur_fond,
            padding: "0.18em 0.6em",
            borderRadius: 6,
          }}
        >
          {mots}
        </span>
      );
    }
    return <span style={commun}>{mots}</span>;
  };

  return (
    <div className="apercu-st">
      {fond ? <img src={fond} alt="" /> : <div className="sansfond" />}
      <div
        className="pose"
        style={{
          alignItems: reglages.position === "centre" ? "center" : "flex-end",
          paddingBottom:
            reglages.position === "centre"
              ? 0
              : `${100 - reglages.ligne_de_base_pct}%`,
          background:
            reglages.voile && reglages.position === "bas" && reglages.style !== "bloc"
              ? "linear-gradient(to top, rgba(0,0,0,.55), rgba(0,0,0,0) 45%)"
              : undefined,
        }}
      >
        {reglages.actifs ? ligne() : null}
      </div>
    </div>
  );
}

export default function SousTitres() {
  const { slug = "" } = useParams();
  const [reglages, setReglages] = useState<Reglages | null>(null);
  const [fond, setFond] = useState<string | null>(null);
  const [erreur, setErreur] = useState<string | null>(null);
  const [enregistre, setEnregistre] = useState(false);

  const recharger = useCallback(() => {
    api.sousTitres(slug).then(setReglages).catch((e) => setErreur(String(e)));
  }, [slug]);

  useEffect(() => {
    recharger();
    // La vignette du projet sert de fond : on juge des couleurs sur une
    // image du film, pas sur un aplat gris.
    api.visuels(slug)
      .then((g) => {
        const avec = g.plans.find((p) => p.fichier && p.type !== "motion");
        if (avec?.fichier) setFond(api.media(slug, avec.fichier));
      })
      .catch(() => {});
  }, [recharger, slug]);

  async function changer(bout: Partial<Reglages>) {
    if (!reglages) return;
    const suivant = { ...reglages, ...bout };
    setReglages(suivant);
    setErreur(null);
    try {
      await api.choisirSousTitres(slug, bout);
      setEnregistre(true);
      window.setTimeout(() => setEnregistre(false), 1400);
    } catch (e) {
      setErreur(String(e));
      recharger();
    }
  }

  if (erreur && !reglages) {
    return <div className="erreur" style={{ margin: 40 }}>{erreur}</div>;
  }
  if (!reglages) return <p className="vide" style={{ padding: 40 }}>Lecture…</p>;

  return (
    <div className="sous-titres">
      <header className="entete">
        <div>
          <Link to={`/projets/${slug}`} className="leger">← {slug}</Link>
          <h1 style={{ fontSize: 28, marginTop: 8 }}>Les sous-titres</h1>
          <p className="chapeau">
            Écrit dans <span className="mono">projet.yaml</span>, appliqué au
            prochain montage.
            {enregistre && <span className="ok"> · enregistré</span>}
          </p>
        </div>
        <label className="bascule">
          <input
            type="checkbox"
            checked={reglages.actifs}
            onChange={(e) => changer({ actifs: e.target.checked })}
          />
          Afficher les sous-titres
        </label>
      </header>

      {erreur && <div className="erreur">{erreur}</div>}

      <Apercu reglages={reglages} fond={fond} />
      <p className="leger">
        Aperçu approché : mêmes couleurs et mêmes proportions que le rendu,
        en HTML. Le film seul fait foi.
      </p>

      <section>
        <h3>La famille</h3>
        <div className="familles">
          {reglages.familles.map((f) => (
            <button
              key={f.nom}
              className={reglages.style === f.nom ? "famille choisie" : "famille"}
              onClick={() => changer({ style: f.nom })}
              disabled={!reglages.actifs}
            >
              <b>{f.titre}</b>
              <span className="leger">{f.note}</span>
            </button>
          ))}
        </div>
      </section>

      <section>
        <h3>Les couleurs</h3>
        <div className="couleurs">
          <Couleur
            titre="Texte"
            valeur={reglages.couleur_texte}
            surChangement={(v) => changer({ couleur_texte: v })}
          />
          <Couleur
            titre="Mot dit"
            valeur={reglages.couleur_mot}
            surChangement={(v) => changer({ couleur_mot: v })}
          />
          <Couleur
            titre={reglages.style === "marqueur" ? "Encre sur marqueur" : "Fond"}
            valeur={reglages.couleur_fond}
            surChangement={(v) => changer({ couleur_fond: v })}
          />
        </div>
      </section>

      <section>
        <h3>La pose</h3>
        <div className="pose-reglages">
          <label>
            Place
            <select
              value={reglages.position}
              onChange={(e) => changer({ position: e.target.value })}
            >
              <option value="bas">en bas</option>
              <option value="centre">au centre</option>
            </select>
          </label>
          <label>
            Ligne de base
            <input
              type="range"
              min={70}
              max={98}
              step={0.2}
              value={reglages.ligne_de_base_pct}
              disabled={reglages.position === "centre"}
              onChange={(e) =>
                setReglages({ ...reglages, ligne_de_base_pct: Number(e.target.value) })
              }
              onMouseUp={(e) =>
                changer({ ligne_de_base_pct: Number(e.currentTarget.value) })
              }
            />
            <span className="mono leger">{reglages.ligne_de_base_pct.toFixed(1)} %</span>
          </label>
          <label className="bascule">
            <input
              type="checkbox"
              checked={reglages.majuscules}
              onChange={(e) => changer({ majuscules: e.target.checked })}
            />
            Majuscules
          </label>
          <label className="bascule">
            <input
              type="checkbox"
              checked={reglages.voile}
              onChange={(e) => changer({ voile: e.target.checked })}
            />
            Voile sous le texte
          </label>
        </div>
      </section>
    </div>
  );
}

function Couleur({
  titre,
  valeur,
  surChangement,
}: {
  titre: string;
  valeur: string;
  surChangement: (valeur: string) => void;
}) {
  // Une palette peut donner du `rgba(…)` — le voile en est. Le sélecteur
  // natif ne sait afficher qu'un hexadécimal : la pastille est donc un
  // simple aplat CSS, qui sait tout montrer, et le sélecteur se glisse
  // dessus. Sans ça la pastille affichait une couleur que le film n'a pas.
  const hexa = /^#[0-9A-Fa-f]{6}$/.test(valeur);
  return (
    <label className="couleur">
      {/* `backgroundColor` et non `background` : le raccourci écraserait le
          damier que la feuille de style pose dessous, et une couleur
          translucide se lirait comme un gris opaque. */}
      <span className="pastille-couleur" style={{ backgroundColor: valeur }}>
        <input
          type="color"
          value={hexa ? valeur : "#FAFAFA"}
          onChange={(e) => surChangement(e.target.value.toUpperCase())}
        />
      </span>
      <span>
        {titre}
        <span className="mono leger">
          {valeur}
          {!hexa && " · du template"}
        </span>
      </span>
    </label>
  );
}
