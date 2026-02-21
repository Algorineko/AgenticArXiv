// src/stores/appStore.ts
import { defineStore } from "pinia";
import { api, getApiBase } from "@/api/client";
import { openEventsSse } from "@/api/sse";
import type {
  ChatResponse,
  Paper,
  PdfAsset,
  TranslateAsset,
  Role,
  ReactStep,
  TranslateTask,
  SseEnvelope,
} from "@/api/types";

export interface ChatMessage {
  role: Role;
  content: string;
  ts: number;
}

function nowTs() {
  return Date.now();
}

// EventSource 不适合放进可序列化 state，放模块变量
let _es: EventSource | null = null;
let _reconnectTimer: number | null = null;
let _reconnectBackoffMs = 1000;

function clearReconnectTimer() {
  if (_reconnectTimer != null) {
    window.clearTimeout(_reconnectTimer);
    _reconnectTimer = null;
  }
}

export const useAppStore = defineStore("app", {
  state: () => ({
    apiBase: getApiBase(),
    sessionId: (localStorage.getItem("session_id") || "demo1") as string,

    loading: false,
    lastError: "" as string,

    messages: [] as ChatMessage[],

    papers: [] as Paper[],
    pdfAssets: [] as PdfAsset[],
    translateAssets: [] as TranslateAsset[],

    // ✅ 翻译任务列表（来自 /chat.tasks 或 SSE）
    tasks: [] as TranslateTask[],

    lastHistory: [] as ReactStep[],

    // 论文列表按钮操作：true=走 /chat 让 agent 决定调用工具；false=直调 /pdf/* 工具接口
    preferAgent: true,

    // SSE 状态（可用于 UI 展示/调试）
    sseStatus: "idle" as "idle" | "connecting" | "connected" | "error",
    sseLastEvent: "" as string,
    sseLastEventTs: 0 as number,
  }),

  getters: {
    pdfMap(state) {
      const m = new Map<string, PdfAsset>();
      (state.pdfAssets || []).forEach((a) => m.set(a.paper_id, a));
      return m;
    },
    translateMap(state) {
      const m = new Map<string, TranslateAsset>();
      (state.translateAssets || []).forEach((a) => m.set(a.paper_id, a));
      return m;
    },
  },

  actions: {
    setSessionId(id: string) {
      const next = (id || "default").trim() || "default";
      if (next === this.sessionId) return;

      this.sessionId = next;
      localStorage.setItem("session_id", this.sessionId);

      // session 切换：清任务 + 重连 SSE（避免串消息）
      this.tasks = [];
      this.closeSse();
      this.ensureSse();
    },

    pushUser(content: string) {
      this.messages.push({ role: "user", content, ts: nowTs() });
    },
    pushAssistant(content: string) {
      this.messages.push({ role: "assistant", content, ts: nowTs() });
    },

    // ---------------- SSE ----------------
    ensureSse() {
      if (typeof window === "undefined") return;

      const sid = this.sessionId || "default";
      if (_es) return;

      clearReconnectTimer();
      this.sseStatus = "connecting";

      _es = openEventsSse(this.apiBase, sid, {
        onOpen: () => {
          this.sseStatus = "connected";
          this.sseLastEvent = "open";
          this.sseLastEventTs = nowTs();
          _reconnectBackoffMs = 1000;
        },
        onError: () => {
          this.sseStatus = "error";
          this.sseLastEvent = "error";
          this.sseLastEventTs = nowTs();

          const readyState = _es?.readyState; // 0 CONNECTING, 1 OPEN, 2 CLOSED
          if (readyState === 2) {
            this.closeSse();
            this._scheduleReconnect();
          }
        },
        onEvent: (evt) => this._handleSseEvent(evt),
      });
    },

    closeSse() {
      clearReconnectTimer();
      if (_es) {
        try {
          _es.close();
        } catch {
          // ignore
        }
      }
      _es = null;
      this.sseStatus = "idle";
    },

    _scheduleReconnect() {
      if (typeof window === "undefined") return;
      if (_reconnectTimer != null) return;

      const delay = Math.min(_reconnectBackoffMs, 15000);
      _reconnectBackoffMs = Math.min(_reconnectBackoffMs * 2, 15000);

      _reconnectTimer = window.setTimeout(() => {
        _reconnectTimer = null;
        this.closeSse();
        this.ensureSse();
      }, delay);
    },

    _upsertTask(t: TranslateTask) {
      const id = t?.task_id;
      if (!id) return;

      const idx = this.tasks.findIndex((x) => x.task_id === id);
      if (idx >= 0) {
        this.tasks[idx] = { ...this.tasks[idx], ...t };
      } else {
        this.tasks.unshift(t);
      }

      if (this.tasks.length > 50) this.tasks.length = 50;
    },

    async _handleSseEvent(evt: SseEnvelope) {
      if (!evt || typeof evt !== "object") return;

      this.sseLastEvent = evt.type || "message";
      this.sseLastEventTs = nowTs();

      if (evt.type === "connected") {
        this.sseStatus = "connected";
        return;
      }

      // 任务事件：{ kind:"translate", task:{...} }
      if (evt.kind === "translate" && evt.task) {
        this._upsertTask(evt.task);
      }

      // created/started：可选刷新一次，让右侧状态更快变化（TRANSLATING 等）
      if (
        (evt.type === "task_created" || evt.type === "task_started") &&
        evt.kind === "translate"
      ) {
        await Promise.allSettled([this.fetchTranslateAssets(), this.fetchPdfAssets()]);
      }

      // succeeded：刷新 assets，立刻显示 READY
      if (evt.type === "task_succeeded" && evt.kind === "translate") {
        await Promise.allSettled([this.fetchTranslateAssets(), this.fetchPdfAssets()]);
      }

      // failed：记录错误
      if (evt.type === "task_failed" && evt.kind === "translate") {
        const msg = evt.task?.error || evt.message || "翻译任务失败";
        this.lastError = msg;
      }
    },

    // ---------------- API（原有方法名保持不变） ----------------
    async refreshSnapshot() {
      // 论文是 session 维度；assets 是全局缓存列表
      try {
        this.ensureSse();

        const [papersRes, pdfRes, trRes] = await Promise.all([
          api.get(`/sessions/${encodeURIComponent(this.sessionId)}/papers`),
          api.get(`/pdf/assets`),
          api.get(`/translate/assets`),
        ]);

        this.papers = papersRes.data?.papers || [];
        this.pdfAssets = pdfRes.data?.assets || [];
        this.translateAssets = trRes.data?.assets || [];
      } catch (e: any) {
        this.lastError = e?.response?.data?.detail || e?.message || String(e);
      }
    },

    async sendChat(message: string) {
      const text = (message || "").trim();
      if (!text) return;

      // 尽量提前连上 SSE，避免错过 task_started/task_succeeded
      this.ensureSse();

      this.loading = true;
      this.lastError = "";
      this.pushUser(text);

      try {
        const res = await api.post<ChatResponse>("/chat", {
          session_id: this.sessionId,
          message: text,
        });

        const data = res.data;
        this.pushAssistant(data.reply || "(空回复)");
        this.lastHistory = data.history || [];

        this.papers = data.papers || [];
        this.pdfAssets = data.pdf_assets || [];
        this.translateAssets = data.translate_assets || [];

        // ✅ /chat 返回 tasks 快照：用于兜底（即使 SSE 短暂未连上也能看到任务）
        if (Array.isArray(data.tasks)) {
          for (const t of data.tasks) this._upsertTask(t);
        }
      } catch (e: any) {
        const msg = e?.response?.data?.detail || e?.message || String(e);
        this.lastError = msg;
        this.pushAssistant(`请求失败：${msg}`);
      } finally {
        this.loading = false;
      }
    },

    async fetchPdfAssets() {
      try {
        const resp = await api.get<{ assets: PdfAsset[] }>("/pdf/assets");
        this.pdfAssets = resp.data?.assets || [];
      } catch {
        // ignore
      }
    },

    async fetchTranslateAssets() {
      try {
        const resp = await api.get<{ assets: TranslateAsset[] }>("/translate/assets");
        this.translateAssets = resp.data?.assets || [];
      } catch {
        // ignore
      }
    },

    async downloadPaper(refIndex1based: number) {
      if (this.preferAgent) {
        await this.sendChat(`下载第${refIndex1based}篇论文PDF`);
        return;
      }

      this.loading = true;
      this.lastError = "";
      try {
        const res = await api.post("/pdf/download", {
          session_id: this.sessionId,
          ref: refIndex1based,
          force: false,
        });
        this.pushAssistant(`下载结果：${JSON.stringify(res.data)}`);
        await this.refreshSnapshot();
      } catch (e: any) {
        const msg = e?.response?.data?.detail || e?.message || String(e);
        this.lastError = msg;
        this.pushAssistant(`下载失败：${msg}`);
      } finally {
        this.loading = false;
      }
    },

    async translatePaper(refIndex1based: number) {
      const tip = `准备翻译第${refIndex1based}篇论文（若未下载将自动先下载再翻译）`;

      // ✅ preferAgent：走 /chat（后端已把 translate_arxiv_pdf 改为 enqueue 异步）
      if (this.preferAgent) {
        await this.sendChat(`${tip}。请开始翻译并输出中文PDF。`);
        return;
      }

      // ✅ 不走 agent：直接调用 /pdf/translate/async（立即返回 task，进度靠 SSE）
      this.ensureSse();

      this.loading = true;
      this.lastError = "";
      try {
        this.pushAssistant(tip);
        const resp = await api.post<{ task: TranslateTask }>("/pdf/translate/async", {
          session_id: this.sessionId,
          ref: refIndex1based,
          force: false,
          service: "bing",
          threads: 4,
          keep_dual: false,
        });

        const task = resp.data?.task;
        if (task?.task_id) {
          this._upsertTask(task);
          this.pushAssistant(`已创建翻译任务：task_id=${task.task_id}（等待 SSE 推送完成）`);
        } else {
          this.pushAssistant(`已发起翻译任务（等待 SSE 推送完成）`);
        }
      } catch (e: any) {
        const msg = e?.response?.data?.detail || e?.message || String(e);
        this.lastError = msg;
        this.pushAssistant(`翻译失败：${msg}`);
      } finally {
        this.loading = false;
      }
    },

    clearChat() {
      this.messages = [];
      this.lastHistory = [];
      this.lastError = "";
    },
  },
});