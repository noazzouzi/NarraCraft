import React from "react";
import { AbsoluteFill, interpolate, useCurrentFrame } from "remotion";
import type { Generique as Donnees, MotionStyle, Typographie } from "./types";

/** Le carton de fin. Fixe, pas défilant.
 *
 *  Il existe pour une raison qui n'est pas esthétique : sur le premier film
 *  complet de ce pipeline, 258 visuels sur 329 étaient sous une licence qui
 *  exige l'attribution, et aucun n'était crédité. Le tableau `credits`
 *  était construit depuis toujours dans `timeline.py`, et aucun composant
 *  ne le lisait.
 *
 *  Il ne calcule rien : les groupes, les comptes et la sélection de noms
 *  sont décidés par `timeline.generique`. Ici on met en page. */
export const Generique: React.FC<{
  generique: Donnees;
  style: MotionStyle;
  typographie: Typographie;
}> = ({ generique, style, typographie }) => {
  const frame = useCurrentFrame();
  // Une apparition franche après une coupe noire claque ; une seconde de
  // fondu pose le carton sans le faire attendre.
  const opacite = interpolate(frame, [0, 20], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  return (
    <AbsoluteFill
      style={{
        backgroundColor: style.fond,
        color: style.texte,
        fontFamily: style.famille || typographie.famille,
        padding: "64px 110px",
        display: "flex",
        flexDirection: "column",
        gap: 24,
        opacity: opacite,
      }}
    >
      <h1
        style={{
          margin: 0,
          fontSize: 48,
          fontWeight: 600,
          letterSpacing: "-0.01em",
          color: style.accent,
        }}
      >
        {generique.titre}
      </h1>

      <div style={{ display: "flex", flexDirection: "column", gap: 17, flexGrow: 1 }}>
        {generique.groupes.map((groupe) => (
          <div key={groupe.licence}>
            <div style={{ fontSize: 27, fontWeight: 600 }}>
              {groupe.licence}
              <span style={{ color: style.attenue, fontWeight: 400 }}>
                {"  ·  "}
                {groupe.nombre} visuel{groupe.nombre > 1 ? "s" : ""}
                {groupe.fonds.length > 0 && `  ·  ${groupe.fonds.join(", ")}`}
              </span>
            </div>
            {groupe.auteurs.length > 0 && (
              <div
                style={{
                  fontSize: 21,
                  lineHeight: 1.4,
                  color: style.attenue,
                  marginTop: 4,
                }}
              >
                {groupe.auteurs.join(" · ")}
                {groupe.reste > 0 && ` · et ${groupe.reste} autres`}
              </div>
            )}
          </div>
        ))}

        {generique.libres > 0 && (
          <div style={{ fontSize: 23, color: style.attenue }}>
            {generique.libres} visuels en domaine public ou CC0
          </div>
        )}
      </div>

      <div style={{ fontSize: 21, color: style.attenue }}>
        {generique.mention}
      </div>
    </AbsoluteFill>
  );
};
