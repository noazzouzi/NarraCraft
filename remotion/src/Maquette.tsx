import React from "react";
import { useCurrentFrame, useVideoConfig } from "remotion";
import { croissance, reveal } from "./panneau";
import { AbsoluteFill } from "remotion";
import type { MotionStyle } from "./types";

/** Une fenêtre de navigateur, construite et jamais capturée.
 *
 *  Sur un sujet dont le point de départ est une publication en ligne, la
 *  capture d'écran est le plan évident — et elle est sous droits, datée
 *  d'une mise en page qui a changé depuis, et impossible à sourcer
 *  proprement. Ce panneau en fabrique une : il énonce le nom du site et la
 *  date comme des faits, il ne reproduit aucune maquette existante.
 *
 *  La même règle que le panneau `journal` s'applique, et le pipeline la
 *  fait respecter : ne jamais attribuer à un média réel un titre qu'il n'a
 *  pas publié, et toujours porter la source. Un faux plausible est l'écart
 *  le plus grave possible sur un sujet judiciaire. */
export const Maquette: React.FC<{
  site: string;
  url?: string;
  date?: string;
  titre: string;
  chapeau?: string;
  source: string;
  style: MotionStyle;
}> = ({ site, url, date, titre, chapeau, source, style }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const fenetre = croissance(frame, fps, 0.7);
  const entete = reveal(frame, fps, 0, style.cascade_s, 0.5);
  const corps = reveal(frame, fps, 1, style.cascade_s, 0.5);
  const attribution = reveal(frame, fps, 3, style.cascade_s, 0.5);

  return (
    <AbsoluteFill
      style={{
        backgroundColor: style.fond,
        fontFamily: style.famille,
        alignItems: "center",
        justifyContent: "center",
        padding: "0 120px",
      }}
    >
      <div
        style={{
          width: "100%",
          maxWidth: 1400,
          borderRadius: 14,
          overflow: "hidden",
          backgroundColor: "#ffffff",
          boxShadow: "0 48px 130px rgba(0,0,0,0.72)",
          opacity: fenetre,
          transform: `translateY(${(1 - fenetre) * 30}px) scale(${0.97 + fenetre * 0.03})`,
        }}
      >
        {/* La barre de fenêtre. Trois pastilles et une adresse : c'est tout
            ce qu'il faut pour qu'on lise « une page web » en une demi-seconde. */}
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: 14,
            padding: "16px 22px",
            backgroundColor: "#e9eaee",
            borderBottom: "1px solid #d3d5db",
          }}
        >
          {["#ff5f57", "#febc2e", "#28c840"].map((couleur) => (
            <div
              key={couleur}
              style={{
                width: 15, height: 15, borderRadius: 8, backgroundColor: couleur,
              }}
            />
          ))}
          <div
            style={{
              flex: 1,
              marginLeft: 16,
              padding: "9px 18px",
              borderRadius: 8,
              backgroundColor: "#ffffff",
              color: "#5c6270",
              fontSize: 22,
              overflow: "hidden",
              whiteSpace: "nowrap",
              textOverflow: "ellipsis",
            }}
          >
            {url || site.toLowerCase().replace(/\s+/g, "")}
          </div>
        </div>

        <div style={{ padding: "54px 64px 62px" }}>
          <div
            style={{
              display: "flex",
              justifyContent: "space-between",
              alignItems: "baseline",
              color: "#8a90a0",
              fontSize: 24,
              letterSpacing: "0.14em",
              textTransform: "uppercase",
              opacity: entete.progress,
              transform: `translateY(${entete.lift}px)`,
            }}
          >
            <span style={{ color: "#1c1f26", fontWeight: 700 }}>{site}</span>
            {date ? <span>{date}</span> : null}
          </div>

          <div
            style={{
              color: "#14171d",
              fontSize: 62,
              fontWeight: 700,
              lineHeight: 1.16,
              letterSpacing: "-0.02em",
              marginTop: 34,
              opacity: corps.progress,
              transform: `translateY(${corps.lift}px)`,
            }}
          >
            {titre}
          </div>

          {chapeau ? (
            <div
              style={{
                color: "#4b5263",
                fontSize: 34,
                lineHeight: 1.45,
                marginTop: 28,
                opacity: corps.progress,
                transform: `translateY(${corps.lift}px)`,
              }}
            >
              {chapeau}
            </div>
          ) : null}
        </div>
      </div>

      {/* La source sous la fenêtre, hors de la maquette. Elle dit que ce
          qu'on vient de voir est une reconstitution, pas une capture. */}
      <div
        style={{
          color: style.attenue,
          fontSize: 24,
          marginTop: 30,
          opacity: attribution.progress,
        }}
      >
        {source}
      </div>
    </AbsoluteFill>
  );
};
