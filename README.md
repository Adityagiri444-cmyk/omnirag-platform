# OmniRAG - Intelligent Multi-Agent Knowledge Platform

OmniRAG is a full-stack Retrieval-Augmented Generation (RAG) platform that lets users upload documents, ask questions about them, and get grounded, evaluated answers - with live visualization of the AI's reasoning steps and downloadable PDF reports.

Built as a 5th-semester mini project / TechXpo submission.

## Features

- **Authenticated document management** - upload, list, delete, and summarize PDF documents per user, with admin/user role separation
- **Multi-agent RAG pipeline** (LangGraph): Coordinator -> (Planner/Decompose/Clarify) -> Retrieval -> Summarizer/Synthesize -> Evaluator, with automatic retry on ungrounded answers
- **Query decomposition** - complex, multi-part questions are automatically broken into sub-questions, answered independently, and synthesized into one coherent answer
- **Hierarchical retrieval** - a two-stage RAPTOR-inspired search: document-level summaries (auto-generated the moment a document is uploaded) narrow down to the right document first, then chunk-level search finds precise passages within it
- **Multimodal document understanding** - tables are extracted and preserved as structured Markdown (not flattened into garbled text), and text embedded in images - screenshots, scanned pages, diagrams - is extracted via OCR, so both become fully searchable and retrievable alongside regular text
- **Real-time agent visualization** - live progress tracking as each pipeline step runs, shown as an animated status bar in the chat UI
- **Chat interface** - full conversation history, not just single Q&A
- **Downloadable PDF reports** - every answer can be exported as a structured report (question, search query, retrieved context, answer, evaluation), with retrieved tables rendered as real formatted tables rather than flattened text
- **Document summarization** - one-click AI summary of any uploaded document
- **Analytics dashboard** - upload trends and document counts, visualized with charts

## Tech Stack

- **Backend**: FastAPI, SQLAlchemy, PostgreSQL, JWT auth (python-jose), bcrypt
- **Frontend**: React, Tailwind CSS, Recharts
- **AI/Orchestration**: LangChain, LangGraph, Groq (free-tier LLM API), HuggingFace sentence-transformers (local embeddings, no API cost)
- **Vector Store**: ChromaDB (local, persistent - two collections: chunk-level and document-summary-level)
- **PDF Processing**: pypdf (text extraction), pdfplumber (table extraction), PyMuPDF + Tesseract OCR (image and scanned-page text extraction), ReportLab (report generation)

## Architecture
User Question
|
v
+-------------+
| Coordinator | classifies: SIMPLE / COMPLEX / AMBIGUOUS
+------+------+
|
+---+--------------------+-----------------+
v v v
SIMPLE COMPLEX AMBIGUOUS
| | |
v v v
+---------+ +-----------+ +----------+
| Planner | | Decompose | | Clarify |
+----+----+ +-----+-----+ +----+-----+
v v |
+-----------+ +-----------+ |
| Retrieval |<--+ | Multi-Hop | |
+-----+-----+ | | (sub-Qs | |
v | | -> retrieve |
+------------+ | | + answer | |
| Summarizer | | | each) | |
+-----+------+ | +-----+-----+ |
v | v |
+-----------+ | +-----------+ |
| Evaluator |---+ |Synthesize | |
+-----+-----+ +-----+-----+ |
| (retry on NO, | |
| max 2 attempts) | |
v v v
Final Answer

### Multi-agent design (grounded in literature review)

- **Coordinator** - classifies each question before any retrieval happens *(ReAct: Yao et al., 2022 - reasoning before acting)*
- **Planner** - rewrites simple questions into optimized search queries
- **Decompose / Multi-Hop / Synthesize** - for complex, multi-part questions: splits into sub-questions, answers each independently, then combines into one coherent answer *(ReAct-inspired systematic task decomposition; AutoGen - Microsoft Research, 2023 - multi-agent delegation patterns)*
- **Clarify** - for ambiguous questions, asks the user for the missing detail instead of guessing
- **Hierarchical Retrieval** - two-stage retrieval: first searches document-level summaries to find the most relevant document(s), then searches only within those documents' chunks for precise passages *(RAPTOR, 2024 - recursive, tree-organized retrieval)*
- **Evaluator** - checks whether an answer is actually grounded in the retrieved context, retrying if not, up to 2 attempts *(Self-RAG, 2024 - self-reflection and self-critique loops)*
- **Orchestration** - the entire multi-path graph, with conditional branching and cycles, is built on LangGraph *(LangChain Ecosystem - stateful multi-agent workflow orchestration)*

### Multimodal ingestion pipeline

Documents aren't extracted as flat text alone - three distinct chunk types are recognized, tagged, and handled differently throughout retrieval and reporting:

- **Text** - standard prose, chunked with LangChain's RecursiveCharacterTextSplitter
- **Tables** - detected and extracted via pdfplumber, converted to Markdown, and kept intact as a single chunk (never split across chunk boundaries) so row/column structure survives. A quality filter discards pdfplumber's occasional false positives, such as a PDF form's bordered field boxes being misdetected as one large table
- **Images** - embedded images and genuinely scanned pages (detected by checking for an empty text layer, not just the absence of embedded images) are OCR'd via PyMuPDF + Tesseract, so text inside screenshots, logos, and scanned documents becomes searchable too

Retrieved table content is preserved verbatim rather than paraphrased by the LLM, and renders as a real formatted table - not flattened pipe-delimited text - in both chat answers and downloaded PDF reports.

## Setup

### Backend
```bash
cd backend
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

**Also install Tesseract OCR** - a separate system program, not just a Python package - so image and scanned-page text extraction works:
- Windows: download and run the installer from the [UB Mannheim Tesseract build](https://github.com/UB-Mannheim/tesseract/wiki), keeping the default install location (`C:\Program Files\Tesseract-OCR\`)
- macOS: `brew install tesseract`
- Linux: `sudo apt install tesseract-ocr`

> `requirements.txt` should include `pdfplumber`, `pymupdf`, `pytesseract`, and `Pillow` for the multimodal pipeline - confirm these are present before running `pip install`.

Create a `.env` file in `backend/` with:
GROQ_API_KEY=your_groq_api_key_here
DATABASE_URL=postgresql://your_pg_username:your_pg_password@localhost:5432/omnirag_db
(Get a free Groq key at console.groq.com. Requires a local PostgreSQL server installed separately - the `omnirag_db` database itself needs to be created once, e.g. `createdb omnirag_db`, before the backend can connect to it.)

Run the server:
```bash
uvicorn main:app --reload
```

### Frontend
```bash
cd omnirag-frontend
npm install
npm start
```

Opens at `http://localhost:3000`.

## Usage

1. Register/log in
2. Upload PDF documents via "My Documents" - tables and images inside them are automatically extracted and indexed alongside the plain text, no extra steps needed
3. Ask questions in "Ask OmniRAG" - watch the live agent progress bar as it retrieves, generates, and evaluates the answer
4. Try a complex, multi-part question to see decomposition in action, a vague one to see the system ask for clarification, or a question about a table or scanned image in one of your documents to see multimodal retrieval at work
5. Download a PDF report of any answer, or generate a one-paragraph summary of any document

## Team

- **Aditya Giri** - Platform Development, Workflow Orchestration, Knowledge Services (FastAPI backend, React frontend, LangGraph orchestration, retrieval engine, query decomposition, hierarchical retrieval, multimodal table/image extraction)
- **Aryan Patel** - Multi-agent reasoning
- **Pranjal Agarwal** - Document intelligence (retrieval)