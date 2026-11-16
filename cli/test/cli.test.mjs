import test from "node:test";
import assert from "node:assert/strict";
import { createServer } from "node:http";
import { spawn } from "node:child_process";
import { mkdtempSync, readFileSync, writeFileSync, mkdirSync, existsSync, statSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import { deviceLogin } from "../src/device.mjs";
import { credentialsPath, detect, loadCredentials, mcpUrl, saveCredentials, setupClaudeCode, setupCodex, setupCursor } from "../src/clients.mjs";

const CLI = fileURLToPath(new URL("../bin/reachai.mjs", import.meta.url));
const tmp = () => mkdtempSync(join(tmpdir(), "reachai-cli-"));

/** A pretend ReachAI: start gives a code; poll answers from a script. */
function mockServer(pollAnswers, { interval = 1 } = {}) {
  const calls = [];
  const server = createServer((req, res) => {
    let body = "";
    req.on("data", (c) => (body += c));
    req.on("end", () => {
      calls.push({ method: req.method, url: req.url, body: body ? JSON.parse(body) : null, auth: req.headers.authorization });
      res.setHeader("content-type", "application/json");
      if (req.url === "/api/device/start") return res.end(JSON.stringify({ device_code: "secret-device-code-1234567890", user_code: "BCDF-GHJK", verification_url: "http://example.test/device?code=BCDF-GHJK", expires_in: 600, interval }));
      if (req.url === "/api/device/poll") return res.end(JSON.stringify(pollAnswers.shift() ?? { status: "pending" }));
      if (req.url === "/api/billing/balance") return res.end(JSON.stringify({ balance: 7, plan: "free" }));
      if (req.url === "/api/gmail") return res.end(JSON.stringify({ connected: true, email: "me@example.com", needs_reconnect: false }));
      res.statusCode = 404; res.end("{}");
    });
  });
  return new Promise((resolve) => server.listen(0, "127.0.0.1", () => resolve({ server, calls, url: `http://127.0.0.1:${server.address().port}` })));
}

test("device login shows the code, waits through pending and slow_down, and returns the key", async () => {
  const m = await mockServer([{ status: "pending" }, { status: "slow_down" }, { status: "approved", api_key: "rai_testkey" }]);
  const waits = [];
  let shown;
  const r = await deviceLogin({ appUrl: m.url, clientName: "Claude Code", onCode: (s) => (shown = s), wait: async (ms) => waits.push(ms) });
  m.server.close();
  assert.equal(r.api_key, "rai_testkey");
  assert.equal(shown.user_code, "BCDF-GHJK");
  assert.deepEqual(waits, [1000, 1000, 3000]); // slow_down made it wait longer
  assert.equal(m.calls[0].body.client_name, "Claude Code");
  assert.ok(m.calls.slice(1).every((c) => c.body.device_code === "secret-device-code-1234567890"));
});

for (const [status, words] of [["denied", /denied/], ["expired", /expired/], ["used", /already collected/]]) {
  test(`device login stops cleanly on ${status}`, async () => {
    const m = await mockServer([{ status }]);
    await assert.rejects(deviceLogin({ appUrl: m.url, clientName: "x", onCode: () => {}, wait: async () => {} }), words);
    m.server.close();
  });
}

test("device login reports a server refusal in the server's own words", async () => {
  const fetchFn = async () => ({ ok: false, status: 429, json: async () => ({ detail: "Too many sign-in requests from this address." }) });
  await assert.rejects(deviceLogin({ appUrl: "http://x", clientName: "x", onCode: () => {}, fetchFn }), /Too many sign-in requests/);
});

test("the key is saved where only the user can read it, and read back", () => {
  const home = tmp();
  const file = saveCredentials({ appUrl: "https://app.example", apiKey: "rai_abc", home });
  assert.equal(file, credentialsPath(home));
  if (process.platform !== "win32") assert.equal(statSync(file).mode & 0o777, 0o600);
  assert.deepEqual({ ...loadCredentials(home), savedAt: undefined }, { appUrl: "https://app.example", apiKey: "rai_abc", savedAt: undefined });
  assert.equal(loadCredentials(tmp()), null);
});

test("Cursor: merges the server in and keeps everything else; refuses to touch a broken file", () => {
  const home = tmp();
  mkdirSync(join(home, ".cursor"));
  writeFileSync(join(home, ".cursor", "mcp.json"), JSON.stringify({ mcpServers: { other: { url: "https://o" } }, theme: "dark" }));
  const r = setupCursor({ appUrl: "https://app.example/", apiKey: "rai_k", home });
  const j = JSON.parse(readFileSync(join(home, ".cursor", "mcp.json"), "utf8"));
  assert.ok(r.ok);
  assert.deepEqual(j.mcpServers.reachai, { url: "https://app.example/api/mcp", headers: { Authorization: "Bearer rai_k" } });
  assert.equal(j.mcpServers.other.url, "https://o");
  assert.equal(j.theme, "dark");
  const bad = tmp();
  mkdirSync(join(bad, ".cursor"));
  writeFileSync(join(bad, ".cursor", "mcp.json"), "{ not json");
  assert.equal(setupCursor({ appUrl: "https://a", apiKey: "k", home: bad }).ok, false);
  assert.equal(readFileSync(join(bad, ".cursor", "mcp.json"), "utf8"), "{ not json");
});

test("Codex: appends once, and the key never goes into the file", () => {
  const home = tmp();
  mkdirSync(join(home, ".codex"));
  writeFileSync(join(home, ".codex", "config.toml"), 'model = "x"\n');
  const first = setupCodex({ appUrl: "https://app.example", home });
  const toml = readFileSync(join(home, ".codex", "config.toml"), "utf8");
  assert.ok(first.ok && toml.includes('model = "x"') && toml.includes("[mcp_servers.reachai]") && toml.includes('bearer_token_env_var = "REACHAI_API_KEY"'));
  assert.ok(!toml.includes("rai_"));
  const again = setupCodex({ appUrl: "https://app.example", home });
  assert.match(again.text, /already has/);
  assert.equal(readFileSync(join(home, ".codex", "config.toml"), "utf8"), toml);
});

test("Claude Code: runs the app's own command, and says what to run if it can't", () => {
  let seen;
  const ok = setupClaudeCode({ appUrl: "https://app.example", apiKey: "rai_k", run: (cmd, args) => ((seen = [cmd, args]), { status: 0 }) });
  assert.ok(ok.ok);
  assert.deepEqual(seen[1].slice(0, 6), ["mcp", "add", "--transport", "http", "--scope", "user"]);
  assert.ok(seen[1].includes("https://app.example/api/mcp") && seen[1].includes("Authorization: Bearer rai_k"));
  const missing = setupClaudeCode({ appUrl: "https://app.example", apiKey: "rai_k", run: () => ({ error: new Error("spawn claude ENOENT"), status: null }) });
  assert.ok(!missing.ok && missing.text.includes("claude mcp add") && !missing.text.includes("rai_k"));
});

test("detect finds the agent apps that are installed", () => {
  const home = tmp();
  mkdirSync(join(home, ".cursor"));
  assert.deepEqual(detect({ home, hasCommand: () => false }), { "claude-code": false, codex: false, cursor: true });
  assert.equal(mcpUrl("https://a.example/"), "https://a.example/api/mcp");
});

function runCli(args, home) {
  return new Promise((resolve) => {
    const p = spawn(process.execPath, [CLI, ...args], { env: { ...process.env, HOME: home, USERPROFILE: home }, stdio: ["ignore", "pipe", "pipe"] });
    let out = "", err = "";
    p.stdout.on("data", (c) => (out += c));
    p.stderr.on("data", (c) => (err += c));
    p.on("close", (code) => resolve({ code, out, err }));
  });
}

test("the command works end to end: login, status, logout", async () => {
  const m = await mockServer([{ status: "pending" }, { status: "approved", api_key: "rai_endtoend" }]);
  const home = tmp();
  const login = await runCli(["login", "--client", "none", "--no-open", "--url", m.url], home);
  assert.equal(login.code, 0, login.err);
  assert.match(login.out, /BCDF-GHJK/);
  assert.match(login.out, /Connected/);
  assert.equal(JSON.parse(readFileSync(credentialsPath(home), "utf8")).apiKey, "rai_endtoend");
  const status = await runCli(["status"], home);
  assert.equal(status.code, 0, status.err);
  assert.match(status.out, /Credits: 7/);
  assert.match(status.out, /connected as me@example.com/);
  assert.ok(m.calls.filter((c) => c.url === "/api/gmail").every((c) => c.auth === "Bearer rai_endtoend"));
  const out = await runCli(["logout"], home);
  assert.match(out.out, /Forgot/);
  assert.equal(existsSync(credentialsPath(home)), false);
  const after = await runCli(["status"], home);
  assert.equal(after.code, 1);
  assert.match(after.err, /Not logged in/);
  m.server.close();
});

test("the command prints a clear message when the person denies", async () => {
  const m = await mockServer([{ status: "denied" }]);
  const r = await runCli(["login", "--client", "none", "--no-open", "--url", m.url], tmp());
  m.server.close();
  assert.equal(r.code, 1);
  assert.match(r.err, /denied/);
});
