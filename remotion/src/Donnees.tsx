import React from "react";
import { useCurrentFrame, useVideoConfig } from "remotion";
import { Fond, croissance, reveal } from "./panneau";
import type { MotionStyle } from "./types";

/** Panneaux de données : tableau, barres, proportion, comparaison.
 *
 *  Aucune bibliothèque de graphiques. Dans Remotion, une animation est une
 *  fonction pure de la frame ; une bibliothèque de charts apporterait ses
 *  propres timings, qui se désynchroniseraient du montage au premier
 *  changement de durée de plan. Une échelle linéaire, c'est une division. */

/** Un tableau, révélé ligne par ligne.
 *
 *  Sur un sujet judiciaire c'est souvent le plan le plus fort disponible :
 *  quatre chefs d'accusation en face de quatre décisions disent en une
 *  image ce que la narration met trente secondes à établir. */
export const Tableau: React.FC<{
  titre?: string;
  colonnes: string[];
  lignes: string[][];
  colonne_accent?: number;
  style: MotionStyle;
}> = ({ titre, colonnes, lignes, colonne_accent, style }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const entete = reveal(frame, fps, 0, style.cascade_s);

  return (
    <Fond style={style} titre={titre}>
      <div style={{ display: "grid", gap: 0 }}>
        <div
          style={{
            display: "grid",
            gridTemplateColumns: `repeat(${colonnes.length}, 1fr)`,
            gap: 32,
            paddingBottom: 18,
            borderBottom: `2px solid ${style.attenue}`,
            opacity: entete.progress * 0.75,
            transform: `translateY(${entete.lift}px)`,
          }}
        >
          {colonnes.map((colonne, index) => (
            <div
              key={index}
              style={{
                color: style.attenue,
                fontSize: 26,
                letterSpacing: "0.14em",
                textTransform: "uppercase",
              }}
            >
              {colonne}
            </div>
          ))}
        </div>

        {lignes.map((ligne, index) => {
          const { progress, lift } = reveal(
            frame, fps, index, style.cascade_s, 0.45,
          );
          return (
            <div
              key={index}
              style={{
                display: "grid",
                gridTemplateColumns: `repeat(${colonnes.length}, 1fr)`,
                gap: 32,
                padding: "26px 0",
                borderBottom: `1px solid ${style.attenue}33`,
                opacity: progress,
                transform: `translateY(${lift}px)`,
              }}
            >
              {ligne.map((cellule, colonne) => (
                <div
                  key={colonne}
                  style={{
                    color: colonne === colonne_accent ? style.accent : style.texte,
                    fontSize: 36,
                    fontWeight: colonne === colonne_accent ? 600 : 400,
                    lineHeight: 1.3,
                  }}
                >
                  {cellule}
                </div>
              ))}
            </div>
          );
        })}
      </div>
    </Fond>
  );
};

/** Des barres horizontales qui poussent depuis zéro.
 *
 *  Horizontales et non verticales parce que les libellés sont du texte
 *  français, souvent long : à la verticale il faudrait l'incliner, et un
 *  libellé incliné ne se lit pas en quatre secondes. */
export const Barres: React.FC<{
  titre?: string;
  unite?: string;
  series: { libelle: string; valeur: number }[];
  style: MotionStyle;
}> = ({ titre, unite, series, style }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const maximum = Math.max(...series.map((s) => s.valeur), 1);

  return (
    <Fond style={style} titre={titre}>
      <div style={{ display: "flex", flexDirection: "column", gap: 34 }}>
        {series.map((serie, index) => {
          const depart = 0.35 + index * style.cascade_s;
          const pousse = croissance(frame, fps, 0.9, depart);
          const part = (serie.valeur / maximum) * pousse;
          return (
            <div key={index}>
              <div
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "baseline",
                  marginBottom: 12,
                  color: style.texte,
                  fontSize: 34,
                }}
              >
                <span style={{ opacity: pousse > 0 ? 1 : 0 }}>{serie.libelle}</span>
                <span
                  style={{
                    color: style.accent,
                    fontWeight: 700,
                    fontVariantNumeric: "tabular-nums",
                    opacity: pousse > 0 ? 1 : 0,
                  }}
                >
                  {/* Le chiffre monte avec la barre : lu avant qu'elle
                      s'arrête, il donne l'échelle sans attendre la fin. */}
                  {Math.round(serie.valeur * pousse)}
                  {unite ? ` ${unite}` : ""}
                </span>
              </div>
              <div
                style={{
                  height: 22,
                  borderRadius: 3,
                  backgroundColor: `${style.attenue}22`,
                  overflow: "hidden",
                }}
              >
                <div
                  style={{
                    height: "100%",
                    width: `${part * 100}%`,
                    backgroundColor: style.accent,
                  }}
                />
              </div>
            </div>
          );
        })}
      </div>
    </Fond>
  );
};

