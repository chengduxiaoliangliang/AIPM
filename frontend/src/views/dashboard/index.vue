<template>
  <div class="dashboard-page page-container" v-loading="loading">
    <!-- Top Stat Cards -->
    <el-row :gutter="16" class="stat-row">
      <el-col :xs="24" :sm="12" :md="6">
        <StatCard
          title="进行中项目"
          :value="stats?.metrics.active_projects || 0"
          unit="个"
          :icon="FolderOpened"
          icon-bg="rgba(47, 84, 232, 0.10)"
          icon-color="#2f54e8"
          :trend="12.5"
          tip="较上月稳步推进"
        />
      </el-col>
      <el-col :xs="24" :sm="12" :md="6">
        <StatCard
          title="活跃任务总数"
          :value="stats?.metrics.in_progress_tasks || 0"
          unit="项"
          :icon="Checked"
          icon-bg="rgba(15, 157, 88, 0.10)"
          icon-color="#0f9d58"
          :trend="8.2"
          tip="迭代任务按期执行"
        />
      </el-col>
      <el-col :xs="24" :sm="12" :md="6">
        <StatCard
          title="待审批工时"
          :value="stats?.metrics.pending_approvals || 0"
          unit="条"
          :icon="Timer"
          icon-bg="rgba(217, 119, 6, 0.10)"
          icon-color="#d97706"
          :trend="-15.4"
          tip="待项目经理审批"
        />
      </el-col>
      <el-col :xs="24" :sm="12" :md="6">
        <StatCard
          title="待解决缺陷"
          :value="stats?.metrics.open_issues || 0"
          unit="个"
          :icon="WarningFilled"
          icon-bg="rgba(220, 38, 38, 0.10)"
          icon-color="#dc2626"
          :trend="-5.0"
          tip="缺陷收敛指标良好"
        />
      </el-col>
    </el-row>

    <!-- Charts Row -->
    <el-row :gutter="16" class="chart-row">
      <!-- Monthly Trends Chart (Line + Bar) -->
      <el-col :xs="24" :lg="16">
        <div class="chart-card vben-card">
          <div class="card-header">
            <div class="header-title">
              <el-icon><TrendCharts /></el-icon>
              <span>月度任务流转与工时交付趋势</span>
            </div>
            <el-radio-group v-model="trendType" size="small">
              <el-radio-button label="task">任务交付</el-radio-button>
              <el-radio-button label="hours">投入工时</el-radio-button>
            </el-radio-group>
          </div>
          <div ref="trendChartRef" class="chart-container"></div>
        </div>
      </el-col>

      <!-- Project Status Donut Chart -->
      <el-col :xs="24" :lg="8">
        <div class="chart-card vben-card">
          <div class="card-header">
            <div class="header-title">
              <el-icon><PieChart /></el-icon>
              <span>项目状态分布</span>
            </div>
          </div>
          <div ref="statusChartRef" class="chart-container"></div>
        </div>
      </el-col>
    </el-row>

    <!-- Bottom Row: Team Workloads & Recent Activities -->
    <el-row :gutter="16" class="bottom-row">
      <!-- Member Workloads -->
      <el-col :xs="24" :lg="14">
        <div class="table-card vben-card">
          <div class="card-header">
            <div class="header-title">
              <el-icon><UserFilled /></el-icon>
              <span>团队成员负荷与交付统计</span>
            </div>
          </div>
          <el-table :data="stats?.member_workloads || []" stripe style="width: 100%">
            <el-table-column label="成员" min-width="140">
              <template #default="{ row }">
                <div class="member-cell">
                  <el-avatar :size="28" :src="row.avatar" />
                  <span class="member-name">{{ row.name }}</span>
                </div>
              </template>
            </el-table-column>
            <el-table-column prop="task_count" label="承担任务" align="center" width="100">
              <template #default="{ row }">
                <el-tag size="small" effect="plain">{{ row.task_count }} 项</el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="logged_hours" label="累计工时" align="center" width="110">
              <template #default="{ row }">
                <span>{{ row.logged_hours }} h</span>
              </template>
            </el-table-column>
            <el-table-column label="任务完成率" min-width="160">
              <template #default="{ row }">
                <el-progress
                  :percentage="row.completion_rate"
                  :color="row.completion_rate >= 80 ? '#0f9d58' : row.completion_rate >= 50 ? '#d97706' : '#2f54e8'"
                  :stroke-width="8"
                />
              </template>
            </el-table-column>
          </el-table>
        </div>
      </el-col>

      <!-- Recent Activities Feed -->
      <el-col :xs="24" :lg="10">
        <div class="table-card vben-card">
          <div class="card-header">
            <div class="header-title">
              <el-icon><List /></el-icon>
              <span>最新项目动态</span>
            </div>
          </div>
          <el-scrollbar max-height="300px">
            <div class="activity-timeline">
              <div
                v-for="act in stats?.recent_activities || []"
                :key="act.id"
                class="activity-item"
              >
                <div class="act-dot"></div>
                <div class="act-content">
                  <div class="act-meta">
                    <span class="act-user">{{ act.username }}</span>
                    <el-tag size="small" effect="light" class="act-module">{{ act.module }}</el-tag>
                    <span class="act-time">{{ act.created_at }}</span>
                  </div>
                  <div class="act-detail">{{ act.details }}</div>
                </div>
              </div>
            </div>
          </el-scrollbar>
        </div>
      </el-col>
    </el-row>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, nextTick, watch } from 'vue'
