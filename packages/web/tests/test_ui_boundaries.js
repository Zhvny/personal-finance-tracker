import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const projectRoot = path.resolve(__dirname, '../../..');

const errorBoundaryPath = path.join(projectRoot, 'packages/web/src/components/ButterflyErrorBoundary.jsx');
const stockAnalyzerPath = path.join(projectRoot, 'packages/web/src/pages/stock_analyzer.jsx');

function testUIBoundaries() {
    console.log('Testing UI Error Boundaries (ButterflyErrorBoundary)...');
    
    if (!fs.existsSync(errorBoundaryPath)) {
        console.error(`File not found: ${errorBoundaryPath}`);
        process.exit(1);
    }

    const ebContent = fs.readFileSync(errorBoundaryPath, 'utf8');

    const ebChecks = [
        { name: 'class ButterflyErrorBoundary', pattern: /export\s+default\s+class\s+ButterflyErrorBoundary\s+extends\s+Component/ },
        { name: 'getDerivedStateFromError implementation', pattern: /static\s+getDerivedStateFromError\(error\)/ },
        { name: 'componentDidCatch implementation', pattern: /componentDidCatch\(error,\s+errorInfo\)/ },
        { name: 'render fallback UI', pattern: /if\s*\(this\.state\.hasError\)/ },
        { name: 'display error message', pattern: /this\.state\.error\?\.message/ },
        { name: 'Retry button', pattern: /onRetry=\{this\.handleRetry\}/ }
    ];

    let passed = true;
    console.log('\nVerifying ButterflyErrorBoundary.jsx:');
    ebChecks.forEach(check => {
        if (check.pattern.test(ebContent)) {
            console.log(`[PASS] ${check.name}`);
        } else {
            console.error(`[FAIL] ${check.name}`);
            passed = false;
        }
    });

    if (!fs.existsSync(stockAnalyzerPath)) {
        console.error(`File not found: ${stockAnalyzerPath}`);
        process.exit(1);
    }

    const saContent = fs.readFileSync(stockAnalyzerPath, 'utf8');

    const saChecks = [
        { name: 'Import ButterflyErrorBoundary', pattern: /import\s+ButterflyErrorBoundary\s+from\s+['"]\.\.\/components\/ButterflyErrorBoundary\.jsx['"]/ },
        { name: 'Usage of ButterflyErrorBoundary', pattern: /<ButterflyErrorBoundary\s+message=['"].*['"]>/ },
        { name: 'Usage of StockAnalyzerContent', pattern: /<StockAnalyzerContent\s*\/>/ }
    ];

    console.log('\nVerifying stock_analyzer.jsx integration:');
    saChecks.forEach(check => {
        if (check.pattern.test(saContent)) {
            console.log(`[PASS] ${check.name}`);
        } else {
            console.error(`[FAIL] ${check.name}`);
            passed = false;
        }
    });

    if (passed) {
        console.log('\nAll UI boundary checks passed.');
        process.exit(0);
    } else {
        console.error('\nSome UI boundary checks failed.');
        process.exit(1);
    }
}

testUIBoundaries();
