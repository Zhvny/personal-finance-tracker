from pathlib import Path

# Setup paths
_HERE = Path(__file__).resolve().parent
_GUI = _HERE.parent
_PROJECT_ROOT = _GUI.parent

def test_stock_analyzer_error_boundary_exists():
    """Verify that ButterflyErrorBoundary exists and is used in stock_analyzer.jsx."""
    sa_path = _GUI / "src" / "pages" / "stock_analyzer.jsx"
    eb_path = _GUI / "src" / "components" / "ButterflyErrorBoundary.jsx"

    sa_content = sa_path.read_text(encoding='utf-8')
    eb_content = eb_path.read_text(encoding='utf-8')

    assert "class ButterflyErrorBoundary extends Component" in eb_content
    assert "import ButterflyErrorBoundary from" in sa_content
    assert "<ButterflyErrorBoundary" in sa_content

def test_stock_analyzer_loading_skeleton_integration():
    """Verify that StockAnalyzerContent uses the skeleton during loading."""
    sa_path = _GUI / "src" / "pages" / "stock_analyzer.jsx"
    content = sa_path.read_text(encoding='utf-8')

    # Check that StockAnalyzerSkeleton is defined
    assert "function StockAnalyzerSkeleton" in content

    # Check that it's used when baseLoading is true
    assert "baseLoading ? <StockAnalyzerSkeleton" in content

def test_stock_analyzer_error_handling_ui():
    """Verify that StockAnalyzerContent handles errors from useTicker."""
    sa_path = _GUI / "src" / "pages" / "stock_analyzer.jsx"
    content = sa_path.read_text(encoding='utf-8')

    # Check for error display logic
    assert "ANALYSIS_FAILURE" in content
    assert "{error}" in content
    assert "clearError()" in content

def test_ticker_context_error_capture():
    """Verify that TickerContext.jsx captures and sets error state on fetch failure."""
    tc_path = _GUI / "src" / "finance" / "TickerContext.jsx"
    content = tc_path.read_text(encoding='utf-8')

    assert "setError(" in content
    assert "Analysis failed" in content
    assert "catch (err)" in content
