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
  background-color: var(--bg-header);
  backdrop-filter: blur(var(--glass-blur)) saturate(var(--glass-saturate));
  -webkit-backdrop-filter: blur(var(--glass-blur)) saturate(var(--glass-saturate));
  border-bottom: 1px solid var(--border-glass-subtle);
  padding: 0 16px;
  display: flex;
  align-items: center;

  .tags-scrollbar {
    width: 100%;
    white-space: nowrap;

    .tags-wrapper {
      display: inline-flex;
      align-items: center;
      gap: 8px;
      padding: 2px 0;
    }
  }

  .tag-item {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    height: 28px;
    padding: 0 12px;
    font-size: 12px;
    font-weight: 500;
    color: var(--text-regular);
    background: rgba(255, 255, 255, 0.4);
    border: 1px solid var(--border-glass-subtle);
    border-radius: var(--radius-xs);
    text-decoration: none;
    transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
    cursor: pointer;

    .tag-dot {
      width: 6px;
      height: 6px;
      border-radius: 50%;
      background-color: #ffffff;
      box-shadow: 0 0 6px #ffffff;
    }

    &:hover {
      color: var(--primary-color);
      border-color: var(--primary-color);
      background: var(--bg-hover);
      transform: translateY(-1px);
    }

    &.active {
      color: #ffffff;
      background: var(--primary-color);
      border-color: var(--primary-color);
      box-shadow: 0 2px 8px rgba(79, 70, 229, 0.35);
      font-weight: 600;

      .close-icon {
        color: rgba(255, 255, 255, 0.8);
        &:hover {
          color: #ffffff;
          background: rgba(0, 0, 0, 0.2);
        }
      }
    }

    .close-icon {
      font-size: 11px;
      border-radius: 50%;
      padding: 1px;
      transition: all 0.2s ease;

      &:hover {
        background-color: rgba(0, 0, 0, 0.1);
      }
    }
  }
}
</style>
