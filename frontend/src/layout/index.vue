<template>
  <div class="layout-container">
    <!-- Sidebar -->
    <Sidebar />

    <!-- Main Content Area -->
    <div class="main-container">
      <Header />
      <TagsView />
      <div class="content-wrapper">
        <AppMain />
      </div>
    </div>

    <!-- Floating AI Assistant Sprite -->
    <AiAssistantSprite />
  </div>
</template>

<script setup lang="ts">
import Sidebar from './components/Sidebar/index.vue'
import Header from './components/Header/index.vue'
import TagsView from './components/TagsView/index.vue'
import AppMain from './components/AppMain.vue'
import AiAssistantSprite from '@/components/AiAssistantSprite.vue'
</script>

<style scoped lang="scss">
.layout-container {
  display: flex;
  width: 100vw;
  height: 100vh;
  overflow: hidden;
  background-color: var(--bg-color);

  .main-container {
    flex: 1;
    display: flex;
    flex-direction: column;
    height: 100vh;
    overflow: hidden;

    .content-wrapper {
      flex: 1;
      overflow-y: auto;
      overflow-x: hidden;
    }
  }
}
</style>
