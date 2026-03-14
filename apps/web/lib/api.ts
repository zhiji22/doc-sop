import type { FileItem, RunItem } from "@/types";

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