// Зеркалит Pydantic-схемы бэкенда (app/schemas/models.py)
export type VerdictStatus = "OK" | "MISSING_FIELDS" | "NO_INFO";

export interface FieldItem {
  key: string;
  label: string;
  value: string;
  bbox: [number, number, number, number] | null;
  page: number;
  source: string;
}

export interface PageInfo {
  width: number;
  height: number;
  image_b64: string | null;
}

export interface Verdict {
  status: VerdictStatus;
  text: string;
  rule_source: string | null;
}

export interface AnalyzeResponse {
  document_type: string | null;
  document_name: string;
  classifier_confidence: number | null;
  pages: PageInfo[];
  fields: FieldItem[];
  verdict: Verdict;
  timings_ms: Record<string, number>;
}

export interface SchemaFieldInfo {
  key: string;
  label: string;
}

export interface SchemaInfo {
  key: string;
  name: string;
  anchors: string[];
  fields: SchemaFieldInfo[];
}

export interface HealthInfo {
  status: string;
  ocr_engine: string;
  schemas_loaded: number;
}
