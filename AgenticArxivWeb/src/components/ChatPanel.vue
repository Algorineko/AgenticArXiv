<template>
  <section class="card chat">
    <header class="card-header">
      <div class="title">对话区</div>

      <div class="row">
        <label class="label">Session:</label>
        <input class="input" v-model="sessionDraft" @change="applySession" placeholder="demo1" />
        <button class="btn" @click="refresh" :disabled="store.loading">刷新快照</button>
        <button class="btn ghost" @click="store.clearChat()">清空对话</button>
      </div>

      <div class="row">
        <label class="label">按钮操作:</label>
        <label class="toggle">
          <input type="checkbox" v-model="store.preferAgent" />
          <span>下载/翻译 使用Agent/直接调用API</span>
        </label>
        <span class="muted">API: {{ store.apiBase }}</span>
      </div>

      <div class="row">
        <label class="label">SSE:</label>
        <span class="pill" :class="store.sseStatus">{{ store.sseStatus }}</span>
        <span class="muted" v-if="store.sseLastEvent">
          last={{ store.sseLastEvent }} · {{ fmt(store.sseLastEventTs) }}
        </span>
      </div>

      <p v-if="store.lastError" class="error">⚠ {{ store.lastError }}</p>
    </header>

    <div class="messages" ref="msgBox">
      <div v-if="store.messages.length === 0" class="empty">
        示例: <code>获取最近7天内AI(cs.AI)方向论文，最多5篇</code>
      </div>

      <div v-for="(m, idx) in store.messages" :key="idx" class="msg" :class="m.role">
        <div class="meta">
          <span class="role">{{ m.role === "user" ? "你" : "Agent" }}</span>
          <span class="time">{{ fmt(m.ts) }}</span>
        </div>
        <pre class="content">{{ m.content }}</pre>
      </div>
    </div>

    <footer class="composer">
      <textarea
        class="textarea"
        v-model="draft"
        :disabled="store.loading"
        placeholder="输入一句话，让 agent 自己决定调用工具…"
        @keydown.enter.exact.prevent="send"
      />

      <div class="actions">
        <button
          v-if="store.lastHistory.length"
          class="btn ghost"
          type="button"
          @click="showDebug = true"
          :title="'查看最近一次 ReAct history（' + store.lastHistory.length + '步）'"
        >
          调试（{{ store.lastHistory.length }}步）
        </button>

        <button class="btn" type="button" @click="quick('获取最近7天内AI(cs.AI)方向论文，最多5篇')">
          快捷: 拉取AI 5篇
        </button>

        <button class="btn primary" type="button" @click="send" :disabled="store.loading || !draft.trim()">
          {{ store.loading ? "发送中…" : "发送" }}
        </button>
      </div>
    </footer>

    <!-- 弹出框展示调试详情 -->
    <Modal
      :open="showDebug"
      title="调试：最近一次 ReAct history"
      @close="showDebug = false"
    >
      <div class="debug-modal">
        <div class="debug-top">
          <div class="muted">
            共 {{ store.lastHistory.length }} 步（Thought / Action / Observation）
          </div>
        </div>

        <div class="history">
          <div v-for="(h, i) in store.lastHistory" :key="i" class="step">
            <div class="h-title">Step {{ i + 1 }}</div>

            <div class="kv">
              <div class="k">Thought</div>
              <pre class="v">{{ h.thought }}</pre>
            </div>

            <div class="kv">
              <div class="k">Action</div>
              <pre class="v">{{ h.action }}</pre>
            </div>

            <div class="kv">
              <div class="k">Observation</div>
              <pre class="v">{{ h.observation }}</pre>
            </div>
          </div>
        </div>
      </div>

      <template #footer>
        <div class="footer-actions">
          <button class="btn" type="button" @click="copyAll">复制全部</button>
          <button class="btn primary" type="button" @click="showDebug = false">关闭</button>
        </div>
      </template>
    </Modal>
  </section>
</template>

<script setup lang="ts">
import { nextTick, onMounted, ref, watch, computed } from "vue";
import { useAppStore } from "@/stores/appStore";
import Modal from "@/components/Modal.vue";

const store = useAppStore();
const draft = ref("");
const sessionDraft = ref(store.sessionId);
const msgBox = ref<HTMLDivElement | null>(null);

const showDebug = ref(false);

function fmt(ts: number) {
  if (!ts) return "-";
  return new Date(ts).toLocaleString();
}

function applySession() {
  store.setSessionId(sessionDraft.value);
  store.refreshSnapshot();
}

async function send() {
  const text = draft.value;
  draft.value = "";
  await store.sendChat(text);
  await nextTick();
  msgBox.value?.scrollTo({ top: msgBox.value.scrollHeight, behavior: "smooth" });
}

