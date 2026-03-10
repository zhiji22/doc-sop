"use client";

import { useState } from "react";
import { useAuth } from "@clerk/nextjs";

type UploadedFileInfo = {
  file_id: string;
  storage_key: string;
  filename: string;
};


export default function Dashboard() {
    const { getToken } = useAuth();
  
    const [log, setLog] = useState<string>("");
    const [uploadedFile, setUploadedFile] = useState<UploadedFileInfo | null>(null);
    const [result, setResult] = useState<any>(null);
  
    async function upload(file: File) {
      setResult(null);
      setLog("1) getting token...");
      const token = await getToken();
  
      setLog("2) presigning...");
      const presignRes = await fetch(`${process.env.NEXT_PUBLIC_API_BASE}/v1/files/presign`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
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
  
      setLog(`3) uploading file to S3-compatible storage... file_id=${file_id}`);
  
      const putRes = await fetch(upload_url, {
        method: "PUT",
        headers: {
          "Content-Type": file.type || "application/octet-stream",
        },
        body: file,
      });
  
      if (!putRes.ok) {
        throw new Error(`upload failed: ${putRes.status}`);
      }
  
      setUploadedFile({
        file_id,
        storage_key,
        filename: file.name,
      });
  
      setLog(`uploaded: ${file.name}`);
    }
  
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
  
        <pre style={{ marginTop: 16, whiteSpace: "pre-wrap" }}>{log}</pre>
  
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