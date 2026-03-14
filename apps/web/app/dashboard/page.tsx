"use client";

import { useEffect, useRef, useState } from "react";
import { useAuth } from "@clerk/nextjs";
import { fetchFiles, fetchRunById, fetchRuns, authedFetch } from "@/lib/api";
import type { FileItem, RunItem } from "@/types";
import { FileList } from "@/components/files/FileList";
import { RunHistory } from "@/components/runs/RunHistory";
import { ResultRenderer } from "@/components/result/ResultRenderer";

import Link from "next/link";

export default function Dashboard() {
  const { getToken } = useAuth();

  const [log, setLog] = useState("");
  const [files, setFiles] = useState<FileItem[]>([]);
  const [runs, setRuns] = useState<RunItem[]>([]);
  const [selectedFile, setSelectedFile] = useState<FileItem | null>(null);
  const [selectedRun, setSelectedRun] = useState<RunItem | null>(null);

  const pollingRef = useRef<NodeJS.Timeout | null>(null);

  function stopPolling() {
    if (pollingRef.current) {
      clearInterval(pollingRef.current);
      pollingRef.current = null;
    }
  }

  async function refreshFilesAndRuns() {
    const [fileData, runData] = await Promise.all([
      fetchFiles(getToken, 30),
      fetchRuns(getToken, 30),
    ]);
    setFiles(fileData);
    setRuns(runData);
  }

  async function upload(file: File) {
    setLog("1) presigning upload...");

    const presignRes = await authedFetch(
      getToken,
      `${process.env.NEXT_PUBLIC_API_BASE}/v1/files/presign`,
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          filename: file.name,
          mime: file.type || "application/octet-stream",
          size: file.size,
        }),
      }
    );

    if (!presignRes.ok) {
      throw new Error(`presign failed: ${await presignRes.text()}`);
    }

    const { upload_url } = await presignRes.json();

    setLog("2) uploading file...");

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

    // 刷新文件列表，并自动选中刚上传的文件（列表按时间倒序，第一条就是最新的）
    const fileData = await fetchFiles(getToken, 30);
    setFiles(fileData);

    const newest = fileData[0];
    if (newest) {
      setSelectedFile(newest);
    }

    await fetchRuns(getToken, 30).then(setRuns);
    setLog(`✅ uploaded: ${file.name}`);
  }

  async function createRun(template: "sop" | "checklist" | "summary") {
    if (!selectedFile) {
      alert("Please select a file first.");
      return;
    }

    stopPolling();
    setSelectedRun(null);
    setLog(`Creating ${template} run...`);

    const res = await authedFetch(
      getToken,
      `${process.env.NEXT_PUBLIC_API_BASE}/v1/runs`,
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          file_id: selectedFile.id,
          template,
        }),
      }
    );

    const data = await res.json();

    if (!res.ok) {
      throw new Error(data.detail || "create run failed");
    }

    setSelectedRun(data);
    setLog(`⏳ run queued: ${data.id}`);
    await refreshFilesAndRuns();

    pollingRef.current = setInterval(async () => {
      try {
        const latest = await fetchRunById(getToken, data.id);
        setSelectedRun(latest);

        if (latest.status === "done" || latest.status === "failed") {
          stopPolling();
          await refreshFilesAndRuns();
          setLog(
            latest.status === "done"
              ? "✅ run completed"
              : `❌ run failed: ${latest.error}`
          );
        } else {
          setLog(`⏳ run status: ${latest.status}`);
        }
      } catch (err) {
        stopPolling();
        setLog(`polling failed: ${String(err)}`);
      }
    }, 1000);
  }

  useEffect(() => {
    refreshFilesAndRuns().catch((err) =>
      setLog(`Failed to load dashboard data: ${String(err)}`)
    );

    return () => stopPolling();
  }, []);

  const filteredRuns = selectedFile
    ? runs.filter((run) => run.file_id === selectedFile.id)
    : runs;

  return (
    <div
      style={{
        padding: 24,
        display: "grid",
        gridTemplateColumns: "280px 320px 1fr",
        gap: 16,
        alignItems: "start",
      }}
    >
      <aside style={panelStyle}>
        <h3 style={{ marginTop: 0 }}>Files</h3>

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

        <div style={{ marginTop: 16 }}>
          <FileList
            files={files}
            selectedFileId={selectedFile?.id ?? null}
            onSelect={(file) => setSelectedFile(file)}
          />
        </div>
      </aside>

      <aside style={panelStyle}>
        <h3 style={{ marginTop: 0 }}>Runs</h3>

        <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginBottom: 16 }}>
          <button onClick={() => createRun("sop")} disabled={!selectedFile}>
            Generate SOP
          </button>
          <button onClick={() => createRun("checklist")} disabled={!selectedFile}>
            Checklist
          </button>
          <button onClick={() => createRun("summary")} disabled={!selectedFile}>
            Summary
          </button>
        </div>

        <div style={{ marginBottom: 12, fontSize: 13, color: "#666" }}>
          {selectedFile ? `Selected file: ${selectedFile.filename}` : "No file selected"}
        </div>

        <RunHistory
          runs={filteredRuns}
          selectedRunId={selectedRun?.id ?? null}
          onSelect={(run) => setSelectedRun(run)}
        />
      </aside>

      <main style={panelStyle}>
        <h3 style={{ marginTop: 0 }}>Result</h3>

        <div style={{ marginBottom: 16, fontSize: 13, color: "#666" }}>{log}</div>

        {!selectedRun ? (
          <div>Select a run to view its result.</div>
        ) : selectedRun.status === "queued" || selectedRun.status === "running" ? (
          <div>
            <div style={{ fontWeight: 600 }}>Processing...</div>
            <div style={{ marginTop: 8 }}>Current status: {selectedRun.status}</div>
          </div>
        ) : selectedRun.status === "failed" ? (
          <div style={{ color: "red" }}>Failed: {selectedRun.error}</div>
        ) : selectedRun?.status === "done" ? (
          <div style={{ marginBottom: 16 }}>
            <Link href={`/runs/${selectedRun.id}`}>Open full detail page</Link>
          </div>
        ) : (
          <ResultRenderer run={selectedRun} />
        )}
      </main>
    </div>
  );
}

const panelStyle: React.CSSProperties = {
  border: "1px solid #ddd",
  borderRadius: 12,
  padding: 16,
  background: "#fafafa",
  minHeight: "80vh",
};