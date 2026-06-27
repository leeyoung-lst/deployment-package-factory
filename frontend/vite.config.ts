import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      "@": "/src",
    },
  },
  server: {
    proxy: {
      "/api": "http://127.0.0.1:8096",
      "/health": "http://127.0.0.1:8096",
    },
  },
});
