import asyncio
import logging
import random
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Dict, Optional

import pandas as pd

from packages.core.infrastructure.cache.butterfly_cache import ButterflyCache
from packages.core.infrastructure.persistence.postgres_ohlcv_repository import PostgresOHLCVRepository

from .butterfly_schemas import ButterflyEdge, ButterflyNode, ButterflyResponse

logger = logging.getLogger("butterfly.service")

def _calculate_correlation_matrix(returns_map: Dict[str, pd.Series]) -> Optional[pd.DataFrame]:
    """
    Top-level helper function for ProcessPoolExecutor calculation.
    Must be top-level to be picklable for cross-process communication.
    """
    if not returns_map:
        return None
    # Anti-Holiday alignment: ffill() ensures we don't discard valid return days
    # from one market just because the other was closed.
    price_df = pd.DataFrame(returns_map).ffill().dropna()

    # Require at least 60 samples for a valid 1y correlation
    if len(price_df) < 60:
        return None

    returns_df = price_df.pct_change().dropna()
    return returns_df.corr()

class ButterflyService:
    """
    Butterfly Effect Service for Risk Correlation Analysis.
    Analyzes how a target ticker correlates with macro-economic indicators.
    Now supports async execution via thread and process pools.
    """

    def __init__(self, ohlcv_repo: PostgresOHLCVRepository, cache: Optional[ButterflyCache] = None):
        self.ohlcv_repo = ohlcv_repo
        self.cache = cache or ButterflyCache()
        self.macros = {
            "SPY": "US Equity Market (S&P 500)",
            "USDIDR=X": "US Dollar strength vs IDR",
            "CL=F": "Crude Oil prices (WTI)",
            "GC=F": "Gold (Safe Haven Asset)",
            "BTC-USD": "Crypto Market Sentiment",
            "^JKSE": "IHSG (Indonesian Stock Market)"
        }
        # Initialize executors
        # ThreadPool for I/O (Database/Repo calls)
        self.io_executor = ThreadPoolExecutor(max_workers=10, thread_name_prefix="ButterflyIO")
        # ProcessPool for CPU-bound tasks (Pandas correlation matrix)
        # Note: Switched to ThreadPool on Windows to avoid [WinError 3] spawn issues.
        # Correlation for < 50 tickers is fast enough for threads.
        self.cpu_executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="ButterflyCPU")

    async def get_risk_map(self, target_ticker: str, max_nodes: int = 50, max_edges: int = 150) -> Dict[str, Any]:
        """
        Calculates correlation between target_ticker and global macros over 1 year.
        Returns a graph structure with nodes and edges validated by ButterflyResponse.
        Uses persistent SQLite cache to avoid redundant computations.
        """
        start_time = time.perf_counter()
        logger.info(f"[Butterfly] graph request: {target_ticker}")

        loop = asyncio.get_running_loop()
        params = {"max_nodes": max_nodes, "max_edges": max_edges}

        # 0. Check Cache (Read-Through)
        cached_data = await loop.run_in_executor(
            self.io_executor,
            self.cache.get,
            target_ticker,
            params
        )
        if cached_data:
            elapsed = (time.perf_counter() - start_time) * 1000
            n = len(cached_data.get("nodes", []))
            e = len(cached_data.get("edges", []))
            logger.info(f"[Butterfly] response sent (cache hit): {elapsed:.2f}ms | nodes: {n} | edges: {e}")
            return cached_data

        all_tickers = [target_ticker] + list(self.macros.keys())

        # 1. Gather all data (Parallelized I/O via run_in_executor)
        tasks = []
        for ticker in all_tickers:
            tasks.append(loop.run_in_executor(
                self.io_executor,
                self.ohlcv_repo.get,
                ticker,
                "1y"
            ))

        results = await asyncio.gather(*tasks)

        returns_map = {}
        for ticker, result in zip(all_tickers, results):
            if result is None:
                logger.debug(f"[Butterfly] result is None for {ticker}")
                continue

            df = result[0] if isinstance(result, tuple) else result
            if df is None:
                logger.debug(f"[Butterfly] df is None for {ticker}")
                continue
            if len(df) < 30:
                logger.debug(f"[Butterfly] df too short ({len(df)}) for {ticker}")
                continue

            df.columns = [c.capitalize() for c in df.columns]
            if 'Close' not in df.columns:
                logger.debug(f"[Butterfly] 'Close' not in columns {df.columns} for {ticker}")
                continue

            returns_map[ticker] = df['Close']

        if target_ticker not in returns_map:
            logger.warning(f"[Butterfly] {target_ticker} not in returns_map. Insufficient data.")
            return ButterflyResponse(
                status="insufficient_data",
                message="Not enough correlation data available",
                nodes=[],
                edges=[]
            ).model_dump()

        # 2. Build aligned returns matrix (Offload to ProcessPool)
        logger.info("[Butterfly] correlation started")
        try:
            corr_matrix = await loop.run_in_executor(
                self.cpu_executor,
                _calculate_correlation_matrix,
                returns_map
            )
        except Exception as e:
            logger.error(f"[Butterfly] CPU Executor failed: {e}")
            # Fallback to empty if calculation fails
            corr_matrix = None

        if corr_matrix is None:
            logger.warning(f"[Butterfly] correlation matrix calculation failed or insufficient data for {target_ticker}")
            return ButterflyResponse(
                status="insufficient_data",
                message="Not enough correlation data available",
                nodes=[],
                edges=[]
            ).model_dump()

        # 3. Create Nodes
        nodes = []
        seen_node_ids = set()

        # Target node first
        target_node = ButterflyNode(
            id=target_ticker,
            ticker=target_ticker,
            label=target_ticker,
            correlation=1.0,
            description="Target Asset",
            impact="Target",
            impact_level="Target"
        )
        nodes.append(target_node)
        seen_node_ids.add(target_ticker)

        # Macro nodes
        for macro_ticker, desc in self.macros.items():
            if macro_ticker not in returns_map or macro_ticker == target_ticker:
                continue

            if macro_ticker in seen_node_ids:
                continue

            if macro_ticker not in corr_matrix.index or target_ticker not in corr_matrix.columns:
                continue

            corr = corr_matrix.loc[target_ticker, macro_ticker]
            # NaN Sanitization
            if pd.isna(corr):
                continue

            abs_corr = abs(corr)
            if abs_corr > 0.7:
                impact = "High"
            elif abs_corr > 0.4:
                impact = "Medium"
            else:
                impact = "Low"

            nodes.append(ButterflyNode(
                id=macro_ticker,
                ticker=macro_ticker,
                label=macro_ticker,
                correlation=round(float(corr), 4),
                description=desc,
                impact=impact,
                impact_level=impact
            ))
            seen_node_ids.add(macro_ticker)

        # 4. Create Edges (all pairs with abs(corr) >= 0.3)
        edges = []
        active_tickers = list(seen_node_ids)
        for i in range(len(active_tickers)):
            for j in range(i + 1, len(active_tickers)):
                t1 = active_tickers[i]
                t2 = active_tickers[j]

                # Self-edge filtering
                if t1 == t2:
                    continue

                if t1 not in corr_matrix.index or t2 not in corr_matrix.columns:
                    continue

                corr = corr_matrix.loc[t1, t2]
                # NaN Sanitization and Correlation Filter
                if not pd.isna(corr) and abs(corr) >= 0.3:
                    # Topological Integrity: verify IDs exist in nodes
                    if t1 in seen_node_ids and t2 in seen_node_ids:
                        edges.append(ButterflyEdge(
                            source=t1,
                            target=t2,
                            weight=round(float(corr), 4)
                        ))

        # 4b. Scaling Controls & Payload Trimming
        is_trimmed = False
        original_node_count = len(nodes)
        original_edge_count = len(edges)

        if len(edges) > max_edges:
            # Sort edges by absolute weight descending
            edges.sort(key=lambda e: abs(e.weight), reverse=True)
            edges = edges[:max_edges]
            is_trimmed = True

        # Ensure target node and core macro nodes are ALWAYS preserved
        core_node_ids = {target_ticker} | set(self.macros.keys())
        active_in_edges = set()
        for e in edges:
            active_in_edges.add(e.source)
            active_in_edges.add(e.target)

        # Keep nodes if they are in edges OR if they are core nodes
        final_nodes = [n for n in nodes if n.id in active_in_edges or n.id in core_node_ids]

        # If we still have too many nodes, trim to strictly respect max_nodes
        if len(final_nodes) > max_nodes:
            # Always keep target ticker if present
            target_nodes = [n for n in final_nodes if n.id == target_ticker]
            other_nodes = [n for n in final_nodes if n.id != target_ticker]

            # Sort others by absolute correlation to preserve high-impact ones
            other_nodes.sort(key=lambda n: abs(n.correlation), reverse=True)

            allowed_others = max_nodes - len(target_nodes)
            if allowed_others > 0:
                final_nodes = target_nodes + other_nodes[:allowed_others]
            else:
                final_nodes = target_nodes

            # Re-filter edges to only include nodes we kept
            kept_node_ids = {n.id for n in final_nodes}
            edges = [e for e in edges if e.source in kept_node_ids and e.target in kept_node_ids]
            is_trimmed = True

        nodes = final_nodes

        # Safe fallback for malformed data/insufficient nodes
        if len(nodes) <= 1:
            logger.warning(f"[Butterfly] {target_ticker} has only {len(nodes)} nodes. Returning insufficient_data.")
            return ButterflyResponse(
                status="insufficient_data",
                message="Not enough correlation data available",
                nodes=[],
                edges=[]
            ).model_dump()

        metadata = {
            "is_trimmed": is_trimmed,
            "original_node_count": original_node_count,
            "original_edge_count": original_edge_count,
            "final_node_count": len(nodes),
            "final_edge_count": len(edges)
        }

        logger.info(f"[Butterfly] nodes generated: {len(nodes)}")
        logger.info(f"[Butterfly] edges generated: {len(edges)}")

        response = ButterflyResponse(nodes=nodes, edges=edges, metadata=metadata).model_dump()
        logger.info("[Butterfly] payload validated")
        logger.info("[Butterfly] payload serialized")

        # 5. Store in Cache (Write-Through)
        await loop.run_in_executor(
            self.io_executor,
            self.cache.set,
            target_ticker,
            response,
            params
        )

        elapsed = (time.perf_counter() - start_time) * 1000
        logger.info(f"[Butterfly] response sent (cache miss): {elapsed:.2f}ms | nodes: {len(nodes)} | edges: {len(edges)}")

        return response

    async def generate_mock_risk_map(self, node_count: int, edge_density: float = 0.1) -> Dict[str, Any]:
        """
        Generates a synthetic risk map for benchmarking UI performance.
        node_count: Number of nodes to generate.
        edge_density: Probability of an edge existing between any two nodes (0 to 1).
        """
        start_time = time.perf_counter()

        nodes = []
        for i in range(node_count):
            ticker = f"MOCK_{i}"
            nodes.append(ButterflyNode(
                id=ticker,
                ticker=ticker,
                label=ticker,
                correlation=round(random.uniform(-1, 1), 4),
                description=f"Synthetic benchmark node {i}",
                impact=random.choice(["Low", "Medium", "High"]),
                impact_level=random.choice(["Low", "Medium", "High"])
            ))

        edges = []
        node_ids = [n.id for n in nodes]
        for i in range(len(node_ids)):
            for j in range(i + 1, len(node_ids)):
                if random.random() < edge_density:
                    edges.append(ButterflyEdge(
                        source=node_ids[i],
                        target=node_ids[j],
                        weight=round(random.uniform(-1, 1), 4)
                    ))

        elapsed_ms = (time.perf_counter() - start_time) * 1000

        metadata = {
            "is_mock": True,
            "generation_time_ms": round(elapsed_ms, 2),
            "node_count": len(nodes),
            "edge_count": len(edges),
            "edge_density": edge_density
        }

        return ButterflyResponse(
            nodes=nodes,
            edges=edges,
            status="success",
            metadata=metadata
        ).model_dump()

    def shutdown(self):
        """Cleanup executors on application shutdown."""
        self.io_executor.shutdown(wait=False)
        self.cpu_executor.shutdown(wait=False)
