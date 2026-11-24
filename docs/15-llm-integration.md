# 15 — LLM integration

## 1. Where the model runs

Only on the backend. The frontend never receives a provider key, never calls a model endpoint, and cannot
select a model. `frontend/lib/api.ts` only talks to `/api/v1/*` on the same origin.

```
Browser --POST /api/v1/assistant/chat--> FastAPI
                                          |-- permission check (assistant:use)
                                          |-- tenant-scoped retrieval (scores, events, risk)
                                          |-- build prompt + grounding block
                                          |-- if LLM_API_KEY: call provider (server-side)
                                          |-- else: local template renderer
                                          <-- reply + grounding + disclaimer + mode
```

## 2. Modes

| Mode | Trigger | Behaviour | Labelling |
| --- | --- | --- | --- |
| `local` | `LLM_API_KEY` empty (default) | Deterministic template answers built from retrieved data | UI badge "Local mode · no external model"; response `mode: "local"` |
| `llm` | `LLM_API_KEY` set | OpenAI-compatible chat completion, temperature 0.2, grounded context injected | UI badge shows model name; response `mode: "llm"`, `model`, `latency_ms` |

Both modes return the same response shape, so the UI does not branch on availability — only on labelling.

## 3. Grounding contract

Every response includes:

```json
{
  "reply": "…",
  "mode": "local",
  "suggestions": ["What should I focus on to improve?"],
  "grounding": {"mode": "local", "context_used": ["subscores", "event_counts_30d", "distance_30d"]},
  "disclaimer": "SafeWay Coach provides general road-safety guidance based on recorded telemetry. …"
}
```

The UI renders `context_used` beneath each answer, so a user can see *what the assistant looked at*. If a
question needs data the assistant does not have, it says so rather than inventing numbers.

## 4. Capability boundaries

`GET /assistant/capabilities` publishes both lists, and the UI renders them verbatim.

**Can answer:** score changes and category breakdowns, recent events and frequency, coaching priorities,
risk assessment explanations, maintenance basics, fleet safety questions for managers.

**Will not:** diagnose medical conditions or fatigue disorders, declare legal violations, predict accidents
or guarantee safety outcomes, contact emergency services.

These are enforced in the prompt (system message) and in code (the coach module never constructs a reply
that asserts a crash probability, a diagnosis or a legal conclusion).

## 5. Prompt construction

```
system:
  You are SafeWay Coach, a road-safety assistant for a fleet platform.
  Use ONLY the provided context. If the context does not contain the answer, say so.
  Never predict accidents, never diagnose medical conditions, never state legal conclusions,
  never claim to have contacted emergency services.
  Always recommend human review for disciplinary decisions.
  Keep answers under 180 words. Prefer concrete, behavioural suggestions.

user:
  <question>

context (JSON):
  { scores, recent events, risk assessment, maintenance alerts }
```

Guardrails applied post-generation:

- Strip any sequence that looks like an API key or credential.
- Refuse (with a fixed message) if the question asks for another driver's data without permission.
- Attach the standard disclaimer to every response.
- Never include raw PII (phone, licence) in the context payload — only aggregates and masked fields.

## 6. Cost and latency controls

| Control | Implementation |
| --- | --- |
| Max message length | 2,000 characters (Pydantic validator) |
| Temperature | 0.2 |
| Timeout | `LLM_TIMEOUT_SECONDS` (30 s default) |
| Fallback | On provider error, return a local-mode answer with `mode: "local"` and a note |
| Rate limit | Shared `RATE_LIMIT_PER_MINUTE` budget |
| Context size | Only aggregates and top-N rows, never full event history |

## 7. Evaluation status

**No formal evaluation has been performed.** There is no golden-question set, no LLM-as-judge harness, and
no human review sample. The model registry entry says so:
`"formal_evaluation": "not performed"`.

Recommended evaluation before enabling LLM mode in production:

1. Build a 50-question set covering scores, events, coaching, risk explanation, maintenance and refusals.
2. Grade factual accuracy against the API response for the same question.
3. Grade refusal correctness for the four prohibited categories.
4. Measure groundedness: does every number in the answer appear in the context?
5. Review a sample for tone and actionability.

## 8. Provider configuration

```env
LLM_PROVIDER=openai-compatible
LLM_BASE_URL=https://api.openai.com/v1
LLM_MODEL=gpt-4o-mini
LLM_API_KEY=sk-...            # server-side only
LLM_TIMEOUT_SECONDS=30
```

Any OpenAI-compatible endpoint works (Azure OpenAI, a local gateway, etc.). The key is read from the
environment at process start and never logged.

## 9. Privacy

- Only the caller's own organisation data is used as context.
- No driver PII is sent to the provider: context uses ids, aggregates and masked fields.
- Provider retention settings are the operator's responsibility; document them in your DPA.
- With no key configured, no data leaves the server at all.
