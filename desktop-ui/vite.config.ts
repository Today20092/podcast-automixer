import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  test: { include: ["src/**/*.test.ts?(x)"] },
  base: "./",
  resolve: { alias: { "@": new URL("./src", import.meta.url).pathname } },
  build: {
    outDir: "../src/podcast_automixer/desktop-ui",
    emptyOutDir: true,
    assetsDir: "assets",
  },
});
