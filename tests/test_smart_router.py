"""Tests for PRD-98: Smart Order Router."""

import math
from datetime import datetime

import pytest

from src.smart_router.config import (
    VenueType,
    RoutingStrategy,
    OrderPriority,
    FeeModel,
    VenueConfig,
    RoutingConfig,
    VENUE_FEES,
    DEFAULT_WEIGHTS,
)
from src.smart_router.models import (
    Venue,
    RouteDecision,
    RoutingScore,
    FillProbability,
    VenueMetrics,
    RoutingAudit,
    CostEstimate,
    RouteSplit,
)
from src.smart_router.venue import VenueManager
from src.smart_router.router import SmartRouter
from src.smart_router.scoring import RouteScorer
from src.smart_router.cost import CostOptimizer


# ── Config Tests ──────────────────────────────────────────────────────


class TestSmartRouterEnums:
    def test_venue_types(self):
        assert len(VenueType) == 5
        assert VenueType.LIT_EXCHANGE.value == "lit_exchange"
        assert VenueType.DARK_POOL.value == "dark_pool"

    def test_routing_strategies(self):
        assert len(RoutingStrategy) == 5
        assert RoutingStrategy.SMART.value == "smart"

    def test_order_priority(self):
        assert len(OrderPriority) == 3

    def test_fee_models(self):
        assert len(FeeModel) == 4

    def test_venue_fees_dict(self):
        assert "NYSE" in VENUE_FEES
        assert "NASDAQ" in VENUE_FEES
        assert "IEX" in VENUE_FEES
        assert len(VENUE_FEES) >= 9

    def test_default_weights(self):
        total = sum(DEFAULT_WEIGHTS.values())
        assert total == pytest.approx(1.0)


class TestRoutingConfig:
    def test_defaults(self):
        cfg = RoutingConfig()
        assert cfg.strategy == RoutingStrategy.SMART
        assert cfg.max_venues == 5
        assert cfg.dark_pool_pct == 0.30
        assert cfg.enable_nbbo_check

    def test_custom_config(self):
        cfg = RoutingConfig(strategy=RoutingStrategy.BEST_PRICE, max_venues=3)
        assert cfg.strategy == RoutingStrategy.BEST_PRICE
        assert cfg.max_venues == 3


# ── Model Tests ───────────────────────────────────────────────────────


class TestVenueModel:
    def test_creation(self):
        v = Venue(venue_id="NYSE", name="New York Stock Exchange",
                  venue_type="lit_exchange", maker_fee=-0.002, taker_fee=0.003)
        assert v.is_active
        assert v.fill_rate == 0.80

    def test_dark_pool(self):
        v = Venue(venue_id="DARK", name="Dark Pool", venue_type="dark_pool",
                  avg_price_improvement=0.0003)
        assert v.avg_price_improvement == 0.0003


class TestRouteDecision:
    def test_n_venues(self):
        d = RouteDecision(
            order_id="O1", symbol="AAPL", side="buy", total_quantity=1000,
            strategy="smart",
            splits=[
                RouteSplit("NYSE", 600),
                RouteSplit("DARK", 400, is_midpoint=True),
            ],
        )
        assert d.n_venues == 2

    def test_dark_pool_pct(self):
        d = RouteDecision(
            order_id="O1", symbol="AAPL", side="buy", total_quantity=1000,
            strategy="smart",
            splits=[
                RouteSplit("NYSE", 700),
                RouteSplit("DARK", 300, is_midpoint=True),
            ],
        )
        assert d.dark_pool_pct == pytest.approx(0.30)

    def test_empty_decision(self):
        d = RouteDecision(
            order_id="O1", symbol="AAPL", side="buy",
            total_quantity=1000, strategy="smart",
        )
        assert d.n_venues == 0
        assert d.dark_pool_pct == 0.0


class TestCostEstimate:
    def test_creation(self):
        ce = CostEstimate(
            venue_id="NYSE", exchange_fee=3.0, spread_cost=5.0,
            impact_cost=2.0, total_cost=10.0, rebate=0.0, net_cost=10.0,
        )
        assert ce.net_cost == 10.0


class TestRoutingAudit:
    def test_creation(self):
        audit = RoutingAudit(
            audit_id="A1", order_id="O1", symbol="AAPL",
            side="buy", quantity=1000, strategy="smart",
            venues_considered=9, venues_selected=3,
        )
        assert audit.reg_nms_compliant


# ── Venue Manager Tests ──────────────────────────────────────────────


