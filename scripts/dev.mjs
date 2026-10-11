#!/usr/bin/env node
/**
 * Лаунчер монорепо без внешних зависимостей.
 *
 *   node scripts/dev.mjs                 → бэкенд (uvicorn) + фронтенд (vite) параллельно
 *   node scripts/dev.mjs --only backend  → только бэкенд
 *   node scripts/dev.mjs --only frontend → только фронтенд
 *   node scripts/dev.mjs --pytest        → pytest (backend/tests)
 *   node scripts/dev.mjs --batch         → batch_eval.py --input-dir data/samples
 *   node scripts/dev.mjs --samples       → scripts/make_samples.py (генерация синтетики)
 *   node scripts/dev.mjs --models        → scripts/download_models.py (прогрев кэша моделей)
 *   node scripts/dev.mjs --dataset       → scripts/download_dataset.py --limit 50
 *
 * Порт бэкенда можно переопределить: UVICORN_PORT=8001 node scripts/dev.mjs
 * Путь к Python-венву: PY_BIN (по умолчанию .venv рядом с корнем).
 */
import { spawn } from "node:child_process";
import { existsSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const BACKEND = path.join(ROOT, "backend");
const FRONTEND = path.join(ROOT, "frontend");

function resolvePython() {
  if (process.env.PY_BIN) return process.env.PY_BIN;
  const candidates = [
    path.join(ROOT, ".venv", "Scripts", "python.exe"), // Windows
    path.join(ROOT, ".venv", "bin", "python"),          // Linux / Colab
  ];
  const found = candidates.find((p) => existsSync(p));
  if (!found) {
    console.error("Не найден venv. Создайте: python -m venv .venv && pip install -r backend/requirements.txt");
    process.exit(1);
  }
  return found;
}

const PY = resolvePython();
const flag = process.argv[2] ?? "";

/** Запуск процесса с префиксом у каждой строки вывода. shell не нужен:
 * пути с кириллицей через cmd искажают вывод, а .cmd-файлы запускаем сами. */
function run(name, command, args, cwd) {
  const child = spawn(command, args, { cwd });
  const pipe = (stream, isError) => {
    let buffer = "";
    stream.on("data", (chunk) => {
      buffer += chunk.toString();
      const lines = buffer.split("\n");
      buffer = lines.pop() ?? "";
      for (const line of lines) {
        if (line.trim()) console.log(`${isError ? "\x1b[31m" : ""}[${name}] ${line}\x1b[0m`);
      }
    });
  };
  pipe(child.stdout);
  pipe(child.stderr, true);
  return child;
}

const children = [];

function stopAll() {
  for (const child of children) {
    if (!child.killed) {
      try {
        child.kill("SIGTERM");
        if (process.platform === "win32") {
          spawn("taskkill", ["/pid", String(child.pid), "/T", "/F"], { stdio: "ignore" });
        }
      } catch {}
    }
  }
}
process.on("SIGINT", () => {
  stopAll();
  process.exit(0);
});

const PORT = process.env.UVICORN_PORT ?? "8000";

if (["--pytest", "--batch", "--samples", "--models", "--dataset"].includes(flag)) {
  const limit = process.argv.includes("--limit") ? process.argv[process.argv.indexOf("--limit") + 1] : "50";
  const jobs = {
    "--pytest": [PY, ["-m", "pytest", "tests", "-q"], BACKEND],
    "--batch": [PY, ["batch_eval.py", "--input-dir", "data/samples", "--output", "results.json"], BACKEND],
    "--samples": [PY, ["scripts/make_samples.py"], ROOT],
    "--models": [PY, ["scripts/download_models.py"], ROOT],
    "--dataset": [PY, ["scripts/download_dataset.py", "--limit", limit], ROOT],
  }[flag];
  const [cmd, args, cwd] = jobs;
  const child = run("py", cmd, args, cwd);
  child.on("exit", (code) => process.exit(code ?? 0));
} else {
  const only = process.argv.includes("--only") ? process.argv[process.argv.indexOf("--only") + 1] : null;

  if (only !== "frontend") {
    children.push(run("api", PY, ["-m", "uvicorn", "app.main:app", "--reload", "--port", PORT], BACKEND));
  }
  if (only !== "backend") {
    // npm run dev внутри воркспейса; на Windows .cmd запускаем через cmd.exe /c
    const isWin = process.platform === "win32";
    children.push(
      isWin
        ? run("web", "cmd.exe", ["/c", "npm", "run", "dev"], FRONTEND)
        : run("web", "npm", ["run", "dev"], FRONTEND),
    );
  }

  const io = setInterval(() => {}, 1 << 30); // держим процесс живым
  for (const child of children) {
    child.on("exit", (code) => {
      if (children.some((c) => !c.killed && c !== child)) {
        console.log(`[${child === children[0] ? "api" : "web"}] процесс завершился (${code}), останавливаю остальные…`);
        stopAll();
        clearInterval(io);
        process.exit(code ?? 0);
      }
    });
  }
}
