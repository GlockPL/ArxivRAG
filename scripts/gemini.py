import os
import json
from pathlib import Path
import pymupdf
import json_repair
import natsort
from dotenv import load_dotenv
from tqdm import tqdm
from google import genai
from google.genai.errors import ClientError
from mistralai import Mistral

load_dotenv(dotenv_path="./.env")


def simple_compress_pdf(input_file):
    """Simple PDF compression using PyMuPDF's built-in compression"""
    output_file = Path("./tmp")
    output_file.mkdir(parents=True, exist_ok=True)
    output_file = output_file / "temp.pdf"

    pdf = pymupdf.open(input_file)
    pdf.save(output_file,
             garbage=4,  # Clean up unused objects
             deflate=True,# Compress streams
             deflate_images=True,
             deflate_fonts=True,
             pretty=False,  # No pretty printing
             linear=False,  # No linear format
             ascii=False)  # Allow binary format
    pdf.close()

    return output_file


def process_file_gemini_flash(file_path: Path, json_path: Path):
    """
    Process a pdf using gemini flash model
    """
    if file_size(file_path) > 50:
        file_path = simple_compress_pdf(file_path)
        if file_size(file_path) > 50:
            return False

    api_key = os.getenv('GEMINI_API_KEY')
    client = genai.Client(api_key=api_key)
    # Upload the PDF using the File API
    try:
        sample_file = client.files.upload(file=file_path, config={"mime_type": 'application/pdf'})
    except ClientError as e:
        print(f"Failed to upload file due to {str(e)}")
        return False

    prompt = f"This is an article from arxiv with article id: {file_path.stem[:-2]}."
    prompt += "Parse the text from this article into valid JSON with this structure:"
    prompt += " {title:str,authors:[str],abstract:str,sections:[title:str,content:str]}."
    prompt += " Discard references, acknowledgements, tabels with captions and images with captions."
    prompt += " Every equation must be parsed into latex inplace."
    try:
        history = [sample_file, prompt]

        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=history)

        response_json = response.text
        print(response_json)
        valid_json = json_repair.loads(response.text)

        correct_json = True if response_json[-5] == "}" else False

        if correct_json:
            with json_path.open('w') as f:
                json.dump(valid_json, f)
        else:
            history.append(response_json)
            history.append("continue generating json")
            response = client.models.generate_content(
                model="gemini-2.0-flash",
                contents=history)
            response_json2 = response.text
            valid_json = json_repair.loads(f"{response_json}{response_json2}")
            print(valid_json)
            with json_path.open('w') as f:
                json.dump(valid_json, f)

        client.files.delete(name=sample_file.name)
        return True
    except Exception as ex:
        print(f"Exception caught: {ex}")
        return False


def file_size(file_path: Path) -> float:
    """
    Calculate the size of a file
    """
    size_in_bytes = file_path.stat().st_size
    # Convert to megabytes
    size_in_mb = size_in_bytes / (1024 * 1024)
    return size_in_mb


def process_file_mistral(file_path: Path, json_path: Path) -> bool:
    """
    Process a pdf using Mistral ocr mode
    """
    if file_size(file_path) > 50:
        return False

    api_key = os.getenv('MISTRAL_API_KEY')
    client = Mistral(api_key=api_key)
    # Upload the PDF using the File API
    uploaded_pdf = client.files.upload(file={"file_name": file_path.name, "content": file_path.open("rb")},
                                       purpose="ocr")
    signed_url = client.files.get_signed_url(file_id=uploaded_pdf.id)
    ocr_response = client.ocr.process(
        model="mistral-ocr-latest",
        document={
            "type": "document_url",
            "document_url": signed_url.url,
        },
        include_image_base64=False
    )

    full_document = "\n\n".join(
        [f"### Page {i + 1}\n{ocr_response.pages[i].markdown}" for i in range(len(ocr_response.pages))])

    prompt = f"This is an article from arxiv with article id: {file_path.stem[:-2]}."
    prompt += "Parse the text from this article into valid JSON with this structure: {title:str,authors:[str],abstract:str,sections:[title:str,content:str]}. Discard references, acknowledgements, tabels with captions and images with captions. Every equation must be parsed into latex inplace."
    prompt += f"\n\n This is the content of the article: {full_document}"

    try:
        client = Mistral(api_key=api_key)

        # Define the messages for the chat
        messages = [
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": prompt
                    }
                ]
            }
        ]
        model = "ministral-8b-latest"
        # Get the chat response
        chat_response = client.chat.complete(
            model=model,
            messages=messages
        )

        json_response = chat_response.choices[0].message.content
        # Print the content of the response
        print(json_response)

        valid_json = json_repair.loads(json_response)

        with json_path.open('w') as f:
            json.dump(valid_json, f)

        return True
    except Exception as ex:
        print(f"Exception caught: {ex}")
        return False


def list_files(use_mistral=False):
    """
    Iterate over all files and process only those that hasn't been processed yet
    """
    pdfs_path = Path('../pdf')
    output_path = Path('./json_gemini')

    for file in natsort.natsorted(pdfs_path.glob('*.pdf'), reverse=True):
        json_path = output_path / f"{file.stem}.json"
        if json_path.exists():
            continue

        if use_mistral:
            process_file_mistral(file, json_path)
        else:
            process_file_gemini_flash(file, json_path)


def clear_all_files():
    """
    Remove remotely uploaded files
    """
    api_key = os.getenv('GEMINI_API_KEY')
    client = genai.Client(api_key=api_key)
    file_list = client.files.list()
    for f in (pbar := tqdm(file_list)):
        pbar.set_description(f"Deleting file: {f.name}")
        client.files.delete(name=f.name)


if __name__ == "__main__":
    list_files(use_mistral=False)
