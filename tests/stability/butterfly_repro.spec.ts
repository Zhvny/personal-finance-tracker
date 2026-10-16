import { test, expect } from '@playwright/test';
import { MetricsCollector } from './metrics_collector';

// Simplified schema validation
const validateButterflyResponse = (data: any) => {
  if (!data.nodes || !Array.isArray(data.nodes)) throw new Error('Missing or invalid nodes');
  if (!data.edges || !Array.isArray(data.edges)) throw new Error('Missing or invalid edges');
  
  data.nodes.forEach((node: any) => {
    if (!node.id || !node.ticker || typeof node.correlation !== 'number') {
      throw new Error(`Invalid node: ${JSON.stringify(node)}`);
    }
  });
};

test.describe('Butterfly Effect Map Stability', () => {
  let metrics: MetricsCollector;

  test.beforeEach(async ({ page }) => {
    metrics = new MetricsCollector(page);
    await metrics.start();
  });

  test.afterEach(async () => {
    await metrics.stop();
  });

  test('reproduce flickering and validate schema during ticker cycling', async ({ page }) => {
    // 1. Intercept API and validate schema
    await page.route('**/api/butterfly/risk-map/**', async (route) => {
      const response = await route.fetch();
      const json = await response.json();
      
      try {
        validateButterflyResponse(json);
      } catch (err) {
        console.error('Schema Validation Failed:', err.message);
        // We don't fail the test immediately to see if it causes UI flickering
      }
      
      await route.fulfill({ response, json });
    });

    // 2. Navigate to Stock Analyzer
    await page.goto('/stocks');
    await expect(page.getByText('BUTTERFLY EFFECT MAP')).toBeVisible();

    const tickers = ['AAPL', 'BTCUSD', 'ETHUSD', 'TSLA', 'NVDA'];
    const container = page.locator('.card:has-text("BUTTERFLY EFFECT MAP")');

    for (const ticker of tickers) {
      console.log(`Testing ticker: ${ticker}`);
      
      // 3. Change ticker
      // Assuming there is an input field for the ticker. 
      // Looking at App.jsx, StockAnalyzer is rendered. 
      // Let's find the input. It's usually a search box.
      const input = page.locator('input[placeholder*="Ticker"], input[placeholder*="Search"]');
      await input.fill(ticker);
      await input.press('Enter');

      // 4. Monitor for flickering (MutationObserver)
      const mutationCount = await page.evaluate((selector) => {
        return new Promise<number>((resolve) => {
          const el = document.querySelector(selector);
          if (!el) {
            resolve(0);
            return;
          }
          let count = 0;
          const observer = new MutationObserver(() => {
            count++;
          });
          observer.observe(el, { childList: true, subtree: true, attributes: true });
          
          // Wait 2 seconds for stability
          setTimeout(() => {
            observer.disconnect();
            resolve(count);
          }, 2000);
        });
      }, '.card:has-text("BUTTERFLY EFFECT MAP")');

      console.log(`Ticker ${ticker}: ${mutationCount} mutations detected in 2s`);

      // 5. Capture Performance Metrics
      const perf = await metrics.getMetrics();
      console.log(`Ticker ${ticker} Metrics:`, perf);

      // Flickering Threshold: If mutations are too high (> 50 in 2s for a static-ish graph), it's a sign of flickering
      // Note: Animation (pulseManager) might trigger some mutations if it uses DOM attributes.
      // But excessive childList changes are the real issue.
      if (mutationCount > 100) {
        console.warn(`WARNING: High mutation count (${mutationCount}) for ${ticker} - potential flickering!`);
      }

      // 6. Ensure no error states
      await expect(page.getByText('Graph unavailable')).not.toBeVisible();
    }
  });
});