function quick(text: string) {
  draft.value = text;
}

async function refresh() {
  await store.refreshSnapshot();
}

onMounted(() => {
  store.ensureSse();
  store.refreshSnapshot();
});

watch(
  () => store.messages.length,
  async () => {
    await nextTick();
    msgBox.value?.scrollTo({ top: msgBox.value.scrollHeight });
  }
);

const allHistoryText = computed(() => {
  const arr = store.lastHistory || [];
  return arr
    .map((h, i) => {
      return [
        `Step ${i + 1}`,
        `Thought: ${h.thought ?? ""}`,
        `Action: ${h.action ?? ""}`,
        `Observation: ${h.observation ?? ""}`,
      ].join("\n");
    })
    .join("\n\n");
});

async function copyAll() {
  const text = allHistoryText.value || "";
  if (!text) return;

  try {
    await navigator.clipboard.writeText(text);
    store.lastError = "";
  } catch {
    try {
      const ta = document.createElement("textarea");
      ta.value = text;
      ta.style.position = "fixed";
      ta.style.opacity = "0";
      document.body.appendChild(ta);
      ta.focus();
      ta.select();
      document.execCommand("copy");
      document.body.removeChild(ta);
    } catch {
      // ignore
    }
  }
}
</script>

<style scoped>
.chat { display:flex; flex-direction:column; height:100%; }
.card-header { border-bottom: 1px solid var(--border); padding-bottom: 10px; }
.title { font-weight: 700; margin-bottom: 8px; }
.row { display:flex; align-items:center; gap:8px; flex-wrap:wrap; margin: 6px 0; }
.label { color: var(--muted); }
.input { height: 32px; padding: 0 10px; border:1px solid var(--border); border-radius: 8px; background: var(--bg2); color: var(--fg); }
.messages { flex:1; overflow:auto; padding: 10px 2px; }
.empty { color: var(--muted); padding: 12px; }
.msg { border:1px solid var(--border); border-radius: 12px; padding: 10px; margin: 10px 8px; background: var(--bg2); }
.msg.user { border-left: 4px solid #4b9; }
.msg.assistant { border-left: 4px solid #59f; }
.meta { display:flex; justify-content:space-between; color: var(--muted); font-size: 12px; margin-bottom: 6px; }
.content { white-space: pre-wrap; margin:0; font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace; }
.composer { border-top: 1px solid var(--border); padding-top: 10px; }
.textarea { width:100%; min-height: 80px; padding: 10px; border:1px solid var(--border); border-radius: 12px; background: var(--bg2); color: var(--fg); resize: vertical; }
.actions {
  display: flex;
  justify-content: flex-end;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
  margin-top: 10px;
}
.error { color: #ff6b6b; margin: 6px 0 0; }
.toggle { display:flex; gap:6px; align-items:center; }
.muted { color: var(--muted); }

.pill{
  display:inline-flex;
  align-items:center;
  height: 20px;
  padding: 0 8px;
  border-radius: 999px;
  border: 1px solid var(--border);
  font-size: 12px;
}
.pill.idle { opacity: .7; }
.pill.connecting { border-color: rgba(255,200,0,.35); }
.pill.connected { border-color: rgba(0,255,153,.35); }
.pill.error { border-color: rgba(255,107,107,.35); }

/* ---- Debug Modal content ---- */
.debug-modal{
  display: flex;
  flex-direction: column;
  gap: 10px;
  min-height: 0;
  color: var(--fg);
}

.debug-top{
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 10px;
  flex-wrap: wrap;
}

.history{
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.step{
  border: 1px solid rgba(255,255,255,0.08);
  border-radius: 14px;
  background: rgba(255,255,255,0.02);
  padding: 10px;
}

.h-title{
  font-weight: 750;
  margin-bottom: 8px;
  color: var(--fg);
}

.kv{
  display: grid;
  grid-template-columns: 96px 1fr;
  gap: 10px;
  align-items: start;
  margin-top: 8px;
}

.k{
  color: var(--muted);
  font-size: 12px;
  padding-top: 2px;
}

/* 强制 ReAct 文本为白色（var(--fg)） */
.v{
  margin: 0;
  white-space: pre-wrap;
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace;
  border: 1px solid rgba(255,255,255,0.08);
  background: rgba(255,255,255,0.015);
  border-radius: 12px;
  padding: 8px;
  overflow: auto;
  color: var(--fg);
}

.footer-actions{
  display: flex;
  justify-content: flex-end;
  gap: 10px;
  flex-wrap: wrap;
}
</style>