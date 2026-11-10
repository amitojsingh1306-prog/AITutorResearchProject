"""Metrics for comparing tutor memory strategies.

The evaluator is intentionally storage-agnostic. Test cases can be run through
conversation buffer, rolling summary, ChromaDB vector memory, Neo4j graph
memory, or hybrid retrieval and then scored with the same functions.
"""

from __future__ import annotations

from dataclasses import dataclass
from time import perf_counter
from typing import Callable, TypeVar


T = TypeVar("T")


@dataclass(frozen=True)
class ClassificationCounts:
    true_positive: int = 0
    false_positive: int = 0
    true_negative: int = 0
    false_negative: int = 0


@dataclass(frozen=True)
class ClassificationMetrics:
    accuracy: float
    precision: float
    recall: float
    f1: float


@dataclass(frozen=True)
class RetrievalCase:
    expected_memory_ids: set[str]
    retrieved_memory_ids: list[str]


@dataclass(frozen=True)
class RetrievalMetrics:
    recall_at_k: float
    precision_at_k: float
    mean_reciprocal_rank: float


@dataclass(frozen=True)
class TimedResult:
    value: object
    latency_ms: float


def classification_metrics(counts: ClassificationCounts) -> ClassificationMetrics:
    total = (
        counts.true_positive
        + counts.false_positive
        + counts.true_negative
        + counts.false_negative
    )
    accuracy = _safe_divide(counts.true_positive + counts.true_negative, total)
    precision = _safe_divide(
        counts.true_positive,
        counts.true_positive + counts.false_positive,
    )
    recall = _safe_divide(
        counts.true_positive,
        counts.true_positive + counts.false_negative,
    )
    f1 = _safe_divide(2 * precision * recall, precision + recall)
    return ClassificationMetrics(
        accuracy=round(accuracy, 4),
        precision=round(precision, 4),
        recall=round(recall, 4),
        f1=round(f1, 4),
    )


def retrieval_metrics(cases: list[RetrievalCase], *, k: int = 5) -> RetrievalMetrics:
    if not cases:
        return RetrievalMetrics(0.0, 0.0, 0.0)

    recall_scores: list[float] = []
    precision_scores: list[float] = []
    reciprocal_ranks: list[float] = []

    for case in cases:
        top_k = case.retrieved_memory_ids[:k]
        hits = [memory_id for memory_id in top_k if memory_id in case.expected_memory_ids]
        recall_scores.append(_safe_divide(len(hits), len(case.expected_memory_ids)))
        precision_scores.append(_safe_divide(len(hits), k))
        reciprocal_ranks.append(_reciprocal_rank(case.expected_memory_ids, top_k))

    return RetrievalMetrics(
        recall_at_k=round(sum(recall_scores) / len(recall_scores), 4),
        precision_at_k=round(sum(precision_scores) / len(precision_scores), 4),
        mean_reciprocal_rank=round(sum(reciprocal_ranks) / len(reciprocal_ranks), 4),
    )


def time_call(function: Callable[..., T], *args: object, **kwargs: object) -> TimedResult:
    start = perf_counter()
    value = function(*args, **kwargs)
    elapsed_ms = (perf_counter() - start) * 1000
    return TimedResult(value=value, latency_ms=round(elapsed_ms, 2))


def _reciprocal_rank(expected_ids: set[str], retrieved_ids: list[str]) -> float:
    for index, memory_id in enumerate(retrieved_ids, start=1):
        if memory_id in expected_ids:
            return 1 / index
    return 0.0


def _safe_divide(numerator: float, denominator: float) -> float:
    if denominator == 0:
        return 0.0
    return numerator / denominator
