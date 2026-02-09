"""Adaptive parameter optimiser using a simple genetic algorithm.

Supports regime-aware optimisation: the best parameter-set may differ for
bull, bear, and sideways markets.  The optimizer maintains elite members
across generations and tracks convergence.
"""

from __future__ import annotations

import copy
import math
import random
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any, Callable

from src.strategy_optimizer.parameters import ParamDef, ParamType, ParameterSpace
from src.strategy_optimizer.evaluator import (
    EvaluationResult,
    PerformanceMetrics,
    StrategyEvaluator,
)


@dataclass
class OptimizerConfig:
    """Tuning knobs for the genetic algorithm."""

    population_size: int = 20
    generations: int = 10
    mutation_rate: float = 0.1
    crossover_rate: float = 0.7
    elite_count: int = 3
    regime_aware: bool = True
    tournament_size: int = 3
    seed: int | None = None


@dataclass
class OptimizationResult:
    """Output of a full optimisation run."""

    best_params: dict[str, Any]
    best_score: float
    generation_history: list[dict[str, Any]] = field(default_factory=list)
    convergence_metric: float = 0.0
    improvements: list[dict[str, Any]] = field(default_factory=list)
    generations_run: int = 0
    regime: str = "unknown"
    completed_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict:
        return {
            "best_params": self.best_params,
            "best_score": self.best_score,
            "generation_history": self.generation_history,
            "convergence_metric": self.convergence_metric,
            "improvements": self.improvements,
            "generations_run": self.generations_run,
            "regime": self.regime,
            "completed_at": self.completed_at.isoformat(),
        }


# ── Individual (candidate solution) ───────────────────────────────────


@dataclass
class _Individual:
    params: dict[str, Any]
    fitness: float = 0.0


# ── Adaptive Optimizer ─────────────────────────────────────────────────


