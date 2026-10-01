"""
Client for the local text-embeddings-inference (TEI) server, see the embeddings service in docker-compose.yml
"""
import time

import httpx
from langchain_core.embeddings import Embeddings


class TEIEmbeddings(Embeddings):
    """
    LangChain embeddings backed by a TEI server.
    Qwen3 embedding models expect an instruction only on queries, documents are embedded as is,
    so queries use the model's built-in "query" prompt.
    """

    def __init__(self, url: str, batch_size: int = 64, timeout: float = 300.0, max_retries: int = 5):
        self.url = url.rstrip("/")
        self.batch_size = batch_size
        self.max_retries = max_retries
        self.client = httpx.Client(timeout=timeout)

    def _embed(self, texts: list[str], prompt_name: str | None = None) -> list[list[float]]:
        payload = {"inputs": texts, "truncate": True, "normalize": True}
        if prompt_name:
            payload["prompt_name"] = prompt_name
        # TEI answers 429 when its request queue is full and 503 while overloaded, so back off and retry
        for attempt in range(self.max_retries + 1):
            response = self.client.post(f"{self.url}/embed", json=payload)
            if response.status_code not in (429, 503) or attempt == self.max_retries:
                break
            time.sleep(2 ** attempt)
        response.raise_for_status()
        return response.json()

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        vectors = []
        for i in range(0, len(texts), self.batch_size):
            vectors.extend(self._embed(texts[i:i + self.batch_size]))
        return vectors

    def embed_query(self, text: str) -> list[float]:
        return self._embed([text], prompt_name="query")[0]
