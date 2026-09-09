import { useState, useRef, useEffect } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { authFetch } from "./api";

const STEP_PATHS = {
  SIMPLE: ["coordinator", "planner", "retrieval", "summarizer", "evaluator"],
  COMPLEX: ["coordinator", "decompose", "multi_hop", "synthesize"],
  AMBIGUOUS: ["coordinator", "clarify"],
  COMPUTE: ["coordinator", "compute"],
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
  compute: "Compute",
};

const INK = "#1B1E3D";
const SIGNAL = "#4C5FD5";
const SAGE = "#4F9D69";
const SLATE = "#5B6472";

const markdownComponents = {
  table: ({ children }) => (
    <div className="overflow-x-auto my-3">
      <table className="min-w-full border-collapse text-sm">{children}</table>
    </div>
  ),
  thead: ({ children }) => (
    <thead style={{ backgroundColor: "#EDEFFB" }}>{children}</thead>
  ),
  th: ({ children }) => (
    <th
      className="text-left px-3 py-2 font-semibold"
      style={{ color: INK, border: "1px solid #E4E6EF" }}
    >
      {children}
    </th>
  ),
  td: ({ children }) => (
    <td className="px-3 py-2" style={{ border: "1px solid #E4E6EF", color: INK }}>
      {children}
    </td>
  ),
  h1: ({ children }) => (
    <h1 className="text-lg font-semibold mt-3 mb-2" style={{ color: INK }}>
      {children}
    </h1>
  ),
  h2: ({ children }) => (
    <h2 className="text-base font-semibold mt-3 mb-2" style={{ color: INK }}>
      {children}
    </h2>
  ),
  h3: ({ children }) => (
    <h3 className="text-sm font-semibold mt-2 mb-1" style={{ color: INK }}>
      {children}
    </h3>
  ),
  p: ({ children }) => <p className="mb-2 leading-relaxed">{children}</p>,
  ul: ({ children }) => <ul className="list-disc pl-5 mb-2 space-y-1">{children}</ul>,
  ol: ({ children }) => <ol className="list-decimal pl-5 mb-2 space-y-1">{children}</ol>,
  code: ({ inline, children }) =>
    inline ? (
      <code
        className="px-1 py-0.5 rounded text-xs"
        style={{ backgroundColor: "#EDEFFB", color: SIGNAL }}
      >
        {children}
      </code>
    ) : (
      <pre
        className="rounded-md p-3 my-2 overflow-x-auto text-xs"
        style={{ backgroundColor: "#1B1E3D", color: "#F5F6FA" }}
      >
        <code>{children}</code>
      </pre>
    ),
  strong: ({ children }) => <strong style={{ color: INK }}>{children}</strong>,
  hr: () => <hr className="my-3" style={{ borderColor: "#E4E6EF" }} />,
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
            setMessages((prev) => [...prev, { type: "error", text: data.error }]);
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
        setMessages((prev) => [...prev, { type: "error", text: "Failed to check status" }]);
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

  const activeSteps = questionType ? STEP_PATHS[questionType] : ["coordinator"];

  return (
    <div
      className="bg-white rounded-lg p-6 flex flex-col h-full"
      style={{
        boxShadow: "0 4px 20px rgba(27,30,61,0.08)",
        borderTop: `3px solid ${SIGNAL}`,
        height: "100%",
        minHeight: "500px",
      }}
    >
      <h3
        className="text-xl font-semibold mb-4 flex-shrink-0"
        style={{ color: INK, fontFamily: "'Lora', serif" }}
      >
        Ask OmniRAG
      </h3>

      <div className="flex-1 overflow-y-auto mb-4 space-y-3 pr-1">
        {messages.length === 0 && !running && (
          <p className="text-sm text-center py-6" style={{ color: "#9298AB" }}>
            Ask a question about your documents to get started.
          </p>
        )}

        {messages.map((msg, i) => {
          if (msg.type === "user") {
            return (
              <div key={i} className="flex justify-end">
                <div
                  className="text-white rounded-lg px-4 py-2 max-w-[85%]"
                  style={{ backgroundColor: SIGNAL }}
                >
                  {msg.text}
                </div>
              </div>
            );
          }
          if (msg.type === "error") {
            return (
              <div key={i} className="flex justify-start">
                <div className="bg-red-50 text-red-600 rounded-lg px-4 py-2 max-w-[85%] text-sm">
                  {msg.text}
                </div>
              </div>
            );
          }
          return (
            <div key={i} className="flex justify-start">
              <div
                className="rounded-lg px-4 py-3 max-w-[85%] w-full text-sm"
                style={{ backgroundColor: "#F5F6FA", border: "1px solid #E4E6EF" }}
              >
                <div style={{ color: INK }}>
                  <ReactMarkdown remarkPlugins={[remarkGfm]} components={markdownComponents}>
                    {msg.text}
                  </ReactMarkdown>
                </div>
                <div className="flex items-center justify-between mt-2 pt-2" style={{ borderTop: "1px solid #E4E6EF" }}>
                  <p className="text-xs" style={{ color: SLATE }}>
                    Evaluation: {msg.evaluation} · Attempts: {msg.attempts}
                  </p>
                  {msg.taskId && (
                    <button
                      onClick={() => handleDownloadReport(msg.taskId)}
                      className="text-xs hover:underline ml-3 whitespace-nowrap"
                      style={{ color: SIGNAL }}
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
            <div
              className="rounded-lg px-4 py-3 max-w-[85%] w-full"
              style={{ backgroundColor: "#F5F6FA", border: "1px solid #E4E6EF" }}
            >
              {questionType && (
                <p className="text-[10px] uppercase tracking-wide mb-2" style={{ color: "#9298AB" }}>
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
                          className="w-8 h-8 rounded-full flex items-center justify-center text-xs font-bold border-2"
                          style={
                            status === "done"
                              ? { backgroundColor: SAGE, borderColor: SAGE, color: "#fff" }
                              : status === "active"
                                ? { backgroundColor: SIGNAL, borderColor: SIGNAL, color: "#fff" }
                                : { backgroundColor: "#F0F1F6", borderColor: "#D5D8E3", color: "#9298AB" }
                          }
                        >
                          {status === "done" ? "✓" : i + 1}
                        </div>
                        <span className="text-[10px] mt-1" style={{ color: SLATE }}>
                          {STEP_LABELS[step]}
                        </span>
                      </div>
                      {i < activeSteps.length - 1 && (
                        <div
                          className="h-0.5 flex-1 -mt-4"
                          style={{ backgroundColor: completedSteps.includes(step) ? SAGE : "#E4E6EF" }}
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

      <form onSubmit={handleSubmit} className="flex items-center gap-3 flex-shrink-0">
        <input
          type="text"
          placeholder="Ask a question about your documents..."
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          className="flex-1 px-3 py-2 border rounded-md focus:outline-none transition-colors"
          style={{ borderColor: "#D5D8E3" }}
          onFocus={(e) => (e.target.style.boxShadow = `0 0 0 2px ${SIGNAL}`)}
          onBlur={(e) => (e.target.style.boxShadow = "none")}
        />
        <button
          type="submit"
          disabled={running || !question.trim()}
          className="px-4 py-2 rounded-md font-medium text-white transition-colors"
          style={{ backgroundColor: running || !question.trim() ? "#B7BEEA" : SIGNAL }}
        >
          {running ? "Thinking..." : "Ask"}
        </button>
      </form>
    </div>
  );
}

export default Query;