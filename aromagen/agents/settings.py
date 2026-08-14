from __future__ import annotations

import os
from pathlib import Path
from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[2]
PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_ROOT = PROJECT_ROOT / "data"

load_dotenv(REPO_ROOT / ".env")


class Settings:
    openai_api_key: str = os.getenv("OPENAI_API_KEY", "")
    openai_model: str = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    openai_vision_model: str = os.getenv(
        "OPENAI_VISION_MODEL", os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    )
    scents_path: Path = Path(os.getenv("SCENTS_JSON_PATH", PROJECT_ROOT / "scent_classification.json"))
    cartridge_sets_path: Path = Path(
        os.getenv("CARTRIDGE_SETS_PATH", PROJECT_ROOT / "cartridge_sets.json")
    )
    prompts_dir: Path = PROJECT_ROOT / "agents" / "prompts"
    dialogue_log_dir: Path = Path(
        os.getenv("DIALOGUE_LOG_DIR", DATA_ROOT / "dialogue")
    )
    dialogue_logging_enabled: bool = os.getenv("DIALOGUE_LOGGING", "true").lower() == "true"
    learned_examples_path: Path = Path(
        os.getenv("LEARNED_EXAMPLES_PATH", DATA_ROOT / "learned_examples.json")
    )
    learned_examples_enabled: bool = os.getenv("LEARNED_EXAMPLES_ENABLED", "true").lower() == "true"
    learned_examples_top_k: int = int(os.getenv("LEARNED_EXAMPLES_TOP_K", "3"))
    sequence_total_seconds: int = int(os.getenv("SEQUENCE_TOTAL_SECONDS", "30"))
    scent_duration_max: int = int(os.getenv("SCENT_DURATION_MAX", "15"))
    descriptor_filter_top_k: int = int(os.getenv("DESCRIPTOR_FILTER_TOP_K", "8"))
    pulse_seconds: float = float(os.getenv("PULSE_SECONDS", "1"))
    pulse_rounds: int = int(os.getenv("PULSE_ROUNDS", "8"))
    validation_layer_enabled: bool = os.getenv("VALIDATION_LAYER_ENABLED", "false").lower() == "true"

    interaction_log_apps_script_url: str = os.getenv("INTERACTION_LOG_APPS_SCRIPT_URL", "")
    interaction_log_token: str = os.getenv("INTERACTION_LOG_TOKEN", "")

    # Local copy of the interaction log (fast read-path for retrieval-augmented
    # composition, dual-written alongside the Apps Script/Sheet on every /log_interaction
    # call -- see aromagen/agents/interaction_retrieval.py).
    interaction_log_local_path: Path = Path(
        os.getenv("INTERACTION_LOG_LOCAL_PATH", DATA_ROOT / "interaction_log.jsonl")
    )
    interaction_log_embeddings_path: Path = Path(
        os.getenv("INTERACTION_LOG_EMBEDDINGS_PATH", DATA_ROOT / "interaction_log_embeddings.json")
    )
    interaction_retrieval_enabled: bool = os.getenv("INTERACTION_RETRIEVAL_ENABLED", "true").lower() == "true"
    interaction_retrieval_top_k: int = int(os.getenv("INTERACTION_RETRIEVAL_TOP_K", "5"))
    interaction_retrieval_embedding_model: str = os.getenv(
        "INTERACTION_RETRIEVAL_EMBEDDING_MODEL", "text-embedding-3-small"
    )

    # Self-consistency ensemble for concrete-smell requests (see openai_client.compose_with_ensemble)
    ensemble_enabled: bool = os.getenv("ENSEMBLE_ENABLED", "true").lower() == "true"
    ensemble_predictor_count: int = int(os.getenv("ENSEMBLE_PREDICTOR_COUNT", "10"))
    ensemble_temperature: float = float(os.getenv("ENSEMBLE_TEMPERATURE", "0.9"))
    ensemble_strong_threshold: int = int(os.getenv("ENSEMBLE_STRONG_THRESHOLD", "5"))
    ensemble_weak_threshold: int = int(os.getenv("ENSEMBLE_WEAK_THRESHOLD", "3"))
    ensemble_retry_predictor_count: int = int(os.getenv("ENSEMBLE_RETRY_PREDICTOR_COUNT", "5"))


settings = Settings()
