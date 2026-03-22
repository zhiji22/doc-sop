import type { FileItem, RunItem, ShareRunResponse, PublicRun, QaAskResponse, QaMessage, CitationItem } from "@/types";

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

// 流式请求 question
export async function askFileQuestionStream(
  getToken: () => Promise<string | null>,
  fileId: string,
  question: string,
  callbacks: {
    onCitations: (citations: CitationItem[]) => void;
    onToken: (token: string) => void;
    onDone: (fullAnswer: string) => void;
    onError: (error: string) => void;
  }
): Promise<void> {
  const token = await getToken();

  const res = await fetch(
    `${process.env.NEXT_PUBLIC_API_BASE}/v1/qa/ask/stream`,
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify({
        file_id: fileId,
        question,
      }),
    }
  );
  if (!res.ok) {
    callbacks.onError(await res.text());
    return;
  }
  // res.body 是一个 ReadableStream，我们用 reader 逐块读取
  const reader = res.body?.getReader();
  if (!reader) {
    callbacks.onError("No response body");
    return;
  }

  const decoder = new TextDecoder();
  let buffer = "";  // 缓冲区，因为一次 read 可能包含多条 SSE 消息，也可能只有半条

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    // 把二进制数据解码成字符串，追加到缓冲区
    buffer += decoder.decode(value, { stream: true });

    // 按 "\n\n" 分割，每个完整的 SSE 消息以 "\n\n" 结尾
    const parts = buffer.split("\n\n");

    // 最后一个 part 可能是不完整的消息，留在缓冲区
    buffer = parts.pop() || "";

    for (const part of parts) {
      // 去掉 "data: " 前缀
      const line = part.trim();
      if (!line.startsWith("data: ")) continue;

      const jsonStr = line.slice(6);  // "data: " 是 6 个字符

      try {
        const msg = JSON.parse(jsonStr);

        if (msg.type === "citations") {
          callbacks.onCitations(msg.citations);
        } else if (msg.type === "token") {
          callbacks.onToken(msg.token);
        } else if (msg.type === "done") {
          callbacks.onDone(msg.answer);
        }
      } catch {
        // JSON 解析失败，忽略这条消息
      }
    }
  }

}