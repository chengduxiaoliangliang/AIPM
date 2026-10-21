<template>
  <div class="tags-view-container">
    <el-scrollbar class="tags-scrollbar">
      <div class="tags-wrapper">
        <router-link
          v-for="tag in tagsStore.visitedTags"
          :key="tag.path"
          :to="tag.path"
          class="tag-item"
          :class="{ active: isActive(tag.path) }"
        >
          <span class="tag-dot" v-if="isActive(tag.path)"></span>
          <span class="tag-title">{{ tag.title }}</span>
          <el-icon
            v-if="!tag.affix"
            class="close-icon"
            @click.prevent.stop="closeTag(tag.path)"
          >
            <Close />
          </el-icon>
        </router-link>
      </div>
    </el-scrollbar>
  </div>
</template>

<script setup lang="ts">
import { useRoute, useRouter } from 'vue-router'
import { useTagsStore } from '@/store/modules/tags'
import { Close } from '@element-plus/icons-vue'

const route = useRoute()
const router = useRouter()
const tagsStore = useTagsStore()

function isActive(path: string) {
  return route.path === path
}

function closeTag(path: string) {
  tagsStore.closeTag(path)
  if (isActive(path)) {
    const latest = tagsStore.visitedTags[tagsStore.visitedTags.length - 1]
    if (latest) {
      router.push(latest.path)
    } else {
      router.push('/dashboard')
    }
  }
}
</script>

<style scoped lang="scss">
.tags-view-container {
  height: var(--tabs-height);
  background: var(--bg-header);
  border-bottom: 1px solid var(--border-color);
  padding: 0 16px;
  display: flex;
  align-items: center;
  flex-shrink: 0;

  .tags-scrollbar {
    width: 100%;
    white-space: nowrap;

    .tags-wrapper {
      display: inline-flex;
      align-items: center;
      gap: 4px;
      padding: 2px 0;
    }
  }

  .tag-item {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    height: 26px;
    padding: 0 9px;
    font-size: 12px;
    font-weight: 450;
    color: var(--text-muted);
    background: transparent;
    border: 1px solid transparent;
    border-radius: var(--radius-xs);
    text-decoration: none;
    cursor: pointer;
    transition: background-color 0.15s ease, color 0.15s ease, border-color 0.15s ease;

    .tag-dot {
      width: 5px;
      height: 5px;
      border-radius: 50%;
      background: var(--primary-color);
    }

    &:hover {
      color: var(--text-regular);
      background: var(--bg-hover);
    }

    &.active {
      color: var(--primary-color);
      background: var(--primary-light);
      border-color: var(--primary-glow);
      font-weight: 500;

      .close-icon {
        color: var(--primary-color);
        opacity: 0.6;

        &:hover {
          opacity: 1;
          background: var(--primary-light);
        }
      }
    }

    .close-icon {
      font-size: 10px;
      border-radius: 50%;
      padding: 1px;
      color: var(--text-faint);
      transition: all 0.15s ease;

      &:hover {
        background: var(--bg-active);
        color: var(--text-regular);
      }
    }
  }
}
</style>
