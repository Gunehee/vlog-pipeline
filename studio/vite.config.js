import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Production build is committed to vlog_pipeline/webdist so a fresh clone
// (or pip install) serves the studio with no node toolchain present.
export default defineConfig({
  plugins: [react()],
  build: {
    outDir: "../vlog_pipeline/webdist",
    emptyOutDir: true,
  },
  server: {
    proxy: {
      "/api": "http://127.0.0.1:5175",
      "/media": "http://127.0.0.1:5175",
    },
  },
});