class TestVenueManager:
    def test_add_venue(self):
        mgr = VenueManager()
        vc = VenueConfig("NYSE", "NYSE", VenueType.LIT_EXCHANGE,
                          FeeModel.MAKER_TAKER, -0.002, 0.003, 0.8, 0.85)
        venue = mgr.add_venue(vc)
        assert venue.venue_id == "NYSE"
        assert mgr.get_venue("NYSE") is not None

    def test_list_venues(self):
        mgr = VenueManager()
        mgr.add_venue(VenueConfig("A", "Venue A"))
        mgr.add_venue(VenueConfig("B", "Venue B"))
        assert len(mgr.list_venues()) == 2

    def test_deactivate(self):
        mgr = VenueManager()
        mgr.add_venue(VenueConfig("A", "Venue A"))
        assert mgr.deactivate_venue("A")
        assert len(mgr.list_venues(active_only=True)) == 0
        assert len(mgr.list_venues(active_only=False)) == 1

    def test_get_lit_venues(self):
        mgr = VenueManager.create_default_venues()
        lit = mgr.get_lit_venues()
        dark = mgr.get_dark_venues()
        assert len(lit) > 0
        assert len(dark) > 0
        assert len(lit) + len(dark) == len(mgr.list_venues())

    def test_cheapest_venue(self):
        mgr = VenueManager.create_default_venues()
        cheapest_taker = mgr.get_cheapest_venue(is_maker=False)
        assert cheapest_taker is not None

    def test_fastest_venue(self):
        mgr = VenueManager.create_default_venues()
        fastest = mgr.get_fastest_venue()
        assert fastest is not None

    def test_rank_by_fill_rate(self):
        mgr = VenueManager.create_default_venues()
        ranked = mgr.rank_venues(by="fill_rate")
        assert len(ranked) > 0
        # Should be sorted descending by fill rate
        for i in range(len(ranked) - 1):
            assert ranked[i].fill_rate >= ranked[i + 1].fill_rate

    def test_rank_by_latency(self):
        mgr = VenueManager.create_default_venues()
        ranked = mgr.rank_venues(by="latency")
        for i in range(len(ranked) - 1):
            assert ranked[i].avg_latency_ms <= ranked[i + 1].avg_latency_ms

    def test_update_metrics(self):
        mgr = VenueManager()
        mgr.add_venue(VenueConfig("NYSE", "NYSE"))
        metrics = VenueMetrics("NYSE", "daily", orders_routed=100,
                                fill_rate=0.92, avg_price_improvement=0.0002)
        mgr.update_metrics("NYSE", metrics)
        v = mgr.get_venue("NYSE")
        assert v.fill_rate == 0.92

    def test_default_venues(self):
        mgr = VenueManager.create_default_venues()
        venues = mgr.list_venues()
        assert len(venues) == 9
        venue_ids = {v.venue_id for v in venues}
        assert "NYSE" in venue_ids
        assert "NASDAQ" in venue_ids
        assert "IEX" in venue_ids


# ── Scorer Tests ──────────────────────────────────────────────────────


class TestRouteScorer:
    def _make_venue(self, venue_id="NYSE", fill_rate=0.85, latency=0.8,
                     taker_fee=0.003, pi=0.0, adverse=0.03):
        return Venue(
            venue_id=venue_id, name=venue_id, venue_type="lit_exchange",
            taker_fee=taker_fee, fill_rate=fill_rate,
            avg_latency_ms=latency, avg_price_improvement=pi,
            adverse_selection_rate=adverse, volume_24h=20_000_000,
        )

    def test_fill_probability(self):
        scorer = RouteScorer()
        venue = self._make_venue(fill_rate=0.85)
        fp = scorer.estimate_fill_probability(venue, 1000, True, 1_000_000)
        assert 0 <= fp.probability <= 1
        assert fp.expected_fill_time_ms > 0

    def test_fill_probability_large_order(self):
        scorer = RouteScorer()
        venue = self._make_venue(fill_rate=0.85)
        fp_small = scorer.estimate_fill_probability(venue, 100, True, 1_000_000)
        fp_large = scorer.estimate_fill_probability(venue, 500_000, True, 1_000_000)
        # Larger orders should generally have lower fill probability
        assert fp_small.probability >= fp_large.probability

    def test_score_venue(self):
        scorer = RouteScorer()
        venue = self._make_venue()
        fp = FillProbability("NYSE", 0.85, 5.0, 0.9, 0.7)
        score = scorer.score_venue(venue, fp, net_cost=0.003)
        assert 0 <= score.composite_score <= 1
        assert score.fill_score == 0.85

    def test_rank_venues(self):
        scorer = RouteScorer()
        scores = [
            RoutingScore("A", composite_score=0.7),
            RoutingScore("B", composite_score=0.9),
            RoutingScore("C", composite_score=0.5),
        ]
        ranked = scorer.rank_venues(scores)
        assert ranked[0].venue_id == "B"
        assert ranked[0].rank == 1
        assert ranked[-1].venue_id == "C"
        assert ranked[-1].rank == 3

    def test_score_all_venues(self):
        scorer = RouteScorer()
        venues = [
            self._make_venue("NYSE", 0.85, 0.8, 0.003),
            self._make_venue("NASDAQ", 0.88, 0.5, 0.003),
            self._make_venue("IEX", 0.78, 1.5, 0.0009),
        ]
        scores = scorer.score_all_venues(venues, 1000)
        assert len(scores) == 3
        assert scores[0].rank == 1
        assert all(s.composite_score > 0 for s in scores)


