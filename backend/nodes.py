from dotenv import load_dotenv
load_dotenv()

from langchain_groq import ChatGroq
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser
from retriever import retrieve, get_document_text, hierarchical_retrieve, get_documents_metadata
from sandbox import run_sandboxed
import re

model = ChatGroq(model="openai/gpt-oss-20b").with_retry(
    retry_if_exception_type=(Exception,),
    stop_after_attempt=3,
    wait_exponential_jitter=True,
)
parser = StrOutputParser()

def format_context(docs: list[dict]) -> str:
    """Join retrieved chunk dicts into a single context string for LLM prompts."""
    return "\n\n".join(d["content"] for d in docs)

def extract_table_markdown(docs: list[dict]) -> list[str]:
    """Pull out just the table chunks' raw content, so it can be appended
    to a final answer verbatim instead of being paraphrased by the LLM."""
    return [d["content"] for d in docs if d.get("chunk_type") == "table"]

def append_tables(answer: str, table_chunks: list[str]) -> str:
    """Append any retrieved table(s) to an LLM-generated answer, verbatim,
    so rows/numbers can't get scrambled by paraphrasing."""
    if not table_chunks:
        return answer
    tables_section = "\n\n---\n\n**Relevant table(s) from source documents:**\n\n" + "\n\n".join(table_chunks)
    return answer + tables_section

coordinator_prompt = PromptTemplate.from_template(
    "You are a coordinator agent for a document Q&A system with conversation memory.\n\n"
    "Recent conversation history:\n{history}\n\n"
    "Current user question: {query}\n\n"
    "Do ALL of the following in one response:\n\n"
    "1. If the current question refers back to the conversation (e.g., uses words like 'it', 'that', "
    "'the previous one', 'explain more', or is otherwise incomplete without context), rewrite it into "
    "a fully self-contained question using the history above. If it's already self-contained, just repeat it as-is.\n\n"
    "2. Classify the RESOLVED question into exactly one category:\n"
    "   - SIMPLE: a single, clear, answerable question about the CONTENT of documents\n"
    "   - COMPLEX: a question with multiple distinct parts, or comparing/combining information from different topics\n"
    "   - AMBIGUOUS: a question too vague or unclear to answer meaningfully even with the history above\n"
    "   - COMPUTE: a question asking for a CALCULATION or STATISTIC about the document collection itself "
    "(e.g., how many documents, total/average word count) - NOT about document content\n\n"
    "3. Depending on the classification, also produce:\n"
    "   - If SIMPLE: the clearest, most specific search query for retrieval (one line)\n"
    "   - If COMPLEX: 2-4 independent sub-questions that together fully cover the resolved question (numbered list, one per line)\n"
    "   - If AMBIGUOUS: one brief, polite clarifying question to ask the user (one line)\n"
    "   - If COMPUTE: a short Python snippet using a pre-existing variable `data` "
    "(a list of dicts with keys 'filename', 'word_count', 'char_count'). "
    "The snippet MUST end with a print() statement. Only use built-in Python plus math/statistics/collections.\n\n"
    "Respond in EXACTLY this format, nothing else:\n"
    "RESOLVED: <the self-contained resolved question>\n"
    "TYPE: <SIMPLE|COMPLEX|AMBIGUOUS|COMPUTE>\n"
    "OUTPUT:\n"
    "<the corresponding output>"
)
coordinator_chain = coordinator_prompt | model | parser

