#!/usr/bin/env node
// reachai: connect your AI agent to your ReachAI account with one approval in the browser.
import { spawn } from "node:child_process";
import { unlinkSync } from "node:fs";
import { deviceLogin } from "../src/device.mjs";
import { credentialsPath, detect, loadCredentials, printInstructions, saveCredentials, setupClaudeCode, setupCodex, setupCursor, mcpUrl } from "../src/clients.mjs";

const DEFAULT_URL = process.env.REACHAI_URL || "https://reach-ai-influencer-marketing.vercel.app";
const HELP = `reachai: connect your AI agent to ReachAI

  reachai login [--client claude-code|codex|cursor|all|none] [--name "My agent"] [--url ${DEFAULT_URL}] [--no-open]
      Shows a code, you approve it in the browser, and your agent apps are set up. Without --client it sets up the ones it finds.
  reachai status      What's set up on your account (credits, Gmail, payments).
  reachai connect     Print how to add ReachAI to any agent app by hand.
  reachai logout      Forget the saved key on this computer (remove it for good on the Agents page).
`;

function flags(argv) {
  const out = { _: [] };
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    if (a.startsWith("--")) {
      const [k, v] = a.slice(2).split("=");
      out[k] = v !== undefined ? v : argv[i + 1] && !argv[i + 1].startsWith("--") ? argv[++i] : true;
    } else out._.push(a);
  }
  return out;
}

function openBrowser(url) {
  const [cmd, args] = process.platform === "darwin" ? ["open", [url]] : process.platform === "win32" ? ["cmd", ["/c", "start", "", url]] : ["xdg-open", [url]];
  try { spawn(cmd, args, { stdio: "ignore", detached: true }).on("error", () => {}).unref(); } catch { /* the link is printed anyway */ }
}

async function login(f) {
  const appUrl = String(f.url || DEFAULT_URL).replace(/\/$/, "");
  const { api_key } = await deviceLogin({
    appUrl, clientName: String(f.name || "reachai CLI"),
    onCode: (s) => {
      console.log(`\nOpen this link, sign in, check the code is ${s.user_code}, and press Approve:\n\n  ${s.verification_url}\n`);
      if (!f["no-open"]) openBrowser(s.verification_url);
      console.log("Waiting for your approval...");
    },
  });
  const file = saveCredentials({ appUrl, apiKey: api_key });
  console.log(`\nConnected. Your key is saved in ${file} (only you can read it).`);
  const found = detect();
  const want = f.client === "all" ? ["claude-code", "codex", "cursor"] : f.client && f.client !== "none" ? String(f.client).split(",") : f.client === "none" ? [] : Object.keys(found).filter((k) => found[k]);
  if (!want.length) console.log("\nNo agent app found. To add ReachAI to one by hand:\n\n" + printInstructions(appUrl));
  for (const c of want) {
    const r = c === "claude-code" ? setupClaudeCode({ appUrl, apiKey: api_key }) : c === "cursor" ? setupCursor({ appUrl, apiKey: api_key }) : c === "codex" ? setupCodex({ appUrl }) : { text: `Unknown client "${c}" (use claude-code, codex, cursor).` };
    console.log("\n" + r.text);
  }
  console.log("\nNext, in your agent, ask it for the ReachAI account status.");
}

async function status() {
  const c = loadCredentials();
  if (!c) throw new Error("Not logged in. Run: reachai login");
  const get = async (path) => (await fetch(`${c.appUrl}${path}`, { headers: { Authorization: `Bearer ${c.apiKey}` } }));
  const [bal, gm] = await Promise.all([get("/api/billing/balance"), get("/api/gmail")]);
  if (bal.status === 401 || gm.status === 401) throw new Error("The saved key was removed or expired. Run: reachai login");
  const b = bal.ok ? await bal.json() : null;
  const g = gm.ok ? await gm.json() : null;
  console.log(`ReachAI at ${c.appUrl}\nCredits: ${b ? b.balance ?? JSON.stringify(b) : "unknown"}\nGmail: ${g ? (g.connected ? `connected as ${g.email}${g.needs_reconnect ? " (needs reconnecting)" : ""}` : "not connected") : "unknown"}\nMCP server: ${mcpUrl(c.appUrl)}`);
}

const [cmd, ...rest] = process.argv.slice(2);
const f = flags(rest);
try {
  if (cmd === "login") await login(f);
  else if (cmd === "status") await status();
  else if (cmd === "connect") console.log(printInstructions(String(f.url || (loadCredentials() || {}).appUrl || DEFAULT_URL)));
  else if (cmd === "logout") {
    try { unlinkSync(credentialsPath()); console.log("Forgot the saved key. Remove it for good on the Agents page of ReachAI."); } catch { console.log("Nothing was saved."); }
  } else console.log(HELP);
} catch (e) {
  console.error(`\n${e.message}`);
  process.exit(1);
}
