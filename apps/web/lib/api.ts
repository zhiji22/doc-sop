import type { FileItem, RunItem, ShareRunResponse, PublicRun, QaAskResponse, QaMessage } from "@/types";

export async function authedFetch(
  getToken: () => Promise<string | null>,
  url: string,
  options?: RequestInit
) {
  const token = await getToken();

  return fetch(url, {
    ...options,
    headers: {
      ...(options?.headers || {}),
      Authorization: `Bearer ${token}`,
    },
  });
}

export async function fetchFiles(
  getToken: () => Promise<string | null>,
  limit = 20
): Promise<FileItem[]> {
  const res = await authedFetch(
    getToken,
    `${process.env.NEXT_PUBLIC_API_BASE}/v1/files?limit=${limit}`
  );

  if (!res.ok) {
    throw new Error(await res.text());
  }

  return res.json();
}

export async function fetchRuns(
  getToken: () => Promise<string | null>,
  limit = 20
): Promise<RunItem[]> {
  const res = await authedFetch(
    getToken,
    `${process.env.NEXT_PUBLIC_API_BASE}/v1/runs?limit=${limit}`
  );

  if (!res.ok) {
    throw new Error(await res.text());
  }

  return res.json();
}

export async function fetchRunById(
  getToken: () => Promise<string | null>,
  runId: string
): Promise<RunItem> {
  const res = await authedFetch(
    getToken,
    `${process.env.NEXT_PUBLIC_API_BASE}/v1/runs/${runId}`
  );

  if (!res.ok) {
    throw new Error(await res.text());
  }

  return res.json();
}

export async function shareRun(
    getToken: () => Promise<string | null>,
    runId: string
): Promise<ShareRunResponse> {
    const res = await authedFetch(
      getToken,
      `${process.env.NEXT_PUBLIC_API_BASE}/v1/runs/${runId}/share`,
      {
        method: "POST",
      }
    );
  
    if (!res.ok) {
      throw new Error(await res.text());
    }
  
    return res.json();
}
  
export async function fetchPublicRun(shareId: string): Promise<PublicRun> {
    const res = await fetch(
      `${process.env.NEXT_PUBLIC_API_BASE}/v1/runs/public/${shareId}`
    );
  
    if (!res.ok) {
      throw new Error(await res.text());
    }
  
    return res.json();
}

export async function unshareRun(
  getToken: () => Promise<string | null>,
  runId: string
): Promise<ShareRunResponse> {
  const res = await authedFetch(
    getToken,
    `${process.env.NEXT_PUBLIC_API_BASE}/v1/runs/${runId}/unshare`,
    {
      method: "POST",
    }
  );

  if (!res.ok) {
    throw new Error(await res.text());
  }

  return res.json();
}

export async function askFileQuestion(
  getToken: () => Promise<string | null>,
  fileId: string,
  question: string
): Promise<QaAskResponse> {
  const res = await authedFetch(
    getToken,
    `${process.env.NEXT_PUBLIC_API_BASE}/v1/qa/ask`,
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        file_id: fileId,
        question,
      }),
    }
  );

  if (!res.ok) {
    throw new Error(await res.text());
  }

  return res.json();
}

export async function fetchQaMessages(
  getToken: () => Promise<string | null>,
  fileId: string,
  limit = 50
): Promise<QaMessage[]> {
  const res = await authedFetch(
    getToken,
    `${process.env.NEXT_PUBLIC_API_BASE}/v1/qa/messages/${fileId}?limit=${limit}`
  );

  if (!res.ok) {
    throw new Error(await res.text());
  }

  return res.json();
}