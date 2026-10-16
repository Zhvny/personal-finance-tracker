import json
import logging
import random
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
import xgboost as xgb
from sklearn.metrics import mean_absolute_error
from sklearn.model_selection import train_test_split

# Use absolute import for the finance-tracker structure
try:
    from apps.cli.investment_tracker.services.data_loader import DataLoader
    from apps.cli.stock_analyzer.domain.config import AppConfig
except ImportError:
    # Fallback for standalone CLI execution
    import sys

    sys.path.append(str(Path(__file__).resolve().parent.parent / "stock_analyzer"))
    sys.path.append(str(Path(__file__).resolve().parent.parent / "investment_tracker" / "services"))
    from domain.config import AppConfig

    try:
        from data_loader import DataLoader
    except ImportError:
        DataLoader = None

# Database Infrastructure
try:
    from packages.core.infrastructure.persistence.postgres_manager import DatabaseManager
except ImportError:
    import sys

    ROOT_PATH = str(Path(__file__).resolve().parent.parent.parent)
    if ROOT_PATH not in sys.path:
        sys.path.append(ROOT_PATH)
    try:
        from packages.core.infrastructure.persistence.postgres_manager import DatabaseManager
    except ImportError:
        DatabaseManager = None

ROOT = Path(__file__).resolve().parent.parent.parent
FEATURES_DIR = ROOT / "data" / "features"
MODELS_PROD_DIR = ROOT / "models" / "prod"
AUDIT_DB = ROOT / "data" / "audit" / "genetic_audit.db"

FEATURE_COLS = ["RET_5", "MA_20_R", "RSI_Z", "ATR_R", "VOL_Z", "RET_1", "MA_50_R"]

logger = logging.getLogger("optimizer.genetic")