def node_coordinator(state: dict) -> dict:
    history_text = state.get("history_text", "(no prior conversation)")
    raw = coordinator_chain.invoke({"history": history_text, "query": state["query"]})

    resolved_match = re.search(r"RESOLVED:\s*(.*?)\n(?=TYPE:)", raw, re.DOTALL)
    resolved_query = resolved_match.group(1).strip() if resolved_match else state["query"]

    type_match = re.search(r"TYPE:\s*(SIMPLE|COMPLEX|AMBIGUOUS|COMPUTE)", raw, re.IGNORECASE)
    classification = type_match.group(1).upper() if type_match else "SIMPLE"

    output_match = re.search(r"OUTPUT:\s*(.*)", raw, re.DOTALL)
    output_text = output_match.group(1).strip() if output_match else ""

    result = {"question_type": classification, "resolved_query": resolved_query}

    if classification == "SIMPLE":
        result["search_query"] = output_text.split("\n")[0].strip()
    elif classification == "COMPLEX":
        sub_questions = []
        for line in output_text.split("\n"):
            cleaned = re.sub(r"^\s*\d+[\.\)]\s*", "", line).strip()
            if cleaned:
                sub_questions.append(cleaned)
        result["sub_questions"] = sub_questions
    elif classification == "AMBIGUOUS":
        result["final_answer"] = output_text.split("\n")[0].strip()
        result["evaluation"] = "N/A (clarification)"
        result["attempts"] = 0
    elif classification == "COMPUTE":
        code = output_text
        if code.startswith("```"):
            code = re.sub(r"^```(?:python)?\n?", "", code)
            code = re.sub(r"\n?```$", "", code)
        result["compute_code"] = code.strip()

    return result

def route_after_coordinator(state: dict) -> str:
    return state["question_type"].lower()

def node_compute(state: dict) -> dict:
    data = get_documents_metadata()
    output = run_sandboxed(state["compute_code"], data)
    return {
        "final_answer": output,
        "evaluation": "N/A (computed)",
        "attempts": 1,
    }

def node_multi_hop(state: dict) -> dict:
    query_to_use = state.get("resolved_query", state["query"])
    sub_answers = []
    collected_tables = []
    collected_docs = []
    for sub_q in state["sub_questions"]:
        docs = hierarchical_retrieve(sub_q, k_docs=2, k_chunks=6)
        context = format_context(docs)
        answer = summarizer_chain.invoke({"context": context, "question": sub_q})
        sub_answers.append({"question": sub_q, "answer": answer})
        collected_tables.extend(extract_table_markdown(docs))
        collected_docs.extend(docs)
    # retrieved_docs is populated here too (not just in node_retrieval) so the
    # PDF report's "Retrieved Context" section has something to show for
    # COMPLEX/multi-hop questions, instead of "No context retrieved."
    return {
        "sub_answers": sub_answers,
        "resolved_query": query_to_use,
        "retrieved_tables": collected_tables,
        "retrieved_docs": collected_docs,
    }

synthesis_prompt = PromptTemplate.from_template(
    "You are given a complex original question and answers to its sub-questions. "
    "Combine them into one clear, coherent final answer to the original question.\n\n"
    "Original question: {query}\n\n"
    "Sub-question answers:\n{sub_answers_formatted}\n\n"
    "Final answer:"
)
synthesis_chain = synthesis_prompt | model | parser

def node_synthesize(state: dict) -> dict:
    query_to_use = state.get("resolved_query", state["query"])
    formatted = "\n\n".join(
        f"Q: {item['question']}\nA: {item['answer']}" for item in state["sub_answers"]
    )
    answer = synthesis_chain.invoke({"query": query_to_use, "sub_answers_formatted": formatted})
    answer = append_tables(answer, state.get("retrieved_tables", []))
    return {"final_answer": answer, "evaluation": "N/A (multi-hop)", "attempts": 1}

summarizer_prompt = PromptTemplate.from_template(
    "Answer the question using only the context below. "
    "If the context doesn't contain the answer, say so. "
    "If the context includes findings attributed to other sources (e.g., "
    "cited studies, prior research, or comparisons to other work — often "
    "marked by reference numbers or phrases like 'a previous study found'), "
    "clearly distinguish those from the main document's own reported "
    "findings, and prioritize the main document's own conclusion when it "
    "directly answers the question.\n\n"
    "Context:\n{context}\n\n"
    "Question: {question}\n\n"
    "Answer:"
)
summarizer_chain = summarizer_prompt | model | parser

