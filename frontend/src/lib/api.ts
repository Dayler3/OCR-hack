import type { AnalyzeResponse, HealthInfo, SchemaInfo } from "@/types";

const BASE = ""; // через Vite-прокси /api → localhost:8000

export async function getSchemas(): Promise<SchemaInfo[]> {
  const r = await fetch(`${BASE}/api/schemas`);
  if (!r.ok) throw new Error(`GET /api/schemas → ${r.status}`);
  return r.json();
}

export async function getHealth(): Promise<HealthInfo> {
  const r = await fetch(`${BASE}/api/health`);
  if (!r.ok) throw new Error(`GET /api/health → ${r.status}`);
  return r.json();
}

export async function analyze(
  file: File,
  question: string,
  docType: string | null,
): Promise<AnalyzeResponse> {
  const form = new FormData();
  form.append("file", file);
  form.append("question", question);
  if (docType) form.append("doc_type", docType);

  const r = await fetch(`${BASE}/api/analyze`, { method: "POST", body: form });
  if (!r.ok) {
    const detail = await r.json().catch(() => null);
    throw new Error(detail?.detail ?? `POST /api/analyze → ${r.status}`);
  }
  return r.json();
}
