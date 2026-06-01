import { useRef, useEffect } from 'react';

/**
 * Hook to count component renders.
 * Stores metrics in window.__renderMetrics for the PERF panel.
 */
export const useRenderCounter = (name: string) => {
  const renderCountRef = useRef(0);
  renderCountRef.current += 1;

  useEffect(() => {
    const target = window as any;
    if (!target.__renderMetrics) {
      target.__renderMetrics = {};
    }

    const now = performance.now();
    if (!target.__renderMetrics[name]) {
      target.__renderMetrics[name] = {
        count: 0,
        lastReset: now,
        fps: 0,
        history: []
      };
    }

    const metrics = target.__renderMetrics[name];
    metrics.count += 1;

    // Calculate average renders per second over the last 2 seconds
    const elapsed = now - metrics.lastReset;
    if (elapsed > 1000) {
      metrics.fps = (metrics.count / elapsed) * 1000;
      metrics.count = 0;
      metrics.lastReset = now;
    }
  });

  return renderCountRef.current;
};
