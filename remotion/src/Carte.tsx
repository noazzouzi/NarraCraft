import React from "react";
import { AbsoluteFill, Easing, interpolate, useCurrentFrame, useVideoConfig } from "remotion";
import { geoMercator, geoPath, geoInterpolate } from "d3-geo";
import { feature } from "topojson-client";
import world from "world-atlas/countries-110m.json";
import type { MotionStyle } from "./types";

const EASE_OUT = Easing.bezier(0.16, 1, 0.3, 1);

// 110m resolution: 105 KB for 177 countries. Enough detail for a full-frame
// map at 1080p, and it parses once when the bundle loads.
const COUNTRIES = feature(world as any, (world as any).objects.countries) as any;

export type Marqueur = { nom: string; coord: [number, number] };

/** Widen a degenerate bounding box.
 *
 *  Two markers span a line, not a box, and fitting a projection to a line
 *  asks it for infinite scale. Padding proportionally — with a floor, so a
 *  single marker still gets a region around it — keeps the subject framed
 *  rather than filling the screen with one coastline. */
function cadre(marqueurs: Marqueur[]): [[number, number], [number, number]] {
  const lons = marqueurs.map((m) => m.coord[0]);
  const lats = marqueurs.map((m) => m.coord[1]);
  const [x0, x1] = [Math.min(...lons), Math.max(...lons)];
  const [y0, y1] = [Math.min(...lats), Math.max(...lats)];

  const marge = Math.max((x1 - x0) * 0.45, (y1 - y0) * 0.45, 7);
  return [
    [x0 - marge, Math.max(y0 - marge, -82)],
    [x1 + marge, Math.min(y1 + marge, 82)],
  ];
}

export const Carte: React.FC<{
  titre?: string;
  marqueurs: Marqueur[];
  relier?: boolean;
  pays?: string[];
  style: MotionStyle;
}> = ({ titre, marqueurs, relier, pays, style }) => {
  const frame = useCurrentFrame();
  const { fps, width, height } = useVideoConfig();

  const [coinSud, coinNord] = cadre(marqueurs);
  // A MultiPoint, not a Polygon. d3-geo reads a ring on a sphere by its
  // winding order, and a rectangle wound the wrong way means "everything
  // except this rectangle" — which fits the whole globe into the frame
  // instead of the two cities. Measured: scale 124 against 1081.
  const projection = geoMercator().fitExtent(
    [[110, 150], [width - 110, height - 150]],
    { type: "MultiPoint", coordinates: [coinSud, coinNord] } as any,
  );
  const chemin = geoPath(projection);

  const apparition = interpolate(frame, [0, fps * 0.9], [0, 1], {
    easing: EASE_OUT, extrapolateLeft: "clamp", extrapolateRight: "clamp",
  });

  const misEnAvant = new Set((pays ?? []).map((p) => p.toLowerCase()));

  // The connecting arc follows a great circle, which is what a route between
  // two distant places actually looks like — a straight line on a Mercator
  // map reads as a graphic, not a journey.
  const debutTrace = 0.6 + marqueurs.length * style.cascade_s;
  const trace = interpolate(
    frame, [debutTrace * fps, (debutTrace + 1.1) * fps], [0, 1],
    { easing: EASE_OUT, extrapolateLeft: "clamp", extrapolateRight: "clamp" },
  );

  const arc = (a: Marqueur, b: Marqueur) => {
    const entre = geoInterpolate(a.coord, b.coord);
    const points = Array.from({ length: 48 }, (_, i) => entre(i / 47));
    const visibles = points.slice(0, Math.max(2, Math.round(points.length * trace)));
    return chemin({ type: "LineString", coordinates: visibles } as any) ?? "";
  };

  return (
    <AbsoluteFill style={{ fontFamily: style.famille }}>
      <svg width={width} height={height} style={{ opacity: apparition }}>
        {COUNTRIES.features.map((pays_: any, index: number) => {
          const nom = String(pays_.properties?.name ?? "").toLowerCase();
          const vedette = misEnAvant.has(nom);
          return (
            <path
              key={index}
              d={chemin(pays_) ?? ""}
              fill={vedette ? style.accent : "#1b2027"}
              fillOpacity={vedette ? 0.22 : 1}
              stroke={vedette ? style.accent : "#2c333d"}
              strokeWidth={vedette ? 1.6 : 0.8}
            />
          );
        })}

        {relier && marqueurs.length > 1
          ? marqueurs.slice(0, -1).map((m, i) => (
              <path
                key={`arc${i}`}
                d={arc(m, marqueurs[i + 1])}
                fill="none"
                stroke={style.accent}
                strokeWidth={2.5}
                strokeDasharray="7 7"
                opacity={trace > 0 ? 0.9 : 0}
              />
            ))
          : null}

        {marqueurs.map((marqueur, index) => {
          const depart = (0.6 + index * style.cascade_s) * fps;
          const pose = interpolate(frame, [depart, depart + fps * 0.45], [0, 1], {
            easing: EASE_OUT, extrapolateLeft: "clamp", extrapolateRight: "clamp",
          });
          const position = projection(marqueur.coord);
          if (!position) return null;
          const [x, y] = position;
          return (
            <g key={marqueur.nom} opacity={pose}>
              <circle cx={x} cy={y} r={26 * (1 - pose) + 9} fill={style.accent}
                      fillOpacity={0.18} />
              <circle cx={x} cy={y} r={7} fill={style.accent} />
              <text
                x={x + 20}
                y={y + 9}
                fill={style.texte}
                fontSize={30}
                fontWeight={600}
                style={{ paintOrder: "stroke", stroke: style.fond, strokeWidth: 5 }}
              >
                {marqueur.nom}
              </text>
            </g>
          );
        })}
      </svg>

      {titre ? (
        <div
          style={{
            position: "absolute",
            top: 72,
            left: 110,
            color: style.attenue,
            fontSize: 30,
            letterSpacing: "0.18em",
            textTransform: "uppercase",
            opacity: apparition,
          }}
        >
          {titre}
        </div>
      ) : null}
    </AbsoluteFill>
  );
};
