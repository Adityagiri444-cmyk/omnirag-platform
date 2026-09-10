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

coordinator_prompt = PromptTemplate.from_template(
    "You are a coordinator agent for a document Q&A system. Given a user's question, do ALL of the following in one response:\n\n"
    "1. Classify the question into exactly one category:\n"
    "   - SIMPLE: a single, clear, answerable question about the CONTENT of documents\n"
    "   - COMPLEX: a question with multiple distinct parts, or comparing/combining information from different topics\n"
    "   - AMBIGUOUS: a question too vague or unclear to answer meaningfully as-is\n"
    "   - COMPUTE: a question asking for a CALCULATION or STATISTIC about the document collection itself "
    "(e.g., how many documents, total/average word count, which document is longest/shortest) - NOT about document content\n\n"
    "2. Depending on the classification, also produce:\n"
    "   - If SIMPLE: the clearest, most specific search query for retrieval (one line)\n"
    "   - If COMPLEX: 2-4 independent sub-questions that together fully cover the original question (numbered list, one per line)\n"
    "   - If AMBIGUOUS: one brief, polite clarifying question to ask the user (one line)\n"
    "   - If COMPUTE: a short Python snippet that computes the answer using a pre-existing variable `data`, "
    "which is a list of dicts, each with keys 'filename', 'word_count', 'char_count'. "
    "The snippet MUST end with a print() statement showing the final answer in a clear sentence. "
    "Only use built-in Python plus math/statistics/collections - no imports needed for simple counts/sums/averages.\n\n"
    "Respond in EXACTLY this format, nothing else:\n"
    "TYPE: <SIMPLE|COMPLEX|AMBIGUOUS|COMPUTE>\n"
    "OUTPUT:\n"
    "<the corresponding output>\n\n"
    "Question: {query}"
)
coordinator_chain = coordinator_prompt | model | parser

def node_coordinator(state: dict) -> dict:
    raw = coordinator_chain.invoke({"query": state["query"]})

    type_match = re.search(r"TYPE:\s*(SIMPLE|COMPLEX|AMBIGUOUS|COMPUTE)", raw, re.IGNORECASE)
    classification = type_match.group(1).upper() if type_match else "SIMPLE"

    output_match = re.search(r"OUTPUT:\s*(.*)", raw, re.DOTALL)
    output_text = output_match.group(1).strip() if output_match else ""

    result = {"question_type": classification}

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
    sub_answers = []
    for sub_q in state["sub_questions"]:
        docs = hierarchical_retrieve(sub_q, k_docs=2, k_chunks=2)
        context = "\n\n".join(docs)
        answer = summarizer_chain.invoke({"context": context, "question": sub_q})
        sub_answers.append({"question": sub_q, "answer": answer})
    return {"sub_answers": sub_answers}

synthesis_prompt = PromptTemplate.from_template(
    "You are given a complex original question and answers to its sub-questions. "
    "Combine them into one clear, coherent final answer to the original question.\n\n"
    "Original question: {query}\n\n"
    "Sub-question answers:\n{sub_answers_formatted}\n\n"
    "Final answer:"
)
synthesis_chain = synthesis_prompt | model | parser

def node_synthesize(state: dict) -> dict:
    formatted = "\n\n".join(
        f"Q: {item['question']}\nA: {item['answer']}" for item in state["sub_answers"]
    )
    answer = synthesis_chain.invoke({"query": state["query"], "sub_answers_formatted": formatted})
    return {"final_answer": answer, "evaluation": "N/A (multi-hop)", "attempts": 1}

summarizer_prompt = PromptTemplate.from_template(
    "Answer the question using only the context below. "
    "If the context doesn't contain the answer, say so.\n\n"
    "Context:\n{context}\n\n"
    "Question: {question}\n\n"
    "Answer:"
)
summarizer_chain = summarizer_prompt | model | parser

def node_summarizer(state: dict) -> dict:
    context = "\n\n".join(state["retrieved_docs"])
    answer = summarizer_chain.invoke({"context": context, "question": state["query"]})
    return {"final_answer": answer}

def node_retrieval(state: dict) -> dict:
    query_to_use = state.get("search_query", state["query"])
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
    context = "\n\n".join(state["retrieved_docs"])
    verdict = evaluator_chain.invoke({
        "question": state["query"],
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
    text = text[:6000]  # keep within model context limits
    return summary_chain.invoke({"text": text})

if __name__ == "__main__":
    test_state = {"query": "How many documents do I have and what's their average word count?", "attempts": 0}
    test_state.update(node_coordinator(test_state))
    print("Question type:", test_state["question_type"])
    print("Generated code:\n", test_state.get("compute_code"))
    test_state.update(node_compute(test_state))
    print("\nFinal Answer:\n", test_state["final_answer"])