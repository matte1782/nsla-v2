# test_llm_client_standalone.py

from app.config import Settings
from app.llm_client import LLMClient


def main():
    # Prova prima cloud, poi puoi cambiare a mano a locale
    settings = Settings(
        use_cloud=True,
        cloud_model_name="kimi-k2:1t-cloud",
        local_model_name="llama3.2:latest",
    )
    client = LLMClient(settings)

    question = "Quali sono i principi generali della responsabilità contrattuale?"
    answer = client.ask_llm_plain(question)

    print("=== MODE ===", client.mode)
    print("=== MODEL USED ===", client.model_name)
    print("=== ANSWER ===")
    print(answer)

    # Check minimo
    assert isinstance(answer, str)
    assert answer.strip() != "", "LLM returned an empty answer"


if __name__ == "__main__":
    main()
