"""
Re-embed all article chunks with the local embedding model served by TEI (see docker-compose.yml).

The chunk texts already contain the LLM generated context from indexing.py, so only the vectors are recomputed.
Work is split in two resumable steps so the expensive part is never lost:

    python -m rag.reembed bench --limit 2000   measure throughput on a sample, nothing is saved
    python -m rag.reembed embed                read chunks from the source collection, embed them and save
                                               shards (vectors + properties) to disk; rerun to resume
    python -m rag.reembed load                 create the target collection and insert all shards with
                                               their vectors; safe to rerun, objects keep their UUIDs

The shards are a full backup of the chunks and vectors, so the target collection can be rebuilt from them
without recomputing anything.
"""
import argparse
import gzip
import json
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import httpx
import numpy as np
import weaviate
from tqdm import tqdm

from rag.db.db import create_collection
from rag.embeddings import TEIEmbeddings
from rag.settings import Settings

PAGE_SIZE = 1000
SHARD_SIZE = 10_000
REQUEST_BATCH_SIZE = 64
CONCURRENT_REQUESTS = 8


def shard_dir(settings: Settings) -> Path:
    return Path("./embeddings") / settings.embedding_model.replace("/", "__")


def check_server_model(settings: Settings):
    """Make sure TEI serves the model the shards are named after."""
    served = httpx.get(f"{settings.embedding_url}/info").json()["model_id"]
    if served != settings.embedding_model:
        raise SystemExit(f"TEI serves {served!r} but EMBEDDING_MODEL is {settings.embedding_model!r}")


def embed_texts(embedder: TEIEmbeddings, texts: list[str]) -> np.ndarray:
    """Embed texts with concurrent requests; texts are grouped by length so batches pad as little as possible."""
    order = sorted(range(len(texts)), key=lambda i: len(texts[i]))
    batches = [order[i:i + REQUEST_BATCH_SIZE] for i in range(0, len(order), REQUEST_BATCH_SIZE)]
    # TEI rejects empty inputs
    batch_texts = [[texts[i] or " " for i in batch] for batch in batches]

    vectors = np.zeros((len(texts), 0), dtype=np.float32)
    with ThreadPoolExecutor(CONCURRENT_REQUESTS) as executor:
        for batch, batch_vectors in zip(batches, executor.map(embedder._embed, batch_texts)):
            if vectors.shape[1] == 0:
                vectors = np.zeros((len(texts), len(batch_vectors[0])), dtype=np.float32)
            vectors[batch] = batch_vectors
    return vectors


def fetch_pages(collection, after=None, limit=None):
    """Iterate over all objects of a collection in UUID order, starting after the given UUID."""
    fetched = 0
    while limit is None or fetched < limit:
        page_size = PAGE_SIZE if limit is None else min(PAGE_SIZE, limit - fetched)
        objects = collection.query.fetch_objects(limit=page_size, after=after).objects
        if not objects:
            return
        fetched += len(objects)
        after = objects[-1].uuid
        yield objects


def write_shard(path: Path, objects, vectors: np.ndarray):
    """Write properties first and vectors last; a shard counts as complete once its .npz exists."""
    with gzip.open(path.with_suffix(".jsonl.gz.tmp"), "wt") as f:
        for obj in objects:
            f.write(json.dumps(obj.properties) + "\n")
    path.with_suffix(".jsonl.gz.tmp").rename(path.with_suffix(".jsonl.gz"))

    with open(path.with_suffix(".npz.tmp"), "wb") as f:
        np.savez(f, uuids=np.array([str(obj.uuid) for obj in objects]), vectors=vectors.astype(np.float16))
    path.with_suffix(".npz.tmp").rename(path.with_suffix(".npz"))


def completed_shards(directory: Path) -> list[Path]:
    return sorted(directory.glob("shard_*.npz"))


