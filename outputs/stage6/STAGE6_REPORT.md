# Stage 6 — Production AI Data Analyst Agent — Report

## Scope decisions (confirmed with user)
- **Agent brain:** deterministic NL intent parsing + validated SQL templates (no LLM). The template registry in `agent_core.py` is the exact interface an LLM planner would implement later; guardrails apply either way.
- **Interface:** CLI only (interactive REPL + one-shot mode). No Streamlit UI.

## Artifacts
| File | Purpose |
|---|---|
| `agent_core.py` | Shared core: clean loader (single source of the Stage-2 auto rules, previously duplicated in `eda.py`/`sql_agent.py`), intent parser, 10 SQL templates with validators + explanations, guardrails |
| `golden_questions.py` | Regression suite: 12 golden questions with exact expected values from Stages 3–5 + 3 guardrail negative tests |
| `cli_agent.py` | CLI agent: REPL (`:help :schema :templates :debug :quit`) and one-shot mode |

## Agent loop (extends Stage 4's)
USER QUESTION → UNDERSTAND INTENT (keyword match) → PLAN (template + parameters, e.g. "top 5", "180 days")
→ GENERATE SQL → GUARDRAIL CHECK → EXECUTE → VALIDATE (exact expected values) → EXPLAIN RESULT

## Guardrails
- **G1** SELECT-only; write/DDL keywords rejected
- **G2** table whitelist (5 tables + `order_items_excluded` audit table); CTE aliases correctly excluded
- **G3** result row limit (200)
- **G4** anti-double-count: `COUNT(*)` over an `orders JOIN order_items` query is rejected (the exact Stage-4 bug: 31,114 item lines vs 19,989 orders)
- **G5** read-only: raw CSVs untouched, DB in-memory, nothing persisted

## Validation summary
- **Golden regression: 12/12 PASS** (revenue 28,141,523; AOV 1,410 over 14,997 paid orders; top product 552,442; top category Thời trang 4,695,503; monthly sum = total; repeat rate 92.5%; top customer spend 23,770; inactive >90d list; COD 5,598 orders; Delivered revenue 21,727,455; parameter extraction "top 5 products" and "inactive for 180 days")
- **Guardrail negative tests: 3/3 PASS** (DELETE blocked; sqlite_master blocked; COUNT(*) double-count blocked)

## Bugs caught by the suite during development (fixed at cause, all documented)
1. G2 whitelist regex treated CTE aliases (`order_rev`, `opc`, `cr`) as tables → CTE names now excluded from the check
2. G4 heuristic misfired on the AOV template's legitimate `COUNT(*)` → replaced with the precise Stage-4 pattern (COUNT(*) + JOIN order_items)
3. `inactive_customers` validator referenced an out-of-scope variable → fixed
4. Test-harness crash comparing a string column to a number → harness fixed, agent untouched

## Known limitations
- Deterministic parser answers only registry-covered questions; unmatched questions get an honest "no template" response (never invented results)
- Intent matching is keyword-based; an LLM planner can replace `understand()` without touching guardrails or validators
- Data caveats from earlier stages still apply (fee/refund scale anomaly, raw category labels pending approval)
