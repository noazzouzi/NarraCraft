import { useEffect, useState } from "react";
import { api, type Catalogue, type Piste } from "../api";

// Les quatre pistes que l'exploration a produites. Le fichier `pistes.md`
// reste la vérité : cet écran n'en est qu'une lecture, et choisir n'écrit
// rien ici — ça lance le brief, qui écrit dans le projet.
export default function Pistes({
  slug,
  vivant,
  surLancement,
}: {
  slug: string;
  vivant: boolean;
  surLancement: (identifiant: string) => void;
}) {
  const [catalogue, setCatalogue] = useState<Catalogue | null>(null);
  const [erreur, setErreur] = useState<string | null>(null);

  useEffect(() => {
    let monte = true;
    api.pistes(slug)
      .then((c) => monte && setCatalogue(c))
      .catch((e) => monte && setErreur(String(e)));
    return () => { monte = false; };
  }, [slug]);

  // Pas encore de pistes : l'exploration n'a pas tourné. Rien à dire.
  if (erreur?.startsWith("404")) return null;
  if (erreur) return <div className="erreur">{erreur}</div>;
  if (!catalogue) return null;

  async function choisir(numero: number) {
    try {
      const { id } = await api.choisir(slug, numero);
      surLancement(id);
    } catch (e) {
      setErreur(String(e));
    }
  }

  return (
    <section className="pistes">
      <h3>
        Quatre pistes
        <span className="leger" style={{ marginLeft: 10, fontWeight: 400 }}>
          {catalogue.retenue
            ? `piste ${catalogue.retenue} retenue`
            : "choisis-en une — la recherche part dessus"}
        </span>
      </h3>

      {catalogue.pistes.map((p) => (
        <Carte
          key={p.numero}
          piste={p}
          retenue={catalogue.retenue === p.numero}
          vivant={vivant}
          surChoix={() => choisir(p.numero)}
        />
      ))}
    </section>
  );
}

function Carte({
  piste,
  retenue,
  vivant,
  surChoix,
}: {
  piste: Piste;
  retenue: boolean;
  vivant: boolean;
  surChoix: () => void;
}) {
  // Le dernier titre est le plus agressif — c'est l'ordre que le format
  // impose. C'est lui qu'on met en grand, les autres restent lisibles
  // dessous : le choix du cadrage appartient à l'utilisateur.
  const titres = piste.titres;
  const accroche = titres[titres.length - 1];
  const preuve = (numero: number) =>
    piste.preuves.find((p) => p.numero === numero);

  return (
    <article className={retenue ? "piste retenue" : "piste"}>
      <header>
        <span className="numero">{piste.numero}</span>
        <div>
          <h4>{accroche?.texte ?? piste.resume}</h4>
          <p className="sous">{piste.resume}</p>
        </div>
        <button onClick={surChoix} disabled={vivant}>
          {retenue ? "Relancer la recherche" : "Choisir"}
        </button>
      </header>

      <p className="angle">{piste.angle}</p>
      <p className="pivot"><b>Pivot</b> · {piste.pivot}</p>

      {titres.length > 1 && (
        <div className="autres-titres">
          {titres.slice(0, -1).map((t) => (
            <span key={t.texte}>
              « {t.texte} »
              <em title={preuve(t.preuve)?.texte}> preuve {t.preuve}</em>
            </span>
          ))}
        </div>
      )}

      <ol className="preuves">
        {piste.preuves.map((p) => (
          <li key={p.numero}>
            {p.texte}{" "}
            {p.url && (
              <a href={p.url} target="_blank" rel="noreferrer">
                {p.source || "source"}
              </a>
            )}
          </li>
        ))}
      </ol>

      {piste.risque && <p className="risque">Risque · {piste.risque}</p>}
    </article>
  );
}
