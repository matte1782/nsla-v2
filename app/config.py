# app/config.py
from functools import lru_cache
from pydantic import BaseModel
from typing import Optional


class Settings(BaseModel):
    """
    Configurazione centrale (M0) condivisa da tutti i moduli.

    Campi principali:
    - llm_backend: "dummy" | "ollama" | "cloud"
    - use_cloud / use_local_model: flag rapidi per orchestrare il backend
    - enable_symbolic_layer: abilita/disabilita translator + Z3
    - benchmark_mode: abilita percorsi e logging specifici per benchmark
    """

    llm_backend: str = "dummy"
    local_model_name: str = "llama3"
    cloud_model_name: Optional[str] = None
    cloud_provider: Optional[str] = None
    use_cloud: bool = False
    use_local_model: bool = True
    enable_symbolic_layer: bool = True
    benchmark_mode: bool = False
    enable_judge_metric: bool = False


@lru_cache
def get_settings() -> Settings:
    # Se vuoi, puoi aggiungere qui il caricamento da .env via pydantic-settings
    # senza dipendenze aggiuntive per ora usiamo solo i default.
    return Settings()
