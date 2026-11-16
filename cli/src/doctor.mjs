// `reachai doctor`: checks a live ReachAI with the saved key. It reads and asks; it never starts a search, sends a message or
// changes a plan. With --grant it also asks for one permission and waits for you to approve it in the browser.
const CORE_TOOLS = [
  "account_status", "list_campaigns", "read_website", "create_campaign", "start_search", "request_permission", "my_permissions",
  "inbox", "reply_context", "submit_reply", "send_message", "track_summary", "add_to_deals", "set_autopilot", "track_setup", "track_snippet",
];
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

async function parse(res) {
  const type = res.headers.get("content-type") || "";
  const text = await res.text();
  if (type.includes("event-stream")) {
    const last = text.split("\n").filter((l) => l.startsWith("data:")).pop();
    return last ? JSON.parse(last.slice(5)) : null;
  }
  try { return JSON.parse(text); } catch { return null; }
}

export function mcpClient({ appUrl, apiKey, fetchFn = fetch }) {
  let id = 0;
  const rpc = async (method, params = {}, key = apiKey) => {
    const res = await fetchFn(`${appUrl}/api/mcp`, {
      method: "POST",
      headers: { "content-type": "application/json", accept: "application/json, text/event-stream", ...(key ? { authorization: `Bearer ${key}` } : {}) },
      body: JSON.stringify({ jsonrpc: "2.0", id: ++id, method, params }),
    });
    return { status: res.status, body: res.status === 200 ? await parse(res) : null };
  };
  const tool = async (name, args = {}) => {
    const r = await rpc("tools/call", { name, arguments: args });
    const result = r.body && r.body.result;
    return { status: r.status, isError: !!(result && result.isError), text: result && result.content && result.content[0] ? result.content[0].text : "", data: (result && result.structuredContent) || {} };
  };
  return { rpc, tool };
}

/** → [{ name, status: "pass" | "fail" | "skip", detail }] */
export async function runDoctor({ appUrl, apiKey, fetchFn = fetch, grant = false, wait = sleep, log = () => {}, grantWaitMs = 5 * 60 * 1000 }) {
  const out = [];
  const add = (name, status, detail = "") => { out.push({ name, status, detail }); log({ name, status, detail }); };
  const auth = { authorization: `Bearer ${apiKey}` };
  const mcp = mcpClient({ appUrl, apiKey, fetchFn });
  const attempt = async (name, fn) => { try { await fn(); } catch (e) { add(name, "fail", e.message); } };

  await attempt("The server answers and tells agents how to connect", async () => {
    const r = await fetchFn(`${appUrl}/llms.txt`);
    const t = await r.text();
    if (r.status !== 200) throw new Error(`/llms.txt returned ${r.status}`);
    add("The server answers and tells agents how to connect", /device login/i.test(t) ? "pass" : "fail", /device login/i.test(t) ? "" : "/llms.txt doesn't mention the device login (is the new version deployed?)");
  });

  await attempt("A wrong key is refused", async () => {
    const r = await mcp.rpc("tools/list", {}, "rai_this_is_not_a_real_key");
    add("A wrong key is refused", r.status === 401 ? "pass" : "fail", r.status === 401 ? "" : `expected 401, got ${r.status}`);
  });

  await attempt("Your key lists the tools", async () => {
    const r = await mcp.rpc("tools/list");
    if (r.status !== 200 || !r.body) throw new Error(r.status === 401 ? "the saved key isn't valid any more: run reachai login" : `HTTP ${r.status}`);
    const names = new Set(((r.body.result || {}).tools || []).map((t) => t.name));
    const missing = CORE_TOOLS.filter((n) => !names.has(n));
    add("Your key lists the tools", missing.length ? "fail" : "pass", missing.length ? `missing: ${missing.join(", ")} (is the new version deployed?)` : `${names.size} tools`);
  });

  await attempt("Account status", async () => {
    const r = await mcp.tool("account_status");
    if (r.isError) throw new Error(r.text);
    const d = r.data;
    add("Account status", "pass", `credits ${d.credits ? d.credits.balance : "?"}, Gmail ${d.gmail && d.gmail.connected ? "connected" : "not connected"}, payments ${d.payments_open ? "open" : "not open"}`);
  });

  await attempt("Your key works on an allowed web endpoint", async () => {
    const r = await fetchFn(`${appUrl}/api/gmail`, { headers: auth });
    add("Your key works on an allowed web endpoint", r.status === 200 ? "pass" : "fail", r.status === 200 ? "" : `GET /api/gmail returned ${r.status}`);
  });

  await attempt("Your key is refused where it must be", async () => {
    const tries = [["POST", "/api/keys", { name: "doctor" }], ["GET", "/api/device/lookup?code=BCDF-GHJK", null], ["POST", "/api/grants/decision", { code: "BCDF-GHJK", approve: true }],
                   ["POST", "/api/billing/checkout", { item: "pack_10" }], ["PUT", "/api/campaigns/none/autopilot", { autopilot: true }]];
    const bad = [];
    for (const [method, path, body] of tries) {
      const r = await fetchFn(`${appUrl}${path}`, { method, headers: { ...auth, "content-type": "application/json" }, body: body ? JSON.stringify(body) : undefined });
      if (r.status !== 403) bad.push(`${method} ${path} returned ${r.status}, expected 403`);
    }
    add("Your key is refused where it must be", bad.length ? "fail" : "pass", bad.join("; "));
  });

  await attempt("Permissions can be listed", async () => {
    const r = await mcp.tool("my_permissions");
    add("Permissions can be listed", r.isError ? "fail" : "pass", r.isError ? r.text : "");
  });

  if (!grant) {
    add("A permission round trip", "skip", "run with --grant to ask for one and approve it in the browser");
  } else {
    await attempt("A permission round trip", async () => {
      const campaigns = await mcp.tool("list_campaigns");
      const first = (campaigns.data.campaigns || [])[0];
      if (!first) return add("A permission round trip", "skip", "no campaign to ask about: make one first");
      const asked = await mcp.tool("request_permission", { campaign_id: first.id || first.campaign_id, ability: "manage_campaign", days: 1, client_name: "reachai doctor" });
      if (asked.isError) throw new Error(asked.text);
      log({ name: "Approve it", status: "info", detail: `Open ${asked.data.approval_url} and press Approve (waiting up to ${Math.round(grantWaitMs / 60000)} minutes)` });
      const until = Date.now() + grantWaitMs;
      let allowed = false;
      while (Date.now() < until && !allowed) {
        await wait(3000);
        const p = await mcp.tool("my_permissions");
        allowed = (p.data.permissions || []).some((g) => g.ability === "manage_campaign" && g.status === "approved" && g.campaign_id === (first.id || first.campaign_id));
      }
      if (!allowed) return add("A permission round trip", "fail", "not approved in time (it lapses by itself; nothing changed)");
      const snippet = await mcp.tool("track_snippet", { campaign_id: first.id || first.campaign_id });
      add("A permission round trip", snippet.isError ? "fail" : "pass", snippet.isError ? snippet.text : "approved, and the tool worked. Remove it now on the Agents page of ReachAI.");
    });
  }
  return out;
}
