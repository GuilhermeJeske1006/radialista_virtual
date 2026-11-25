import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

// A partir do Node 25 o Web Storage nativo vem ligado: sem --localstorage-file
// o localStorage global do Node fica undefined e esconde o do jsdom nos testes.
// A flag existe desde o Node 22; em versoes anteriores nao ha o que desligar.
const nodeMajor = Number(process.versions.node.split(".")[0]);
const workerExecArgv = nodeMajor >= 22 ? ["--no-experimental-webstorage"] : [];

export default defineConfig({
  plugins: [react()],
  test: {
    environment: "jsdom",
    setupFiles: ["./vitest.setup.ts"],
    globals: true,
    exclude: ["node_modules", ".next"],
    poolOptions: {
      forks: { execArgv: workerExecArgv },
    },
    coverage: {
      provider: "v8",
      reporter: ["text", "html"],
      exclude: ["node_modules/", ".next/", "**/*.config.*", "vitest.setup.ts"],
    },
  },
});
