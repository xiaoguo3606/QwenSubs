/** Interval-based task polling with cleanup support. */
export function createTaskPoller(intervalMs = 1000) {
  let timer = null
  let stopped = false

  function stop() {
    stopped = true
    if (timer !== null) {
      clearInterval(timer)
      timer = null
    }
  }

  function start(tick) {
    stop()
    stopped = false
    let inFlight = false
    timer = setInterval(async () => {
      if (stopped || inFlight) return
      inFlight = true
      try {
        await tick()
      } finally {
        inFlight = false
      }
    }, intervalMs)
    return stop
  }

  return { start, stop }
}