def node_summarizer(state: dict) -> dict:
    query_to_use = state.get("resolved_query", state["query"])
    docs = state["retrieved_docs"]
    context = format_context(docs)
    answer = summarizer_chain.invoke({"context": context, "question": query_to_use})
    answer = append_tables(answer, extract_table_markdown(docs))
    return {"final_answer": answer}

def node_retrieval(state: dict) -> dict:
    query_to_use = state.get("search_query", state.get("resolved_query", state["query"]))
    docs = hierarchical_retrieve(query_to_use, k_docs=2, k_chunks=3)
    return {"retrieved_docs": docs}

evaluator_prompt = PromptTemplate.from_template(
    "Question: {question}\n"
    "Context used:\n{context}\n"
    "Generated Answer: {answer}\n\n"
    "Does the answer fully and accurately answer the question using ONLY the context above? "
    "Reply with exactly one word: YES or NO."
)
evaluator_chain = evaluator_prompt | model | parser

def node_evaluator(state: dict) -> dict:
    query_to_use = state.get("resolved_query", state["query"])
    context = format_context(state["retrieved_docs"])
    verdict = evaluator_chain.invoke({
        "question": query_to_use,
        "context": context,
        "answer": state["final_answer"]
    }).strip().upper()
    attempts = state.get("attempts", 0) + 1
    return {"evaluation": verdict, "attempts": attempts}

def route_after_evaluator(state: dict) -> str:
    if state["evaluation"] == "YES" or state["attempts"] >= 2:
        return "done"
    return "retry"

summary_prompt = PromptTemplate.from_template(
    "Summarize the following document in one clear, well-written paragraph. "
    "Cover the main topic and the most important points.\n\n"
    "Document:\n{text}\n\n"
    "Summary:"
)
summary_chain = summary_prompt | model | parser

def summarize_document(filename: str) -> str:
    text = get_document_text(filename)
    if not text:
        return "No content found for this document."
    text = text[:6000]
    return summary_chain.invoke({"text": text})

research_report_prompt = PromptTemplate.from_template(
    "You are writing a structured research report on the topic below, based ONLY on the "
    "provided source excerpts from the user's uploaded documents. Do not use outside knowledge "
    "beyond what's in the excerpts.\n\n"
    "Topic: {topic}\n\n"
    "Source excerpts (from multiple documents):\n{context}\n\n"
    "Write a well-organized report with these sections:\n"
    "1. Introduction - briefly frame the topic based on what the sources cover\n"
    "2. Key Findings - organize the substantive content from the sources into 2-4 thematic subsections, "
    "citing which document each point comes from where possible\n"
    "3. Gaps or Limitations - note anything the topic implies that the uploaded documents do NOT cover\n"
    "4. Conclusion - a brief synthesis\n\n"
    "Use clear Markdown formatting with headers. Report:"
)
research_report_chain = research_report_prompt | model | parser

def generate_research_report(topic: str) -> dict:
    """
    Retrieves broadly across ALL documents (not narrowed to one via hierarchical
    retrieval, since a research topic may legitimately span several documents)
    and synthesizes a structured multi-section report.
    """
    chunks = retrieve(topic, k=8)
    if not chunks:
        return {
            "topic": topic,
            "report": "No relevant content found in your uploaded documents for this topic.",
            "sources_used": 0,
        }

    context = "\n\n---\n\n".join(c["content"] for c in chunks)
    report_text = research_report_chain.invoke({"topic": topic, "context": context})
    report_text = append_tables(report_text, extract_table_markdown(chunks))

    return {
        "topic": topic,
        "report": report_text,
        "sources_used": len(chunks),
    }

if __name__ == "__main__":
    test_state = {"query": "What is RAG?", "attempts": 0, "history_text": "(no prior conversation)"}
    test_state.update(node_coordinator(test_state))
    print("Resolved:", test_state["resolved_query"])
    print("Type:", test_state["question_type"])