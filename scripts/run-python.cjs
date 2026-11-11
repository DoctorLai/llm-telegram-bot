const { spawnSync } = require("node:child_process");
const { existsSync } = require("node:fs");
const { join, resolve } = require("node:path");

function run() {
  const projectEnvironment = resolve(__dirname, "..", ".venv");
  const environment = process.env.VIRTUAL_ENV ||
    (existsSync(projectEnvironment) ? projectEnvironment : null);
  const candidates = environment
    ? [process.platform === "win32"
      ? join(environment, "Scripts", "python.exe")
      : join(environment, "bin", "python")]
    : ["python3", "python"];

  for (const executable of candidates) {
    const result = spawnSync(executable, process.argv.slice(2), { stdio: "inherit" });
    if (result.error) {
      if (!environment && result.error.code === "ENOENT") {
        continue;
      }
      console.error(`Cannot start ${executable}: ${result.error.message}`);
      console.error("Check the selected Python environment and its installed dependencies.");
      process.exitCode = 1;
      return;
    }
    if (result.signal) {
      process.kill(process.pid, result.signal);
      return;
    }
    process.exitCode = result.status ?? 1;
    return;
  }

  console.error(
    "Python 3.11+ was not found. Install Python and create .venv, " +
    "then install requirements-dev.txt as described in CONTRIBUTING.md."
  );
  process.exitCode = 1;
}

run();
