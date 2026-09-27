import { resolve } from "node:path";
import tailwindcss from "@tailwindcss/vite";
import { defineConfig } from "vite";

const dashboard = resolve(import.meta.dirname, "src/wp_main/dashboard");

export default defineConfig({
  plugins: [tailwindcss()],
  publicDir: false,
  build: {
    // ソースと出力のずれを確かめるテストは、一時ディレクトリに出力させて比べる
    outDir: process.env.DASHBOARD_OUT_DIR || resolve(dashboard, "static/dist"),
    emptyOutDir: true,
    // テンプレートは {% static 'dist/dashboard.css' %} で固定の名前を読むため、ハッシュを付けない
    rollupOptions: {
      input: resolve(dashboard, "frontend/main.js"),
      output: {
        entryFileNames: "dashboard.js",
        assetFileNames: "dashboard[extname]",
      },
    },
  },
});
