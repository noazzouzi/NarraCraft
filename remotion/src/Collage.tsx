import React from "react";
import {
  AbsoluteFill, Img, interpolate, random, staticFile, useCurrentFrame,
  useVideoConfig,
} from "remotion";
import { EASE_OUT } from "./panneau";
import { attenuee, camera } from "./mouvement";
import { Traitement } from "./Traitement";
import type { CollageStyle, Piece, Planche, Mouvement } from "./types";

/** Le style « collage Vox » : une planche de papier composée, pas une image.
 *
 *  Ce composant ne décide de rien. La liste des pièces, leur place, leur
 *  taille, leur rotation et leur profondeur sont calculées par
 *  `fresque.collage` et voyagent dans `06-timeline.json` — où elles se
 *  relisent et se corrigent à la main. Les couleurs viennent du template.
 *
 *  Ce qui se passe ICI et nulle part ailleurs, c'est le dessin : un bord
 *  déchiré, une trame d'impression, une ombre de papier. C'est la même
 *  frontière que partout : le pipeline dit quoi et où, le moteur dit comment.
 *
 *  Et c'est ce découplage qui paie. Les pièces existent séparément jusqu'à la
 *  dernière frame, donc elles bougent à des vitesses différentes selon leur
 *  profondeur. Une affiche générée par un modèle d'image a ses couches cuites
 *  dans les pixels : elle ne peut que glisser d'un bloc. */

type CollageProps = {
  planche: Planche;
  style: CollageStyle;
  mouvement: Mouvement;
  image: string | null;
  grain?: number;
  vignette?: number;
};

/** Un bord déchiré, en `clip-path`.
 *
 *  Le contour est tiré d'une graine stable, donc deux rendus du même plan
 *  donnent la même déchirure — et deux pièces n'ont jamais la même. Les
 *  amplitudes sont séparées par axe : sur une pièce large, une amplitude
 *  unique en pourcentage ferait onduler le haut deux fois plus que le côté.
 *
 *  `clip-path` et pas un SVG : ça découpe n'importe quel élément, l'image
 *  comprise, et ça reste composé par le GPU. */
function bordDechire(graine: string, ax: number, ay: number, pas = 9): string {
  const points: string[] = [];
  const cote = (
    nom: string, fabrique: (t: number, ecart: number) => [number, number],
  ) => {
    for (let i = 0; i < pas; i++) {
      const t = i / pas;
      const ecart = random(`${graine}:${nom}:${i}`) - 0.5;
      const [x, y] = fabrique(t, ecart * 2);
      points.push(`${x.toFixed(2)}% ${y.toFixed(2)}%`);
    }
  };
  cote("h", (t, e) => [t * 100, e * ay]);
  cote("d", (t, e) => [100 + e * ax, t * 100]);
  cote("b", (t, e) => [100 - t * 100, 100 + e * ay]);
  cote("g", (t, e) => [e * ax, 100 - t * 100]);
  return `polygon(${points.join(", ")})`;
}

/** Une coupe aux ciseaux : droite, mais jamais d'équerre. */
function bordCoupe(graine: string, ax: number, ay: number): string {
  const d = (nom: string) => (random(`${graine}:${nom}`) - 0.5) * 2;
  return `polygon(${d("a") * ax}% ${d("b") * ay}%, ${100 + d("c") * ax}% ${d("d") * ay}%, ` +
    `${100 + d("e") * ax}% ${100 + d("f") * ay}%, ${d("g") * ax}% ${100 + d("h") * ay}%)`;
}

/** Les découpes des accents. Ce sont des formes, pas des décisions : le
 *  pipeline a déjà choisi laquelle va où. */
const DECOUPES: Record<string, string> = {
  triangle: "polygon(50% 2%, 98% 98%, 2% 98%)",
  cercle: "circle(48% at 50% 50%)",
  demi_cercle: "polygon(0% 100%, 0% 50%, 4% 30%, 15% 12%, 33% 2%, 50% 0%, " +
    "67% 2%, 85% 12%, 96% 30%, 100% 50%, 100% 100%)",
  fleche: "polygon(50% 0%, 100% 46%, 68% 46%, 68% 100%, 32% 100%, 32% 46%, 0% 46%)",
  zigzag: "polygon(0% 62%, 12% 6%, 25% 62%, 37% 6%, 50% 62%, 62% 6%, 75% 62%, " +
    "87% 6%, 100% 62%, 87% 100%, 75% 44%, 62% 100%, 50% 44%, 37% 100%, " +
    "25% 44%, 12% 100%, 0% 100%)",
};

/** La trame d'impression, posée sur les aplats.
 *
 *  Un aplat de couleur unie se lit comme du vecteur — c'est exactement le
 *  défaut mesuré sur les essais de génération locale (saturation 187/255
 *  contre 95 attendus). Des points de trame le ramènent à de l'imprimé. */
const trame = (opacite: number, taille: number): React.CSSProperties => ({
  backgroundImage:
    `radial-gradient(circle at 50% 50%, rgba(0,0,0,0.9) 23%, rgba(0,0,0,0) 24%)`,
  backgroundSize: `${taille}px ${taille}px`,
  opacity: opacite,
  mixBlendMode: "soft-light",
});

const Accent: React.FC<{ piece: Piece; style: CollageStyle }> = ({ piece, style }) => (
  <div
    style={{
      width: "100%", height: "100%",
      backgroundColor: piece.couleur === "encre" ? style.encre : style.accent,
      clipPath: DECOUPES[piece.forme] ?? DECOUPES.triangle,
    }}
  >
    <AbsoluteFill style={trame(style.trame * 0.8, 5)} />
  </div>
);

