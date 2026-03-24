"use client";

import { useEffect, useState } from "react";
import { useAuth } from "@clerk/nextjs";
import { askFileQuestion, askFileQuestionStream, fetchQaMessages } from "@/lib/api";
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

      const userQuestion = question.trim();
      setQuestion(""); // 立刻清空输入框
      
      // 1.  先把用户消息加到界面上 
      const userMsg: QaMessage = {
        id: `temp-user-${Date.now()}`,
        file_id: file.id,
        user_id: "",
        role: "user",
        content: userQuestion,
        citations: [],
      };
      setMessages((prev) => [...prev, userMsg]);

      // 2. 创建一个"正在生成"的assistant 消息占位
      const assistantMsgId = `temp-assistant-${Date.now()}`;
      const assistantMsg: QaMessage = {
        id: assistantMsgId,
        file_id: file.id,
        user_id: "",
        role: "assistant",
        content: "",
        citations: []
      }

      setMessages((prev) => [...prev, assistantMsg]);

      // 3. 调用流式接口
      await askFileQuestionStream(getToken, file.id, userQuestion, {
        onCitations: (citations) => {
          // 收到citations时，更新assistant消息的citations
          setMessages((prev) => (
            prev.map((msg) => (
              msg.id === assistantMsgId ? {...msg, citations} : msg
            ))
          ))
        },
        onToken: (token) => {
          // 每收到一个 token，追加到 assistant 消息的 content 后面
          setMessages((prev) =>
            prev.map((msg) =>
              msg.id === assistantMsgId
                ? { ...msg, content: msg.content + token }
                : msg
            )
          );
        },
        onToolCall: (toolName, toolArgs) => {
          // Agent 正在调用工具时，在 assistant 消息中显示状态
          setMessages((prev) =>
            prev.map((msg) =>
              msg.id === assistantMsgId
                ? {
                    ...msg,
                    content: msg.content + `\n🔧 Using tool: ${toolName}(${JSON.stringify(toolArgs)})\n`,
                  }
                : msg
            )
          );
        },
        onToolResult: (toolName, resultPreview) => {
          setMessages((prev) =>
            prev.map((msg) =>
              msg.id === assistantMsgId
                ? {
                    ...msg,
                    content: msg.content + `✅ Got result from ${toolName}\n\n`,
                  }
                : msg
            )
          );
        },
        onDone: (_fullAnswer) => {
          // 流结束，可以做一些收尾工作
          // 答案已经通过 onToken 逐字拼好了，不需要额外处理
        },
        onError: (err) => {
          setError(err);
        },
      })

      // await loadMessages(file.id);
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