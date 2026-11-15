# Model and prompt benchmarks

Live tests that chose ReachAI's models and prompts. Results and the decisions they led to are in
[`docs/MODEL_BENCHMARKS.md`](../../../docs/MODEL_BENCHMARKS.md).

They call real APIs and cost a few cents, so they are **not** part of `pytest`. Run one from `backend/`:

```bash
python scripts/benchmarks/reason_loop.py
```

Keys: `GOOGLE_API_KEY`, `GROQ_API_KEY` (direct providers), `TYPESAFE_API_KEY` (Jev scores everything), and an
OpenRouter key for the cross-company model comparisons (sent by the environment's proxy, or set
`Authorization` yourself). Raw results are written to `results/` (git-ignored).

| Script | Tests |
|---|---|
| `outreach_reply_models.py`, `direct_providers.py` | Which model writes replies |
| `reason_models.py`, `reason_prompts.py`, `reason_loop.py` | "Why this creator": model, prompt, and the checked loop |
| `reply_agent.py [runs]` | The whole reply agent against 10 simulated creators (pushy, legal question, out of office, manager, opt-out, injection, decline, follow-up…) |
