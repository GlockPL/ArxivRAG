import json
from pathlib import Path

def process_jsonl(input_file):
    ids = []
    all_pdfs = list(Path('../../pdf/').glob('*.pdf'))
    all_pdfs = set([f.stem for f in all_pdfs])
    with open(input_file, 'r') as f:
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
    with open(output_file, 'w') as f:
        f.write('\n'.join(ids))

# Example usage
input_jsonl = "../../arxiv-metadata-oai-snapshot.json"
output_txt = "../../ids_with_cs_ai.txt"

collected_ids = process_jsonl(input_jsonl)
write_output(collected_ids, output_txt)