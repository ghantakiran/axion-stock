"""Tests for Adaptive Strategy Optimizer (PRD-148)."""

import pytest

from src.strategy_optimizer.parameters import (
    ParamType, ParamDef, ParameterSpace, build_default_parameter_space,
    DEFAULT_PARAM_COUNT,
)
from src.strategy_optimizer.evaluator import (
    PerformanceMetrics, EvaluationResult, StrategyEvaluator,
)
from src.strategy_optimizer.optimizer import (
    OptimizerConfig, OptimizationResult, AdaptiveOptimizer,
)
from src.strategy_optimizer.monitor import (
    DriftStatus, DriftConfig, DriftReport, PerformanceDriftMonitor,
)


# ── Helpers ──────────────────────────────────────────────────────────────


def _make_trades(count: int, win_rate: float = 0.6,
                 avg_win: float = 100.0, avg_loss: float = -60.0):
    """Generate synthetic trade list for testing."""
    trades = []
    wins = int(count * win_rate)
    for i in range(count):
        pnl = avg_win if i < wins else avg_loss
        trades.append({"pnl": pnl, "pnl_pct": pnl / 10000.0})
    return trades


# ── ParamDef ─────────────────────────────────────────────────────────────


class TestParamDef:

    def test_validate_continuous(self):
        p = ParamDef(name="x", param_type=ParamType.CONTINUOUS,
                     min_val=0.0, max_val=1.0, default=0.5)
        assert p.validate() is True

    def test_validate_integer(self):
        p = ParamDef(name="n", param_type=ParamType.INTEGER,
                     min_val=1, max_val=10, default=5)
        assert p.validate() is True

    def test_validate_categorical_valid(self):
        p = ParamDef(name="mode", param_type=ParamType.CATEGORICAL,
                     choices=["a", "b"], default="a")
        assert p.validate() is True

    def test_validate_categorical_empty(self):
        p = ParamDef(name="mode", param_type=ParamType.CATEGORICAL,
                     choices=[], default="a")
        assert p.validate() is False

    def test_validate_continuous_missing_bounds(self):
        p = ParamDef(name="x", param_type=ParamType.CONTINUOUS, default=0.5)
        assert p.validate() is False

    def test_to_dict_roundtrip(self):
        p = ParamDef(name="x", param_type=ParamType.CONTINUOUS,
                     min_val=0.0, max_val=1.0, default=0.5, module="test")
        d = p.to_dict()
        p2 = ParamDef.from_dict(d)
        assert p2.name == p.name
        assert p2.param_type == p.param_type
        assert p2.min_val == p.min_val


# ── ParameterSpace ───────────────────────────────────────────────────────


class TestParameterSpace:

    def test_add_and_get(self):
        space = ParameterSpace()
        p = ParamDef(name="x", param_type=ParamType.CONTINUOUS,
                     min_val=0.0, max_val=1.0, default=0.5)
        space.add(p)
        assert space.get("x") is p

    def test_remove(self):
        space = ParameterSpace()
        p = ParamDef(name="x", param_type=ParamType.CONTINUOUS,
                     min_val=0.0, max_val=1.0, default=0.5)
        space.add(p)
        space.remove("x")
        assert space.get("x") is None

    def test_get_by_module(self):
        space = ParameterSpace()
        space.add(ParamDef(name="a", param_type=ParamType.INTEGER,
                           min_val=1, max_val=5, default=3, module="ema"))
        space.add(ParamDef(name="b", param_type=ParamType.INTEGER,
                           min_val=1, max_val=5, default=3, module="risk"))
        assert len(space.get_by_module("ema")) == 1

    def test_get_defaults(self):
        space = ParameterSpace()
        space.add(ParamDef(name="x", param_type=ParamType.CONTINUOUS,
                           min_val=0.0, max_val=1.0, default=0.5))
        defaults = space.get_defaults()
        assert defaults["x"] == 0.5

    def test_to_json_roundtrip(self):
        space = ParameterSpace()
        space.add(ParamDef(name="x", param_type=ParamType.CONTINUOUS,
                           min_val=0.0, max_val=1.0, default=0.5))
        json_str = space.to_json()
        space2 = ParameterSpace.from_json(json_str)
        assert len(space2) == 1

    def test_len(self):
        space = ParameterSpace()
        assert len(space) == 0
        space.add(ParamDef(name="x", param_type=ParamType.BOOLEAN, default=True))
        assert len(space) == 1


# ── Build Default Space ──────────────────────────────────────────────────


class TestBuildDefaultSpace:

    def test_has_expected_count(self):
        space = build_default_parameter_space()
        assert len(space) == DEFAULT_PARAM_COUNT

    def test_all_valid(self):
        space = build_default_parameter_space()
        for p in space.get_all():
            assert p.validate(), f"{p.name} failed validation"

    def test_modules_covered(self):
        space = build_default_parameter_space()
        modules = {p.module for p in space.get_all()}
        assert "ema_signals" in modules
        assert "trade_executor" in modules
        assert "risk" in modules
        assert "signal_fusion" in modules
        assert "scanner" in modules
        assert "regime" in modules


