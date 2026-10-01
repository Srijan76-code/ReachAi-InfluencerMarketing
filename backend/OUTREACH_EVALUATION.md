# Outreach Evaluation

The evaluation suite uses the real ranked leads in `data/influencer_list.py`. It creates 28 cases: each of the seven leads is evaluated across four collaboration/campaign variants. No golden pitch text is stored.

## Deterministic tests

From `backend/`:

```bash
pytest tests/evals -q
```

These tests cover schema, creator and brand identity, collaboration, deliverables, available channels, evidence IDs, forbidden internal scores, question limits, dataset balance, batch identity, and graph checkpoint configuration. They do not call an LLM.

## Seed a LangSmith dataset

Set the existing LangSmith environment variables, then run:

```bash
python -m tests.evals.runner --seed-only
```

The seed is idempotent for `reach-ai-outreach-real-leads-v1`.

## Run an experiment

```bash
python -m tests.evals.runner --experiment-prefix outreach-v1
```

The runner invokes the same `build_outreach_graph()` used by the product, with an in-memory checkpointer for dataset execution. Production jobs continue using the Postgres checkpointer in `app/outreach/runtime.py`. The run uses one generation call per creator and the graph's existing optional repair path; the judge makes one structured call per case.

LangSmith receives code evaluator metrics for schema, identity, collaboration, deliverables, channel set, evidence, question count, forbidden data, and non-empty channels. The single LLM judge returns groundedness, personalization, campaign relevance, naturalness, channel fit, value proposition, CTA quality, creator specificity, issues, and an aggregate weighted score.

Use the LangSmith experiment comparison view to compare prompt/model versions. Open an individual example trace to inspect prepared creator input, generation, validation, repair, latency, and model token metadata when the configured integration exposes it.
