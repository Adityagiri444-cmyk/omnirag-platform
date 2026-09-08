import { useState, useEffect } from "react";
import { authFetch } from "./api";

const INK = "#1B1E3D";
const SIGNAL = "#4C5FD5";
const SLATE = "#5B6472";
const AMBER = "#C97B2E";

function Documents() {
  const [documents, setDocuments] = useState([]);
  const [file, setFile] = useState(null);
  const [error, setError] = useState("");
  const [uploading, setUploading] = useState(false);
  const [searchTerm, setSearchTerm] = useState("");
  const [summaries, setSummaries] = useState({});
  const [summarizing, setSummarizing] = useState({});

  const fetchDocuments = async () => {
    try {
      const response = await authFetch("http://localhost:8000/documents/");
      const data = await response.json();
      setDocuments(data);
    } catch (err) {
      setError("Failed to load documents");
    }
  };

  useEffect(() => {
    fetchDocuments();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleUpload = async (e) => {
    e.preventDefault();
    if (!file) return;

    setError("");
    setUploading(true);

    const formData = new FormData();
    formData.append("file", file);

    try {
      const response = await authFetch("http://localhost:8000/documents/upload", {
        method: "POST",
        body: formData,
      });

      if (!response.ok) {
        const errData = await response.json();
        throw new Error(errData.detail || "Upload failed");
      }

      setFile(null);
      fetchDocuments();
    } catch (err) {
      setError(err.message);
    } finally {
      setUploading(false);
    }
  };

  const handleDelete = async (id) => {
    try {
      const response = await authFetch(`http://localhost:8000/documents/${id}`, {
        method: "DELETE",
      });

      if (!response.ok) {
        const errData = await response.json();
        throw new Error(errData.detail || "Delete failed");
      }

      fetchDocuments();
    } catch (err) {
      setError(err.message);
    }
  };

  const handleSummarize = async (id) => {
    setSummarizing((prev) => ({ ...prev, [id]: true }));
    try {
      const response = await authFetch(`http://localhost:8000/documents/${id}/summary`);
      if (!response.ok) throw new Error("Failed to generate summary");
      const data = await response.json();
      setSummaries((prev) => ({ ...prev, [id]: data.summary }));
    } catch (err) {
      setSummaries((prev) => ({ ...prev, [id]: "Failed to generate summary." }));
    } finally {
      setSummarizing((prev) => ({ ...prev, [id]: false }));
    }
  };

  const filteredDocuments = documents.filter((doc) =>
    doc.filename.toLowerCase().includes(searchTerm.toLowerCase())
  );

  return (
    <div className="bg-white rounded-lg shadow-md p-6">
      <h3 className="text-xl font-semibold mb-4" style={{ color: INK, fontFamily: "'Lora', serif" }}>
        My Documents
      </h3>

      <form onSubmit={handleUpload} className="flex items-center gap-3 mb-4">
        <input
          type="file"
          accept=".pdf"
          onChange={(e) => setFile(e.target.files[0])}
          className="text-sm"
          style={{ color: SLATE }}
        />
        <button
          type="submit"
          disabled={uploading || !file}
          className="px-4 py-2 rounded-md font-medium text-white transition-colors whitespace-nowrap"
          style={{ backgroundColor: uploading || !file ? "#B7BEEA" : SIGNAL }}
        >
          {uploading ? "Uploading..." : "Upload PDF"}
        </button>
      </form>

      <input
        type="text"
        placeholder="Search documents by name..."
        value={searchTerm}
        onChange={(e) => setSearchTerm(e.target.value)}
        className="w-full px-3 py-2 border rounded-md mb-4 focus:outline-none transition-colors"
        style={{ borderColor: "#D5D8E3" }}
        onFocus={(e) => (e.target.style.boxShadow = `0 0 0 2px ${SIGNAL}`)}
        onBlur={(e) => (e.target.style.boxShadow = "none")}
      />

      {error && (
        <p className="text-sm mb-3" style={{ color: "#C0392B" }}>
          {error}
        </p>
      )}

      <ul className="divide-y" style={{ borderColor: "#EEEFF4" }}>
        {filteredDocuments.map((doc) => (
          <li key={doc.id} className="py-3">
            <div className="flex items-center justify-between">
              <span style={{ color: INK }}>{doc.filename}</span>
              <div className="flex gap-2">
                <button
                  onClick={() => handleSummarize(doc.id)}
                  disabled={summarizing[doc.id]}
                  className="px-3 py-1 text-sm rounded-md transition-colors disabled:opacity-50"
                  style={{ backgroundColor: "#EDEFFB", color: SIGNAL }}
                >
                  {summarizing[doc.id] ? "Summarizing..." : "Summarize"}
                </button>
                <button
                  onClick={() => handleDelete(doc.id)}
                  className="px-3 py-1 text-sm rounded-md transition-colors"
                  style={{ backgroundColor: "#FBEFE7", color: AMBER }}
                >
                  Delete
                </button>
              </div>
            </div>
            {summaries[doc.id] && (
              <p
                className="text-sm mt-2 rounded-md p-3"
                style={{ color: SLATE, backgroundColor: "#F5F6FA" }}
              >
                {summaries[doc.id]}
              </p>
            )}
          </li>
        ))}
      </ul>

      {documents.length === 0 && (
        <p className="text-sm text-center py-4" style={{ color: "#9298AB" }}>
          No documents uploaded yet.
        </p>
      )}
      {documents.length > 0 && filteredDocuments.length === 0 && (
        <p className="text-sm text-center py-4" style={{ color: "#9298AB" }}>
          No documents match your search.
        </p>
      )}
    </div>
  );
}

export default Documents;