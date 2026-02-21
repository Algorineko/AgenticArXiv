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
          <span>优先走 Agent（/chat）</span>
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
        你可以直接说：<code>获取最近7天内AI(cs.AI)方向论文，最多5篇</code>
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
        <button class="btn primary" @click="send" :disabled="store.loading || !draft.trim()">
          {{ store.loading ? "发送中…" : "发送" }}
        </button>
        <button class="btn" @click="quick('获取最近7天内AI(cs.AI)方向论文，最多5篇')">
          快捷：拉取AI 5篇
        </button>
      </div>

      <details class="debug" v-if="store.lastHistory.length">
        <summary>调试：最近一次 ReAct history（{{ store.lastHistory.length }}步）</summary>
        <div class="history">
          <div v-for="(h, i) in store.lastHistory" :key="i" class="step">
            <div class="h-title">Step {{ i + 1 }}</div>
            <pre>Thought: {{ h.thought }}</pre>
            <pre>Action: {{ h.action }}</pre>
            <pre>Observation: {{ h.observation }}</pre>
          </div>
        </div>
      </details>
    </footer>
  </section>
</template>

<script setup lang="ts">
import { nextTick, onMounted, ref, watch } from "vue";
import { useAppStore } from "@/stores/appStore";

const store = useAppStore();
const draft = ref("");
const sessionDraft = ref(store.sessionId);
const msgBox = ref<HTMLDivElement | null>(null);

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
.actions { display:flex; gap:10px; flex-wrap:wrap; margin-top: 10px; }
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

.debug { margin-top: 10px; color: var(--muted); }
.history { padding: 8px 0; }
.step { border:1px dashed var(--border); border-radius: 10px; padding: 8px; margin: 8px 0; background: var(--bg2); }
.h-title { font-weight: 700; color: var(--fg); margin-bottom: 4px; }
</style>
