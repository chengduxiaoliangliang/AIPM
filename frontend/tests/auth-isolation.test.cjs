/**
 * Verifies that auth credentials are isolated per browser tab.
 * Each "tab" gets its own sessionStorage; localStorage is shared by all tabs.
 */
const fs = require('fs')
const path = require('path')
const ts = require('typescript')

const SRC = path.join(__dirname, '../src/utils/auth.ts')

function makeStorage(initial = {}) {
  const map = new Map(Object.entries(initial))
  return {
    getItem: (k) => (map.has(k) ? map.get(k) : null),
    setItem: (k, v) => void map.set(k, String(v)),
    removeItem: (k) => void map.delete(k),
    _dump: () => Object.fromEntries(map),
  }
}

let failures = 0
function check(label, cond, extra = '') {
  console.log(`${cond ? 'PASS' : 'FAIL'}  ${label}${extra ? '  -> ' + extra : ''}`)
  if (!cond) failures++
}

async function main() {
  // Legacy state: an old build wrote the token to localStorage.
  const local = makeStorage({ aipm_token: 'LEGACY_TOKEN', aipm_user: '{"username":"old"}' })
  const tabA = makeStorage()
  const tabB = makeStorage()

  globalThis.localStorage = local
  globalThis.sessionStorage = tabA

  // Transpile TS -> JS and load it fresh
  const source = fs.readFileSync(SRC, 'utf8')
  const js = ts.transpileModule(source, {
    compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2020 },
  }).outputText
  const tmp = path.join(__dirname, '.auth-runtime.mjs')
  fs.writeFileSync(tmp, js)
  const { authStorage } = await import('file://' + tmp.replace(/\\/g, '/'))

  check('导入时清理 localStorage 中的旧凭据', !local.getItem('aipm_token') && !local.getItem('aipm_user'),
    JSON.stringify(local._dump()))

  // Tab A signs in
  authStorage.setToken('TOKEN_A')
  authStorage.setUser({ username: 'admin' })
  check('Tab A token 写入 sessionStorage', tabA.getItem('aipm_token') === 'TOKEN_A')
  check('Tab A 不写入 localStorage', !local.getItem('aipm_token'))

  // Tab B signs in as a different account
  globalThis.sessionStorage = tabB
  authStorage.setToken('TOKEN_B')
  authStorage.setUser({ username: 'zhangsan' })

  check('Tab B token 独立存储', tabB.getItem('aipm_token') === 'TOKEN_B')
  check('Tab A 的 token 未被 Tab B 覆盖', tabA.getItem('aipm_token') === 'TOKEN_A',
    'tabA=' + tabA.getItem('aipm_token'))

  // Switch back to Tab A — it must still be the first account
  globalThis.sessionStorage = tabA
  check('切回 Tab A 仍读到自己的 token', authStorage.getToken() === 'TOKEN_A')
  check('切回 Tab A 仍读到自己的用户', authStorage.getUser().username === 'admin')

  globalThis.sessionStorage = tabB
  check('切到 Tab B 读到自己的用户', authStorage.getUser().username === 'zhangsan')

  // Tab A logs out — must not affect Tab B
  globalThis.sessionStorage = tabA
  authStorage.clear()
  check('Tab A 登出后自身已清空', authStorage.getToken() === '')
  globalThis.sessionStorage = tabB
  check('Tab A 登出不影响 Tab B', authStorage.getToken() === 'TOKEN_B')

  // Corrupted user payload must not crash the app
  tabB.setItem('aipm_user', '{not-json')
  check('损坏的 user JSON 不会抛异常', (() => {
    try { return authStorage.getUser() === null } catch { return false }
  })())

  fs.unlinkSync(tmp)
  console.log('\n' + (failures === 0 ? '全部通过' : `${failures} 项失败`))
  process.exit(failures === 0 ? 0 : 1)
}

main().catch((e) => { console.error(e); process.exit(1) })
