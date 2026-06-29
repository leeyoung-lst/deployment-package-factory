import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [react()],
  build: {
    chunkSizeWarningLimit: 750,
    rollupOptions: {
      output: {
        manualChunks(id) {
          const normalizedId = id.replace(/\\/g, "/");
          if (!normalizedId.includes("node_modules")) return undefined;
          if (normalizedId.includes("/node_modules/.pnpm/remixicon@") || normalizedId.includes("/node_modules/remixicon/")) {
            return "vendor-icons";
          }
          if (
            normalizedId.includes("/node_modules/.pnpm/react@") ||
            normalizedId.includes("/node_modules/.pnpm/react-dom@") ||
            normalizedId.includes("/node_modules/react/") ||
            normalizedId.includes("/node_modules/react-dom/") ||
            normalizedId.includes("/node_modules/scheduler/")
          ) {
            return "vendor-react";
          }
          return "vendor";
        },
      },
    },
  },
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
