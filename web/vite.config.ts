import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// En développement, l'interface tourne sur 5173 et l'API sur 4321.
// Le proxy évite d'écrire une adresse absolue dans le code du front :
// `fetch("/api/...")` marche des deux côtés, dev comme production.
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      "/api": { target: "http://127.0.0.1:4321", changeOrigin: true },
    },
  },
});
