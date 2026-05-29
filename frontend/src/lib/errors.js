/**
 * Map common English error messages to Chinese.
 */
const ERROR_MAP = [
  [/out of memory/i, '显存不足，请尝试使用更小的模型或降低精度'],
  [/CUDA out of memory/i, 'CUDA 显存不足，请尝试使用 CPU 或更小的模型'],
  [/No CUDA/i, '未检测到 CUDA 设备，请选择 CPU 运行'],
  [/model.*not found/i, '模型文件未找到，请前往设置页面下载模型'],
  [/download.*fail/i, '模型下载失败，请检查网络连接'],
  [/connection.*refused/i, '连接被拒绝，请检查服务地址是否正确'],
  [/time.*out|timeout/i, '连接超时，请检查网络或服务状态'],
  [/file.*not found/i, '文件未找到，请重新上传音频'],
  [/permission.*denied/i, '权限不足，请检查文件权限'],
  [/cancelled/i, '任务已取消'],
  [/invalid.*file/i, '无效的音频文件，请检查格式'],
  [/text.*required/i, '请输入对齐文本'],
  [/audio.*duration/i, '音频时长超出限制'],
  [/split.*point/i, '分割点无效'],
];

/**
 * Translate an English error string to Chinese if possible.
 */
export function translateError(msg) {
  if (!msg) return msg;
  for (const [pattern, zh] of ERROR_MAP) {
    if (pattern.test(msg)) return zh;
  }
  // Fallback prefix
  if (!/[一-鿿]/.test(msg)) {
    return `错误: ${msg}`;
  }
  return msg;
}
