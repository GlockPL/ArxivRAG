"""
Script that outputs filenames of arxiv articles
to download from kaggle google cloud storage
"""
import json
from pathlib import Path


def process_jsonl(input_file):
    """
    Process kaggle jsonl file with data about every arxiv article
    """
    ids = []
    all_pdfs = list(Path('../../pdf/').glob('*.pdf'))
    all_pdfs = {f.stem for f in all_pdfs}
    with open(input_file, 'r', encoding="utf-8") as f:
        for line in f:
            try:
                entry = json.loads(line.strip())
                if "cs.AI" in entry.get("categories", []):
                    versions = entry["versions"]
                    version = versions[-1]["version"]
                    file_name = f"{entry['id']}{version}"
                    if entry["id"][:2] == "25" and file_name not in all_pdfs:
                        ids.append(file_name)
            except json.JSONDecodeError:
                # Skip malformed JSON lines
                continue
    return ids[::-1]


def write_output(ids, output_file):
    """
    Write a file with all the filenames of arxiv articles line by line
    """
    with open(output_file, 'w', encoding="utf-8") as f:
        f.write('\n'.join(ids))


if __name__ == "__main__":
    # Example usage
    INPUT_JSONL = "../../arxiv-metadata-oai-snapshot.json"
    OUTPUT_TXT = "../../ids_with_cs_ai.txt"

    collected_ids = process_jsonl(INPUT_JSONL)
    write_output(collected_ids, OUTPUT_TXT)
