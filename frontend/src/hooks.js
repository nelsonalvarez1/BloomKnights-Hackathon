import { useEffect, useRef, useState } from 'react'

// Smoothly counts a number up to `target` when it changes. Used across the
// fusion dashboard so no value ever just snaps into place.
export function useCountUp(target, { duration = 900, decimals = 0 } = {}) {
  const [value, setValue] = useState(0)
  const fromRef = useRef(0)
  const rafRef = useRef(0)

  useEffect(() => {
    const from = fromRef.current
    const to = Number(target) || 0
    const start = performance.now()
    cancelAnimationFrame(rafRef.current)

    const tick = (now) => {
      const t = Math.min((now - start) / duration, 1)
      const eased = 1 - Math.pow(1 - t, 3) // easeOutCubic
      const v = from + (to - from) * eased
      setValue(v)
      if (t < 1) rafRef.current = requestAnimationFrame(tick)
      else fromRef.current = to
    }
    rafRef.current = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(rafRef.current)
  }, [target, duration])

  const p = 10 ** decimals
  return Math.round(value * p) / p
}
