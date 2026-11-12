import { defineConfig } from "vite";

// Relative base: the built site works at any path (Cloudflare Pages root, a GitHub Pages sub-folder, a local file server).
export default defineConfig({
  base: "./",
  build: { target: "es2022", chunkSizeWarningLimit: 900 },
  server: { host: "127.0.0.1", port: 5180 },
  preview: { host: "127.0.0.1", port: 5181 },
});
