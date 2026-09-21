import { useEffect, useRef, useState } from "react";
import { api, type Hook as Accroche } from "../api";

// Les quinze premières secondes décident du reste. Elles se valident en
// les entendant : un hook qui ne marche pas s'entend tout de suite, alors
// qu'il peut passer trois relectures en markdown.
export default function Hook({ slug }: { slug: string }) {
  const [hook, setHook] = useState<Accroche | null>(null);
  const [source, setSource] = useState<string | null>(null);
  const [mesure, setMesure] = useState("");
  const [alerte, setAlerte] = useState("");
  const [occupe, setOccupe] = useState(false);
  const [erreur, setErreur] = useState<string | null>(null);
  const lecteur = useRef<HTMLAudioElement>(null);

  useEffect(() => {
    let monte = true;
    api.hook(slug)
      .then((h) => {
        if (!monte) return;
        setHook(h);
        // Un essai déjà synthétisé se réécoute sans repasser par le moteur.
        if (h.fichier) setSource(api.media(slug, h.fichier));
      })
      .catch((e) => monte && setErreur(String(e)));
    return () => { monte = false; };
  }, [slug]);

  if (erreur?.startsWith("404")) return null;
  if (erreur) return <div className="erreur">{erreur}</div>;
  if (!hook) return null;

  async function ecouter() {
    setOccupe(true);
    setErreur(null);
    try {
      const dit = await api.direLeHook(slug);
      setMesure(dit.mesure);
      setAlerte(dit.alerte);
      // Le fichier garde son nom d'une synthèse à l'autre : sans ce
      // paramètre, le navigateur rejoue la version précédente.
      setSource(`${api.media(slug, dit.fichier)}?t=${Date.now()}`);
      requestAnimationFrame(() => lecteur.current?.play().catch(() => {}));
    } catch (e) {
      setErreur(String(e));
    } finally {
      setOccupe(false);
    }
  }

  return (
    <section className="hook">
      <header>
        <div>
          <h3>Le hook</h3>
          <p className="sous">
            {hook.beat} · {hook.mots} mots · {hook.intention}
          </p>
        </div>
        <button onClick={ecouter} disabled={occupe}>
          {occupe ? "Synthèse…" : source ? "Réécouter" : "Écouter le hook"}
        </button>
      </header>

      <p className="texte">{hook.texte}</p>

      {source && <audio ref={lecteur} controls src={source} />}
      {mesure && <p className="mesure mono">{mesure}</p>}
      {alerte && <p className="alerte">{alerte}</p>}
    </section>
  );
}