def bench(args, settings: Settings):
    check_server_model(settings)
    embedder = TEIEmbeddings(settings.embedding_url)
    with weaviate.connect_to_local(host=settings.weaviate_host) as client:
        source = client.collections.get(args.source)
        total = source.aggregate.over_all(total_count=True).total_count
        objects = [obj for page in fetch_pages(source, limit=args.limit) for obj in page]

    texts = [obj.properties.get(settings.text_key) or "" for obj in objects]
    start = time.time()
    embed_texts(embedder, texts)
    elapsed = time.time() - start

    rate = len(texts) / elapsed
    print(f"model: {settings.embedding_model}")
    print(f"embedded {len(texts)} chunks in {elapsed:.1f}s -> {rate:.0f} chunks/s")
    print(f"estimated time for all {total} chunks: {total / rate / 3600:.1f} h")


def embed(args, settings: Settings):
    check_server_model(settings)
    embedder = TEIEmbeddings(settings.embedding_url)
    directory = shard_dir(settings)
    directory.mkdir(parents=True, exist_ok=True)

    # Resume after the last object of the last complete shard
    shards = completed_shards(directory)
    after = None
    done = 0
    for shard in shards:
        uuids = np.load(shard)["uuids"]
        done += len(uuids)
        after = str(uuids[-1])

    with weaviate.connect_to_local(host=settings.weaviate_host) as client:
        source = client.collections.get(args.source)
        total = source.aggregate.over_all(total_count=True).total_count

        buffer = []
        shard_index = len(shards)
        with tqdm(total=total, initial=done, unit="chunk") as progress:
            def flush(objects):
                nonlocal shard_index
                texts = [obj.properties.get(settings.text_key) or "" for obj in objects]
                vectors = embed_texts(embedder, texts)
                write_shard(directory / f"shard_{shard_index:05d}", objects, vectors)
                shard_index += 1
                progress.update(len(objects))

            for page in fetch_pages(source, after=after):
                buffer.extend(page)
                if len(buffer) >= SHARD_SIZE:
                    flush(buffer[:SHARD_SIZE])
                    buffer = buffer[SHARD_SIZE:]
            if buffer:
                flush(buffer)

    print(f"Shards saved in {directory}")


def load(args, settings: Settings):
    directory = shard_dir(settings)
    shards = completed_shards(directory)
    if not shards:
        raise SystemExit(f"No shards found in {directory}, run the embed step first")

    with weaviate.connect_to_local(host=settings.weaviate_host) as client:
        if not client.collections.exists(args.target):
            create_collection(client, args.target)
        target = client.collections.get(args.target)

        expected = 0
        failed = 0
        for shard in tqdm(shards, unit="shard"):
            data = np.load(shard)
            uuids, vectors = data["uuids"], data["vectors"].astype(np.float32)
            with gzip.open(shard.with_suffix(".jsonl.gz"), "rt") as f:
                properties = [json.loads(line) for line in f]
            expected += len(uuids)

            with target.batch.fixed_size(batch_size=500, concurrent_requests=4) as batch:
                for uuid, vector, props in zip(uuids, vectors, properties):
                    batch.add_object(properties=props, uuid=str(uuid), vector=vector.tolist())
            failed += len(target.batch.failed_objects)
            for failure in target.batch.failed_objects[:3]:
                print(f"Failed object: {failure.message}")

        count = target.aggregate.over_all(total_count=True).total_count

    print(f"{args.target}: {count} objects, {expected} in shards, {failed} failed inserts")


def main():
    settings = Settings()
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("step", choices=["bench", "embed", "load"])
    parser.add_argument("--source", default="Arxiv", help="collection to read chunks from")
    parser.add_argument("--target", default="ArxivQwen3", help="collection to load the new vectors into")
    parser.add_argument("--limit", type=int, default=2000, help="number of chunks for the bench step")
    args = parser.parse_args()

    {"bench": bench, "embed": embed, "load": load}[args.step](args, settings)


if __name__ == "__main__":
    main()
