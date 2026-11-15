import asyncio, os, time, statistics, httpx, json
SYSTEM = "You write short, warm negotiation emails from a startup founder to a content creator. Never invent facts. 60-120 words, plain text."
USER = ("FACTS: brand Lumen, a habit-tracking app; goal signups; fair price $150-210; our last offer $150.\n"
        "CONVERSATION: you: 'Hi Priya, loved your morning-routine video... would you be open to a collaboration with Lumen?' "
        "creator: 'Thanks! My rate for a 60s integration is $320. Also, do you need usage rights for ads?'\n"
        "Write the founder's reply: counter at $195 + 10% commission on signups. Usage rights are not decided: say you'll confirm.")
async def gemini(c, model):
    r = await c.post(f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
        headers={"x-goog-api-key": os.environ["GOOGLE_API_KEY"]},
        json={"systemInstruction": {"parts": [{"text": SYSTEM}]}, "contents": [{"role": "user", "parts": [{"text": USER}]}]}, timeout=60)
    r.raise_for_status(); j = r.json()
    return j["candidates"][0]["content"]["parts"][-1]["text"], j.get("usageMetadata", {})
async def groq(c, model):
    r = await c.post("https://api.groq.com/openai/v1/chat/completions", headers={"Authorization": f"Bearer {os.environ['GROQ_API_KEY']}"},
        json={"model": model, "messages": [{"role": "system", "content": SYSTEM}, {"role": "user", "content": USER}]}, timeout=60)
    r.raise_for_status(); j = r.json(); return j["choices"][0]["message"]["content"], j.get("usage", {})
MODELS = [("gemini", "gemini-3.5-flash"), ("gemini", "gemini-3.8-flash"), ("gemini", "gemini-3.1-flash-lite"),
          ("gemini", "gemini-pro-latest"), ("gemini", "gemini-3.1-pro-preview"), ("groq", "openai/gpt-oss-120b")]
RESULTS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results")
os.makedirs(RESULTS, exist_ok=True)

async def main():
    out = {}
    async with httpx.AsyncClient() as c:
        for kind, m in MODELS:
            times, errs, sample = [], [], None
            for i in range(5):
                t = time.monotonic()
                try:
                    text, usage = await (gemini(c, m) if kind == "gemini" else groq(c, m))
                    times.append(time.monotonic() - t); sample = text
                except Exception as e:
                    errs.append(f"{type(e).__name__}:{getattr(getattr(e,'response',None),'status_code','')}")
            out[m] = {"ok": len(times), "errors": errs, "median_s": round(statistics.median(times), 2) if times else None,
                      "max_s": round(max(times), 2) if times else None, "sample": sample}
            print(m, out[m]["ok"], "/5 ok", "median", out[m]["median_s"], "max", out[m]["max_s"], errs, flush=True)
    json.dump(out, open(os.path.join(RESULTS, "direct_providers.json"), "w"), indent=1)
asyncio.run(main())
