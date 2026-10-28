"""src/spice.py and the "spice" metric: memoization, batching, fallbacks — plus
one end-to-end check against the real Java server when SPICE is set up."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from conftest import REAL_SPICE_HOME
from src import spice
from src.fewshot_task import FewShotTask
from src.optimizer.task import Example

GOLD = "Own vessel is proceeding northward on course 012 degrees at 17.6 knots under clear skies."


@pytest.fixture
def fake_server(monkeypatch):
    """Replace the JVM with a recorder that scores every pair 0.5."""
    calls: list[list[tuple[str, str]]] = []

    def score(pairs):
        calls.append(list(pairs))
        return [0.5 for _ in pairs]

    monkeypatch.setattr(spice._server, "score", score)
    monkeypatch.setattr(spice, "_memo", {})
    return calls


def test_pairs_are_scored_once_and_empty_strings_score_zero(fake_server):
    pairs = [(GOLD, "a"), (GOLD, "b"), (GOLD, " a "), (GOLD, ""), ("", "x")]
    assert spice.spice_scores(pairs) == [0.5, 0.5, 0.5, 0.0, 0.0]
    assert spice.spice_scores([(GOLD, "b"), (GOLD, "c")]) == [0.5, 0.5]
    assert fake_server == [[(GOLD, "a"), (GOLD, "b")], [(GOLD, "c")]]


def test_spice_metric_scores_a_holdout_batch_in_one_request(monkeypatch, fake_server):
    monkeypatch.setattr(spice, "start", lambda: None)
    task = FewShotTask(metric_name="spice")
    examples = [Example(inputs={"query": "q"}, outputs={"response": GOLD}) for _ in range(3)]
    predictions = [{"response": f"prediction {i}"} for i in range(3)]
    assert task.metric_batch(examples, predictions) == [0.5, 0.5, 0.5]
    assert len(fake_server) == 1
    assert task.metric_name == "spice" and task.warnings == []


def test_spice_is_the_default_and_falls_back_to_token_f1_when_unavailable():
    task = FewShotTask()  # SPICE looks "not installed" in unit tests
    assert task.metric_name == "token_f1"
    assert task.warnings[0].startswith("spice unavailable (RuntimeError: SPICE is not installed")


def test_a_failed_spice_batch_is_scored_with_token_f1_and_counted(monkeypatch):
    monkeypatch.setattr(spice, "start", lambda: None)

    def broken(pairs):
        raise ValueError("SPICE error: parser crashed")

    monkeypatch.setattr(spice, "spice_scores", broken)
    task = FewShotTask(metric_name="spice")
    example = Example(inputs={"query": "q"}, outputs={"response": "a b c"})
    assert task.metric(example, {"response": "a b c"}) == 1.0
    assert task.warnings == [
        "spice failed on 1 prediction(s) (first: ValueError('SPICE error: parser crashed')); "
        "token_f1 was used for those"
    ]


def test_preload_is_skipped_when_switched_off_or_not_installed(monkeypatch):
    assert spice.preload_spice() is None  # SPICE_PRELOAD=false in tests
    monkeypatch.setenv("SPICE_PRELOAD", "true")
    assert spice.preload_spice() is None  # SPICE_HOME points nowhere in tests


_REAL = Path(REAL_SPICE_HOME)
_HAVE_SPICE = (
    shutil.which("java") is not None
    and (_REAL / "server" / "edu" / "anu" / "spice" / "SpiceServer.class").is_file()
    and (_REAL / "lib" / "stanford-corenlp-3.6.0-models.jar").is_file()
)


@pytest.mark.skipif(not _HAVE_SPICE, reason="SPICE not set up (run spice/setup.sh --with-corenlp)")
def test_real_spice_server(monkeypatch):
    server = spice._SpiceServer()
    monkeypatch.setattr(spice, "SPICE_HOME", _REAL)
    monkeypatch.setattr(spice, "_server", server)
    monkeypatch.setattr(spice, "_memo", {})
    try:
        identical, unrelated = spice.spice_scores([(GOLD, GOLD), (GOLD, "A fishing boat sails in dense fog at night.")])
    finally:
        server.close()
    assert identical == pytest.approx(1.0)
    assert unrelated == pytest.approx(0.0)