const Ruban: React.FC<{ piece: Piece; style: CollageStyle }> = ({ piece, style }) => (
  <div
    style={{
      width: "100%", height: "100%",
      backgroundColor: style.adhesif,
      // Un adhésif arraché n'a pas deux bouts nets, mais ses longs bords le
      // sont : il a été coupé dans un rouleau.
      clipPath: bordDechire(piece.graine, 0, 14, 5),
    }}
  />
);

/** Une feuille de papier : le tampon du fond, ou la photo collée dessus. */
const Papier: React.FC<{
  piece: Piece; style: CollageStyle; image: string | null;
}> = ({ piece, style, image }) => {
  const dechire = piece.bords !== "coupe";
  // L'amplitude est convertie en pourcentage de CHAQUE côté, pour que la
  // déchirure garde la même profondeur en pixels sur les quatre.
  const ax = dechire ? 2.6 : 0.9;
  const ay = ax * (piece.w / Math.max(piece.h, 0.001)) * (9 / 16);
  const decoupe = dechire
    ? bordDechire(piece.graine, ax, ay)
    : bordCoupe(piece.graine, ax * 0.5, ay * 0.5);

  if (piece.role === "bloc" || !image) {
    return (
      <div
        style={{
          width: "100%", height: "100%", clipPath: decoupe,
          backgroundColor: piece.couleur === "encre" ? style.encre : style.accent,
        }}
      >
        <AbsoluteFill style={trame(style.trame, 6)} />
      </div>
    );
  }

  const lisere = style.lisere_px;
  return (
    <div
      style={{
        width: "100%", height: "100%", clipPath: decoupe,
        backgroundColor: style.lisere,
        padding: lisere,
        boxSizing: "border-box",
      }}
    >
      <div style={{ position: "relative", width: "100%", height: "100%", overflow: "hidden" }}>
        <Img
          src={staticFile(image)}
          style={{
            width: "100%", height: "100%", objectFit: "cover",
            filter: style.photo === "brut"
              ? "none"
              : "grayscale(1) contrast(1.3) brightness(0.96)",
          }}
        />
        {/* Duotone : l'encre prend les ombres, le papier relève les hautes
            lumières. Deux fusions plutôt qu'un filtre, parce qu'un filtre CSS
            ne sait pas remplacer une couleur par une autre. */}
        {style.photo === "duotone" ? (
          <>
            <AbsoluteFill
              style={{ backgroundColor: style.accent, mixBlendMode: "multiply", opacity: 0.55 }}
            />
            <AbsoluteFill
              style={{ backgroundColor: style.papier, mixBlendMode: "screen", opacity: 0.10 }}
            />
          </>
        ) : null}
        <AbsoluteFill style={trame(style.trame * 0.65, 4)} />
      </div>
    </div>
  );
};

const CORPS: Record<string, React.FC<{
  piece: Piece; style: CollageStyle; image: string | null;
}>> = {
  papier: Papier,
  ruban: ({ piece, style }) => <Ruban piece={piece} style={style} />,
};

export const Collage: React.FC<CollageProps> = ({
  planche, style, mouvement, image, grain, vignette,
}) => {
  const frame = useCurrentFrame();
  const { durationInFrames, fps } = useVideoConfig();
  const vue = camera(mouvement, frame, durationInFrames);

  return (
    <AbsoluteFill style={{ backgroundColor: style.papier, overflow: "hidden" }}>
      {/* La fibre du papier. Elle est sous tout le reste : ce sont les pièces
          qui sont posées dessus, pas l'inverse. */}
      <Traitement grain={style.grain} vignette={0} />

      {planche.pieces.map((piece, index) => {
        const vueLocale = attenuee(vue, piece.profondeur, style.parallaxe_min);
        // Les pièces arrivent l'une après l'autre, très vite. À vingt-cinq
        // plans par minute une cascade lente mangerait le plan entier ; ce
        // qu'on cherche ici est seulement que la planche ne tombe pas d'un
        // bloc, ce qui se lirait comme une diapositive.
        const depart = index * style.cascade_s * fps;
        const pose = interpolate(frame, [depart, depart + fps * 0.34], [0, 1], {
          easing: EASE_OUT, extrapolateLeft: "clamp", extrapolateRight: "clamp",
        });

        const Corps = CORPS[piece.forme] ?? Accent;
        return (
          <AbsoluteFill
            key={piece.graine}
            style={{
              transform: `translate(${vueLocale.x}%, ${vueLocale.y}%) ` +
                `scale(${vueLocale.scale}) rotate(${vueLocale.rotation}deg)`,
              transformOrigin: "center center",
            }}
          >
            <div
              style={{
                position: "absolute",
                left: `${(piece.x - piece.w / 2) * 100}%`,
                top: `${(piece.y - piece.h / 2) * 100}%`,
                width: `${piece.w * 100}%`,
                height: `${piece.h * 100}%`,
                opacity: pose,
                transform: `rotate(${piece.rotation_deg}deg) ` +
                  `translateY(${(1 - pose) * 14}px) scale(${0.97 + pose * 0.03})`,
                transformOrigin: "center center",
                // L'ombre suit la découpe parce qu'elle est appliquée au
                // PARENT du `clip-path` : un `box-shadow` serait découpé avec
                // la pièce et ne sortirait jamais de ses bords.
                // Mesuré au premier rendu : une ombre de 6 px sur un cadre
                // de 1920 ne se voit pas, et sans ombre les pièces sont
                // peintes sur le papier au lieu d'être posées dessus.
                filter: `drop-shadow(0 ${10 + piece.profondeur * 26}px ` +
                  `${16 + piece.profondeur * 34}px ${style.ombre})`,
              }}
            >
              <Corps piece={piece} style={style} image={image} />
            </div>
          </AbsoluteFill>
        );
      })}

      <Traitement grain={grain} vignette={vignette} />
    </AbsoluteFill>
  );
};
