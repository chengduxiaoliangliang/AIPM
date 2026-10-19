<template>
  <section class="app-main">
    <router-view v-slot="{ Component, route }">
      <transition name="fade-transform" mode="out-in">
        <component :is="Component" :key="route.path" />
      </transition>
    </router-view>
  </section>
</template>

<script setup lang="ts">
</script>

<style scoped>
.app-main {
  width: 100%;
  position: relative;
  overflow-x: hidden;
  background-color: var(--bg-color);
  min-height: calc(100vh - var(--header-height) - var(--tabs-height));
}
</style>
