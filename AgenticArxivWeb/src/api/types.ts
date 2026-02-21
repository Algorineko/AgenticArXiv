// src/api/types.ts

export type Role = "user" | "assistant";

// ReAct history step
export interface ReactStep {
  thought: string;
  action: string;
  observation: string;
  [k: string]: any;
}

export interface Paper {
  id: string;
  title: string;
  authors?: string[];
  summary?: string | null;
  published?: string | null;
  updated?: string | null;
  pdf_url?: string | null;
  primary_category?: string | null;
  categories?: string[];
  comment?: string | null;
  links?: string[];
  [k: string]: any;
}

export interface PdfAsset {
  paper_id: string;
  pdf_url?: string | null;
  local_path?: string | null;
  status?: string; // READY / DOWNLOADING / FAILED ...
  size_bytes?: number | null;
  sha256?: string | null;
  downloaded_at?: string | null;
  updated_at?: string | null;
  error?: string | null;
  [k: string]: any;
}

export interface TranslateAsset {
  paper_id: string;
  input_pdf_path?: string | null;
  output_mono_path?: string | null;
  output_dual_path?: string | null;
  status?: string; // READY / TRANSLATING / FAILED ...
  service?: string | null;
  threads?: number | null;
  translated_at?: string | null;
  updated_at?: string | null;
  error?: string | null;
  log_path?: string | null;
  [k: string]: any;
}

// 后端 models.schemas.TranslateTask（按 endpoints.py / translate_runner.py 的字段适配）
export interface TranslateTask {
  task_id: string;
  session_id: string;
  paper_id: string;

  status: string; // PENDING / RUNNING / SUCCEEDED / FAILED ...
  progress?: number; // 0~1

  input_pdf_url?: string | null;
  input_pdf_path?: string | null;
  output_pdf_path?: string | null;

  error?: string | null;
  meta?: Record<string, any>;

  created_at?: string | null;
  updated_at?: string | null;

  [k: string]: any;
}

export interface ChatRequest {
  session_id: string;
  message: string;
  agent_model?: string | null;
}

export interface ChatResponse {
  session_id: string;
  message: string;
  reply: string;
  history: ReactStep[];

  papers: Paper[];
  pdf_assets: PdfAsset[];
  translate_assets: TranslateAsset[];

  // ✅ 后端已新增 tasks
  tasks?: TranslateTask[];
}

export interface PdfAssetsResponse {
  assets: PdfAsset[];
}

export interface TranslateAssetsResponse {
  assets: TranslateAsset[];
}

// SSE envelope：event_bus.publish 的结构
export interface SseEnvelope {
  type: string; // connected / task_created / task_started / task_succeeded / task_failed / ...
  session_id?: string;

  kind?: string; // translate
  task?: TranslateTask;

  message?: string;
  [k: string]: any;
}
