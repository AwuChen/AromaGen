# Extended setup & troubleshooting

## Install

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
pip install -r aromagen/agents/requirements.txt
cp .env.example .env
```

## BLE device not found

1. Device powered on, within range, not paired elsewhere
2. Device name contains `wear` (case-insensitive)
3. Run `python scan_devices.py`
4. Change keyword in `backend.py` → `DEVICE_NAME_KEYWORD` if needed

## AI backend errors

- Confirm `OPENAI_API_KEY` in `.env`
- Check port 8000 free: `lsof -ti:8000 | xargs kill -9`
- Logs: uvicorn output in terminal

## Paths

| Resource | Default path |
|----------|--------------|
| Scent catalog | `aromagen/scent_classification.json` |
| Dialogue logs | `aromagen/data/dialogue/` |
| Learned examples | `aromagen/data/learned_examples.json` |
| Prompts | `aromagen/agents/prompts/` |

Override with environment variables — see `.env.example`.
