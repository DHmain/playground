import { defineConfig } from "vite";
export default defineConfig({
  server: { proxy: { "/api": "http://127.0.0.1:8000" } },
  build: {
    outDir: "dist",
    target: "es2022",
    rollupOptions: {
      input: { main: "index.html", landing: "demos/landing/index.html" },
    },
  },
});
