import { defineConfig } from "@playwright/test";
export default defineConfig({
  testDir: "./tests",
  workers: 1,
  timeout: 90000,
  use: { baseURL: "http://127.0.0.1:8765", headless: true },
  webServer: [
    {
      command: "python3 -B game_test.py --port 8765",
      url: "http://127.0.0.1:8765",
      reuseExistingServer: false,
    },
    {
      command: "python3 -B server.py --bind 127.0.0.1 --port 8766",
      url: "http://127.0.0.1:8766",
      reuseExistingServer: false,
    },
  ],
});
