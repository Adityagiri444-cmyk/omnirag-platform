# OmniRAG - Intelligent Multi-Agent Knowledge Platform

OmniRAG is a full-stack Retrieval-Augmented Generation (RAG) platform that lets users upload documents, ask questions about them, and get grounded, evaluated answers - with live visualization of the AI's reasoning steps and downloadable PDF reports.

Built as a 5th-semester mini project.

## Features

- **Authenticated document management** - upload, list, delete, and summarize PDF documents per user, with admin/user role separation
- **Multi-agent RAG pipeline** (LangGraph): Coordinator -> (Planner/Decompose/Clarify) -> Retrieval -> Summarizer/Synthesize -> Evaluator, with automatic retry on ungrounded answers
- **Query decomposition** - complex, multi-part questions are automatically broken into sub-questions, answered independently, and synthesized into one coherent answer
- **Hierarchical retrieval** - a two-stage RAPTOR-inspired search: document-level summaries narrow down to the right document first, then chunk-level search finds precise passages within it
- **Real-time agent visualization** - live progress tracking as each pipeline step runs, shown as an animated status bar in the chat UI
- **Chat interface** - full conversation history, not just single Q&A
- **Downloadable PDF reports** - every answer can be exported as a structured report (question, search query, retrieved context, answer, evaluation)
- **Document summarization** - one-click AI summary of any uploaded document
- **Analytics dashboard** - upload trends and document counts, visualized with charts

## Tech Stack

- **Backend**: FastAPI, SQLAlchemy, SQLite, JWT auth (python-jose), bcrypt
- **Frontend**: React, Tailwind CSS, Recharts
- **AI/Orchestration**: LangChain, LangGraph, Groq (free-tier LLM API), HuggingFace sentence-transformers (local embeddings, no API cost)
- **Vector Store**: ChromaDB (local, persistent - two collections: chunk-level and document-summary-level)
- **PDF Processing**: pypdf (extraction), ReportLab (report generation)

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

## Setup

### Backend
```bash
cd backend
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

Create a `.env` file in `backend/` with:
GROQ_API_KEY=your_groq_api_key_here
(Get a free key at console.groq.com)

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
2. Upload PDF documents via "My Documents"
3. Ask questions in "Ask OmniRAG" - watch the live agent progress bar as it retrieves, generates, and evaluates the answer
4. Try a complex, multi-part question to see decomposition in action, or a vague one to see the system ask for clarification
5. Download a PDF report of any answer, or generate a one-paragraph summary of any document

## Team

- **Aditya Giri** - Platform Development, Workflow Orchestration, Knowledge Services (FastAPI backend, React frontend, LangGraph orchestration, retrieval engine, query decomposition, hierarchical retrieval)
- **Aryan Patel** - Multi-agent reasoning
- **Pranjal Agarwal** - Document intelligence (retrieval)