class AdaptiveOptimizer:
    """Genetic-algorithm-based strategy parameter optimiser.

    Lifecycle:
        1. ``optimize()`` — run full GA loop and return best result.
        2. ``suggest_params()`` — convenience: run optimize and return params.
        3. ``get_improvement_history()`` — generation-over-generation deltas.

    The GA uses tournament selection, uniform crossover, and per-gene
    mutation.  Elitism preserves the top ``elite_count`` individuals each
    generation.
    """

    def __init__(self, config: OptimizerConfig | None = None) -> None:
        self.config = config or OptimizerConfig()
        self._rng = random.Random(self.config.seed)
        self._history: list[dict[str, Any]] = []
        self._improvements: list[dict[str, Any]] = []

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def optimize(
        self,
        param_space: ParameterSpace,
        evaluator: StrategyEvaluator,
        trade_history: list[dict[str, Any]],
        equity_curve: list[float] | None = None,
    ) -> OptimizationResult:
        """Run a full GA optimization and return the best result."""

        cfg = self.config
        params_list = param_space.get_all()

        # 1) Initialise population
        population = self._init_population(params_list, cfg.population_size)

        # 2) Evaluate initial population
        self._evaluate_population(population, evaluator, trade_history, equity_curve)

        best_ever = max(population, key=lambda ind: ind.fitness)
        prev_best_score = best_ever.fitness

        self._history = []
        self._improvements = []

        for gen in range(cfg.generations):
            # 3) Selection + crossover + mutation
            new_pop: list[_Individual] = []

            # Elitism
            sorted_pop = sorted(population, key=lambda ind: ind.fitness, reverse=True)
            elites = [copy.deepcopy(ind) for ind in sorted_pop[: cfg.elite_count]]
            new_pop.extend(elites)

            # Fill rest with offspring
            while len(new_pop) < cfg.population_size:
                parent1 = self._tournament_select(population, cfg.tournament_size)
                parent2 = self._tournament_select(population, cfg.tournament_size)

                if self._rng.random() < cfg.crossover_rate:
                    child_params = self._crossover(
                        parent1.params, parent2.params, params_list
                    )
                else:
                    child_params = copy.deepcopy(parent1.params)

                child_params = self._mutate(child_params, params_list, cfg.mutation_rate)
                new_pop.append(_Individual(params=child_params))

            population = new_pop[: cfg.population_size]

            # Evaluate
            self._evaluate_population(population, evaluator, trade_history, equity_curve)

            gen_best = max(population, key=lambda ind: ind.fitness)
            gen_avg = sum(ind.fitness for ind in population) / len(population)

            self._history.append({
                "generation": gen,
                "best_score": gen_best.fitness,
                "avg_score": round(gen_avg, 2),
                "best_params": copy.deepcopy(gen_best.params),
            })

            if gen_best.fitness > best_ever.fitness:
                improvement = gen_best.fitness - prev_best_score
                self._improvements.append({
                    "generation": gen,
                    "old_score": prev_best_score,
                    "new_score": gen_best.fitness,
                    "delta": round(improvement, 2),
                })
                best_ever = copy.deepcopy(gen_best)
                prev_best_score = gen_best.fitness

        # Convergence: std-dev of final generation scores
        final_scores = [ind.fitness for ind in population]
        convergence = _std(final_scores) if len(final_scores) > 1 else 0.0

        return OptimizationResult(
            best_params=best_ever.params,
            best_score=best_ever.fitness,
            generation_history=self._history,
            convergence_metric=round(convergence, 4),
            improvements=self._improvements,
            generations_run=cfg.generations,
            regime=evaluator.regime,
        )

    def suggest_params(
        self,
        param_space: ParameterSpace,
        evaluator: StrategyEvaluator,
        trade_history: list[dict[str, Any]],
        equity_curve: list[float] | None = None,
    ) -> dict[str, Any]:
        """Convenience: run optimize and return only the best params dict."""
        result = self.optimize(param_space, evaluator, trade_history, equity_curve)
        return result.best_params

    def get_improvement_history(self) -> list[dict[str, Any]]:
        return list(self._improvements)

    # ------------------------------------------------------------------
    # GA operators
    # ------------------------------------------------------------------

    def _init_population(
        self, params_list: list[ParamDef], size: int
    ) -> list[_Individual]:
        """Generate *size* random individuals within parameter bounds."""
        pop: list[_Individual] = []
        for _ in range(size):
            genes: dict[str, Any] = {}
            for p in params_list:
                genes[p.name] = self._random_value(p)
            pop.append(_Individual(params=genes))
        return pop

    def _evaluate_population(
        self,
        population: list[_Individual],
        evaluator: StrategyEvaluator,
        trades: list[dict[str, Any]],
        equity_curve: list[float] | None,
    ) -> None:
        for ind in population:
            if ind.fitness == 0.0:
                result = evaluator.evaluate(ind.params, trades, equity_curve)
                ind.fitness = result.score

    def _tournament_select(
        self, population: list[_Individual], k: int
    ) -> _Individual:
        """Tournament selection: pick *k* random individuals, return fittest."""
        candidates = self._rng.sample(population, min(k, len(population)))
        return max(candidates, key=lambda ind: ind.fitness)

    def _crossover(
        self,
        p1: dict[str, Any],
        p2: dict[str, Any],
        params_list: list[ParamDef],
    ) -> dict[str, Any]:
        """Uniform crossover: each gene picked from either parent."""
        child: dict[str, Any] = {}
        for p in params_list:
            if self._rng.random() < 0.5:
                child[p.name] = p1.get(p.name, p.default)
            else:
                child[p.name] = p2.get(p.name, p.default)
        return child

    def _mutate(
        self,
        genes: dict[str, Any],
        params_list: list[ParamDef],
        rate: float,
    ) -> dict[str, Any]:
        """Per-gene mutation with probability *rate*."""
        for p in params_list:
            if self._rng.random() < rate:
                genes[p.name] = self._random_value(p)
        return genes

    def _random_value(self, p: ParamDef) -> Any:
        """Generate a random value within the parameter bounds."""
        if p.param_type == ParamType.CONTINUOUS:
            return round(self._rng.uniform(p.min_val, p.max_val), 4)
        elif p.param_type == ParamType.INTEGER:
            return self._rng.randint(int(p.min_val), int(p.max_val))
        elif p.param_type == ParamType.CATEGORICAL:
            return self._rng.choice(p.choices)
        elif p.param_type == ParamType.BOOLEAN:
            return self._rng.choice([True, False])
        return p.default


# ── helpers ────────────────────────────────────────────────────────────


def _std(values: list[float]) -> float:
    if len(values) < 2:
        return 0.0
    mean = sum(values) / len(values)
    var = sum((v - mean) ** 2 for v in values) / (len(values) - 1)
    return math.sqrt(var) if var > 0 else 0.0
