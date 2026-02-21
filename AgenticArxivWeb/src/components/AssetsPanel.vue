<template>
  <section class="card assets">
    <header class="card-header">
      <div class="title">下载/翻译缓存</div>
      <p class="muted">
        PDF: {{ pdfList.length }} 条 · 翻译: {{ trList.length }} 条 · 任务: {{ store.tasks.length }} 条
      </p>
    </header>

    <div class="lists">
      <!-- 任务区（最近翻译任务） -->
      <div class="block">
        <div class="block-title">最近翻译任务（SSE）</div>
        <div class="list-scroll">
          <div v-if="!taskList.length" class="empty">暂无任务（发起“翻译第N篇”后这里会实时更新）</div>

          <div v-for="t in taskList" :key="t.task_id" class="item">
            <div class="item-top">
              <div class="mono id">{{ t.paper_id }}</div>
              <span class="pill" :class="statusClass(t.status)">{{ t.status }}</span>
            </div>

            <div class="sub mono">task_id: {{ t.task_id }}</div>

            <div class="sub" v-if="typeof t.progress === 'number'">
              progress: {{ Math.round(t.progress * 100) }}%
            </div>

            <div class="sub mono" v-if="t.output_pdf_path">out: {{ t.output_pdf_path }}</div>
            <div class="sub err" v-if="t.error">error: {{ t.error }}</div>
          </div>
        </div>
      </div>

      <!-- 已下载 -->
      <div class="block">
        <div class="block-title">已下载（READY）</div>
        <div class="list-scroll">
          <div v-if="!pdfList.length" class="empty">暂无已下载 PDF</div>

          <div v-for="a in pdfList" :key="a.paper_id" class="item">
            <div class="item-top">
              <div class="mono id">{{ a.paper_id }}</div>
              <span class="pill ok">READY</span>
            </div>
            <div class="sub mono">path: {{ a.local_path }}</div>
            <div class="sub">
              size: {{ formatBytes(a.size_bytes) }} · updated: {{ a.updated_at }}
            </div>
          </div>
        </div>
      </div>

      <!-- 已翻译 -->
      <div class="block">
        <div class="block-title">已翻译（READY）</div>
        <div class="list-scroll">
          <div v-if="!trList.length" class="empty">暂无已翻译 PDF</div>

          <div v-for="t in trList" :key="t.paper_id" class="item">
            <div class="item-top">
              <div class="mono id">{{ t.paper_id }}</div>
              <span class="pill ok">READY</span>
            </div>
            <div class="sub mono">out: {{ t.output_mono_path }}</div>
            <div class="sub">
              threads: {{ t.threads }} · updated: {{ t.updated_at }}
            </div>
            <div class="sub" v-if="t.output_dual_path">
              dual: <span class="mono">{{ t.output_dual_path }}</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed } from "vue";
import { useAppStore } from "@/stores/appStore";

const store = useAppStore();

const taskList = computed(() => (store.tasks || []).slice(0, 10));

const pdfList = computed(() => {
  const arr = Array.from(store.pdfMap.values()).filter((x) => x.status === "READY");
  return arr.sort((a, b) => (String(b.updated_at || "")).localeCompare(String(a.updated_at || "")));
});

const trList = computed(() => {
  const arr = Array.from(store.translateMap.values()).filter((x) => x.status === "READY");
  return arr.sort((a, b) => (String(b.updated_at || "")).localeCompare(String(a.updated_at || "")));
});

function formatBytes(n: number | null | undefined) {
  const v0 = Number(n || 0);
  if (!Number.isFinite(v0) || v0 <= 0) return "0 B";
  const units = ["B", "KB", "MB", "GB", "TB"];
  let v = v0;
  let i = 0;
  while (v >= 1024 && i < units.length - 1) {
    v /= 1024;
    i++;
  }
  return `${v.toFixed(i === 0 ? 0 : 2)} ${units[i]}`;
}

function statusClass(s: string) {
  const x = (s || "").toUpperCase();
  if (x.includes("SUCC")) return "ok";
  if (x.includes("FAIL")) return "bad";
  if (x.includes("RUN")) return "warn";
  return "neutral";
}
</script>

<style scoped>
.assets {
  height: 100%;
  display: flex;
  flex-direction: column;
  min-height: 0;
}

.card-header {
  margin-bottom: 10px;
  padding-bottom: 10px;
  border-bottom: 1px solid var(--border);
}

.title { font-weight: 700; margin-bottom: 6px; }
.muted { color: var(--muted); margin: 0; font-size: 12px; }

/* 三块列表：任务 + 下载 + 翻译 */
.lists {
  flex: 1;
  min-height: 0;
  display: grid;
  grid-template-rows: 1fr 1fr 1fr;
  gap: 12px;
}

.block {
  border: 1px solid var(--border);
  border-radius: 14px;
  background: rgba(255,255,255,0.02);
  padding: 10px;
  min-height: 0;
  display: flex;
  flex-direction: column;
}

.block-title {
  font-weight: 650;
  color: var(--muted);
  font-size: 12px;
  margin-bottom: 8px;
}

.list-scroll {
  flex: 1;
  min-height: 0;
  overflow: auto;
  padding-right: 2px;
}

.item {
  border: 1px solid rgba(255,255,255,0.06);
  border-radius: 12px;
  padding: 10px;
  background: rgba(255,255,255,0.015);
  margin-bottom: 8px;
}

.item-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  margin-bottom: 4px;
}

.mono { font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace; }
.id { font-weight: 700; }
.sub { color: var(--muted); font-size: 12px; line-height: 1.35; margin-top: 2px; }
.sub.err { color: #ff6b6b; }

.pill {
  display: inline-flex;
  align-items: center;
  height: 20px;
  padding: 0 8px;
  border-radius: 999px;
  border: 1px solid var(--border);
  font-size: 12px;
  user-select: none;
}

.pill.ok { border-color: rgba(0,255,153,.35); }
.pill.bad { border-color: rgba(255,107,107,.35); }
.pill.warn { border-color: rgba(255,200,0,.35); }
.pill.neutral { opacity: .75; }

.empty { color: var(--muted); font-size: 12px; padding: 6px 2px; }
</style>
