import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const projectRoot = path.resolve(__dirname, '../../..');

const stockAnalyzerPath = path.join(projectRoot, 'packages/web/src/pages/stock_analyzer.jsx');

function testLoadingState() {
    console.log('Testing UI Loading State Logic (REQ-4)...');
    
    if (!fs.existsSync(stockAnalyzerPath)) {
        console.error(`File not found: ${stockAnalyzerPath}`);
        process.exit(1);
    }

    const content = fs.readFileSync(stockAnalyzerPath, 'utf8');

    const checks = [
        { name: 'baseLoading state declaration', pattern: /const\s+\[baseLoading,\s+setBaseLoading\]\s+=\s+useState\(false\);/ },
        { name: 'loadBaseData sets loading to true', pattern: /setBaseLoading\(true\);/ },
        { name: 'loadBaseData sets loading to false in finally', pattern: /finally\s*{\s*if\s*\(!silent\)\s*setBaseLoading\(false\);/ },
        { name: 'conditional rendering of StockAnalyzerSkeleton', pattern: /baseLoading\s*\?\s*<StockAnalyzerSkeleton/ },
        { name: 'tickerLoading state from useTicker', pattern: /const\s+{\s*data,\s*loading:\s*tickerLoading/ },
        { name: 'conditional rendering for ticker analysis', pattern: /tickerLoading\s*\?\s*\(/ }
    ];

    let passed = true;
    checks.forEach(check => {
        if (check.pattern.test(content)) {
            console.log(`[PASS] ${check.name}`);
        } else {
            console.error(`[FAIL] ${check.name}`);
            passed = false;
        }
    });

    if (passed) {
        console.log('\nAll UI loading state checks passed for REQ-4.');
        process.exit(0);
    } else {
        console.error('\nSome UI loading state checks failed.');
        process.exit(1);
    }
}

testLoadingState();
