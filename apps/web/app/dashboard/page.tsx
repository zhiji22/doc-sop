/**
 * Dashboard 页面（/dashboard）
 * 核心交互页面，提供两个主要功能：
 *   1. 上传文件（PDF/DOCX）→ 通过预签名 URL 直传 MinIO
 *   2. 选择模板生成结构化输出 → 调用后端 LLM 服务
 *
 * 此页面受 middleware.ts 保护，必须登录后才能访问。
 */
"use client";

import { useState } from "react";
import { useAuth } from "@clerk/nextjs";

/** 上传成功后保存的文件信息 */
type UploadedFileInfo = {
  file_id: string;
  storage_key: string;
  filename: string;
};


export default function Dashboard() {
  // 从 Clerk 获取 getToken 方法，用于请求后端 API 时附带 JWT
  const { getToken } = useAuth();

  const [log, setLog] = useState<string>("");           // 操作日志，显示当前步骤
  const [uploadedFile, setUploadedFile] = useState<UploadedFileInfo | null>(null);  // 已上传的文件信息
  const [result, setResult] = useState<any>(null);       // LLM 生成的结构化结果

  /**
   * 文件上传流程（三步）：
   *   1. 调用后端 /v1/files/presign → 获取预签名 URL
   *   2. 用预签名 URL 将文件 PUT 到 MinIO（浏览器直传，不经过后端）
   *   3. 保存文件信息，等待用户选择模板生成
   */
  async function upload(file: File) {
    setResult(null);

    // 步骤 1：获取 Clerk JWT token
    setLog("1) getting token...");
    const token = await getToken();

    // 步骤 2：请求后端生成预签名上传 URL
    setLog("2) presigning...");
    const presignRes = await fetch(`${process.env.NEXT_PUBLIC_API_BASE}/v1/files/presign`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${token}`,   // 携带 JWT 认证
      },
      body: JSON.stringify({
        filename: file.name,
        mime: file.type || "application/octet-stream",
        size: file.size,
      }),
    });

    if (!presignRes.ok) {
      const t = await presignRes.text();
      throw new Error(`presign failed: ${t}`);
    }

    const { upload_url, file_id, storage_key } = await presignRes.json();

    // 步骤 3：用预签名 URL 直接 PUT 文件到 MinIO
    setLog(`3) uploading file to S3-compatible storage... file_id=${file_id}`);

    const putRes = await fetch(upload_url, {
      method: "PUT",
      headers: {
        "Content-Type": file.type || "application/octet-stream",
      },
      body: file,   // 文件二进制直传
    });

    if (!putRes.ok) {
      throw new Error(`upload failed: ${putRes.status}`);
    }

    // 上传成功，保存文件信息供后续生成使用
    setUploadedFile({
      file_id,
      storage_key,
      filename: file.name,
    });

    setLog(`uploaded: ${file.name}`);
  }

  /**
   * 创建生成任务：
   * 调用后端 /v1/runs，传入 file_id 和模板类型，
   * 后端同步执行：下载文件 → 解析文档 → LLM 生成 → 返回结果。
   */
  async function createRun(template: "sop" | "checklist" | "summary") {
    if (!uploadedFile) {
      alert("Please upload a file first.");
      return;
    }

    setLog(`4) creating run (${template})...`);
    const token = await getToken();

    const runRes = await fetch(`${process.env.NEXT_PUBLIC_API_BASE}/v1/runs`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify({
        file_id: uploadedFile.file_id,
        template,
      }),
    });

    const data = await runRes.json();

    if (!runRes.ok) {
      throw new Error(data.detail || "create run failed");
    }

    setResult(data);
    setLog(`run completed: ${data.id}`);
  }

  return (
    <div style={{ padding: 24 }}>
      <h2>Dashboard</h2>

      {/* 文件选择器：仅接受 PDF 和 DOCX */}
      <input
        type="file"
        accept=".pdf,.docx"
        onChange={(e) => {
          const f = e.target.files?.[0];
          if (f) {
            upload(f).catch((err) => setLog(String(err)));
          }
        }}
      />

      {/* 上传成功后显示模板选择按钮 */}
      {uploadedFile && (
        <div style={{ marginTop: 16 }}>
          <div>Uploaded: {uploadedFile.filename}</div>
          <div style={{ marginTop: 12, display: "flex", gap: 8 }}>
            <button onClick={() => createRun("sop")}>Generate SOP</button>
            <button onClick={() => createRun("checklist")}>Generate Checklist</button>
            <button onClick={() => createRun("summary")}>Generate Summary</button>
          </div>
        </div>
      )}

      {/* 操作日志 */}
      <pre style={{ marginTop: 16, whiteSpace: "pre-wrap" }}>{log}</pre>

      {/* LLM 生成结果展示 */}
      {result && (
        <div style={{ marginTop: 24 }}>
          <h3>Run Result</h3>
          <pre style={{ whiteSpace: "pre-wrap", overflowX: "auto" }}>
            {JSON.stringify(result, null, 2)}
          </pre>
        </div>
      )}
    </div>
  );
}