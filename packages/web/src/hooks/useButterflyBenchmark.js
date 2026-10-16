import { useState, useEffect, useRef } from 'react';

export function useButterflyBenchmark() {
  const [metrics, setMetrics] = useState({ fps: 0, memory: 0 });
  const [benchmarkMode, setBenchmarkMode] = useState(false);
  const [scale, setScale] = useState(10);
  
  const frameCount = useRef(0);
  const lastTime = useRef(performance.now());

  useEffect(() => {
    if (!benchmarkMode) return;

    let requestRef;
    const updateMetrics = () => {
      frameCount.current++;
      const now = performance.now();
      const delta = now - lastTime.current;

      if (delta >= 1000) {
        const fps = Math.round((frameCount.current * 1000) / delta);
        
        // Memory API might not be available in all browsers
        const memory = window.performance?.memory 
          ? Math.round(window.performance.memory.usedJSHeapSize / (1024 * 1024))
          : 0;

        setMetrics({ fps, memory });
        frameCount.current = 0;
        lastTime.current = now;
      }
      requestRef = requestAnimationFrame(updateMetrics);
    };

    requestRef = requestAnimationFrame(updateMetrics);
    return () => cancelAnimationFrame(requestRef);
  }, [benchmarkMode]);

  return {
    benchmarkMode,
    setBenchmarkMode,
    metrics,
    scale,
    setScale
  };
}