// 按需引入：全量 import 会把 1MB 的 echarts 打进包里
import * as echarts from 'echarts/core'
// 加前缀避免与 Element 图标 PieChart 重名
import { BarChart as EBarChart, LineChart as ELineChart, PieChart as EPieChart } from 'echarts/charts'
import { GridComponent, LegendComponent, TooltipComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'

// 类型从完整包引入，仅参与编译、不进产物
import type { EChartsOption } from 'echarts'

echarts.use([
  EBarChart, ELineChart, EPieChart,
  GridComponent, LegendComponent, TooltipComponent,
  CanvasRenderer
])

/** 图表配色跟随 CSS 变量，暗色模式自动适配 */
const CHART_COLORS = ['#2f54e8', '#0f9d58', '#d97706', '#7c3aed', '#0891b2']

function cssVar(name: string, fallback: string) {
  const v = getComputedStyle(document.documentElement).getPropertyValue(name).trim()
  return v || fallback
}
import { getDashboardStatsApi } from '@/api/stats'
import StatCard from '@/components/StatCard.vue'
import type { DashboardStats } from '@/types'
import {
  FolderOpened,
  Checked,
  Timer,
  WarningFilled,
  TrendCharts,
  PieChart,
  UserFilled,
  List
} from '@element-plus/icons-vue'

const loading = ref(false)
const stats = ref<DashboardStats | null>(null)
const trendType = ref<'task' | 'hours'>('task')

const trendChartRef = ref<HTMLElement>()
const statusChartRef = ref<HTMLElement>()

let trendChart: echarts.ECharts | null = null
let statusChart: echarts.ECharts | null = null

async function loadStats() {
  loading.value = true
  try {
    const res = await getDashboardStatsApi()
    stats.value = res.data
    await nextTick()
    renderTrendChart()
    renderStatusChart()
  } finally {
    loading.value = false
  }
}

function renderTrendChart() {
  if (!trendChartRef.value || !stats.value) return
  if (!trendChart) {
    trendChart = echarts.init(trendChartRef.value)
  }

  const months = stats.value.monthly_trends.map((m) => m.month)
  const created = stats.value.monthly_trends.map((m) => m.created_tasks)
  const completed = stats.value.monthly_trends.map((m) => m.completed_tasks)
  const hours = stats.value.monthly_trends.map((m) => m.logged_hours)

  const option: EChartsOption = {
    tooltip: { trigger: 'axis' },
    legend: {
      data: trendType.value === 'task' ? ['创建任务数', '完成任务数'] : ['投入工时 (小时)'],
      bottom: 0,
      icon: 'roundRect',
      itemWidth: 10,
      itemHeight: 10,
      itemGap: 16,
      textStyle: { color: cssVar('--text-muted', '#667085'), fontSize: 12 }
    },
    grid: { left: '3%', right: '4%', bottom: '10%', top: '8%', containLabel: true },
    xAxis: {
      type: 'category',
      data: months,
      axisLine: { lineStyle: { color: cssVar('--border-color', '#e4e7ec') } },
      axisTick: { show: false },
      axisLabel: { color: cssVar('--text-muted', '#667085'), fontSize: 11 }
    },
    yAxis: {
      type: 'value',
      axisLabel: { color: cssVar('--text-faint', '#98a2b3'), fontSize: 11 },
      splitLine: { lineStyle: { color: cssVar('--border-color', '#e4e7ec'), type: 'dashed' } }
    },
    series:
      trendType.value === 'task'
        ? [
            {
              name: '创建任务数',
              type: 'bar',
              data: created,
              barWidth: 24,
              itemStyle: {
                color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
                  { offset: 0, color: '#5b7af5' },
                  { offset: 1, color: '#2f54e8' }
                ]),
                borderRadius: [3, 3, 0, 0]
              }
            },
            {
              name: '完成任务数',
              type: 'line',
              smooth: true,
              data: completed,
              itemStyle: { color: '#0f9d58' },
              lineStyle: { width: 2 },
              symbolSize: 5,
              areaStyle: {
                color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
                  { offset: 0, color: 'rgba(15, 157, 88, 0.16)' },
                  { offset: 1, color: 'rgba(15, 157, 88, 0.01)' }
                ])
              }
            }
          ]
        : [
            {
              name: '投入工时 (小时)',
              type: 'bar',
              data: hours,
              barWidth: 24,
              itemStyle: {
                color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
                  { offset: 0, color: '#4a6bf0' },
                  { offset: 1, color: '#2f54e8' }
                ]),
                borderRadius: [3, 3, 0, 0]
              }
            }
          ]
  }
  trendChart.setOption(option, true)
}

