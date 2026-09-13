import re
import os
import shutil
from pypdf import PdfReader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_chroma import Chroma
from langchain_core.documents import Document
from table_extractor import extract_tables_from_pdf

UPLOADS_DIR = "uploads"
CHROMA_DIR = "chroma_db"

def clear_existing_index():
    if os.path.exists(CHROMA_DIR):
        shutil.rmtree(CHROMA_DIR)
        print(f"Cleared existing index at {CHROMA_DIR}/")

def extract_text_from_pdf(filepath):
    reader = PdfReader(filepath)
    text = ""
    for page in reader.pages:
        text += page.extract_text() or ""
    return text

def load_all_documents():
    text_docs = []
    table_docs = []
    for filename in os.listdir(UPLOADS_DIR):
        if filename.endswith(".pdf"):
            filepath = os.path.join(UPLOADS_DIR, filename)
            print(f"Extracting: {filename}")

            # Strip the "<user_id>_" prefix so source metadata matches the DB filename
            clean_filename = re.sub(r"^\d+_", "", filename)

            text = extract_text_from_pdf(filepath)
            text_docs.append(Document(
                page_content=text,
                metadata={"source": clean_filename, "chunk_type": "text"}
            ))

            tables = extract_tables_from_pdf(filepath, clean_filename)
            if tables:
                print(f"  Found {len(tables)} table(s) in {filename}")
            table_docs.extend(tables)

    return text_docs, table_docs

def build_vector_store():
    clear_existing_index()
    text_docs, table_docs = load_all_documents()
    print(f"Loaded {len(text_docs)} documents, {len(table_docs)} tables")

    splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50)
    text_chunks = splitter.split_documents(text_docs)
    print(f"Split text into {len(text_chunks)} chunks")

    # Table chunks bypass the splitter entirely — splitting a Markdown table
    # midway breaks its row/column alignment, which defeats the point of
    # extracting it separately in the first place.
    all_chunks = text_chunks + table_docs
    print(f"Total chunks (text + tables): {len(all_chunks)}")

    print("Loading embedding model (first run downloads it, may take a minute)...")
    embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")

    print("Building Chroma vector store...")
    vectorstore = Chroma.from_documents(
        documents=all_chunks,
        embedding=embeddings,
        persist_directory=CHROMA_DIR
    )
    print(f"Done. Vector store saved to {CHROMA_DIR}/")
    return vectorstore

if __name__ == "__main__":
    build_vector_store()