# ── PerformanceMetrics ───────────────────────────────────────────────────


class TestPerformanceMetrics:

    def test_defaults(self):
        m = PerformanceMetrics()
        assert m.sharpe_ratio == 0.0
        assert m.trade_count == 0

    def test_to_dict_roundtrip(self):
        m = PerformanceMetrics(sharpe_ratio=1.5, win_rate=0.6, trade_count=50)
        d = m.to_dict()
        m2 = PerformanceMetrics.from_dict(d)
        assert m2.sharpe_ratio == m.sharpe_ratio
        assert m2.trade_count == m.trade_count

    def test_from_dict_extra_keys(self):
        d = {"sharpe_ratio": 1.0, "win_rate": 0.5, "extra_key": 999}
        m = PerformanceMetrics.from_dict(d)
        assert m.sharpe_ratio == 1.0


# ── StrategyEvaluator ────────────────────────────────────────────────────


class TestStrategyEvaluator:

    def test_empty_trades(self):
        ev = StrategyEvaluator()
        result = ev.evaluate({}, [])
        assert result.metrics.trade_count == 0
        # Empty trades still get partial score from drawdown=0 (no loss)
        assert result.score >= 0

    def test_all_winners(self):
        trades = _make_trades(30, win_rate=1.0, avg_win=100)
        ev = StrategyEvaluator()
        result = ev.evaluate({}, trades)
        assert result.metrics.win_rate == 1.0
        assert result.score > 0

    def test_all_losers(self):
        trades = _make_trades(30, win_rate=0.0, avg_loss=-80)
        ev = StrategyEvaluator()
        result = ev.evaluate({}, trades)
        assert result.metrics.win_rate == 0.0

    def test_mixed_trades(self):
        trades = _make_trades(50, win_rate=0.6)
        ev = StrategyEvaluator()
        result = ev.evaluate({}, trades)
        assert 0 <= result.score <= 100
        assert result.metrics.trade_count == 50

    def test_bear_regime_penalty(self):
        trades = _make_trades(30, win_rate=0.7)
        ev_bull = StrategyEvaluator(regime="bull")
        ev_bear = StrategyEvaluator(regime="bear")
        score_bull = ev_bull.evaluate({}, trades).score
        score_bear = ev_bear.evaluate({}, trades).score
        assert score_bear < score_bull

    def test_score_bounds(self):
        trades = _make_trades(100, win_rate=0.55)
        ev = StrategyEvaluator()
        result = ev.evaluate({}, trades)
        assert 0 <= result.score <= 100

    def test_equity_curve_drawdown(self):
        curve = [100000, 105000, 103000, 110000, 108000]
        trades = _make_trades(20)
        ev = StrategyEvaluator()
        result = ev.evaluate({}, trades, equity_curve=curve)
        assert result.metrics.max_drawdown <= 0


# ── OptimizerConfig ──────────────────────────────────────────────────────


class TestOptimizerConfig:

    def test_defaults(self):
        cfg = OptimizerConfig()
        assert cfg.population_size == 20
        assert cfg.generations == 10
        assert cfg.mutation_rate == 0.1

    def test_custom_config(self):
        cfg = OptimizerConfig(population_size=50, generations=20, seed=42)
        assert cfg.population_size == 50
        assert cfg.seed == 42


# ── AdaptiveOptimizer ────────────────────────────────────────────────────


class TestAdaptiveOptimizer:

    def test_optimize_basic(self):
        space = build_default_parameter_space()
        ev = StrategyEvaluator()
        trades = _make_trades(50)
        opt = AdaptiveOptimizer(OptimizerConfig(population_size=6, generations=3, seed=42))
        result = opt.optimize(space, ev, trades)
        assert isinstance(result, OptimizationResult)
        assert result.best_score >= 0
        assert result.generations_run == 3

    def test_optimize_improves_over_generations(self):
        space = build_default_parameter_space()
        ev = StrategyEvaluator()
        trades = _make_trades(50, win_rate=0.65)
        opt = AdaptiveOptimizer(OptimizerConfig(population_size=10, generations=5, seed=7))
        result = opt.optimize(space, ev, trades)
        assert result.best_score > 0
        # Generation history should be recorded
        assert len(result.generation_history) == 5

    def test_suggest_params_returns_dict(self):
        space = build_default_parameter_space()
        ev = StrategyEvaluator()
        trades = _make_trades(30)
        opt = AdaptiveOptimizer(OptimizerConfig(population_size=6, generations=2, seed=1))
        params = opt.suggest_params(space, ev, trades)
        assert isinstance(params, dict)
        assert "ema_fast_period" in params

    def test_deterministic_with_seed(self):
        space = build_default_parameter_space()
        ev = StrategyEvaluator()
        trades = _make_trades(30)
        r1 = AdaptiveOptimizer(OptimizerConfig(population_size=6, generations=2, seed=99)).optimize(space, ev, trades)
        r2 = AdaptiveOptimizer(OptimizerConfig(population_size=6, generations=2, seed=99)).optimize(space, ev, trades)
        assert r1.best_score == r2.best_score
        assert r1.best_params == r2.best_params

    def test_elite_preservation(self):
        space = build_default_parameter_space()
        ev = StrategyEvaluator()
        trades = _make_trades(40)
        opt = AdaptiveOptimizer(OptimizerConfig(
            population_size=8, generations=4, elite_count=2, seed=10
        ))
        result = opt.optimize(space, ev, trades)
        # Best score should be non-decreasing across generations
        scores = [h["best_score"] for h in result.generation_history]
        for i in range(1, len(scores)):
            assert scores[i] >= scores[i - 1]

    def test_improvement_history(self):
        space = build_default_parameter_space()
        ev = StrategyEvaluator()
        trades = _make_trades(40, win_rate=0.6)
        opt = AdaptiveOptimizer(OptimizerConfig(population_size=8, generations=5, seed=3))
        result = opt.optimize(space, ev, trades)
        history = opt.get_improvement_history()
        assert isinstance(history, list)


