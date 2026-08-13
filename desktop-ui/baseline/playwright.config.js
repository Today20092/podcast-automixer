import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: ".",
  testMatch: "baseline.spec.js",
  timeout: 90_000,
  workers: 1,
  reporter: "line",
  use: { baseURL: "http://127.0.0.1:5173", browserName: "chromium", channel: "msedge", colorScheme: "light" },
  webServer: {
    command: "pnpm exec vite --host 127.0.0.1",
    cwd: "..",
    url: "http://127.0.0.1:5173",
    reuseExistingServer: true,
  },
});