# ── Cost Optimizer Tests ──────────────────────────────────────────────


class TestCostOptimizer:
    def _make_venue(self, venue_id="NYSE", taker=0.003, maker=-0.002,
                     fill_rate=0.85, pi=0.0):
        return Venue(
            venue_id=venue_id, name=venue_id, venue_type="lit_exchange",
            taker_fee=taker, maker_fee=maker, fill_rate=fill_rate,
            avg_price_improvement=pi,
        )

    def test_estimate_cost(self):
        opt = CostOptimizer()
        venue = self._make_venue()
        est = opt.estimate_cost(venue, 1000, 100.0, 1_000_000)
        assert est.exchange_fee >= 0
        assert est.spread_cost > 0
        assert est.impact_cost > 0
        assert est.net_cost > 0

    def test_maker_rebate(self):
        opt = CostOptimizer()
        venue = self._make_venue(maker=-0.002)
        est = opt.estimate_cost(venue, 1000, 100.0, 1_000_000, is_maker=True)
        assert est.rebate > 0

    def test_find_cheapest(self):
        opt = CostOptimizer()
        venues = [
            self._make_venue("NYSE", taker=0.003),
            self._make_venue("IEX", taker=0.0009),
            self._make_venue("MEMX", taker=0.0025),
        ]
        cheapest = opt.find_cheapest(venues, 1000, 100.0)
        assert cheapest is not None
        assert cheapest.venue_id == "IEX"

    def test_compare_venues(self):
        opt = CostOptimizer()
        venues = [
            self._make_venue("NYSE", taker=0.003),
            self._make_venue("IEX", taker=0.0009),
        ]
        compared = opt.compare_venues(venues, 1000, 100.0)
        assert len(compared) == 2
        # Sorted by net cost ascending
        assert compared[0].net_cost <= compared[1].net_cost

    def test_optimal_split_cost(self):
        opt = CostOptimizer()
        venues = [
            self._make_venue("NYSE", fill_rate=0.85),
            self._make_venue("NASDAQ", fill_rate=0.88),
        ]
        cost = opt.optimal_split_cost(venues, 5000, 100.0)
        assert cost > 0

    def test_maker_taker_savings(self):
        opt = CostOptimizer()
        venue = self._make_venue(taker=0.003, maker=-0.002)
        savings = opt.maker_taker_savings(venue, 1000, 100.0)
        assert savings > 0  # Maker should be cheaper

    def test_empty_venues(self):
        opt = CostOptimizer()
        assert opt.find_cheapest([], 1000, 100.0) is None
        assert opt.optimal_split_cost([], 1000, 100.0) == 0.0


# ── Smart Router Tests ───────────────────────────────────────────────