class GeneticOptimizer:
    """XGBoost Hyperparameter Evolution Engine."""

    def __init__(self, iterations=None, pop_size=None, mutation_rate=None):
        self.config = AppConfig.load()
        self.iterations = iterations or self.config.ga_generations
        self.pop_size = pop_size or self.config.ga_pop_size
        self.mutation_rate = mutation_rate or self.config.ga_mutation_rate
        self.data_loader = DataLoader() if DataLoader else None
        self._init_audit_db()

    def _init_audit_db(self):
        AUDIT_DB.parent.mkdir(parents=True, exist_ok=True)
        MODELS_PROD_DIR.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(AUDIT_DB))
        conn.execute("""
            CREATE TABLE IF NOT EXISTS evolution_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticker TEXT,
                category TEXT,
                iteration INTEGER,
                params TEXT,
                mae REAL,
                is_winner INTEGER,
                timestamp TEXT
            )
        """)
        conn.commit()
        conn.close()

    def _get_random_params(self):
        return {
            "n_estimators": random.randint(50, 500),
            "max_depth": random.randint(3, 10),
            "learning_rate": random.uniform(0.01, 0.3),
            "subsample": random.uniform(0.6, 1.0),
            "colsample_bytree": random.uniform(0.6, 1.0),
            "gamma": random.uniform(0, 5),
            "random_state": 42,
            "n_jobs": -1,
        }

    def _crossover(self, parent1, parent2):
        child = {}
        for key in parent1:
            if key in ["random_state", "n_jobs"]:
                child[key] = parent1[key]
            else:
                child[key] = random.choice([parent1[key], parent2[key]])
        return child

    def _mutate(self, params):
        key_to_mutate = random.choice(
            ["n_estimators", "max_depth", "learning_rate", "subsample", "colsample_bytree", "gamma"]
        )
        if key_to_mutate == "n_estimators":
            params[key_to_mutate] = random.randint(50, 500)
        elif key_to_mutate == "max_depth":
            params[key_to_mutate] = random.randint(3, 10)
        elif key_to_mutate == "learning_rate":
            params[key_to_mutate] = random.uniform(0.01, 0.3)
        elif key_to_mutate == "subsample":
            params[key_to_mutate] = random.uniform(0.6, 1.0)
        elif key_to_mutate == "colsample_bytree":
            params[key_to_mutate] = random.uniform(0.6, 1.0)
        elif key_to_mutate == "gamma":
            params[key_to_mutate] = random.uniform(0, 5)
        return params

    def _evaluate_params(self, params, X_train, y_train, X_test, y_test):
        try:
            model = xgb.XGBRegressor(**params)
            model.fit(X_train, y_train)
            preds = model.predict(X_test)
            mae = mean_absolute_error(y_test, preds)
            return mae, model
        except Exception as e:
            logger.error(f"Error evaluating params {params}: {e}")
            return float("inf"), None

    def _generate_features_from_returns(self, ticker):
        if not self.data_loader:
            return None

        returns = self.data_loader.get_returns(ticker)
        if returns.size < 100:
            return None

        df = pd.DataFrame(returns, columns=["RET_1"])
        # Simple feature set: Lags and MAs of returns
        df["RET_5"] = df["RET_1"].rolling(window=5).mean()
        df["MA_20_R"] = df["RET_1"].rolling(window=20).mean()
        df["MA_50_R"] = df["RET_1"].rolling(window=50).mean()

        # Z-scores and volatility proxies from returns
        df["RSI_Z"] = (df["RET_1"] - df["RET_1"].rolling(20).mean()) / (df["RET_1"].rolling(20).std() + 1e-8)
        df["ATR_R"] = df["RET_1"].rolling(20).std()
        df["VOL_Z"] = (df["RET_1"].abs() - df["RET_1"].abs().rolling(20).mean()) / (
            df["RET_1"].abs().rolling(20).std() + 1e-8
        )

        df["TARGET"] = df["RET_1"].shift(-1)
        return df.dropna()

    def evolve(self, ticker, category, task_id=None):
        feat_path = FEATURES_DIR / category / f"{ticker}_features.csv"
        if feat_path.exists():
            df = pd.read_csv(feat_path, index_col=0, parse_dates=True)
        else:
            df = self._generate_features_from_returns(ticker)

        if df is None or len(df) < 100:
            print(f"Insufficient data for {ticker} (minimum 100 rows required)")
            return None

        X = df[FEATURE_COLS].values
        y = df["TARGET"].values

        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, shuffle=False)

        # 1. Initialize Population
        pop = [self._get_random_params() for _ in range(self.pop_size)]

        best_mae = float("inf")
        best_model = None
        best_params = None
        results = []

        print(f"Starting Genetic Evolution for {ticker} ({category})...")

        for gen in range(self.iterations):
            # Early Termination Check (Every 5 generations)
            if task_id and DatabaseManager and (gen % 5 == 0):
                try:
                    res = DatabaseManager.query(
                        "SELECT status FROM system.optimization_tasks WHERE task_id = %s", (task_id,), schema="system"
                    )
                    if res and res[0]["status"] == "timeout":
                        print(f"🛑 [Optimizer] ABORTED: Evolution for {ticker} timed out via system signal.")
                        break
                except Exception as e:
                    logger.error(f"Failed to check task status for {task_id}: {e}")

            # 2. Evaluate Population
            fitness = []
            for i in range(self.pop_size):
                mae, model = self._evaluate_params(pop[i], X_train, y_train, X_test, y_test)
                fitness.append(mae)

                is_winner = 0
                if mae < best_mae:
                    best_mae = mae
                    best_model = model
                    best_params = pop[i]
                    is_winner = 1

                results.append(
                    {"iteration": gen * self.pop_size + i, "params": pop[i], "mae": mae, "is_winner": is_winner}
                )

            fitness = np.array(fitness)
            if (gen + 1) % 5 == 0:
                print(f"  Generation {gen+1}/{self.iterations} complete. Current Best MAE: {best_mae:.6f}")

            # 3. Selection (Tournament)
            new_pop = []
            # Elitism: keep best
            new_pop.append(best_params)

            while len(new_pop) < self.pop_size:
                # Tournament selection
                idx1, idx2 = random.sample(range(self.pop_size), 2)
                parent1 = pop[idx1] if fitness[idx1] < fitness[idx2] else pop[idx2]

                idx3, idx4 = random.sample(range(self.pop_size), 2)
                parent2 = pop[idx3] if fitness[idx3] < fitness[idx4] else pop[idx4]

                # 4. Crossover
                child = self._crossover(parent1, parent2)

                # 5. Mutation
                if random.random() < self.mutation_rate:
                    child = self._mutate(child)

                new_pop.append(child)

            pop = new_pop

        # Update winners in local results list before logging
        for res in results:
            res["is_winner"] = 1 if res["mae"] == best_mae else 0

        # Log to DB
        self._log_to_db(ticker, category, results)

        # Save Best Model
        model_path = MODELS_PROD_DIR / f"{ticker}_sniper.json"
        best_model.save_model(str(model_path))

        # Save metadata atomically
        meta_path = MODELS_PROD_DIR / f"{ticker}_meta.json"
        temp_meta = meta_path.with_suffix(".tmp")
        try:
            with open(temp_meta, "w") as f:
                json.dump(
                    {
                        "ticker": ticker,
                        "category": category,
                        "best_mae": float(best_mae),
                        "params": best_params,
                        "optimized_at": datetime.now().isoformat(),
                    },
                    f,
                    indent=4,
                )
            temp_meta.replace(meta_path)
        except Exception as e:
            logger.error(f"Failed to save metadata for {ticker}: {e}")
            if temp_meta.exists():
                temp_meta.unlink()

        print(f"Evolution Complete. Winner MAE: {best_mae:.6f} -> {model_path}")
        return best_mae

    def _log_to_db(self, ticker, category, results):
        timestamp = datetime.now().isoformat()
        data = [
            (ticker, category, res["iteration"], json.dumps(res["params"]), res["mae"], res["is_winner"], timestamp)
            for res in results
        ]

        try:
            with sqlite3.connect(str(AUDIT_DB), timeout=30.0) as conn:
                conn.executemany(
                    """
                    INSERT INTO evolution_logs 
                    (ticker, category, iteration, params, mae, is_winner, timestamp)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                    data,
                )
        except sqlite3.Error as e:
            logger.error(f"Failed to log evolution to DB: {e}")


class PortfolioOptimizer:
    """
    Genetic Algorithm for Portfolio Weight Optimization.
    Externalized constraints: max_assets, sparsity_penalty, GA params.
    """

    _pool = None

    def __init__(self, pop_size=None, generations=None, mutation_rate=None):
        self.config = AppConfig.load()
        self.pop_size = pop_size or self.config.ga_pop_size
        self.generations = generations or self.config.ga_generations
        self.mutation_rate = mutation_rate or self.config.ga_mutation_rate
        self.data_loader = DataLoader() if DataLoader else None

        # Pull constraints from config
        self.max_assets = self.config.ga_max_assets
        self.sparsity_penalty = self.config.ga_sparsity_penalty
        self.concentration_tolerance = self.config.ga_concentration_tolerance

        # Setup exclusion logger
        self.exclusion_logger = logging.getLogger("optimizer.exclusions")
        self.exclusion_logger.setLevel(logging.INFO)
        log_file = ROOT / "logs" / "optimizer_exclusions.log"
        if not self.exclusion_logger.handlers:
            log_file.parent.mkdir(parents=True, exist_ok=True)
            handler = logging.FileHandler(log_file)
            handler.setFormatter(logging.Formatter("%(asctime)s - %(message)s"))
            self.exclusion_logger.addHandler(handler)

        logger.info("[Optimization] optimizer initialized")

    def fetch_real_returns(self, tickers: list, timeframe: str = "2y") -> pd.DataFrame:
        """Fetches real historical returns using DataLoader."""
        if not self.data_loader:
            return pd.DataFrame()

        all_returns = {}
        for ticker in tickers:
            returns = self.data_loader.get_returns(ticker, timeframe)
            if returns.size > 0:
                all_returns[ticker] = returns

        if not all_returns:
            return pd.DataFrame()

        # Align returns by length (simplest alignment for now)
        min_len = min(len(r) for r in all_returns.values())
        truncated_returns = {t: r[-min_len:] for t, r in all_returns.items()}
        return pd.DataFrame(truncated_returns)

    def _calculate_metrics(self, weights, returns, sentiment_bias=None):
        """Calculates expected return and volatility for given weights."""
        mean_returns = returns.mean()
        if sentiment_bias is not None:
            mean_returns = mean_returns * sentiment_bias

        port_return = np.sum(mean_returns * weights) * 252
        port_vol = np.sqrt(np.dot(weights.T, np.dot(returns.cov() * 252, weights)))
        sharpe = port_return / (port_vol + 1e-8)
        return port_return, port_vol, sharpe

    def get_universe_audit(self, returns_df):
        """Returns detailed audit of ticker filtering logic."""
        initial_tickers = list(returns_df.columns)
        total = len(initial_tickers)
        excluded = []

        # 1. Basic filtering logic (All NaNs)
        nan_all = returns_df.columns[returns_df.isna().all()].tolist()
        for t in nan_all:
            excluded.append({"ticker": t, "reason": "Insufficient history (All NaNs)"})

        df = returns_df.drop(columns=nan_all)

        # 2. Emergency Universe Shrinking (Data Completeness)
        nan_counts = df.isna().sum()
        inf_counts = (~np.isfinite(df)).sum() - nan_counts

        invalid_mask = (nan_counts > 0) | (inf_counts > 0)
        invalid_tickers = invalid_mask[invalid_mask].index.tolist()

        for t in invalid_tickers:
            reasons = []
            if nan_counts[t] > 0:
                reasons.append(f"{nan_counts[t]} NaNs")
            if inf_counts[t] > 0:
                reasons.append(f"{inf_counts[t]} Infs")
            excluded.append({"ticker": t, "reason": f"Invalid data ({', '.join(reasons)})"})

        df = df.drop(columns=invalid_tickers)
        final_tickers = list(df.columns)

        # 3. Performance Shrinkage
        perf_limit = 600
        if len(final_tickers) > perf_limit:
            proxies = df.mean() / (df.std() + 1e-8)
            top_tickers = proxies.nlargest(perf_limit).index.tolist()
            dropped = set(final_tickers) - set(top_tickers)
            for t in dropped:
                excluded.append({"ticker": t, "reason": f"Performance fallback (Universe > {perf_limit})"})
            final_tickers = top_tickers

        return {"total": total, "eligible": len(final_tickers), "excluded": excluded}

    def optimize(
        self,
        returns_df,
        target="sharpe",
        risk_tolerance=0.5,
        sentiment_map=None,
        max_assets=None,
        sparsity_penalty=None,
        progress_callback=None,
        task_id=None,
    ):
        """
        Runs the genetic evolution.
        target: 'sharpe', 'min_vol', 'risk_adjusted', or 'sentiment_weighted'
        """
        import time

        start_time = time.time()
        initial_tickers = list(returns_df.columns)
        n_initial = len(initial_tickers)
        print(f"[Optimizer] tickers loaded: {n_initial}")

        # Local overrides
        max_assets = max_assets or self.max_assets
        sparsity_penalty = sparsity_penalty or self.sparsity_penalty

        # 1. Basic filtering logic (All NaNs)
        filtered_df = returns_df.dropna(axis=1, how="all")
        final_tickers = list(filtered_df.columns)
        n_final = len(final_tickers)
        n_filtered = n_initial - n_final

        if n_filtered > 0:
            dropped = set(initial_tickers) - set(final_tickers)
            for t in dropped:
                msg = f"filtered ticker: {t} (reason: NaN values/Insufficient history)"
                print(f"[Optimizer] {msg}")
                self.exclusion_logger.info(msg)

        # 2. Emergency Universe Shrinking (Data Completeness)
        # Check for assets with incomplete history (NaNs) or invalid values (Inf)
        # that would break covariance
        nan_counts = filtered_df.isna().sum()
        inf_counts = (~np.isfinite(filtered_df)).sum() - nan_counts

        invalid_mask = (nan_counts > 0) | (inf_counts > 0)

        if invalid_mask.any():
            invalid_tickers = invalid_mask[invalid_mask].index.tolist()
            print(
                f"[Optimizer] Emergency universe shrinking: Removing {len(invalid_tickers)} assets due to invalid data (NaNs/Infs)."
            )
            for t in invalid_tickers:
                reason_parts = []
                if nan_counts[t] > 0:
                    reason_parts.append(f"{nan_counts[t]} NaNs")
                if inf_counts[t] > 0:
                    reason_parts.append(f"{inf_counts[t]} Infs")
                reason = ", ".join(reason_parts)
                msg = f"filtered ticker: {t} (reason: INVALID DATA - {reason})"
                print(f"  - {t}: INVALID DATA ({reason})")
                self.exclusion_logger.info(msg)

            filtered_df = filtered_df.drop(columns=invalid_tickers)
            final_tickers = list(filtered_df.columns)
            n_final = len(final_tickers)
            print(f"[Optimizer] adjusted universe: {n_final} assets")

        # 3. Performance Shrinkage (Large Universe Fallback)
        perf_limit = 100  # Threshold for GA performance (Aligned with tests)
        if n_final > perf_limit:
            print(f"⚠️ [Optimizer] Performance fallback: Universe size {n_final} exceeds limit ({perf_limit}).")
            print(f"Shrinking to top {perf_limit} assets by risk-adjusted return estimate.")

            # Use simple return/vol as proxy for importance
            proxies = filtered_df.mean() / (filtered_df.std() + 1e-8)
            top_tickers = proxies.nlargest(perf_limit).index.tolist()

            dropped = set(final_tickers) - set(top_tickers)
            print(f"[Optimizer] Removed {len(dropped)} assets for performance optimization.")
            for t in dropped:
                self.exclusion_logger.info(
                    f"filtered ticker: {t} (reason: Performance fallback - Universe > {perf_limit})"
                )

            filtered_df = filtered_df[top_tickers]
            final_tickers = top_tickers
            n_final = len(final_tickers)

        print(f"[Optimizer] final tickers: {n_final}")

        if n_final == 0:
            print("[Optimizer] Error: No assets available for optimization.")
            return None

        # [SILENT TRUNCATION DETECTION]
        # Warn if the final universe is significantly smaller than the max_assets constraint,
        # indicating that historical data overlap issues silently dropped many tickers.
        # A normal run will have n_final <= max_assets; we only alert when it's much smaller.
        truncation_warning = False
        truncation_threshold = max(2, max_assets // 2)  # Alert if less than 50% of max_assets
        if n_final < truncation_threshold:
            truncation_warning = True
            msg = f"SILENT TRUNCATION ALERT: Optimizer running on only {n_final} assets (Constraint: {max_assets}, Threshold: {truncation_threshold}). Check historical data overlap."
            print(f"⚠️ {msg}")
            logger.critical(msg)

        # Prepare sentiment bias vector
        sentiment_bias = np.ones(n_final)
        if sentiment_map:
            for i, ticker in enumerate(filtered_df.columns):
                sentiment_bias[i] = sentiment_map.get(ticker, 1.0)

        # 1. Initialize population
        pop = np.random.random((self.pop_size, n_final))

        # Initial normalization and constraint enforcement
        for i in range(self.pop_size):
            pop[i] = self._enforce_constraints(pop[i], max_assets, sparsity_penalty)

        best_weights = pop[0].copy()
        best_fitness = -np.inf
        history = []
        point_cloud = []

        # Time-based watchdog (max 60s per optimization)
        timeout = 60.0

        for gen in range(self.generations):
            # Progress Reporting
            if progress_callback:
                progress = (gen + 1) / self.generations
                # Report every 5% or at the end
                report_step = max(1, int(self.generations * 0.05))
                if (gen + 1) % report_step == 0 or gen == self.generations - 1:
                    progress_callback(progress)

            # Early Termination Check (Every 5 generations)
            if task_id and DatabaseManager and (gen % 5 == 0):
                try:
                    res = DatabaseManager.query(
                        "SELECT status FROM system.optimization_tasks WHERE task_id = %s", (task_id,), schema="system"
                    )
                    if res and res[0]["status"] == "timeout":
                        print(f"🛑 [Optimizer] ABORTED: Task {task_id} timed out via system signal.")
                        break
                except Exception as e:
                    logger.error(f"Failed to check task status for {task_id}: {e}")

            if time.time() - start_time > timeout:
                print(
                    f"🛑 [Optimizer] TIMEOUT: Interrupted at generation {gen}/{self.generations}. Using best result found."
                )
                break

            fitness = []
            for i in range(self.pop_size):
                ret, vol, sharpe = self._calculate_metrics(pop[i], filtered_df, sentiment_bias)

                if target == "sharpe":
                    fit = sharpe
                elif target == "min_vol":
                    fit = -vol
                elif target == "sentiment_weighted":
                    fit = sharpe
                else:
                    fit = ret * risk_tolerance - vol * (1 - risk_tolerance)

                # Apply Concentration Penalty (HHI based)
                hhi = np.sum(pop[i] ** 2)
                if hhi > self.concentration_tolerance:
                    fit -= (hhi - self.concentration_tolerance) * 10

                fitness.append(fit)

                if fit > best_fitness:
                    best_fitness = fit
                    best_weights = pop[i]

                if gen == self.generations - 1 or random.random() < 0.05:
                    raw_ret, raw_vol, raw_sharpe = self._calculate_metrics(pop[i], filtered_df)
                    point_cloud.append(
                        {"return": float(raw_ret), "volatility": float(raw_vol), "sharpe": float(raw_sharpe)}
                    )

            fitness = np.array(fitness)
            history.append(float(best_fitness))

            # Selection: Tournament
            new_pop = []
            for _ in range(self.pop_size):
                candidates_idx = np.random.choice(range(self.pop_size), min(3, self.pop_size))
                winner_idx = candidates_idx[np.argmax(fitness[candidates_idx])]
                new_pop.append(pop[winner_idx])

            # Crossover
            for i in range(0, self.pop_size, 2):
                if i + 1 < self.pop_size:
                    if random.random() < 0.8:
                        p1, p2 = new_pop[i], new_pop[i + 1]
                        alpha = random.random()
                        new_pop[i] = alpha * p1 + (1 - alpha) * p2
                        new_pop[i + 1] = alpha * p2 + (1 - alpha) * p1

            # Mutation
            for i in range(self.pop_size):
                if random.random() < self.mutation_rate:
                    new_pop[i] += np.random.normal(0, 0.05, n_final)

                # Enforce constraints (Sparsity, Max Assets, Min Assets, Normalization)
                new_pop[i] = self._enforce_constraints(new_pop[i], max_assets, sparsity_penalty)

            pop = np.array(new_pop)

        # [SHRINKAGE WATCHDOG]
        non_zero_assets = np.count_nonzero(best_weights)
        print(f"[Optimizer] optimization universe final: {non_zero_assets}")
        if non_zero_assets < n_final * 0.2 and n_final > 5:
            print(
                f"⚠️ WATCHDOG WARNING: Significant weight collapse. {n_final} assets in universe but only {non_zero_assets} selected."
            )
            print(f"Check if sparsity_penalty ({sparsity_penalty}) or max_assets ({max_assets}) is too aggressive.")

        logger.info("[Optimization] completed")

        results = {
            "weights": dict(zip(filtered_df.columns, best_weights.tolist())),
            "fitness_history": history,
            "point_cloud": point_cloud,
            "final_metrics": [float(m) for m in self._calculate_metrics(best_weights, filtered_df)],
            "diagnostics": {
                "truncation_warning": truncation_warning,
                "initial_universe": n_initial,
                "final_universe": n_final,
                "assets_selected": int(np.count_nonzero(best_weights)),
            },
        }

        # Persistent save and audit
        self.save_results(results, target)

        return results

    def save_results(self, results, target):
        """Persists optimization results to prod models and audit DB."""
        # 1. Atomic JSON update
        output_path = MODELS_PROD_DIR / "active_portfolio.json"
        temp_path = output_path.with_suffix(".tmp")

        timestamp = datetime.now().isoformat()
        payload = {
            "updated_at": timestamp,
            "target": target,
            "metrics": {
                "return": results["final_metrics"][0],
                "volatility": results["final_metrics"][1],
                "sharpe": results["final_metrics"][2],
            },
            "weights": results["weights"],
        }

        try:
            with open(temp_path, "w") as f:
                json.dump(payload, f, indent=4)
            temp_path.replace(output_path)
            print(f"[Optimizer] Saved active portfolio to {output_path}")
        except Exception as e:
            print(f"[Optimizer] Failed to save active portfolio: {e}")
            if temp_path.exists():
                temp_path.unlink()

        # 2. Database logging
        try:
            with sqlite3.connect(str(AUDIT_DB), timeout=30.0) as conn:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS portfolio_audit (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        target TEXT,
                        expected_return REAL,
                        expected_vol REAL,
                        sharpe REAL,
                        asset_count INTEGER,
                        timestamp TEXT
                    )
                """)
                conn.execute(
                    """
                    INSERT INTO portfolio_audit 
                    (target, expected_return, expected_vol, sharpe, asset_count, timestamp)
                    VALUES (?, ?, ?, ?, ?, ?)
                """,
                    (
                        target,
                        payload["metrics"]["return"],
                        payload["metrics"]["volatility"],
                        payload["metrics"]["sharpe"],
                        len(results["weights"]),
                        timestamp,
                    ),
                )

                # Cache invalidation signal: Update a version counter
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS system_state (
                        key TEXT PRIMARY KEY,
                        value TEXT,
                        updated_at TEXT
                    )
                """)
                conn.execute(
                    """
                    INSERT OR REPLACE INTO system_state (key, value, updated_at)
                    VALUES (?, ?, ?)
                """,
                    ("portfolio_version", timestamp, timestamp),
                )
        except sqlite3.Error as e:
            logger.error(f"Failed to log portfolio results to DB: {e}")

    async def optimize_async(self, *args, **kwargs):
        """Runs the optimization in a separate thread to avoid blocking the event loop."""
        import asyncio
        from functools import partial

        logger.info("[Optimization] task started")

        if PortfolioOptimizer._pool is None:
            PortfolioOptimizer._pool = ThreadPoolExecutor(max_workers=4)

        loop = asyncio.get_running_loop()
        func = partial(self.optimize, *args, **kwargs)
        return await loop.run_in_executor(PortfolioOptimizer._pool, func)

    def _enforce_constraints(self, weights, max_assets=None, sparsity_penalty=None):
        """Surgical enforcement of portfolio constraints."""
        w = np.clip(weights, 0, 1)

        # Local overrides
        max_assets = max_assets or self.max_assets
        sparsity_penalty = sparsity_penalty or self.sparsity_penalty

        # 1. Sparsity Penalty (floor)
        # Assets below sparsity_penalty are killed to force concentration or clear exit
        w[w < sparsity_penalty] = 0

        # 2. Max Assets (Top-N only)
        if np.count_nonzero(w) > max_assets:
            # Keep only top-N weights
            threshold = np.sort(w)[-max_assets]
            w[w < threshold] = 0

        # 3. Min Assets (Force diversification if possible)
        # If we have too few assets, we don't force it here, but HHI penalty will handle it

        # 4. Re-normalize
        total = w.sum()
        if total > 0:
            w = w / total
        else:
            # Fallback to equal weight if everything killed
            w = np.ones(len(w)) / len(w)

        return w


def run_monthly_optimization():
    config = AppConfig.load()
    optimizer = GeneticOptimizer(iterations=config.ga_generations)
    # ... rest of implementation ...
    # Get top tickers to optimize (or all from models/)
    MODELS_DIR = ROOT / "models"
    model_files = list(MODELS_DIR.rglob("*_sniper.json"))

    # Filter out prod directory if it's inside models
    model_files = [m for m in model_files if "prod" not in str(m.parent)]

    print(f"Found {len(model_files)} models to optimize.")

    # For the monthly job, maybe just pick top 10 for performance if there are too many,
    # or run all if time allows. Let's do a subset of 10 major tickers for now.
    tickers_to_run = [
        ("AAPL", "us"),
        ("MSFT", "us"),
        ("NVDA", "us"),
        ("AMZN", "us"),
        ("GOOGL", "us"),
        ("XAUUSD", "forex"),
        ("BTCUSD", "crypto"),
        ("ETHUSD", "crypto"),
        ("SPY", "us"),
        ("QQQ", "us"),
    ]

    for ticker, cat in tickers_to_run:
        try:
            optimizer.evolve(ticker, cat)
        except Exception as e:
            print(f"Failed to evolve {ticker}: {e}")


if __name__ == "__main__":
    run_monthly_optimization()
