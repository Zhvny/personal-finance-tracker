import { Page, CDPSession } from '@playwright/test';

export interface PerformanceMetrics {
  fps: number;
  memoryUsage: number; // in MB
  domNodes: number;
}

export class MetricsCollector {
  private client: CDPSession | null = null;
  private page: Page;

  constructor(page: Page) {
    this.page = page;
  }

  async start() {
    this.client = await this.page.context().newCDPSession(this.page);
    await this.client.send('Performance.enable');
  }

  async getMetrics(): Promise<PerformanceMetrics> {
    if (!this.client) throw new Error('MetricsCollector not started');

    const metrics = await this.client.send('Performance.getMetrics');
    const getMetric = (name: string) => metrics.metrics.find(m => m.name === name)?.value || 0;

    // Memory: JSHeapUsedSize
    const memoryUsage = getMetric('JSHeapUsedSize') / 1024 / 1024;
    
    // DOM Nodes
    const domNodes = getMetric('Nodes');

    // FPS estimation - this is tricky via CDP getMetrics. 
    // Usually we need to use 'requestAnimationFrame' in-page to calculate FPS.
    const fps = await this.page.evaluate(async () => {
      return new Promise<number>((resolve) => {
        let frames = 0;
        const start = performance.now();
        function check() {
          frames++;
          if (performance.now() - start > 1000) {
            resolve(frames);
          } else {
            requestAnimationFrame(check);
          }
        }
        requestAnimationFrame(check);
      });
    });

    return { fps, memoryUsage, domNodes };
  }

  async stop() {
    if (this.client) {
      await this.client.send('Performance.disable');
    }
  }
}
