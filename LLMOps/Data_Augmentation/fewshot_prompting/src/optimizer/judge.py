"""Decisions between candidate prompts.

A candidate (instruction, demos) replaces the current one only when both hold:

1. Its evidence rises — by more than ``z`` standard errors of the paired
   per-example differences, and by more than ``margin``. By default the
   evidence is the share of reference-answer tokens that are the task model's
   first choice when it reads the reference (teacher-forced top-1 accuracy,
   ``likelihood.py``); without a server that scores references it is the
   metric itself.
2. The task metric — the score the service reports — does not fall.

Why two measurements: with a dozen leave-one-out examples the metric alone
picks the wrong one of two prompts often (any change flips a discrete choice
in some answers, and every flip moves that example's score a lot), and how
often depends on the metric. On held-out scenes (dev data, 300 candidate pairs
per version), the leave-one-out metric agreed with the held-out difference in
70% of pairs with SPICE (English) but 47% with token-F1 (Korean); first-choice
accuracy in 55% and 73%. Requiring both to rise was the most precise rule in
both languages: every candidate it accepted over the starting prompt was better
on the held-out scenes. The reference log-likelihood (``kind="llh"``) is
available but agreed in only 52% of pairs — it rewards spreading probability
over the reference's unpredictable words rather than writing like it.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from src.optimizer.scoring import evaluate_demos, likelihood_per_example
from src.optimizer.task import Example, Task


@dataclass
class Candidate:
    """An (instruction, demos) prompt with its metric score (``None`` until
    measured) and the per-example evidence decisions compare."""

    instruction: str | None
    demos: list[Example]
    score: float | None
    evidence: list[float] | None = None


def _mean(xs: Sequence[float]) -> float:
    return sum(xs) / len(xs) if xs else 0.0


def paired_gain(new: Sequence[float], old: Sequence[float]) -> tuple[float, float]:
    """Mean and standard error of the per-example differences ``new - old``."""
    d = [a - b for a, b in zip(new, old)]
    if not d:
        return 0.0, 0.0
    m = _mean(d)
    if len(d) < 2:
        return m, 0.0
    var = sum((x - m) ** 2 for x in d) / (len(d) - 1)
    return m, (var / len(d)) ** 0.5


@dataclass
class Judge:
    """Scores candidates on ``scoring`` (leave-one-out) and decides between them.
    ``scorer`` is a ``likelihood.ReferenceScorer`` or ``None`` (metric only).
    Must be used inside ``dspy.context(lm=task_lm)``."""

    task: Task
    scoring: list[Example]
    scorer: object | None = None
    z: float = 0.0
    margin: float = 0.0
    # The evidence: "metric" (the task metric itself), "top1" (share of reference
    # tokens that are the model's first choice) or "llh" (mean log-probability of
    # the references); the last two need a scorer and keep the metric from falling.
    kind: str = "metric"

    @property
    def uses_likelihood(self) -> bool:
        """Whether decisions use reference scoring (else the metric alone)."""
        return self.scorer is not None and self.kind != "metric"

    def _metric_vector(self, instruction: str | None, demos: Sequence[Example]) -> list[float]:
        return [s.score for s in evaluate_demos(self.task, demos, self.scoring, instruction=instruction)]

    def candidate(self, instruction: str | None, demos: Sequence[Example], *, metric: bool = False) -> Candidate:
        """Score (instruction, demos): its evidence always, its metric when
        ``metric`` (in metric-only mode the two are the same measurement)."""
        demos = list(demos)
        if not self.uses_likelihood:
            vec = self._metric_vector(instruction, demos)
            return Candidate(instruction, demos, _mean(vec), vec)
        evidence = likelihood_per_example(self.task, demos, self.scoring, instruction=instruction, scorer=self.scorer,
                                          kind=self.kind)
        score = _mean(self._metric_vector(instruction, demos)) if metric else None
        return Candidate(instruction, demos, score, evidence)

    def measure(self, cand: Candidate) -> float:
        """The candidate's metric score, measured now if it was not yet."""
        if cand.score is None:
            cand.score = _mean(self._metric_vector(cand.instruction, cand.demos))
        return cand.score

    def improves(self, new: Candidate, old: Candidate) -> tuple[bool, str]:
        """Whether ``new`` should replace ``old``, and a one-line account. The
        metric of ``new`` is measured only once its evidence has passed."""
        gain, se = paired_gain(new.evidence or [], old.evidence or [])
        what = self.kind if self.uses_likelihood else "metric"
        line = f"{what} {_mean(old.evidence or []):.4f} -> {_mean(new.evidence or []):.4f} ({gain:+.4f} ± {se:.4f})"
        if not (gain > self.margin and gain > self.z * se):
            return False, line
        if not self.uses_likelihood:
            return True, line
        old_score, new_score = self.measure(old), self.measure(new)
        line += f", metric {old_score:.4f} -> {new_score:.4f}"
        return new_score >= old_score, line
