# AromaGen

**AromaGen** is a wearable olfactory interface that maps free-form text, speech, and images into timed scent sequences over a programmable odorant palette, with human-in-the-loop refinement for personal memory and sensory experiences.

Developed at the MIT Media Lab. This repository contains the **open-source stack**: AI composition backend, BLE device control, demo UI, and study *instrumentation* (Apps Script templates). **Production interaction logs, RAG feedback corpora, and participant study exports are not included** — see [`docs/PUBLIC_RELEASE.md`](docs/PUBLIC_RELEASE.md).

---

## Repository structure

```
AromaGen/
├── aromagen/                 # Core Python package
│   ├── agents/               # FastAPI backend (compose, feedback, accept)
│   ├── data/
│   │   ├── samples/          # Public schema examples only
│   │   ├── dialogue/         # Local logs (gitignored)
│   │   └── exports/          # Training splits (generated locally)
│   ├── ui/demo/              # Main demo (:8080)
│   ├── ui/simplex/           # Anchor simplex UI (:8081)
│   ├── ui/axis/              # Axis mixer UI (:8082)
│   ├── scent_classification.json
│   └── cartridge_sets.json
├── backend.py                # BLE device server (port 5001)
├── scripts/                  # Startup & data export utilities
├── docs/                     # Study protocol & documentation
├── analysis/                 # Demo corpus analysis: themes, noise, scent usage, feedback coding
└── requirements.txt          # BLE backend dependencies
```

---

## Quick start

### Prerequisites

- Python 3.9+
- OpenAI API key
- BLE neck-worn scent device (name must contain `wear`)

### 1. Clone and configure

```bash
git clone https://github.com/AwuChen/AromaGen.git
cd AromaGen
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
pip install -r aromagen/agents/requirements.txt

cp .env.example .env
# Edit .env and set OPENAI_API_KEY
```

### 2. Start all services

```bash
./start_all.sh
```

Or run separately:

| Service | Command | URL |
|---------|---------|-----|
| BLE backend | `./start_ble_backend.sh` | http://localhost:5001 |
| AI backend | `./restart_ai_backend.sh` | http://localhost:8000 |
| Demo UI | `./start_frontend.sh` | http://localhost:8080 |
| Simplex navigation UI | `./scripts/start_simplex_ui.sh` | http://127.0.0.1:8081 |
| Axis mixer UI | `./scripts/start_axis_ui.sh` | http://127.0.0.1:8082 |

### 3. Use the demo

1. Open **http://localhost:8080**
2. Describe a memory or smell experience (voice, text, or image)
3. Play the generated 30-second sequence on the device
4. Give spoken feedback to refine; press **This works** to save for future compose

---

## API (AI backend, port 8000)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/compose` | POST | `{ "sentence": "..." }` → scent sequence |
| `/feedback` | POST | Refine sequence from user feedback |
| `/accept` | POST | Save accepted composition to example bank |
| `/transcribe` | POST | Audio → text (multipart) |
| `/describe_image` | POST | Image → sensory text (multipart) |

Interactive docs: http://localhost:8000/docs

---

## Data & logging (local only)

By default, new sessions can be logged under `aromagen/data/dialogue/` when `DIALOGUE_LOGGING=true`. Those files are **gitignored** and are not published with this repo.

Optional **interaction logging + retrieval** (frontend “Log” button, `interaction_log.jsonl`, embeddings cache) is configured per installation via `.env`. Leave unset for a clean public clone; set `INTERACTION_RETRIEVAL_ENABLED=false` until you have your own log.

Schema reference: [`aromagen/data/samples/dialogue_sample.jsonl`](aromagen/data/samples/dialogue_sample.jsonl). Details: [`aromagen/data/README.md`](aromagen/data/README.md).

**Export training JSONL** (after you collect local sessions):

```bash
python scripts/export_training_data.py
```

---

## Configuration

Environment variables (`.env`, see `.env.example` for the full annotated list):

| Variable | Default | Description |
|----------|---------|-------------|
| `OPENAI_API_KEY` | — | Required |
| `OPENAI_MODEL` | `gpt-4o-mini` | Compose / feedback model |
| `LEARNED_EXAMPLES_ENABLED` | `true` | Inject accepted examples at compose |
| `LEARNED_EXAMPLES_TOP_K` | `3` | Retrieved examples |
| `DIALOGUE_LOGGING` | `true` | Write JSONL logs |
| `SEQUENCE_TOTAL_SECONDS` | `30` | Total sequence duration |
| `DESCRIPTOR_FILTER_TOP_K` | `24` | Odorants shown to the model per request (≥ catalog size = no filtering) |
| `ENSEMBLE_ENABLED` | `true` | Self-consistency ensemble for concrete-smell requests |
| `PULSE_SECONDS` / `PULSE_ROUNDS` | `1` / `8` | Interleaved hardware pulse-train timing |
| `INTERACTION_LOG_APPS_SCRIPT_URL` / `INTERACTION_LOG_TOKEN` | — | **Optional.** Private Sheet + Apps Script you deploy (`aromagen/production_logging/apps_script/`). Controls auto-hide when unset. |
| `INTERACTION_LOG_SHEET_URL` | — | Optional browser link for “Open Log Sheet” (never commit a lab sheet URL). |
| `INTERACTION_RETRIEVAL_ENABLED` | `true` | RAG from local `interaction_log.jsonl` (no-op if empty; use `false` on fresh clones) |
| `VALIDATION_LAYER_ENABLED` | `false` | Extra relevance-validation pass after compose |

---

## For collaborators (intern onboarding)

1. Clone repo, set up `.env`
2. Run `./start_all.sh` and verify http://localhost:8080
3. Read `aromagen/data/README.md` and `docs/PUBLIC_RELEASE.md`
4. Review `docs/STUDY_PROTOCOL.md` for study history (formal study data stays private)
5. BLE issues: run `python scan_devices.py` — device name must include `wear`

**Suggested task split:**

- **Dataset:** stats, clustering, figures from `aromagen/data/dialogue/`
- **Training:** SFT on `aromagen/data/exports/training_*.jsonl`
- **Study:** MFC protocol, IRB instruments, July sessions

---

## Hardware

- Off-the-shelf SCENTAC-style neck wearable, 12 fixed odorant slots
- Single palette spanning 12 standardized descriptor categories (pleasant → unpleasant) — see `cartridge_sets.json`
- BLE discovery: devices with `wear` in the name (`backend.py`)

Multi-device sync (optional): `./start_sync_server.sh` + `SYNC_SERVER_URL=ws://...`

---

## Documentation

- [`docs/PUBLIC_RELEASE.md`](docs/PUBLIC_RELEASE.md) — What must not be published; git history notes
- [`aromagen/data/README.md`](aromagen/data/README.md) — Local data layout & schema
- [`docs/STUDY_PROTOCOL.md`](docs/STUDY_PROTOCOL.md) — CHI user study protocol (MFC evaluation)
- [`docs/SETUP.md`](docs/SETUP.md) — Extended setup & troubleshooting
- [`analysis/README.md`](analysis/README.md) — June demo corpus analysis (themes, noise audit, scent usage, feedback coding)

---

## License

MIT License — see [LICENSE](LICENSE).

---

## Citation

```bibtex
@inproceedings{aromagen2026,
  title={AromaGen: Conversational AI for Wearable Olfactory Memory},
  author={Chen, Awu and Liang, Paul and others},
  booktitle={Proceedings of CHI},
  year={2026}
}
```

*(Update when published.)*
