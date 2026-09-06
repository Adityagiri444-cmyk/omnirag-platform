import { useState, useRef, useEffect } from "react";
import { authFetch } from "./api";

const STEP_PATHS = {
  SIMPLE: ["coordinator", "planner", "retrieval", "summarizer", "evaluator"],
  COMPLEX: ["coordinator", "decompose", "multi_hop", "synthesize"],
  AMBIGUOUS: ["coordinator", "clarify"],
};

const STEP_LABELS = {
  coordinator: "Coordinator",
  planner: "Planner",
  retrieval: "Retrieval",
  summarizer: "Summarizer",
  evaluator: "Evaluator",
  decompose: "Decompose",
  multi_hop: "Multi-Hop",
  synthesize: "Synthesize",
  clarify: "Clarify",
};

function Query() {
  const [question, setQuestion] = useState("");
  const [messages, setMessages] = useState([]);
  const [running, setRunning] = useState(false);
  const [completedSteps, setCompletedSteps] = useState([]);
  const [currentStep, setCurrentStep] = useState(null);
  const [questionType, setQuestionType] = useState(null);
  const pollRef = useRef(null);
  const bottomRef = useRef(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, running]);

  const pollStatus = (taskId) => {
    pollRef.current = setInterval(async () => {
      try {
        const response = await authFetch(`http://localhost:8000/query/status/${taskId}`);
        const data = await response.json();

        setCompletedSteps(data.completed_steps || []);
        setCurrentStep(data.current_step);
        setQuestionType(data.question_type);

        if (data.done) {
          clearInterval(pollRef.current);
          setRunning(false);

          if (data.error) {
            setMessages((prev) => [
              ...prev,
              { type: "error", text: data.error },
            ]);
          } else {
            setMessages((prev) => [
              ...prev,
              {
                type: "assistant",
                text: data.answer,
                evaluation: data.evaluation,
                attempts: data.attempts,
                taskId: taskId,
              },
            ]);
          }
        }
      } catch (err) {
        clearInterval(pollRef.current);
        setRunning(false);
        setMessages((prev) => [
          ...prev,
          { type: "error", text: "Failed to check status" },
        ]);
      }
    }, 2000);
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!question.trim() || running) return;

    const userQuestion = question.trim();
    setMessages((prev) => [...prev, { type: "user", text: userQuestion }]);
    setQuestion("");
    setCompletedSteps([]);
    setCurrentStep(null);
    setQuestionType(null);
    setRunning(true);

    try {
      const response = await authFetch("http://localhost:8000/query/start", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question: userQuestion }),
      });

      if (!response.ok) {
        const errData = await response.json();
        throw new Error(errData.detail || "Failed to start query");
      }

      const data = await response.json();
      pollStatus(data.task_id);
    } catch (err) {
      setRunning(false);
      setMessages((prev) => [...prev, { type: "error", text: err.message }]);
    }
  };

  const handleDownloadReport = async (taskId) => {
    try {
      const response = await authFetch(`http://localhost:8000/query/report/${taskId}`);
      if (!response.ok) throw new Error("Failed to generate report");

      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = `omnirag_report_${taskId.slice(0, 8)}.pdf`;
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);
    } catch (err) {
      alert("Could not download report: " + err.message);
    }
  };

  const getStepStatus = (step) => {
    if (completedSteps.includes(step)) return "done";
    if (currentStep === step) return "active";
    return "pending";
  };

  // Before we know the question_type, show the default (coordinator-only) skeleton;
  // once known, show that path's actual steps.
  const activeSteps = questionType ? STEP_PATHS[questionType] : ["coordinator"];

  return (
    <div className="bg-white rounded-lg shadow-md p-6">
      <h3 className="text-xl font-bold text-gray-800 mb-4">Ask OmniRAG</h3>

      <div className="max-h-96 overflow-y-auto mb-4 space-y-3 pr-1">
        {messages.length === 0 && !running && (
          <p className="text-gray-400 text-sm text-center py-6">
            Ask a question about your documents to get started.
          </p>
        )}

        {messages.map((msg, i) => {
          if (msg.type === "user") {
            return (
              <div key={i} className="flex justify-end">
                <div className="bg-blue-500 text-white rounded-lg px-4 py-2 max-w-[80%]">
                  {msg.text}
                </div>
              </div>
            );
          }
          if (msg.type === "error") {
            return (
              <div key={i} className="flex justify-start">
                <div className="bg-red-50 text-red-600 rounded-lg px-4 py-2 max-w-[80%] text-sm">
                  {msg.text}
                </div>
              </div>
            );
          }
          return (
            <div key={i} className="flex justify-start">
              <div className="bg-gray-50 border border-gray-200 rounded-lg px-4 py-2 max-w-[80%]">
                <p className="text-gray-800">{msg.text}</p>
                <div className="flex items-center justify-between mt-1">
                  <p className="text-xs text-gray-400">
                    Evaluation: {msg.evaluation} · Attempts: {msg.attempts}
                  </p>
                  {msg.taskId && (
                    <button
                      onClick={() => handleDownloadReport(msg.taskId)}
                      className="text-xs text-blue-500 hover:underline ml-3 whitespace-nowrap"
                    >
                      Download Report
                    </button>
                  )}
                </div>
              </div>
            </div>
          );
        })}

        {running && (
          <div className="flex justify-start">
            <div className="bg-gray-50 border border-gray-200 rounded-lg px-4 py-3 max-w-[80%] w-full">
              {questionType && (
                <p className="text-[10px] uppercase tracking-wide text-gray-400 mb-2">
                  {questionType} question detected
                </p>
              )}
              <div className="flex items-center justify-between">
                {activeSteps.map((step, i) => {
                  const status = getStepStatus(step);
                  return (
                    <div key={step} className="flex items-center flex-1">
                      <div className="flex flex-col items-center flex-1">
                        <div
                          className={`w-8 h-8 rounded-full flex items-center justify-center text-xs font-bold border-2 ${status === "done"
                              ? "bg-green-500 border-green-500 text-white"
                              : status === "active"
                                ? "bg-blue-500 border-blue-500 text-white animate-pulse"
                                : "bg-gray-100 border-gray-300 text-gray-400"
                            }`}
                        >
                          {status === "done" ? "✓" : i + 1}
                        </div>
                        <span className="text-[10px] mt-1 text-gray-500">
                          {STEP_LABELS[step]}
                        </span>
                      </div>
                      {i < activeSteps.length - 1 && (
                        <div
                          className={`h-0.5 flex-1 -mt-4 ${completedSteps.includes(step) ? "bg-green-400" : "bg-gray-200"
                            }`}
                        />
                      )}
                    </div>
                  );
                })}
              </div>
            </div>
          </div>
        )}

        <div ref={bottomRef} />
      </div>

      <form onSubmit={handleSubmit} className="flex items-center gap-3">
        <input
          type="text"
          placeholder="Ask a question about your documents..."
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          className="flex-1 px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-400"
        />
        <button
          type="submit"
          disabled={running || !question.trim()}
          className="px-4 py-2 bg-blue-500 text-white rounded-md font-medium hover:bg-blue-600 transition-colors disabled:bg-gray-300 disabled:cursor-not-allowed"
        >
          {running ? "Thinking..." : "Ask"}
        </button>
      </form>
    </div>
  );
}

export default Query;