"""
Client for the local text-embeddings-inference (TEI) server, see the embeddings service in docker-compose.yml
"""
import asyncio
import time

import httpx
from langchain_core.embeddings import Embeddings

# TEI answers 429 when its request queue is full and 503 while overloaded, so back off and retry
RETRY_STATUS_CODES = (429, 503)


class TEIEmbeddings(Embeddings):
    """
    LangChain embeddings backed by a TEI server.
    Qwen3 embedding models expect an instruction only on queries, documents are embedded as is,
    so queries use the model's built-in "query" prompt.
    """

    def __init__(self, url: str, batch_size: int = 64, timeout: float = 300.0, max_retries: int = 5):
        self.url = url.rstrip("/")
        self.batch_size = batch_size
        self.timeout = timeout
        self.max_retries = max_retries
        self.client = httpx.Client(timeout=timeout)
        self._async_client = None

    @property
    def async_client(self) -> httpx.AsyncClient:
        # Created lazily so it binds to the event loop that uses it
        if self._async_client is None:
            self._async_client = httpx.AsyncClient(timeout=self.timeout)
        return self._async_client

    @staticmethod
    def _payload(texts: list[str], prompt_name: str | None) -> dict:
        payload = {"inputs": texts, "truncate": True, "normalize": True}
        if prompt_name:
            payload["prompt_name"] = prompt_name
        return payload

    def _embed(self, texts: list[str], prompt_name: str | None = None) -> list[list[float]]:
        payload = self._payload(texts, prompt_name)
        for attempt in range(self.max_retries + 1):
            response = self.client.post(f"{self.url}/embed", json=payload)
            if response.status_code not in RETRY_STATUS_CODES or attempt == self.max_retries:
                break
            time.sleep(2 ** attempt)
        response.raise_for_status()
        return response.json()

    async def _aembed(self, texts: list[str], prompt_name: str | None = None) -> list[list[float]]:
        payload = self._payload(texts, prompt_name)
        for attempt in range(self.max_retries + 1):
            response = await self.async_client.post(f"{self.url}/embed", json=payload)
            if response.status_code not in RETRY_STATUS_CODES or attempt == self.max_retries:
                break
            await asyncio.sleep(2 ** attempt)
        response.raise_for_status()
        return response.json()

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        vectors = []
        for i in range(0, len(texts), self.batch_size):
            vectors.extend(self._embed(texts[i:i + self.batch_size]))
        return vectors

    def embed_query(self, text: str) -> list[float]:
        return self._embed([text], prompt_name="query")[0]

    async def aembed_documents(self, texts: list[str]) -> list[list[float]]:
        vectors = []
        for i in range(0, len(texts), self.batch_size):
            vectors.extend(await self._aembed(texts[i:i + self.batch_size]))
        return vectors

    async def aembed_query(self, text: str) -> list[float]:
        return (await self._aembed([text], prompt_name="query"))[0]

    async def aclose(self):
        if self._async_client is not None:
            await self._async_client.aclose()
