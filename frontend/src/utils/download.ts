/** 触发浏览器下载一个 Blob */
export function saveBlob(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
  // 给浏览器一点时间开始下载再释放
  setTimeout(() => URL.revokeObjectURL(url), 2000)
}
