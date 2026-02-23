<template>
  <div class="app">
    <header class="topbar">
      <div class="topbar-inner">
        <div class="brand">
          <div class="logo">🧩</div>
          <div>
            <div class="name">AgenticArxiv Web</div>
            <div class="desc">对话 + 论文临时记忆 + 下载/翻译缓存</div>
          </div>
        </div>

        <!-- 顶栏按钮：只显示右侧两个面板中的一个 -->
        <div class="nav-actions" role="tablist" aria-label="Right panel toggle">
          <button
            class="btn tab"
            :class="rightView === 'papers' ? 'primary' : 'ghost'"
            role="tab"
            :aria-selected="rightView === 'papers'"
            @click="rightView = 'papers'"
          >
            论文信息区
          </button>

          <button
            class="btn tab"
            :class="rightView === 'assets' ? 'primary' : 'ghost'"
            role="tab"
            :aria-selected="rightView === 'assets'"
            @click="rightView = 'assets'"
          >
            下载/翻译缓存
          </button>
        </div>
      </div>
    </header>

    <main class="grid">
      <ChatPanel />

      <div class="right">
        <!-- 动态组件 + KeepAlive：只渲染一个，但切换会保留状态 -->
        <KeepAlive>
          <component :is="rightComponent" class="right-panel" />
        </KeepAlive>
      </div>
    </main>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from "vue";
import ChatPanel from "@/components/ChatPanel.vue";
import PapersPanel from "@/components/PapersPanel.vue";
import AssetsPanel from "@/components/AssetsPanel.vue";

type RightView = "papers" | "assets";

const rightView = ref<RightView>("papers");

const rightComponent = computed(() => {
  return rightView.value === "papers" ? PapersPanel : AssetsPanel;
});
</script>

<style scoped>
.app { min-height: 100vh; background: var(--bg); color: var(--fg); }

.topbar {
  position: sticky;
  top: 0;
  z-index: 10;
  backdrop-filter: blur(10px);
  background: rgba(10,10,12,0.75);
  border-bottom: 1px solid var(--border);
}

.topbar-inner{
  max-width: 1400px;
  margin: 0 auto;
  padding: 14px 18px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 14px;
  flex-wrap: wrap; /* 小屏时按钮自动换行 */
}

.brand { display:flex; gap:12px; align-items:center; }
.logo { font-size: 24px; }
.name { font-weight: 800; }
.desc { color: var(--muted); font-size: 12px; margin-top: 2px; }

.nav-actions{
  display: flex;
  gap: 8px;
  align-items: center;
  flex-wrap: wrap;
}

.btn.tab{
  height: 32px;
  border-radius: 10px;
}

.grid {
  max-width: 1400px;
  margin: 0 auto;
  padding: 14px 18px;
  display: grid;
  grid-template-columns: 1.2fr 1fr;
  gap: 14px;
  height: calc(100vh - 64px);
}

/* 右侧变成“单面板占满” */
.right {
  min-height: 0;
  display: flex;
  flex-direction: column;
}

.right-panel{
  flex: 1;
  min-height: 0;
}

@media (max-width: 1100px) {
  .grid { grid-template-columns: 1fr; height: auto; }
}
</style>
