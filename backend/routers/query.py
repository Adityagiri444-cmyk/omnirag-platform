import uuid
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from models import User
from dependencies import get_current_user
from graph import graph
from report_generator import generate_query_report
from token_tracker import TokenUsageTracker
from conversation_memory import add_turn, format_history, clear_history

router = APIRouter(prefix="/query", tags=["Query"])

class QueryRequest(BaseModel):
    question: str

class QueryResponse(BaseModel):
    answer: str
    evaluation: str
    attempts: int

task_status: dict = {}

usage_totals = {
    "total_queries": 0,
    "total_llm_calls": 0,
    "total_tokens": 0,
}

def is_rate_limit_error(exc: Exception) -> bool:
    text = str(exc).lower()
    return "429" in text or "rate limit" in text or "rate_limit" in text

def run_graph_task(task_id: str, question: str, user_id: int):
    task_status[task_id] = {
        "current_step": "starting",
        "completed_steps": [],
        "done": False,
        "question": question,
        "question_type": None,
        "search_query": None,
        "retrieved_docs": None,
        "answer": None,
        "evaluation": None,
        "attempts": None,
        "error": None,
        "token_usage": None,
    }
    history_text = format_history(user_id)
    state = {"query": question, "attempts": 0, "history_text": history_text}
    tracker = TokenUsageTracker()
    config = {"callbacks": [tracker]}
    try:
        for step_output in graph.stream(state, config=config):
            node_name = list(step_output.keys())[0]
            node_update = step_output[node_name]
            state.update(node_update)
            task_status[task_id]["current_step"] = node_name
            task_status[task_id]["completed_steps"].append(node_name)
            task_status[task_id]["question_type"] = state.get("question_type")

        usage = tracker.summary()
        final_answer = state.get("final_answer")

        task_status[task_id]["done"] = True
        task_status[task_id]["current_step"] = None
        task_status[task_id]["search_query"] = state.get("search_query")
        task_status[task_id]["retrieved_docs"] = state.get("retrieved_docs")
        task_status[task_id]["answer"] = final_answer
        task_status[task_id]["evaluation"] = state.get("evaluation")
        task_status[task_id]["attempts"] = state.get("attempts")
        task_status[task_id]["token_usage"] = usage

        if final_answer and state.get("question_type") != "AMBIGUOUS":
            add_turn(user_id, question, final_answer)

        usage_totals["total_queries"] += 1
        usage_totals["total_llm_calls"] += usage["llm_calls"]
        usage_totals["total_tokens"] += usage["total_tokens"]
    except Exception as e:
        task_status[task_id]["done"] = True
        if is_rate_limit_error(e):
            task_status[task_id]["error"] = (
                "We're hitting high demand on the free AI service right now. "
                "Please wait about 30 seconds and try again."
            )
        else:
            task_status[task_id]["error"] = str(e)

@router.post("/", response_model=QueryResponse)
def run_query(
    request: QueryRequest,
    current_user: User = Depends(get_current_user)
):
    history_text = format_history(current_user.id)
    result = graph.invoke({"query": request.question, "attempts": 0, "history_text": history_text})
    if result.get("final_answer"):
        add_turn(current_user.id, request.question, result["final_answer"])
    return {
        "answer": result["final_answer"],
        "evaluation": result["evaluation"],
        "attempts": result["attempts"]
    }

@router.post("/start")
def start_query(
    request: QueryRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user)
):
    task_id = str(uuid.uuid4())
    background_tasks.add_task(run_graph_task, task_id, request.question, current_user.id)
    return {"task_id": task_id}

@router.post("/clear-memory")
def clear_memory(current_user: User = Depends(get_current_user)):
    clear_history(current_user.id)
    return {"detail": "Conversation memory cleared"}

@router.get("/status/{task_id}")
def get_query_status(
    task_id: str,
    current_user: User = Depends(get_current_user)
):
    status = task_status.get(task_id)
    if not status:
        raise HTTPException(status_code=404, detail="Task not found")
    return status

@router.get("/usage/summary")
def get_usage_summary(current_user: User = Depends(get_current_user)):
    avg_tokens = (
        usage_totals["total_tokens"] / usage_totals["total_queries"]
        if usage_totals["total_queries"] > 0 else 0
    )
    return {
        "total_queries": usage_totals["total_queries"],
        "total_llm_calls": usage_totals["total_llm_calls"],
        "total_tokens": usage_totals["total_tokens"],
        "avg_tokens_per_query": round(avg_tokens, 1),
        "requests_last_minute": TokenUsageTracker.requests_in_last_minute(),
        "rpm_limit": 30,
    }

@router.get("/report/{task_id}")
def download_report(
    task_id: str,
    current_user: User = Depends(get_current_user)
):
    status = task_status.get(task_id)
    if not status:
        raise HTTPException(status_code=404, detail="Task not found")
    if not status.get("done"):
        raise HTTPException(status_code=400, detail="Query still in progress")
    if status.get("error"):
        raise HTTPException(status_code=400, detail="Cannot generate report for a failed query")

    pdf_buffer = generate_query_report(status)
    return StreamingResponse(
        pdf_buffer,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=omnirag_report_{task_id[:8]}.pdf"}
    )