import test from "node:test";
import assert from "node:assert/strict";
import { createServer } from "node:http";
import { runDoctor } from "../src/doctor.mjs";

const TOOLS = ["account_status", "list_campaigns", "read_website", "create_campaign", "start_search", "request_permission", "my_permissions",
  "inbox", "reply_context", "submit_reply", "send_message", "track_summary", "add_to_deals", "set_autopilot", "track_setup", "track_snippet"];

/** A pretend ReachAI. `opts` switch on things a broken deployment would do. */
function mock(opts = {}) {
  const log = [];
  const server = createServer((req, res) => {
    let body = "";
    req.on("data", (c) => (body += c));
    req.on("end", () => {
      const auth = req.headers.authorization;
      log.push(`${req.method} ${req.url}`);
      const json = (status, data) => { res.statusCode = status; res.setHeader("content-type", "application/json"); res.end(JSON.stringify(data)); };
      if (req.url === "/llms.txt") { res.setHeader("content-type", "text/plain"); return res.end(opts.oldVersion ? "# ReachAI" : "# ReachAI\n### Sign in without copying a key (device login)"); }
      if (req.url === "/api/mcp") {
        if (auth !== "Bearer rai_good" && !opts.acceptAnyKey) return json(401, { error: "invalid" });
        const rpc = JSON.parse(body);
        if (rpc.method === "tools/list") return json(200, { jsonrpc: "2.0", id: rpc.id, result: { tools: TOOLS.filter((t) => !(opts.missing || []).includes(t)).map((name) => ({ name })) } });
        const name = rpc.params.name;
        const ok = (text, data = {}) => json(200, { jsonrpc: "2.0", id: rpc.id, result: { content: [{ type: "text", text }], structuredContent: data, isError: false } });
        if (name === "account_status") return ok("status", { credits: { balance: 3 }, gmail: { connected: false }, payments_open: false });
        if (name === "my_permissions") return ok("perms", { permissions: opts.approved ? [{ ability: "manage_campaign", status: "approved", campaign_id: "c1" }] : [] });
        if (name === "list_campaigns") return ok("campaigns", { campaigns: opts.noCampaign ? [] : [{ id: "c1" }] });
        if (name === "request_permission") return ok("asked", { approval_url: "http://x/grant?code=BCDF-GHJK" });
        if (name === "track_snippet") return ok("snippet", { snippet: "<script>" });
        return json(200, { jsonrpc: "2.0", id: rpc.id, result: { content: [{ type: "text", text: "nope" }], isError: true } });
      }
      if (auth !== "Bearer rai_good") return json(401, {});
      if (req.url === "/api/gmail") return json(200, { connected: false });
      if (opts.keyCanDoAnything) return json(200, {});
      return json(403, { detail: "An API key can't use this endpoint." });
    });
  });
  return new Promise((r) => server.listen(0, "127.0.0.1", () => r({ server, log, url: `http://127.0.0.1:${server.address().port}` })));
}

const byName = (results, name) => results.find((r) => r.name === name);

test("a healthy deployment passes every check and says what the account has", async () => {
  const m = await mock();
  const r = await runDoctor({ appUrl: m.url, apiKey: "rai_good" });
  m.server.close();
  assert.deepEqual(r.filter((x) => x.status === "fail"), []);
  assert.equal(byName(r, "Account status").detail, "credits 3, Gmail not connected, payments not open");
  assert.equal(byName(r, "Your key lists the tools").detail, `${TOOLS.length} tools`);
  assert.equal(byName(r, "A permission round trip").status, "skip");
  assert.ok(m.log.includes("POST /api/keys"), "it tried to mint a key with the key, and must have been refused");
});

test("it never starts a search, sends, or changes a plan (it only calls read and ask tools)", async () => {
  const calls = [];
  const m = await mock();
  const real = globalThis.fetch;
  const spy = async (url, init) => { if (init && init.body && String(url).endsWith("/api/mcp")) { const b = JSON.parse(init.body); if (b.method === "tools/call") calls.push(b.params.name); } return real(url, init); };
  await runDoctor({ appUrl: m.url, apiKey: "rai_good", fetchFn: spy });
  m.server.close();
  assert.deepEqual(calls.sort(), ["account_status", "my_permissions"]);
});

test("it fails loudly when a key can do something it must not", async () => {
  const m = await mock({ keyCanDoAnything: true });
  const r = await runDoctor({ appUrl: m.url, apiKey: "rai_good" });
  m.server.close();
  const bad = byName(r, "Your key is refused where it must be");
  assert.equal(bad.status, "fail");
  assert.match(bad.detail, /POST \/api\/keys returned 200, expected 403/);
});

test("it fails when a wrong key is accepted", async () => {
  const m = await mock({ acceptAnyKey: true });
  const r = await runDoctor({ appUrl: m.url, apiKey: "rai_good" });
  m.server.close();
  assert.equal(byName(r, "A wrong key is refused").status, "fail");
});

test("it names the tools that are missing (an old deployment)", async () => {
  const m = await mock({ missing: ["send_message", "track_snippet"], oldVersion: true });
  const r = await runDoctor({ appUrl: m.url, apiKey: "rai_good" });
  m.server.close();
  assert.match(byName(r, "Your key lists the tools").detail, /missing: send_message, track_snippet/);
  assert.equal(byName(r, "The server answers and tells agents how to connect").status, "fail");
});

test("a key that was removed gets the fix in plain words", async () => {
  const m = await mock();
  const r = await runDoctor({ appUrl: m.url, apiKey: "rai_removed" });
  m.server.close();
  const t = byName(r, "Your key lists the tools");
  assert.equal(t.status, "fail");
  assert.match(t.detail, /run reachai login/);
});

test("with --grant it asks, waits for the approval, tries the tool and tells you to remove it", async () => {
  const approved = await mock({ approved: true });
  const seen = [];
  const r = await runDoctor({ appUrl: approved.url, apiKey: "rai_good", grant: true, wait: async () => {}, log: (x) => seen.push(x) });
  approved.server.close();
  const round = byName(r, "A permission round trip");
  assert.equal(round.status, "pass");
  assert.match(round.detail, /Remove it now/);
  assert.ok(seen.some((x) => x.status === "info" && /grant\?code=BCDF-GHJK/.test(x.detail)));
});

test("with --grant and nothing approved it times out without harm", async () => {
  const m = await mock();
  const r = await runDoctor({ appUrl: m.url, apiKey: "rai_good", grant: true, wait: async () => {}, grantWaitMs: 1 });
  m.server.close();
  assert.equal(byName(r, "A permission round trip").status, "fail");
  assert.match(byName(r, "A permission round trip").detail, /nothing changed/);
});

test("with --grant and no campaign it skips instead of failing", async () => {
  const m = await mock({ noCampaign: true });
  const r = await runDoctor({ appUrl: m.url, apiKey: "rai_good", grant: true, wait: async () => {} });
  m.server.close();
  assert.equal(byName(r, "A permission round trip").status, "skip");
});
