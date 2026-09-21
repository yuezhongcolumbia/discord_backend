from langchain_ollama import OllamaEmbeddings


class OllamaTextEmbedder:
    def __init__(
        self,
        model_name: str,
    ) -> None:
        self._embeddings = OllamaEmbeddings(
            model=model_name,
        )

    def embed(
        self,
        text: str,
    ) -> list[float]:
        return self._embeddings.embed_query(text)