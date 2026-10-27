# Navigation simplex UI

Triangle-based smell navigation: three anchor blends define corners; the participant places a target memory inside the simplex; the system barycentrically mixes 12-channel recipes and plays the result.

## Flow

1. **Anchors** — Smell three compositions (token-labeled A/B/C). Presets ship in-repo; optional LLM generation from a target phrase (`POST /simplex/prepare_anchors`).
2. **Placement** — Click or drag inside the triangle where the target feels relative to the anchors.
3. **Blend** — Weights `(w₁, w₂, w₃)` sum to 1. Recipe `r = w₁r_A + w₂r_B + w₃r_C`, normalized for the device. Optional nearest match from `learned_examples.json`.
4. **Iterate** — Play blend; nudge dot or start another round with the same anchors.

## Run locally

```bash
./start_all.sh          # BLE :5001 + agents :8000
./scripts/start_simplex_ui.sh   # UI :8081
```

Open http://127.0.0.1:8081

Playback goes through the AI backend (`POST /device/play_sequence`), which forwards to BLE `:5001`.

## API (agents, :8000)

| Route | Purpose |
|-------|---------|
| `GET /simplex/presets` | Demo anchor recipes |
| `POST /simplex/prepare_anchors` | `{ "target": "grandma's perfume" }` → 3 composed anchors |
| `POST /simplex/from_point` | Anchors + click `(point_x, point_y)` → blend + pulse train |
| `POST /simplex/interpolate` | Anchors + explicit `[w1,w2,w3]` |
| `POST /device/play_sequence` | `{ "sequence": [{ "scent_id", "duration" }] }` → BLE backend |

UI lives in `aromagen/ui/simplex/`.
