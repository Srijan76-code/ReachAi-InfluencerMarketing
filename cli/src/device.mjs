// Device login: ask ReachAI for a code, let the person approve it in the browser, then collect the key (shown once).
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

async function post(fetchFn, url, body) {
  const res = await fetchFn(url, { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify(body) });
  let data = null;
  try { data = await res.json(); } catch { /* not JSON */ }
  if (!res.ok) {
    const detail = data && typeof data.detail === "string" ? data.detail : `HTTP ${res.status}`;
    const err = new Error(detail);
    err.status = res.status;
    throw err;
  }
  return data;
}

/** → { api_key }. `onCode({ user_code, verification_url, expires_in })` shows the person what to do. */
export async function deviceLogin({ appUrl, clientName, onCode, fetchFn = fetch, wait = sleep }) {
  const start = await post(fetchFn, `${appUrl}/api/device/start`, { client_name: clientName });
  await onCode(start);
  const deadline = Date.now() + start.expires_in * 1000;
  let interval = (start.interval || 5) * 1000;
  while (Date.now() < deadline + 5000) {
    await wait(interval);
    const r = await post(fetchFn, `${appUrl}/api/device/poll`, { device_code: start.device_code });
    if (r.status === "approved") return { api_key: r.api_key };
    if (r.status === "denied") throw new Error("You denied the connection. Nothing was set up.");
    if (r.status === "expired") throw new Error("The code expired. Run the command again.");
    if (r.status === "used") throw new Error("This sign-in was already collected. Run the command again.");
    if (r.status === "slow_down") interval += 2000;
  }
  throw new Error("Timed out waiting for approval. Run the command again.");
}
