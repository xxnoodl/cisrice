import { defineConfig } from "@playwright/test";
export default defineConfig({
  testDir: "./e2e", workers: 1, retries: 0, timeout: 60000, globalTimeout: 120000,
  reporter: "line", forbidOnly: true,
  use: { baseURL: process.env.CISRICE_E2E_URL ?? "http://127.0.0.1:14173", headless: true, trace: "off" },
});
