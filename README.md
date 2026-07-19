# AromaGen

**AromaGen** is a wearable olfactory interface that maps free-form text, speech, and images into timed scent sequences over a programmable odorant palette, with human-in-the-loop refinement for personal memory and sensory experiences.

Developed at the MIT Media Lab. This repository contains the full stack: AI composition backend, BLE device control, demo UI, interaction dataset, and study materials.

---

## Repository structure

```
AromaGen/
├── aromagen/                 # Core Python package
│   ├── agents/               # FastAPI backend (compose, feedback, accept)
│   ├── ui/demo/              # Web demo (http://localhost:8080)
│   ├── data/
│   │   ├── dialogue/         # Interaction logs (JSONL)
│   │   ├── learned_examples.json
│   │   └── exports/          # Training splits (generated)
│   ├── scent_classification.json
│   ├── cartridge_sets.json
│   └── cartridge_state.json
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

## Interaction dataset

Demo and exhibition sessions are logged to `aromagen/data/dialogue/`. See [`aromagen/data/README.md`](aromagen/data/README.md) for schema and statistics.

**Export training JSONL:**

```bash
python scripts/export_training_data.py
```

Produces `training_compose.jsonl`, `training_feedback.jsonl`, and `training_accept.jsonl` in `aromagen/data/exports/`.

---

## Configuration

Environment variables (`.env`):

| Variable | Default | Description |
|----------|---------|-------------|
| `OPENAI_API_KEY` | — | Required |
| `OPENAI_MODEL` | `gpt-4o-mini` | Compose / feedback model |
| `LEARNED_EXAMPLES_ENABLED` | `true` | Inject accepted examples at compose |
| `LEARNED_EXAMPLES_TOP_K` | `3` | Retrieved examples |
| `DIALOGUE_LOGGING` | `true` | Write JSONL logs |
| `SEQUENCE_TOTAL_SECONDS` | `30` | Total sequence duration |

---

## For collaborators (intern onboarding)

1. Clone repo, set up `.env`
2. Run `./start_all.sh` and verify http://localhost:8080
3. Read `aromagen/data/README.md` and run `python scripts/export_training_data.py`
4. Review `docs/STUDY_PROTOCOL.md` for July user study plan
5. BLE issues: run `python scan_devices.py` — device name must include `wear`

**Suggested task split:**

- **Dataset:** stats, clustering, figures from `aromagen/data/dialogue/`
- **Training:** SFT on `aromagen/data/exports/training_*.jsonl`
- **Study:** MFC protocol, IRB instruments, July sessions

---

## Hardware

- Off-the-shelf SCENTAC-style neck wearable, 12 sequential odorant slots
- Cartridge halves (food + abstract/floral) — see `cartridge_sets.json`
- BLE discovery: devices with `wear` in the name (`backend.py`)

Multi-device sync (optional): `./start_sync_server.sh` + `SYNC_SERVER_URL=ws://...`

---

## Documentation

- [`aromagen/data/README.md`](aromagen/data/README.md) — Dataset schema & stats
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
