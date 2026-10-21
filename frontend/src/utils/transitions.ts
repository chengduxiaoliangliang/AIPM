/**
 * 退出登录的幕布过渡。
 *
 * 直接 `router.push('/login')` 会让整页瞬间换掉，观感上像是页面崩了一下。
 * 这里用一层深色幕布盖住路由切换的瞬间：淡入 → 切换 → 淡出，
 * 退出这件事就有了起止，和登录页的深色底也能自然衔接。
 *
 * 尊重系统的「减少动态效果」设置：开启时直接跳过，不做任何动画。
 */

function prefersReducedMotion(): boolean {
  if (typeof window === 'undefined' || !window.matchMedia) return false
  return window.matchMedia('(prefers-reduced-motion: reduce)').matches
}

export interface Curtain {
  /** 淡出并移除幕布 */
  close: () => Promise<void>
}

const FADE_IN_MS = 240
const FADE_OUT_MS = 300

/** 幕布完全盖住页面所需的时间，调用方据此决定何时切换路由 */
export const CURTAIN_COVER_MS = FADE_IN_MS

export function playLogoutCurtain(label = '正在安全退出…'): Curtain {
  if (prefersReducedMotion()) {
    return { close: async () => {} }
  }

  const el = document.createElement('div')
  el.className = 'logout-curtain'
  el.setAttribute('role', 'status')
  el.setAttribute('aria-live', 'polite')
  el.innerHTML = `
    <div class="logout-curtain__inner">
      <div class="logout-curtain__mark">AIPM</div>
      <div class="logout-curtain__text">${label}</div>
      <div class="logout-curtain__bar"><span></span></div>
    </div>`

  document.body.appendChild(el)
  // 强制一次重排，保证过渡从 opacity:0 开始，否则首帧会被合并掉
  void el.offsetWidth
  el.classList.add('is-visible')

  return {
    close: () =>
      new Promise<void>((resolve) => {
        el.classList.remove('is-visible')
        window.setTimeout(() => {
          el.remove()
          resolve()
        }, FADE_OUT_MS)
      })
  }
}
