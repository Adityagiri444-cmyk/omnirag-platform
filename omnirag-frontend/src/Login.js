import { useState } from "react";

function Login({ onLoginSuccess }) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      const response = await fetch("http://localhost:8000/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password }),
      });
      if (!response.ok) {
        const errData = await response.json();
        throw new Error(errData.detail || "Login failed");
      }
      const data = await response.json();
      localStorage.setItem("access_token", data.access_token);
      localStorage.setItem("refresh_token", data.refresh_token);
      onLoginSuccess();
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex" style={{ backgroundColor: "#F5F6FA" }}>
      {/* Left panel - brand moment, hidden on small screens */}
      <div
        className="hidden md:flex md:w-1/2 flex-col justify-between p-12 relative overflow-hidden"
        style={{ backgroundColor: "#1B1E3D" }}
      >
        {/* Subtle connected-nodes pattern evoking a knowledge graph, static (no motion) */}
        <svg
          className="absolute inset-0 w-full h-full opacity-[0.07]"
          viewBox="0 0 400 600"
          preserveAspectRatio="xMidYMid slice"
        >
          <circle cx="60" cy="80" r="3" fill="#fff" />
          <circle cx="180" cy="140" r="3" fill="#fff" />
          <circle cx="300" cy="90" r="3" fill="#fff" />
          <circle cx="120" cy="250" r="3" fill="#fff" />
          <circle cx="260" cy="280" r="3" fill="#fff" />
          <circle cx="340" cy="220" r="3" fill="#fff" />
          <circle cx="80" cy="380" r="3" fill="#fff" />
          <circle cx="220" cy="420" r="3" fill="#fff" />
          <circle cx="150" cy="500" r="3" fill="#fff" />
          <circle cx="310" cy="480" r="3" fill="#fff" />
          <line x1="60" y1="80" x2="180" y2="140" stroke="#fff" strokeWidth="1" />
          <line x1="180" y1="140" x2="300" y2="90" stroke="#fff" strokeWidth="1" />
          <line x1="180" y1="140" x2="120" y2="250" stroke="#fff" strokeWidth="1" />
          <line x1="120" y1="250" x2="260" y2="280" stroke="#fff" strokeWidth="1" />
          <line x1="260" y1="280" x2="340" y2="220" stroke="#fff" strokeWidth="1" />
          <line x1="120" y1="250" x2="80" y2="380" stroke="#fff" strokeWidth="1" />
          <line x1="80" y1="380" x2="220" y2="420" stroke="#fff" strokeWidth="1" />
          <line x1="220" y1="420" x2="150" y2="500" stroke="#fff" strokeWidth="1" />
          <line x1="220" y1="420" x2="310" y2="480" stroke="#fff" strokeWidth="1" />
        </svg>

        <div className="relative z-10">
          <h1
            className="text-4xl font-semibold text-white mb-4"
            style={{ fontFamily: "'Lora', serif" }}
          >
            OmniRAG
          </h1>
          <p className="text-lg" style={{ color: "#A8AEC7" }}>
            Ask questions of your documents. Get grounded, evaluated answers,
            not guesses.
          </p>
        </div>

        <div className="relative z-10 text-sm" style={{ color: "#7B82A3" }}>
          Multi-agent retrieval &middot; hierarchical search &middot; explainable reasoning
        </div>
      </div>

      {/* Right panel - the actual login form */}
      <div className="w-full md:w-1/2 flex items-center justify-center p-8">
        <div className="w-full max-w-sm">
          <h2
            className="text-2xl font-semibold mb-1"
            style={{ color: "#1B1E3D", fontFamily: "'Lora', serif" }}
          >
            Welcome back
          </h2>
          <p className="text-sm mb-8" style={{ color: "#5B6472" }}>
            Sign in to continue to your documents
          </p>

          <form onSubmit={handleSubmit}>
            <div className="mb-4">
              <label className="block text-sm font-medium mb-1" style={{ color: "#1B1E3D" }}>
                Email
              </label>
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                className="w-full px-3 py-2 border rounded-md focus:outline-none focus:ring-2 transition-colors"
                style={{ borderColor: "#D5D8E3" }}
                onFocus={(e) => (e.target.style.boxShadow = "0 0 0 2px #4C5FD5")}
                onBlur={(e) => (e.target.style.boxShadow = "none")}
              />
            </div>
            <div className="mb-6">
              <label className="block text-sm font-medium mb-1" style={{ color: "#1B1E3D" }}>
                Password
              </label>
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                className="w-full px-3 py-2 border rounded-md focus:outline-none transition-colors"
                style={{ borderColor: "#D5D8E3" }}
                onFocus={(e) => (e.target.style.boxShadow = "0 0 0 2px #4C5FD5")}
                onBlur={(e) => (e.target.style.boxShadow = "none")}
              />
            </div>
            {error && (
              <p className="text-sm mb-4" style={{ color: "#C0392B" }}>
                {error}
              </p>
            )}
            <button
              type="submit"
              disabled={loading}
              className="w-full py-2.5 rounded-md font-medium text-white transition-colors"
              style={{
                backgroundColor: loading ? "#8993E0" : "#4C5FD5",
              }}
            >
              {loading ? "Signing in..." : "Sign in"}
            </button>
          </form>
        </div>
      </div>
    </div>
  );
}

export default Login;