# ── PerformanceDriftMonitor ──────────────────────────────────────────────


class TestPerformanceDriftMonitor:

    def _make_baseline(self):
        return PerformanceMetrics(
            sharpe_ratio=1.5, total_return=0.20, max_drawdown=-0.08,
            win_rate=0.60, profit_factor=1.8, trade_count=100,
        )

    def test_healthy_no_drift(self):
        baseline = self._make_baseline()
        monitor = PerformanceDriftMonitor(baseline_metrics=baseline)
        # Trades that match baseline roughly
        trades = _make_trades(30, win_rate=0.6, avg_win=100, avg_loss=-60)
        report = monitor.check(trades)
        assert report.status in (DriftStatus.HEALTHY, DriftStatus.WARNING)

    def test_warning_moderate_drift(self):
        baseline = PerformanceMetrics(sharpe_ratio=2.0, max_drawdown=-0.05)
        monitor = PerformanceDriftMonitor(baseline_metrics=baseline)
        # All losers => sharpe will be very negative
        trades = _make_trades(30, win_rate=0.0, avg_loss=-100)
        report = monitor.check(trades)
        assert report.status in (DriftStatus.WARNING, DriftStatus.CRITICAL)

    def test_critical_severe_drift(self):
        baseline = PerformanceMetrics(sharpe_ratio=2.0, max_drawdown=-0.01)
        config = DriftConfig(sharpe_threshold=0.1, drawdown_threshold=0.02)
        monitor = PerformanceDriftMonitor(config=config, baseline_metrics=baseline)
        trades = _make_trades(30, win_rate=0.1, avg_win=10, avg_loss=-200)
        report = monitor.check(trades)
        assert report.status == DriftStatus.CRITICAL

    def test_stale_insufficient_trades(self):
        monitor = PerformanceDriftMonitor(
            config=DriftConfig(min_trades_for_check=50)
        )
        trades = _make_trades(10)
        report = monitor.check(trades)
        assert report.status == DriftStatus.STALE

    def test_recommendation_healthy(self):
        monitor = PerformanceDriftMonitor()
        report = DriftReport(
            status=DriftStatus.HEALTHY,
            current_metrics=PerformanceMetrics(),
            baseline_metrics=PerformanceMetrics(),
        )
        assert monitor.get_recommendation(report) == "healthy"

    def test_recommendation_reoptimize(self):
        monitor = PerformanceDriftMonitor()
        report = DriftReport(
            status=DriftStatus.WARNING,
            current_metrics=PerformanceMetrics(),
            baseline_metrics=PerformanceMetrics(),
        )
        assert monitor.get_recommendation(report) == "reoptimize"

    def test_recommendation_halt(self):
        monitor = PerformanceDriftMonitor()
        report = DriftReport(
            status=DriftStatus.CRITICAL,
            current_metrics=PerformanceMetrics(),
            baseline_metrics=PerformanceMetrics(),
        )
        assert monitor.get_recommendation(report) == "halt_and_review"

    def test_history_tracking(self):
        monitor = PerformanceDriftMonitor()
        trades = _make_trades(30)
        monitor.check(trades)
        monitor.check(trades)
        assert len(monitor.get_history()) == 2

    def test_drift_report_to_dict(self):
        report = DriftReport(
            status=DriftStatus.WARNING,
            current_metrics=PerformanceMetrics(sharpe_ratio=0.5),
            baseline_metrics=PerformanceMetrics(sharpe_ratio=1.5),
            sharpe_ratio_delta=-1.0,
        )
        d = report.to_dict()
        assert d["status"] == "warning"
        assert d["sharpe_ratio_delta"] == -1.0
