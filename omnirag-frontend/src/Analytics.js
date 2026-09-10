import { useState, useEffect } from "react";
import { BarChart, Bar, XAxis, YAxis, Tooltip, CartesianGrid, ResponsiveContainer } from "recharts";
import { authFetch } from "./api";

const INK = "#1B1E3D";
const SLATE = "#5B6472";
const SIGNAL = "#4C5FD5";
const AMBER = "#C97B2E";

function Analytics() {
  const [stats, setStats] = useState(null);
  const [usage, setUsage] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    const fetchStats = async () => {
      try {
        const response = await authFetch("http://localhost:8000/documents/stats");
        if (!response.ok) throw new Error("Failed to load stats");
        const data = await response.json();
        setStats(data);
      } catch (err) {
        setError(err.message);
      }
    };

    const fetchUsage = async () => {
      try {
        const response = await authFetch("http://localhost:8000/query/usage/summary");
        if (response.ok) {
          const data = await response.json();
          setUsage(data);
        }
      } catch (err) {
        // Non-critical, fail silently if usage stats aren't available yet
      }
    };

    fetchStats();
    fetchUsage();

    const interval = setInterval(() => {
      fetchStats();
      fetchUsage();
    }, 5000);

    return () => clearInterval(interval);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  if (error) {
    return (
      <div className="bg-white rounded-lg shadow-md p-6">
        <p className="text-red-500 text-sm">{error}</p>
      </div>
    );
  }

  if (!stats) {
    return (
      <div className="bg-white rounded-lg shadow-md p-6">
        <div className="animate-pulse space-y-3">
          <div className="h-4 bg-gray-200 rounded w-1/3"></div>
          <div className="h-4 bg-gray-200 rounded w-1/2"></div>
          <div className="h-40 bg-gray-100 rounded"></div>
        </div>
      </div>
    );
  }

  const rpmUsed = usage?.requests_last_minute || 0;
  const rpmLimit = usage?.rpm_limit || 30;
  const rpmPercent = Math.min((rpmUsed / rpmLimit) * 100, 100);
  const rpmColor = rpmPercent > 80 ? AMBER : SIGNAL;

  return (
    <div className="bg-white rounded-lg shadow-md p-6">
      <h3 className="text-xl font-semibold mb-4" style={{ color: INK, fontFamily: "'Lora', serif" }}>
        Analytics
      </h3>
      <p className="text-gray-600 mb-4">Total Documents: {stats.total_documents}</p>

      {stats.upload_history.length > 0 && (
        <div className="mb-6">
          <h4 className="text-sm font-semibold text-gray-500 mb-2">Uploads (Last 7 Days)</h4>
          <ResponsiveContainer width="100%" height={220}>
            <BarChart data={stats.upload_history}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="date" tick={{ fontSize: 12 }} />
              <YAxis allowDecimals={false} tick={{ fontSize: 12 }} />
              <Tooltip />
              <Bar dataKey="count" fill={SIGNAL} radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}

      {stats.documents_per_user.length > 0 && (
        <div className="mb-6">
          <h4 className="text-sm font-semibold text-gray-500 mb-2">Documents Per User</h4>
          <ResponsiveContainer width="100%" height={220}>
            <BarChart data={stats.documents_per_user}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="user" tick={{ fontSize: 12 }} />
              <YAxis allowDecimals={false} tick={{ fontSize: 12 }} />
              <Tooltip />
              <Bar dataKey="count" fill="#10b981" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}

      {usage && usage.total_queries > 0 && (
        <div>
          <h4 className="text-sm font-semibold text-gray-500 mb-2">LLM Token Usage</h4>

          <div className="mb-3">
            <div className="flex items-center justify-between text-xs mb-1">
              <span style={{ color: SLATE }}>Rate limit (per minute)</span>
              <span style={{ color: rpmColor, fontWeight: 600 }}>
                {rpmUsed} / {rpmLimit}
              </span>
            </div>
            <div className="w-full h-2 rounded-full" style={{ backgroundColor: "#EEEFF4" }}>
              <div
                className="h-2 rounded-full transition-all"
                style={{ width: `${rpmPercent}%`, backgroundColor: rpmColor }}
              />
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div className="bg-gray-50 rounded-md p-3">
              <div className="text-xs text-gray-400">Total Queries</div>
              <div className="text-xl font-bold text-gray-800">{usage.total_queries}</div>
            </div>
            <div className="bg-gray-50 rounded-md p-3">
              <div className="text-xs text-gray-400">Total LLM Calls</div>
              <div className="text-xl font-bold text-gray-800">{usage.total_llm_calls}</div>
            </div>
            <div className="bg-gray-50 rounded-md p-3">
              <div className="text-xs text-gray-400">Total Tokens</div>
              <div className="text-xl font-bold text-gray-800">{usage.total_tokens.toLocaleString()}</div>
            </div>
            <div className="bg-gray-50 rounded-md p-3">
              <div className="text-xs text-gray-400">Avg Tokens / Query</div>
              <div className="text-xl font-bold text-gray-800">{usage.avg_tokens_per_query}</div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default Analytics;