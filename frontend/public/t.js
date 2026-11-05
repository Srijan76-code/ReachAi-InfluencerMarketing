/* ReachAI signup snippet (docs: /docs/track). Remembers which creator's link brought a visitor (?ref=CODE, for
   30 days, on your site only) and, on your thank-you page, tells ReachAI about one signup for that creator.
   No cookies, nothing about the person is sent: only the creator's code. */
(function () {
  var s = document.currentScript;
  if (!s) return;
  var key = s.getAttribute("data-key");
  var api = new URL(s.src).origin;
  var KEEP = 30 * 864e5;
  try {
    var ref = new URLSearchParams(location.search).get("ref");
    if (ref) localStorage.setItem("reachai_ref", JSON.stringify({ ref: ref, at: Date.now() }));
  } catch (e) {}
  window.reachai = function (kind) {
    try {
      kind = kind === "sale" ? "sale" : "signup";
      var saved = JSON.parse(localStorage.getItem("reachai_ref") || "null");
      if (!saved || Date.now() - saved.at > KEEP) return;
      var done = "reachai_" + kind;
      if (localStorage.getItem(done) === saved.ref) return; // once per visitor
      navigator.sendBeacon(api + "/api/t/" + encodeURIComponent(key), JSON.stringify({ ref: saved.ref, kind: kind }));
      localStorage.setItem(done, saved.ref);
    } catch (e) {}
  };
  if (s.hasAttribute("data-signup")) window.reachai("signup");
  if (s.hasAttribute("data-sale")) window.reachai("sale");
})();
