import React from "react";
import { interpolate, useCurrentFrame, useVideoConfig } from "remotion";
import { Carte } from "./Carte";
import { Barres, Comparaison, Proportion, Tableau } from "./Donnees";
import { Document } from "./Document";
import { Journal } from "./Journal";
import { Maquette } from "./Maquette";
import { Reseau } from "./Reseau";
import { EASE_OUT, Fond, Scene, reveal } from "./panneau";
import type { MotionStyle } from "./types";

/** A dated timeline. The single most useful panel on a judicial or
 *  historical subject: it replaces the illustrative photograph nobody has. */
export const Chronologie: React.FC<{
  titre?: string;
  evenements: { date: string; texte: string }[];
  style: MotionStyle;
}> = ({ titre, evenements, style }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  // The line draws itself first, then the events land on it.
  const ligne = interpolate(frame, [0, fps * 0.8], [0, 1], {
    easing: EASE_OUT,
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  return (
    <Fond style={style} titre={titre}>
      <div style={{ position: "relative", paddingTop: 30 }}>
        <div
          style={{
            position: "absolute",
            top: 30,
            left: 0,
            height: 2,
            width: `${ligne * 100}%`,
            backgroundColor: style.attenue,
            opacity: 0.45,
          }}
        />
        <div style={{ display: "flex", justifyContent: "space-between", gap: 40 }}>
          {evenements.map((evenement, index) => {
            const { progress, lift } = reveal(
              frame, fps, index, style.cascade_s, 0.7,
            );
            return (
              <div
                key={index}
                style={{
                  flex: 1,
                  opacity: progress,
                  transform: `translateY(${lift}px)`,
                }}
              >
                <div
                  style={{
                    width: 14,
                    height: 14,
                    borderRadius: 7,
                    backgroundColor: style.accent,
                    marginTop: -36,
                    marginBottom: 34,
                  }}
                />
                <div style={{ color: style.accent, fontSize: 34, fontWeight: 600 }}>
                  {evenement.date}
                </div>
                <div
                  style={{
                    color: style.texte,
                    fontSize: 30,
                    lineHeight: 1.35,
                    marginTop: 12,
                  }}
                >
                  {evenement.texte}
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </Fond>
  );
};

/** A quotation with its source. On a judicial subject the exact wording of a
 *  ruling carries more weight than any picture of a courthouse. */
export const Citation: React.FC<{
  texte: string;
  source: string;
  style: MotionStyle;
}> = ({ texte, source, style }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const corps = reveal(frame, fps, 0, style.cascade_s);
  const attribution = reveal(frame, fps, 1, style.cascade_s, 0.4);

  return (
    <Fond style={style}>
      <div style={{ display: "flex", gap: 44 }}>
        <div
          style={{
            width: 4,
            backgroundColor: style.accent,
            opacity: corps.progress,
            transformOrigin: "top",
            transform: `scaleY(${corps.progress})`,
          }}
        />
        <div style={{ flex: 1 }}>
          <div
            style={{
              color: style.texte,
              fontSize: 54,
              lineHeight: 1.42,
              opacity: corps.progress,
              transform: `translateY(${corps.lift}px)`,
            }}
          >
            {texte}
          </div>
          <div
            style={{
              color: style.attenue,
              fontSize: 28,
              marginTop: 44,
              letterSpacing: "0.04em",
              opacity: attribution.progress,
              transform: `translateY(${attribution.lift}px)`,
            }}
          >
            {source}
          </div>
        </div>
      </div>
    </Fond>
  );
};

/** One figure, and what it compares to. A number without a concrete
 *  comparison leaves no trace — the same rule the writing skill applies. */
export const Chiffre: React.FC<{
  valeur: string;
  libelle: string;
  comparaison?: string;
  style: MotionStyle;
}> = ({ valeur, libelle, comparaison, style }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const nombre = reveal(frame, fps, 0, style.cascade_s);
  const texte = reveal(frame, fps, 1, style.cascade_s);
  const compare = reveal(frame, fps, 2, style.cascade_s);

  return (
    <Fond style={style}>
      <div style={{ textAlign: "center" }}>
        <div
          style={{
            color: style.accent,
            fontSize: 190,
            fontWeight: 700,
            lineHeight: 1,
            letterSpacing: "-0.03em",
            opacity: nombre.progress,
            transform: `translateY(${nombre.lift}px)`,
          }}
        >
          {valeur}
        </div>
        <div
          style={{
            color: style.texte,
            fontSize: 46,
            marginTop: 28,
            opacity: texte.progress,
            transform: `translateY(${texte.lift}px)`,
          }}
        >
          {libelle}
        </div>
        {comparaison ? (
          <div
            style={{
              color: style.attenue,
              fontSize: 32,
              marginTop: 38,
              opacity: compare.progress,
              transform: `translateY(${compare.lift}px)`,
            }}
          >
            {comparaison}
          </div>
        ) : null}
      </div>
    </Fond>
  );
};

/** Dispatch on `motion.kind`. The shape was validated by the pipeline at the
 *  visual-plan checkpoint, so an unknown kind here means the two drifted. */
export const MotionGraphic: React.FC<{
  motion: Record<string, unknown>;
  style: MotionStyle;
  fond?: string | null;
}> = ({ motion, style, fond }) => (
  <Scene style={style} image={fond}>
    <Panneau motion={motion} style={style} />
  </Scene>
);

const Panneau: React.FC<{
  motion: Record<string, unknown>;
  style: MotionStyle;
}> = ({ motion, style }) => {
  switch (motion.kind) {
    case "chronologie":
      return (
        <Chronologie
          titre={motion.titre as string | undefined}
          evenements={motion.evenements as { date: string; texte: string }[]}
          style={style}
        />
      );
    case "citation":
      return (
        <Citation
          texte={motion.texte as string}
          source={motion.source as string}
          style={style}
        />
      );
    case "chiffre":
      return (
        <Chiffre
          valeur={motion.valeur as string}
          libelle={motion.libelle as string}
          comparaison={motion.comparaison as string | undefined}
          style={style}
        />
      );
    case "carte":
      return (
        <Carte
          titre={motion.titre as string | undefined}
          marqueurs={motion.marqueurs as { nom: string; coord: [number, number] }[]}
          relier={motion.relier as boolean | undefined}
          pays={motion.pays as string[] | undefined}
          style={style}
        />
      );
    case "document":
      return (
        <Document
          entete={motion.entete as string | undefined}
          reference={motion.reference as string | undefined}
          lignes={motion.lignes as string[]}
          surligne={motion.surligne as number | undefined}
          surligne_frame={motion.surligne_frame as number | undefined}
          ecriture={motion.ecriture as string | undefined}
          style={style}
        />
      );
    case "tableau":
      return (
        <Tableau
          titre={motion.titre as string | undefined}
          colonnes={motion.colonnes as string[]}
          lignes={motion.lignes as string[][]}
          colonne_accent={motion.colonne_accent as number | undefined}
          style={style}
        />
      );
    case "barres":
      return (
        <Barres
          titre={motion.titre as string | undefined}
          unite={motion.unite as string | undefined}
          series={motion.series as { libelle: string; valeur: number }[]}
          style={style}
        />
      );
    case "proportion":
      return (
        <Proportion
          titre={motion.titre as string | undefined}
          valeur={motion.valeur as number}
          total={motion.total as number}
          libelle={motion.libelle as string}
          libelle_total={motion.libelle_total as string | undefined}
          style={style}
        />
      );
    case "comparaison":
      return (
        <Comparaison
          titre={motion.titre as string | undefined}
          gauche={motion.gauche as { titre: string; points: string[] }}
          droite={motion.droite as { titre: string; points: string[] }}
          style={style}
        />
      );
    case "reseau":
      return (
        <Reseau
          titre={motion.titre as string | undefined}
          noeuds={motion.noeuds as { nom: string; role?: string }[]}
          liens={motion.liens as { de: number; a: number; libelle?: string }[]}
          style={style}
        />
      );
    case "maquette":
      return (
        <Maquette
          site={motion.site as string}
          url={motion.url as string | undefined}
          date={motion.date as string | undefined}
          titre={motion.titre as string}
          chapeau={motion.chapeau as string | undefined}
          source={motion.source as string}
          style={style}
        />
      );
    case "journal":
      return (
        <Journal
          journal={motion.journal as string}
          date={motion.date as string}
          titre={motion.titre as string}
          chapeau={motion.chapeau as string | undefined}
          surligne_frame={motion.surligne_frame as number | undefined}
          style={style}
        />
      );
    default:
      return (
        <Fond style={style}>
          <div style={{ color: style.attenue, fontSize: 36 }}>
            motion.kind inconnu : {String(motion.kind)}
          </div>
        </Fond>
      );
  }
};
