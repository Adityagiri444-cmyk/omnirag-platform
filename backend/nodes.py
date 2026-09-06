from dotenv import load_dotenv
load_dotenv()

from langchain_groq import ChatGroq
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser
from retriever import retrieve, get_document_text, hierarchical_retrieve
import re

model = ChatGroq(model="openai/gpt-oss-20b")
parser = StrOutputParser()

planner_prompt = PromptTemplate.from_template(
    "You are a query planning agent for a document retrieval system. "
    "Given a user's question, rewrite it into the clearest, most specific search query "
    "that will retrieve the most relevant document passages. "
    "If the question has multiple parts, focus on the core information need. "
    "Reply with ONLY the rewritten search query, nothing else.\n\n"
    "User question: {query}\n\n"
    "Search query:"
)
planner_chain = planner_prompt | model | parser

def node_planner(state: dict) -> dict:
    search_query = planner_chain.invoke({"query": state["query"]}).strip()
    return {"search_query": search_query}

coordinator_prompt = PromptTemplate.from_template(
    "You are a coordinator agent that decides how to handle a user's question before any retrieval happens.\n\n"
    "Classify the question into exactly one category:\n"
    "- SIMPLE: a single, clear, answerable question about one topic\n"
    "- COMPLEX: a question with multiple distinct parts or that requires comparing/combining information from different topics\n"
    "- AMBIGUOUS: a question that is too vague, unclear, or missing context to answer meaningfully as-is\n\n"
    "Question: {query}\n\n"
    "Reply with ONLY one word: SIMPLE, COMPLEX, or AMBIGUOUS."
)
coordinator_chain = coordinator_prompt | model | parser

def node_coordinator(state: dict) -> dict:
    classification = coordinator_chain.invoke({"query": state["query"]}).strip().upper()
    if classification not in ("SIMPLE", "COMPLEX", "AMBIGUOUS"):
        classification = "SIMPLE"  # safe fallback
    return {"question_type": classification}

def route_after_coordinator(state: dict) -> str:
    return state["question_type"].lower()

decompose_prompt = PromptTemplate.from_template(
    "Break the following complex question into 2-4 simpler, independent sub-questions "
    "that together fully cover the original question. "
    "Reply with ONLY a numbered list, one sub-question per line, nothing else.\n\n"
    "Question: {query}\n\n"
    "Sub-questions:"
)
decompose_chain = decompose_prompt | model | parser

def node_decompose(state: dict) -> dict:
    raw = decompose_chain.invoke({"query": state["query"]})
    sub_questions = []
    for line in raw.strip().split("\n"):
        cleaned = re.sub(r"^\s*\d+[\.\)]\s*", "", line).strip()
        if cleaned:
            sub_questions.append(cleaned)
    return {"sub_questions": sub_questions}

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

clarify_prompt = PromptTemplate.from_template(
    "The following user question is too vague or ambiguous to answer directly from documents. "
    "Write one brief, polite clarifying question asking the user for the specific detail needed.\n\n"
    "Question: {query}\n\n"
    "Clarifying question:"
)
clarify_chain = clarify_prompt | model | parser

def node_clarify(state: dict) -> dict:
    clarification = clarify_chain.invoke({"query": state["query"]})
    return {"final_answer": clarification, "evaluation": "N/A (clarification)", "attempts": 0}

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
    test_state = {"query": "What is RAG?", "attempts": 0}
    test_state.update(node_planner(test_state))
    test_state.update(node_retrieval(test_state))
    test_state.update(node_summarizer(test_state))
    test_state.update(node_evaluator(test_state))
    print("Search Query:", test_state["search_query"])
    print("\nFinal Answer:\n", test_state["final_answer"])
    print("\nEvaluation:", test_state["evaluation"])
    print("Route decision:", route_after_evaluator(test_state))