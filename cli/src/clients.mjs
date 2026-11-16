// Setting up an agent app to use ReachAI. Each function returns what it did, in words, so the person can see it.
import { existsSync, mkdirSync, readFileSync, writeFileSync, chmodSync } from "node:fs";
import { homedir } from "node:os";
import { dirname, join } from "node:path";
import { spawnSync } from "node:child_process";

export const mcpUrl = (appUrl) => `${appUrl.replace(/\/$/, "")}/api/mcp`;

export function credentialsPath(home = homedir()) {
  return join(home, ".config", "reachai", "credentials.json");
}

export function saveCredentials({ appUrl, apiKey, home = homedir() }) {
  const file = credentialsPath(home);
  mkdirSync(dirname(file), { recursive: true });
  writeFileSync(file, JSON.stringify({ appUrl, apiKey, savedAt: new Date().toISOString() }, null, 2) + "\n", { mode: 0o600 });
  try { chmodSync(file, 0o600); } catch { /* not supported on this system */ }
  return file;
}

export function loadCredentials(home = homedir()) {
  try { return JSON.parse(readFileSync(credentialsPath(home), "utf8")); } catch { return null; }
}

/** Claude Code: `claude mcp add` (the app's own command), so its config format is never guessed. */
export function setupClaudeCode({ appUrl, apiKey, run = spawnSync }) {
  const args = ["mcp", "add", "--transport", "http", "--scope", "user", "reachai", mcpUrl(appUrl), "--header", `Authorization: Bearer ${apiKey}`];
  const r = run("claude", args, { encoding: "utf8" });
  if (r.error || r.status !== 0) {
    const why = (r.stderr || (r.error && r.error.message) || "").toString().trim().split("\n")[0];
    return { ok: false, text: `Claude Code: couldn't run "claude mcp add"${why ? ` (${why})` : ""}. Run it yourself:\n  claude mcp add --transport http --scope user reachai ${mcpUrl(appUrl)} --header "Authorization: Bearer <your key>"` };
  }
  return { ok: true, text: "Claude Code: added the ReachAI server (user scope). Start a new session to use it." };
}

/** Cursor: merge into ~/.cursor/mcp.json, keeping everything else in the file. */
export function setupCursor({ appUrl, apiKey, home = homedir() }) {
  const file = join(home, ".cursor", "mcp.json");
  let json = {};
  if (existsSync(file)) {
    try { json = JSON.parse(readFileSync(file, "utf8") || "{}"); } catch { return { ok: false, text: `Cursor: ${file} isn't valid JSON, so I left it alone. Add the server yourself (see "reachai connect --print").` }; }
  }
  json.mcpServers = { ...(json.mcpServers || {}), reachai: { url: mcpUrl(appUrl), headers: { Authorization: `Bearer ${apiKey}` } } };
  mkdirSync(dirname(file), { recursive: true });
  writeFileSync(file, JSON.stringify(json, null, 2) + "\n", { mode: 0o600 });
  return { ok: true, text: `Cursor: added ReachAI to ${file}. Restart Cursor to use it.` };
}

/** Codex: append a server block that reads the key from an environment variable (the key never goes into the file). */
export function setupCodex({ appUrl, home = homedir() }) {
  const file = join(home, ".codex", "config.toml");
  const current = existsSync(file) ? readFileSync(file, "utf8") : "";
  if (/\[mcp_servers\.reachai\]/.test(current)) return { ok: true, text: `Codex: ${file} already has a reachai server; left it as it is.` };
  const block = `${current && !current.endsWith("\n") ? "\n" : ""}\n[mcp_servers.reachai]\nurl = "${mcpUrl(appUrl)}"\nbearer_token_env_var = "REACHAI_API_KEY"\n`;
  mkdirSync(dirname(file), { recursive: true });
  writeFileSync(file, current + block);
  return { ok: true, text: `Codex: added ReachAI to ${file}. Codex reads the key from REACHAI_API_KEY: run  export REACHAI_API_KEY=$(node -e "console.log(JSON.parse(require('fs').readFileSync(process.env.HOME+'/.config/reachai/credentials.json')).apiKey)")  (or add it to your shell profile).` };
}

export function detect({ home = homedir(), hasCommand = (c) => spawnSync(c, ["--version"], { encoding: "utf8" }).status === 0 } = {}) {
  return { "claude-code": hasCommand("claude"), codex: existsSync(join(home, ".codex")), cursor: existsSync(join(home, ".cursor")) };
}

export function printInstructions(appUrl) {
  const url = mcpUrl(appUrl);
  return [
    "Claude Code:", `  claude mcp add --transport http --scope user reachai ${url} --header "Authorization: Bearer <your key>"`, "",
    "Cursor (~/.cursor/mcp.json):", `  {"mcpServers": {"reachai": {"url": "${url}", "headers": {"Authorization": "Bearer <your key>"}}}}`, "",
    "Codex (~/.codex/config.toml):", "  [mcp_servers.reachai]", `  url = "${url}"`, '  bearer_token_env_var = "REACHAI_API_KEY"', "",
    `Your key is saved in ${credentialsPath()} (readable only by you). Never paste it into a chat or commit it.`,
  ].join("\n");
}
