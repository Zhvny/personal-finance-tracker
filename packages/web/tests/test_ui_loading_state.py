from pathlib import Path

# Setup paths
_HERE = Path(__file__).resolve().parent
_GUI = _HERE.parent

def test_stock_analyzer_loading_state_logic():
    """
    Verify that StockAnalyzerContent correctly manages its loading state.
    It should show the skeleton when base data is being fetched.
    """
    sa_path = _GUI / "src" / "pages" / "stock_analyzer.jsx"
    content = sa_path.read_text(encoding='utf-8')

    # 1. Verify loading state declaration
    assert 'const [baseLoading, setBaseLoading] = useState(false);' in content

    # 2. Verify loadBaseData sets loading
    assert 'setBaseLoading(true);' in content
    assert 'finally {' in content
    assert 'setBaseLoading(false);' in content

    # 3. Verify render logic respects 'baseLoading' from local state AND 'tickerLoading' from TickerContext
    # The component should show skeleton if local 'baseLoading' is true OR 'tickerLoading' is true
    # Current implementation: {baseLoading ? <StockAnalyzerSkeleton ... /> : ...}
    # AND inside main content: {tickerLoading ? ( ... loading indicator ... ) : ...}

    assert 'baseLoading ? <StockAnalyzerSkeleton' in content
    assert 'tickerLoading ? (' in content

def test_stock_analyzer_ticker_context_integration():
    """
    Verify StockAnalyzerContent uses useTicker and respects its loading state.
    """
    sa_path = _GUI / "src" / "pages" / "stock_analyzer.jsx"
    content = sa_path.read_text(encoding='utf-8')

    # Verify useTicker usage
    assert 'const { data, loading: tickerLoading, error, analyze, clearError } = useTicker();' in content

    # Verify conditional rendering for ticker analysis loading
    assert 'tickerLoading ? (' in content
    assert 'QUANT_ENGINE_LOAD' in content
