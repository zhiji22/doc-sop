"use client";

import { useEffect, useState } from "react";
import { useAuth } from "@clerk/nextjs";
import { askFileQuestion, fetchQaMessages } from "@/lib/api";
import type { FileItem, QaMessage } from "@/types";

export function FileQaPanel({ file }: { file: FileItem | null }) {
  const { getToken } = useAuth();

  const [question, setQuestion] = useState("");
  const [messages, setMessages] = useState<QaMessage[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function loadMessages(fileId: string) {
    const data = await fetchQaMessages(getToken, fileId, 50);
    setMessages(data);
  }

  async function submitQuestion() {
    if (!file || !question.trim()) return;

    try {
      setLoading(true);
      setError("");

      await askFileQuestion(getToken, file.id, question.trim());
      setQuestion("");
      await loadMessages(file.id);
    } catch (err) {
      setError(String(err));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    if (file?.id) {
      loadMessages(file.id).catch((err) => setError(String(err)));
    } else {
      setMessages([]);
    }
  }, [file?.id]);

  if (!file) {
    return <div>Select a file to start asking questions.</div>;
  }

  return (
    <div style={{ display: "grid", gap: 12 }}>
      <div style={{ fontWeight: 600 }}>Ask about this document</div>

      <div style={{ display: "flex", gap: 8 }}>
        <input
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          placeholder="Ask a question about the document..."
          style={{
            flex: 1,
            padding: 10,
            border: "1px solid #ddd",
            borderRadius: 8,
          }}
        />
        <button onClick={submitQuestion} disabled={loading || !question.trim()}>
          {loading ? "Asking..." : "Ask"}
        </button>
      </div>

      {error && <div style={{ color: "red" }}>{error}</div>}

      <div style={{ display: "grid", gap: 10, marginTop: 8 }}>
        {messages.length === 0 ? (
          <div style={{ color: "#666" }}>No questions yet.</div>
        ) : (
          messages.map((msg) => (
            <div
              key={msg.id}
              style={{
                border: "1px solid #ddd",
                borderRadius: 10,
                padding: 12,
                background: msg.role === "user" ? "#fafafa" : "#fff",
              }}
            >
              <div style={{ fontWeight: 600, marginBottom: 6 }}>
                {msg.role === "user" ? "You" : "Assistant"}
              </div>

              <div style={{ whiteSpace: "pre-wrap" }}>{msg.content}</div>

              {msg.role === "assistant" && msg.citations && msg.citations.length > 0 && (
                <div style={{ marginTop: 10 }}>
                  <div style={{ fontSize: 13, fontWeight: 600 }}>Citations</div>
                  <div style={{ display: "grid", gap: 6, marginTop: 6 }}>
                    {msg.citations.map((c, idx) => (
                      <div
                        key={idx}
                        style={{
                          border: "1px solid #eee",
                          borderRadius: 8,
                          padding: 8,
                          background: "#fafafa",
                          fontSize: 13,
                        }}
                      >
                        <div><strong>Chunk {c.chunk_index}</strong></div>
                        <div>{c.snippet}</div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          ))
        )}
      </div>
    </div>
  );
}