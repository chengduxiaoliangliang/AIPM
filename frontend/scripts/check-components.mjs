#!/usr/bin/env node
/**
 * 检查模板里用到的全局组件是否都已注册。
 *
 * 自从 main.ts 改为「按需注册」后，写一个没注册的 <el-xxx> 或图标不会报错，
 * 只会静默渲染成空白。这个脚本在构建前把这类遗漏变成明确的失败。
 *
 * 判定逻辑：模板里的 PascalCase 标签，如果既没有在本文件内 import，
 * 也不在 main.ts 的全局注册表里，就视为遗漏。
 */
import fs from 'node:fs'
import path from 'node:path'

const SRC = path.resolve('src')
const MAIN = path.join(SRC, 'main.ts')

/** 递归收集文件 */
function walk(dir, out = []) {
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    const full = path.join(dir, entry.name)
    if (entry.isDirectory()) walk(full, out)
    else out.push(full)
  }
  return out
}

/** 从 main.ts 里取全局注册的组件名 */
function globalComponents() {
  const src = fs.readFileSync(MAIN, 'utf-8')
  const names = new Set()

  // import { A, B as C } from '...'
  const importBlocks = src.match(/import\s*\{([\s\S]*?)\}\s*from\s*['"][^'"]+['"]/g) || []
  for (const block of importBlocks) {
    const inner = block.slice(block.indexOf('{') + 1, block.lastIndexOf('}'))
    for (const part of inner.split(',')) {
      const name = part.trim().split(/\s+as\s+/).pop().trim()
      if (/^[A-Z]/.test(name)) names.add(name)
    }
  }

  // 注册对象里的键名
  const objectKeys = src.match(/^\s{2}([A-Z]\w*),$/gm) || []
  for (const line of objectKeys) names.add(line.trim().replace(/,$/, ''))

  return names
}

/** 单个 .vue 文件里本地 import 的名字 */
function localImports(src) {
  const names = new Set()
  const blocks = src.match(/import\s*\{([\s\S]*?)\}\s*from\s*['"][^'"]+['"]/g) || []
  for (const block of blocks) {
    const inner = block.slice(block.indexOf('{') + 1, block.lastIndexOf('}'))
    for (const part of inner.split(',')) {
      const name = part.trim().split(/\s+as\s+/).pop().trim()
      if (name) names.add(name)
    }
  }
  // import Foo from '...'
  const defaults = src.match(/import\s+([A-Z]\w*)\s+from/g) || []
  for (const d of defaults) names.add(d.replace(/import\s+/, '').replace(/\s+from/, ''))

  // const Foo = defineAsyncComponent(...) —— 异步组件也属于本地定义
  const asyncComps = src.match(/const\s+([A-Z]\w*)\s*=\s*defineAsyncComponent/g) || []
  for (const d of asyncComps) names.add(d.match(/const\s+([A-Z]\w*)/)[1])

  return names
}

const globals = globalComponents()
console.log(`main.ts 全局注册 ${globals.size} 个组件`)

const problems = []
for (const file of walk(SRC).filter((f) => f.endsWith('.vue'))) {
  const src = fs.readFileSync(file, 'utf-8')
  const template = src.split('</template>')[0]
  const local = localImports(src)

  const tags = new Set()
  for (const m of template.matchAll(/<([A-Z][A-Za-z0-9]*)[\s/>]/g)) tags.add(m[1])

  for (const tag of tags) {
    if (local.has(tag) || globals.has(tag)) continue
    // <component :is="..."> 这类动态组件无法静态判断，跳过
    problems.push({ file: path.relative(SRC, file), tag })
  }
}

if (problems.length) {
  console.error(`\n✗ 发现 ${problems.length} 个未注册的组件：`)
  for (const p of problems) console.error(`  ${p.file}  <${p.tag}>`)
  console.error('\n请把它们加入 src/main.ts 的注册表，或在该文件内单独 import。')
  process.exit(1)
}

console.log('✓ 模板中所有组件均已注册')
