import React from "react";
import { useCurrentFrame, useVideoConfig } from "remotion";
import { Fond, croissance, reveal } from "./panneau";
import type { MotionStyle } from "./types";

type Noeud = { nom: string; role?: string; x?: number; y?: number };
type Lien = { de: number; a: number; libelle?: string };

/** Des personnes, et ce qui les relie.
 *
 *  Sur une affaire d'association de malfaiteurs, c'est une illustration
 *  littérale : l'infraction retenue ne dit pas qu'un homme a reçu de
 *  l'argent, elle dit qu'un groupe s'est organisé. Aucune photographie ne
 *  montre ça. Un graphe, si.
 *
 *  Les positions sont facultatives. Données, elles sont respectées — c'est
 *  le plan visuel qui compose. Absentes, les nœuds se répartissent sur un
 *  cercle, ce qui est déterministe et lisible jusqu'à sept ou huit. On ne
 *  fait volontairement aucun placement par simulation de forces : deux
 *  rendus de la même timeline doivent donner la même image. */
export const Reseau: React.FC<{
  titre?: string;
  noeuds: Noeud[];
  liens?: Lien[];
  style: MotionStyle;
}> = ({ titre, noeuds, liens = [], style }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const largeur = 1640;
  const hauteur = 780;

  const places = noeuds.map((noeud, index) => {
    if (typeof noeud.x === "number" && typeof noeud.y === "number") {
      return { ...noeud, px: noeud.x * largeur, py: noeud.y * hauteur };
    }
    // Cercle, en partant du haut. Le premier nœud est donc toujours en
    // haut au centre : c'est là que l'œil commence.
    const angle = (index / noeuds.length) * Math.PI * 2 - Math.PI / 2;
    return {
      ...noeud,
      px: largeur / 2 + Math.cos(angle) * largeur * 0.33,
      py: hauteur / 2 + Math.sin(angle) * hauteur * 0.36,
    };
  });

  return (
    <Fond style={style} titre={titre}>
      <svg
        viewBox={`0 0 ${largeur} ${hauteur}`}
        style={{ width: "100%", height: "auto", overflow: "visible" }}
      >
        {/* Les liens se tracent avant que les noms arrivent : on voit la
            structure, puis on apprend qui est qui. */}
        {liens.map((lien, index) => {
          const de = places[lien.de];
          const a = places[lien.a];
          if (!de || !a) return null;
          const trace = croissance(frame, fps, 0.6, 0.15 + index * 0.12);
          return (
            <g key={`lien-${index}`}>
              <line
                x1={de.px}
                y1={de.py}
                x2={de.px + (a.px - de.px) * trace}
                y2={de.py + (a.py - de.py) * trace}
                stroke={style.attenue}
                strokeWidth={2}
                opacity={0.6}
              />
              {lien.libelle && trace > 0.95 ? (
                <text
                  x={(de.px + a.px) / 2}
                  y={(de.py + a.py) / 2 - 12}
                  fill={style.attenue}
                  fontSize={22}
                  textAnchor="middle"
                  fontFamily={style.famille}
                >
                  {lien.libelle}
                </text>
              ) : null}
            </g>
          );
        })}

        {places.map((noeud, index) => {
          const { progress } = reveal(
            frame, fps, index, style.cascade_s * 0.7, 0.5,
          );
          return (
            <g key={`noeud-${index}`} opacity={progress}>
              <circle
                cx={noeud.px}
                cy={noeud.py}
                r={13 * progress}
                fill={style.accent}
              />
              <text
                x={noeud.px}
                y={noeud.py - 30}
                fill={style.texte}
                fontSize={34}
                fontWeight={600}
                textAnchor="middle"
                fontFamily={style.famille}
              >
                {noeud.nom}
              </text>
              {noeud.role ? (
                <text
                  x={noeud.px}
                  y={noeud.py + 46}
                  fill={style.attenue}
                  fontSize={24}
                  textAnchor="middle"
                  fontFamily={style.famille}
                >
                  {noeud.role}
                </text>
              ) : null}
            </g>
          );
        })}
      </svg>
    </Fond>
  );
};