function renderStatusChart() {
  if (!statusChartRef.value || !stats.value) return
  if (!statusChart) {
    statusChart = echarts.init(statusChartRef.value)
  }

  const data = stats.value.project_status_dist.map((d) => ({
    name: d.name,
    value: d.count
  }))

  const option: EChartsOption = {
    color: CHART_COLORS,
    tooltip: { trigger: 'item' },
    legend: {
      bottom: 0,
      icon: 'circle',
      itemWidth: 8,
      itemHeight: 8,
      textStyle: { color: cssVar('--text-muted', '#667085'), fontSize: 12 }
    },
    series: [
      {
        name: '项目状态',
        type: 'pie',
        radius: ['56%', '74%'],
        avoidLabelOverlap: false,
        itemStyle: {
          borderRadius: 4,
          borderColor: cssVar('--bg-card', '#ffffff'),
          borderWidth: 2
        },
        label: { show: false, position: 'center' },
        emphasis: {
          label: { show: true, fontSize: 16, fontWeight: 'bold' }
        },
        data: data.length ? data : [{ name: '进行中', value: 3 }]
      }
    ]
  }
  statusChart.setOption(option, true)
}

watch(trendType, () => {
  renderTrendChart()
})

onMounted(() => {
  loadStats()
  window.addEventListener('resize', () => {
    trendChart?.resize()
    statusChart?.resize()
  })
})
</script>

<style scoped lang="scss">
.dashboard-page {
  display: flex;
  flex-direction: column;
  gap: 16px;

  .stat-row {
    margin-bottom: 0;
  }

  .chart-card,
  .table-card {
    padding: 18px 20px;
    height: 100%;

    .card-header {
      display: flex;
      align-items: center;
      justify-content: space-between;
      margin-bottom: 16px;

      .header-title {
        font-size: 15px;
        font-weight: 600;
        color: var(--text-main);
        display: flex;
        align-items: center;
        gap: 8px;
      }
    }

    .chart-container {
      width: 100%;
      height: 320px;
    }
  }

  .member-cell {
    display: flex;
    align-items: center;
    gap: 8px;

    .member-name {
      font-weight: 500;
      color: var(--text-main);
    }
  }

  .activity-timeline {
    display: flex;
    flex-direction: column;
    gap: 16px;
    padding: 4px 8px;

    .activity-item {
      display: flex;
      gap: 12px;
      position: relative;

      .act-dot {
        width: 8px;
        height: 8px;
        border-radius: 50%;
        background-color: var(--primary-color);
        margin-top: 6px;
        flex-shrink: 0;
        box-shadow: 0 0 0 3px var(--primary-light);
      }

      .act-content {
        flex: 1;

        .act-meta {
          display: flex;
          align-items: center;
          gap: 8px;
          margin-bottom: 4px;

          .act-user {
            font-weight: 600;
            font-size: 13px;
            color: var(--text-main);
          }

          .act-module {
            font-size: 11px;
            height: 20px;
            line-height: 18px;
          }

          .act-time {
            font-size: 11px;
            color: var(--text-muted);
            margin-left: auto;
          }
        }

        .act-detail {
          font-size: 13px;
          color: var(--text-regular);
          line-height: 1.4;
        }
      }
    }
  }
}
</style>
