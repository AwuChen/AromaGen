# Public release checklist

The GitHub repository is **open source** (MIT). It ships **code, prompts, and hardware integration** — not lab production databases.

## What must stay private (never commit)

| Data | Why | Local path (gitignored) |
|------|-----|-------------------------|
| OpenAI / Apps Script secrets | Credentials | `.env`, `.admin_token`, `.clasp.json` |
| Dialogue session logs | User utterances, demos | `aromagen/data/dialogue/dialogue_*.jsonl` |
| Interaction log + embeddings | RAG feedback corpus | `interaction_log.jsonl`, `interaction_log_embeddings.json` |
| Learned example bank | Accepted compositions from sessions | `learned_examples.json` |
| Training exports | Derived from logs | `aromagen/data/exports/*.jsonl` |
| Production sheet CSV dumps | Same as interaction log | `aromagen/agents/*Interaction Log*.csv` |
| CHI / user study master CSVs | Participant IDs, trials | `data_analysis_users/*.csv` |
| Unpublished paper PDFs | Submission artifacts | `documentation/` |

Public clone defaults: empty example bank, empty interaction log, retrieval disabled unless you populate logs locally (see README).

## If sensitive data was ever pushed

Removing files in a new commit **does not erase git history**. If production logs or study CSVs were on `main`:

1. Rotate any exposed Apps Script tokens and treat OpenAI keys as uncompromised only if they were never in the repo.
2. Consider [GitHub secret scanning](https://docs.github.com/en/code-security/secret-scanning) and removing the Sheet link from any public fork.
3. To purge history: `git filter-repo` (or BFG) on the affected paths, then force-push — coordinate with all collaborators first.

## Before tagging a release

- [ ] `git status` — no `.env`, no `dialogue_*.jsonl`, no `interaction_log*` with real rows
- [ ] Demo UI — no hardcoded Google Sheet URLs (`script.js` uses `/health` only)
- [ ] README — citation, license, hardware, optional features clearly marked
- [ ] `.env.example` — placeholders only

## Sample data

Schema reference: `aromagen/data/samples/dialogue_sample.jsonl`. Regenerate exports locally after your own sessions with `python scripts/export_training_data.py`.
