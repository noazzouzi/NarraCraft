import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { fileURLToPath, URL } from "node:url";

// `@moteur` pointe sur les composants Remotion, qui vivent hors de `web/`.
// C'est volontaire : le lecteur du navigateur et le moteur de rendu jouent
// exactement les mêmes composants, à partir du même `06-timeline.json`. Un
// aperçu qui diverge du film ne servirait à rien.
export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      "@moteur": fileURLToPath(new URL("../remotion/src", import.meta.url)),
    },
    // Les composants vivent dans `remotion/`, qui a ses propres
    // `node_modules`. Sans ça, deux copies de React se retrouvent dans la
    // page et tous les hooks cassent — « Cannot read properties of null
    // (reading 'useMemo') ». Le symptôme ne dit pas la cause.
    dedupe: ["react", "react-dom", "remotion"],
  },
  server: {
    fs: { allow: [".."] },
    proxy: {
      "/api": { target: "http://127.0.0.1:4321", changeOrigin: true },
    },
  },
});
