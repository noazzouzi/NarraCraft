import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { Player } from "@remotion/player";
import { Documentaire } from "@moteur/Documentaire";
import type { Timeline } from "@moteur/types";

// `Window.remotion_staticBase` est déjà déclaré par Remotion : on ne le
// redéclare pas, on s'en sert.

export default function Apercu() {
  const { slug = "" } = useParams();
  const [timeline, setTimeline] = useState<Timeline | null>(null);
  const [erreur, setErreur] = useState<string | null>(null);

  // `staticFile("05-visuals/S000.jpg")` doit rendre l'adresse de la route
  // média de CE projet. Remotion lit cette base globale, donc elle est
  // posée avant que le lecteur ne monte — et remise à jour si on change de
  // projet sans recharger la page.
  window.remotion_staticBase = `/api/projets/${slug}/media`;

  useEffect(() => {
    fetch(`/api/projets/${slug}/timeline`)
      .then(async (r) => {
        if (!r.ok) throw new Error(await r.text());
        return r.json();
      })
      .then(setTimeline)
      .catch((e) => setErreur(String(e)));
  }, [slug]);

  return (
    <div className="apercu">
      <header>
        <Link to={`/projets/${slug}`} className="leger">← Le projet</Link>
        {timeline && (
          <span className="leger mono">
            {timeline.clips.length} plans · {Math.round(timeline.duree_frames / timeline.fps)} s ·{" "}
            {timeline.width}×{timeline.height} · {timeline.fps} fps
          </span>
        )}
      </header>

      {erreur && <div className="erreur">{erreur}</div>}

      {timeline && (
        <div className="scene">
          <Player
            component={Documentaire}
            inputProps={timeline}
            durationInFrames={Math.max(timeline.duree_frames, 1)}
            fps={timeline.fps}
            compositionWidth={timeline.width}
            compositionHeight={timeline.height}
            style={{ width: "100%" }}
            controls
            doubleClickToFullscreen
            acknowledgeRemotionLicense
          />
        </div>
      )}

      {!timeline && !erreur && <p className="vide">Lecture du montage…</p>}

      <p className="leger" style={{ maxWidth: 760 }}>
        Ce lecteur joue les mêmes composants que le moteur de rendu, à partir du
        même <span className="mono">06-timeline.json</span>. Ce que tu vois ici
        est ce que le mp4 contiendra — sans attendre le rendu.
      </p>
    </div>
  );
}