/** Une part dans un tout.
 *
 *  Un chiffre isolé ne dit rien tant qu'on ne sait pas de quoi il est la
 *  part. Vingt jours ne veut rien dire ; vingt jours sur cinq ans se voit
 *  d'un coup d'œil, et c'est un pour cent de la barre. */
export const Proportion: React.FC<{
  titre?: string;
  valeur: number;
  total: number;
  libelle: string;
  libelle_total?: string;
  style: MotionStyle;
}> = ({ titre, valeur, total, libelle, libelle_total, style }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const pousse = croissance(frame, fps, 1.1, 0.35);
  const texte = reveal(frame, fps, 0, style.cascade_s, 1.0);
  const part = total > 0 ? valeur / total : 0;

  return (
    <Fond style={style} titre={titre}>
      <div
        style={{
          height: 74,
          borderRadius: 4,
          backgroundColor: `${style.attenue}22`,
          overflow: "hidden",
          position: "relative",
        }}
      >
        <div
          style={{
            height: "100%",
            width: `${part * pousse * 100}%`,
            backgroundColor: style.accent,
            // Une part minuscule disparaîtrait : on garde un trait visible.
            minWidth: pousse > 0.05 ? 6 : 0,
          }}
        />
      </div>

      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          marginTop: 26,
          color: style.attenue,
          fontSize: 30,
        }}
      >
        <span style={{ color: style.accent, fontWeight: 600 }}>{libelle}</span>
        {libelle_total ? <span>{libelle_total}</span> : null}
      </div>

      <div
        style={{
          color: style.texte,
          fontSize: 64,
          fontWeight: 700,
          marginTop: 46,
          fontVariantNumeric: "tabular-nums",
          opacity: texte.progress,
          transform: `translateY(${texte.lift}px)`,
        }}
      >
        {(part * 100).toLocaleString("fr-FR", { maximumFractionDigits: 1 })} %
      </div>
    </Fond>
  );
};

/** Deux colonnes opposées.
 *
 *  Le dispositif central d'un documentaire à pivot : ce que le spectateur
 *  croit d'un côté, ce qui a été établi de l'autre. La colonne de gauche
 *  arrive en premier et celle de droite ensuite, parce que l'ordre est
 *  l'argument. */
export const Comparaison: React.FC<{
  titre?: string;
  gauche: { titre: string; points: string[] };
  droite: { titre: string; points: string[] };
  style: MotionStyle;
}> = ({ titre, gauche, droite, style }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const colonne = (
    contenu: { titre: string; points: string[] },
    retard: number,
    accentue: boolean,
  ) => {
    const tete = reveal(frame, fps, 0, style.cascade_s, retard);
    return (
      <div style={{ flex: 1 }}>
        <div
          style={{
            color: accentue ? style.accent : style.attenue,
            fontSize: 30,
            letterSpacing: "0.12em",
            textTransform: "uppercase",
            paddingBottom: 18,
            borderBottom: `2px solid ${accentue ? style.accent : style.attenue}`,
            opacity: tete.progress,
            transform: `translateY(${tete.lift}px)`,
          }}
        >
          {contenu.titre}
        </div>
        {contenu.points.map((point, index) => {
          const { progress, lift } = reveal(
            frame, fps, index, style.cascade_s, retard + 0.35,
          );
          return (
            <div
              key={index}
              style={{
                color: accentue ? style.texte : `${style.texte}99`,
                fontSize: 36,
                lineHeight: 1.36,
                marginTop: 30,
                opacity: progress,
                transform: `translateY(${lift}px)`,
              }}
            >
              {point}
            </div>
          );
        })}
      </div>
    );
  };

  return (
    <Fond style={style} titre={titre}>
      <div style={{ display: "flex", gap: 80, alignItems: "flex-start" }}>
        {colonne(gauche, 0, false)}
        <div
          style={{
            width: 1,
            alignSelf: "stretch",
            backgroundColor: `${style.attenue}55`,
          }}
        />
        {colonne(droite, 0.9, true)}
      </div>
    </Fond>
  );
};
