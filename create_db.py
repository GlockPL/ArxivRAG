import numpy as np

from pathlib import Path
from tqdm import tqdm
from langchain_huggingface.embeddings import HuggingFaceEmbeddings
from langchain_chroma import Chroma
from langchain_community.document_loaders import TextLoader
from langchain.text_splitter import LatexTextSplitter


# class CustomTexLoader(BaseLoader):
#     def __init__(self, file_path: str | Path) -> None:
#         """Initialize the loader with a file path.
#
#         Args:
#             file_path: The path to the file to load.
#         """
#         self.file_path = str(file_path)
#
#     def lazy_load(self):
#         for encoding in encodings:
#             try:
#                 with open(self.file_path, 'r', encoding=encoding) as f:
#                     text = f.read()
#                 break
#             except UnicodeDecodeError:
#                 continue
#         else:
#             raise RuntimeError(f"Unable to load the file with the given encodings: {encodings}")
#
#         # Optionally convert LaTeX to plain text
#         try:
#             latex_converter = LatexNodes2Text()
#             plain_text = latex_converter.latex_to_text(text)
#             plain_text = plain_text.strip()
#
#             if plain_text == '':
#                 plain_text = text
#         except IndexError:
#             plain_text = text
#
#         yield Document(
#                     page_content=plain_text,
#                     metadata={"source": self.file_path},
#                 )


def embeddings():
    # encodings = ['utf-8', 'latin-1', 'iso-8859-1']

    tex_files = list(Path('/home/glock/Dokumenty/Arxiv_Articles/tex/').glob('*/*.tex'))#
    persist_directory = Path('./db')
    persist_directory.mkdir(parents=True, exist_ok=True)
    latex_text_splitter = LatexTextSplitter(chunk_size=2000, chunk_overlap=200)
    model_name = 'maidalun1020/bce-embedding-base_v1'
    model_kwargs = {'device': 'cuda'}
    encode_kwargs = {'batch_size': 64, 'normalize_embeddings': True}  # , 'show_progress_bar': True
    embed_model = HuggingFaceEmbeddings(
        model_name=model_name,
        model_kwargs=model_kwargs,
        encode_kwargs=encode_kwargs
    )

    for path_to_tex in (pbar := tqdm(tex_files)):
        try:
            loader = TextLoader(path_to_tex, autodetect_encoding=True)
            tex_docs = loader.load()
            splits = latex_text_splitter.split_documents(tex_docs)
            pbar.set_postfix_str(f"Split size: {len(splits)}")
            _ = Chroma.from_documents(documents=splits, embedding=embed_model,
                                             persist_directory=str(persist_directory))

        except RuntimeError as er:
            continue


if __name__ == "__main__":
    embeddings()
