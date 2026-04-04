<template>
  <section class="settings-page">
    <div class="settings-card">
      <h2 class="section-title">连接</h2>

      <div class="field">
        <label class="field-label">API 地址</label>
        <div class="field-value mono">{{ store.apiBase }}</div>
      </div>

      <div class="field">
        <label class="field-label">SSE 状态</label>
        <div class="field-row">
          <span class="pill" :class="store.sseStatus">{{ sseLabel }}</span>
          <button class="btn" @click="reconnectSse">重连</button>
        </div>
        <div class="field-hint" v-if="store.sseLastEvent">
          最近事件: {{ store.sseLastEvent }} · {{ fmtTs(store.sseLastEventTs) }}
        </div>
      </div>
    </div>

    <div class="settings-card">
      <h2 class="section-title">数据</h2>

      <div class="field">
        <label class="field-label">快照</label>
        <div class="field-row">
          <button class="btn" @click="store.refreshSnapshot()" :disabled="store.loading">刷新全部快照</button>
        </div>
        <div class="field-hint">
          论文 {{ store.papers.length }} 篇 · PDF {{ store.pdfAssets.length }} 条 · 翻译 {{ store.translateAssets.length }} 条
        </div>
      </div>

    </div>

    <div class="settings-card muted-card">
      <div class="about">AgenticArxiv v0.2.0 · ReAct Agent + arXiv 论文管理</div>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed } from "vue";
import { useAppStore } from "@/stores/appStore";

const store = useAppStore();

const sseLabelMap: Record<string, string> = {
  idle: "未连接",
  connecting: "连接中…",
  connected: "已连接",
  error: "连接失败",
};

const sseLabel = computed(() => sseLabelMap[store.sseStatus] || store.sseStatus);

function reconnectSse() {
  store.closeSse();
  store.ensureSse();
}

function fmtTs(ts: number) {
  if (!ts) return "-";
  return new Date(ts).toLocaleString();
}
</script>

<style scoped>
.settings-page {
  padding: 20px;
  max-width: 640px;
  margin: 0 auto;
  display: flex;
  flex-direction: column;
  gap: 16px;
  height: calc(100vh - 36px);
  overflow: auto;
}

.settings-card {
  border: 1px solid var(--border);
  border-radius: 16px;
  background: rgba(255,255,255,0.02);
  padding: 16px;
}

.section-title {
  font-size: 14px;
  font-weight: 700;
  margin: 0 0 14px 0;
}

.field {
  margin-bottom: 16px;
}
.field:last-child { margin-bottom: 0; }

.field-label {
  display: block;
  font-size: 12px;
  color: var(--muted);
  margin-bottom: 6px;
  font-weight: 600;
}

.field-row {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.field-value {
  font-size: 13px;
  padding: 6px 10px;
  border: 1px solid var(--border);
  border-radius: 8px;
  background: var(--bg2);
}

.field-hint {
  color: var(--muted);
  font-size: 11px;
  margin-top: 4px;
}

.mono {
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  font-size: 13px;
}

/* Pill */
.pill {
  display: inline-flex;
  align-items: center;
  height: 22px;
  padding: 0 10px;
  border-radius: 999px;
  border: 1px solid var(--border);
  font-size: 12px;
}
.pill.idle { opacity: .7; }
.pill.connecting { border-color: rgba(255,200,0,.35); }
.pill.connected { border-color: rgba(0,255,153,.35); }
.pill.error { border-color: rgba(255,107,107,.35); }

.muted-card {
  background: transparent;
  border-color: transparent;
}
.about {
  text-align: center;
  color: var(--muted);
  font-size: 12px;
}
</style>
