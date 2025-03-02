from pathlib import Path
from google import genai
from google.genai.errors import ClientError
import json_repair
import json
import natsort
import os
from dotenv import load_dotenv
from tqdm import tqdm

load_dotenv(dotenv_path="./.env")

def process_file_gemini_flash(file_path: Path, json_path: Path):
    api_key = os.getenv('GEMINI_API_KEY')
    client = genai.Client(api_key=api_key)
    # Upload the PDF using the File API
    try:
        sample_file = client.files.upload(file=file_path, config=dict(mime_type='application/pdf'))
    except ClientError as e:
        print(f"Failed to upload file due to {str(e)}")
        return

    prompt = f"This is an article from arxiv with article id: {file_path.stem[:-2]}."
    prompt += "Parse the text from this article into valid JSON with this structure: {title:str,authors:[str],abstract:str,sections:[title:str,content:str]}. Discard references, acknowledgements, tabels with captions and images with captions. Every equation must be parses into latex inplace."
    try:

        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=[sample_file, prompt])


        print(response.text)
        valid_json = json_repair.loads(response.text)

        with json_path.open('w') as f:
            json.dump(valid_json, f)

        client.files.delete(name=sample_file.name)

    except Exception as ex:
        print(f"Exception caught: {ex}")



def list_files():
    pdfs_path = Path('../pdf')
    output_path = Path('./json_gemini')

    for file in natsort.natsorted(pdfs_path.glob('*.pdf'), reverse=True):
        json_path = output_path / f"{file.stem}.json"
        if json_path.exists():
            continue

        process_file_gemini_flash(file, json_path)


def clear_all_files():
    api_key = os.getenv('GEMINI_API_KEY')
    client = genai.Client(api_key=api_key)
    file_list = client.files.list()
    for f in (pbar:=tqdm(file_list)):
        pbar.set_description(f"Deleting file: {f.name}")
        client.files.delete(name=f.name)

if __name__ == "__main__":
    list_files()
    # clear_all_files()

