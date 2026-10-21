import { createApp } from 'vue'
import App from './App.vue'
import router from './router'
import { setupRouterGuard } from './router/guard'
import pinia from './store'

// ── Element Plus：按需注册 ──────────────────────────────────────────────
// 全量 app.use(ElementPlus) 会把整个组件库塞进首屏。这里只注册模板里真正
// 用到的组件（48 个），其余由打包器 tree-shake 掉。
//
// 样式仍整体引入：按组件拆 CSS 容易漏掉 ElMessage / ElLoading 这类编程式
// 组件的样式，省下的约 40KB(gzip) 不值得承担"弹窗没样式"的风险。
import 'element-plus/dist/index.css'
import {
  ElLoading,
  ElAvatar, ElBadge, ElBreadcrumb, ElBreadcrumbItem,
  ElButton, ElButtonGroup, ElCheckbox, ElCheckboxGroup,
  ElCol, ElConfigProvider, ElDatePicker, ElDialog,
  ElDrawer, ElDropdown, ElDropdownItem, ElDropdownMenu,
  ElEmpty, ElForm, ElFormItem, ElIcon,
  ElInput, ElInputNumber, ElLink, ElMenu,
  ElMenuItem, ElOption, ElOptionGroup, ElPagination,
  ElPopconfirm, ElProgress, ElRadioButton, ElRadioGroup,
  ElRow, ElScrollbar, ElSelect, ElSlider,
  ElSubMenu, ElSwitch, ElTabPane, ElTable,
  ElTableColumn, ElTabs, ElTag, ElTimeline,
  ElTimelineItem, ElTooltip, ElTreeSelect, ElUpload,
} from 'element-plus'

// 图标同理：全量注册是 293 个，实际只用到 47 个
import {
  ArrowDown, ArrowRight, Calendar, ChatDotRound,
  Check, Checked, Clock, Close,
  DArrowRight, Delete, Document, Download,
  Expand, Files, Fold, FolderOpened,
  FullScreen, Grid, Key, Link,
  List, Loading, Lock, MagicStick,
  Management, Minus, Moon, Odometer,
  OfficeBuilding, PieChart, Plus, Promotion,
  Reading, Refresh, RefreshLeft, Service,
  Setting, Sunny, SwitchButton, Tickets,
  Timer, TrendCharts, UploadFilled, User,
  UserFilled, View, WarningFilled,
} from '@element-plus/icons-vue'

// Global Styles
import './styles/index.scss'

const app = createApp(App)

// 用变量名作为组件名注册，避免依赖各组件内部的 name 字段
const components: Record<string, any> = {
  ElAvatar,
  ElBadge,
  ElBreadcrumb,
  ElBreadcrumbItem,
  ElButton,
  ElButtonGroup,
  ElCheckbox,
  ElCheckboxGroup,
  ElCol,
  ElConfigProvider,
  ElDatePicker,
  ElDialog,
  ElDrawer,
  ElDropdown,
  ElDropdownItem,
  ElDropdownMenu,
  ElEmpty,
  ElForm,
  ElFormItem,
  ElIcon,
  ElInput,
  ElInputNumber,
  ElLink,
  ElMenu,
  ElMenuItem,
  ElOption,
  ElOptionGroup,
  ElPagination,
  ElPopconfirm,
  ElProgress,
  ElRadioButton,
  ElRadioGroup,
  ElRow,
  ElScrollbar,
  ElSelect,
  ElSlider,
  ElSubMenu,
  ElSwitch,
  ElTabPane,
  ElTable,
  ElTableColumn,
  ElTabs,
  ElTag,
  ElTimeline,
  ElTimelineItem,
  ElTooltip,
  ElTreeSelect,
  ElUpload,
}
Object.entries(components).forEach(([name, comp]) => app.component(name, comp))

const iconComponents: Record<string, any> = {
  ArrowDown,
  ArrowRight,
  Calendar,
  ChatDotRound,
  Check,
  Checked,
  Clock,
  Close,
  DArrowRight,
  Delete,
  Document,
  Download,
  Expand,
  Files,
  Fold,
  FolderOpened,
  FullScreen,
  Grid,
  Key,
  Link,
  List,
  Loading,
  Lock,
  MagicStick,
  Management,
  Minus,
  Moon,
  Odometer,
  OfficeBuilding,
  PieChart,
  Plus,
  Promotion,
  Reading,
  Refresh,
  RefreshLeft,
  Service,
  Setting,
  Sunny,
  SwitchButton,
  Tickets,
  Timer,
  TrendCharts,
  UploadFilled,
  User,
  UserFilled,
  View,
  WarningFilled,
}
Object.entries(iconComponents).forEach(([name, comp]) => app.component(name, comp))

// v-loading 指令
app.use(ElLoading)

app.use(pinia)
app.use(router)

// Setup Router Security Guard
setupRouterGuard(router)

app.mount('#app')