class TestSmartRouter:
    def test_smart_routing(self):
        router = SmartRouter(config=RoutingConfig(strategy=RoutingStrategy.SMART))
        decision = router.route_order("O1", "AAPL", "buy", 5000, 175.0, 25_000_000)
        assert decision.order_id == "O1"
        assert decision.symbol == "AAPL"
        assert decision.n_venues > 0
        assert len(decision.splits) > 0

    def test_best_price_routing(self):
        router = SmartRouter(config=RoutingConfig(strategy=RoutingStrategy.BEST_PRICE))
        decision = router.route_order("O2", "MSFT", "buy", 1000, 380.0, 15_000_000)
        assert decision.n_venues == 1  # Single best venue

    def test_lowest_cost_routing(self):
        router = SmartRouter(config=RoutingConfig(strategy=RoutingStrategy.LOWEST_COST))
        decision = router.route_order("O3", "GOOG", "sell", 500, 140.0, 10_000_000)
        assert decision.n_venues == 1

    def test_fastest_fill_routing(self):
        router = SmartRouter(config=RoutingConfig(strategy=RoutingStrategy.FASTEST_FILL))
        decision = router.route_order("O4", "TSLA", "buy", 3000, 250.0, 20_000_000)
        assert decision.n_venues > 1  # Split across multiple venues

    def test_dark_pool_allocation(self):
        router = SmartRouter(config=RoutingConfig(
            strategy=RoutingStrategy.SMART, dark_pool_pct=0.30,
        ))
        decision = router.route_order("O5", "AAPL", "buy", 10000, 175.0, 25_000_000)
        assert decision.dark_pool_pct > 0  # Some dark pool allocation

    def test_audit_log(self):
        router = SmartRouter()
        router.route_order("O1", "AAPL", "buy", 1000, 175.0, 25_000_000)
        router.route_order("O2", "MSFT", "sell", 500, 380.0, 15_000_000)
        audits = router.get_audit_log()
        assert len(audits) == 2
        assert audits[0].order_id == "O1"
        assert audits[1].order_id == "O2"
        assert audits[0].reg_nms_compliant

    def test_venue_stats(self):
        router = SmartRouter()
        router.route_order("O1", "AAPL", "buy", 1000, 175.0, 25_000_000)
        stats = router.get_venue_stats()
        assert len(stats) > 0

    def test_nbbo_recorded(self):
        router = SmartRouter()
        decision = router.route_order(
            "O1", "AAPL", "buy", 1000, 175.0, 25_000_000,
            nbbo_bid=174.98, nbbo_ask=175.02,
        )
        assert decision.nbbo_bid == 174.98
        assert decision.nbbo_ask == 175.02

    def test_no_venues(self):
        router = SmartRouter(venue_manager=VenueManager())
        decision = router.route_order("O1", "AAPL", "buy", 1000, 175.0)
        assert decision.n_venues == 0

    def test_sample_decision(self):
        decision = SmartRouter.generate_sample_decision()
        assert decision.symbol == "AAPL"
        assert decision.n_venues > 0


# ── Integration Tests ─────────────────────────────────────────────────


class TestSmartRouterIntegration:
    def test_full_routing_workflow(self):
        """End-to-end: venues -> scoring -> cost -> routing -> audit."""
        mgr = VenueManager.create_default_venues()
        config = RoutingConfig(strategy=RoutingStrategy.SMART, dark_pool_pct=0.25)
        router = SmartRouter(venue_manager=mgr, config=config)

        # Route multiple orders
        for i in range(5):
            decision = router.route_order(
                f"ORD-{i:03d}", "AAPL", "buy" if i % 2 == 0 else "sell",
                1000 + i * 500, 175.0, 25_000_000,
                nbbo_bid=174.98, nbbo_ask=175.02,
            )
            assert decision.n_venues > 0
            assert decision.total_estimated_cost > 0

        audits = router.get_audit_log()
        assert len(audits) == 5

        stats = router.get_venue_stats()
        assert sum(stats.values()) > 0

    def test_strategy_comparison(self):
        """Compare routing results across strategies."""
        mgr = VenueManager.create_default_venues()
        results = {}

        for strategy in RoutingStrategy:
            config = RoutingConfig(strategy=strategy)
            router = SmartRouter(venue_manager=mgr, config=config)
            decision = router.route_order("O1", "AAPL", "buy", 5000, 175.0, 25_000_000)
            results[strategy.value] = {
                "venues": decision.n_venues,
                "cost": decision.total_estimated_cost,
                "dark_pct": decision.dark_pool_pct,
            }

        assert len(results) == 5
        # Best price and lowest cost should use 1 venue
        assert results["best_price"]["venues"] == 1
        assert results["lowest_cost"]["venues"] == 1


# ── Module Import Test ────────────────────────────────────────────────


class TestSmartRouterModuleImports:
    def test_import_all(self):
        import src.smart_router as sr
        assert hasattr(sr, "SmartRouter")
        assert hasattr(sr, "VenueManager")
        assert hasattr(sr, "RouteScorer")
        assert hasattr(sr, "CostOptimizer")
        assert hasattr(sr, "VenueType")
        assert hasattr(sr, "RoutingStrategy")
        assert hasattr(sr, "RouteDecision")
        assert hasattr(sr, "RoutingAudit")
