"""Reference likelihood: how probable a prompt makes the examples' own answers.

Scoring a candidate prompt by generating answers and comparing them with the
references is noisy with a dozen examples: a small change of the prompt flips a
discrete choice in some answers (a category, a sentence more or less), and every
flip moves that example's score by a lot. The log-probability the task model
gives each reference answer under the prompt moves smoothly with the prompt and
needs one prefill per example, no generation. Decisions between candidate
prompts use it; the scores the service reports stay the task metric.

The score of one example is the mean log-probability per token of its reference
answer followed by the end-of-turn marker, so a prompt that makes the model
want to keep writing after the reference ends scores lower too. (Whatever the
chat template puts after the marker, such as a newline, is not scored.)

Needs an OpenAI-compatible server that returns prompt logprobs and tokenizes
(vLLM: ``prompt_logprobs``, ``/tokenize``). ``ReferenceScorer.probe`` tells
whether the server does; callers fall back to the metric when it does not.
"""

from __future__ import annotations

import hashlib
import json
import threading
from collections.abc import Sequence
from typing import Any

import requests


class LikelihoodUnavailable(RuntimeError):
    """The LLM server cannot score reference answers."""


class ReferenceScorer:
    """Mean log-probability per token of a reference answer given chat messages."""

    def __init__(self, base_url: str, model: str, api_key: str | None = None, *, timeout: float = 600.0,
                 cache: Any = None) -> None:
        self.base_url = base_url.rstrip("/")
        self.root = self.base_url[: -len("/v1")] if self.base_url.endswith("/v1") else self.base_url
        self.model = model
        self.headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
        self.timeout = timeout
        self.cache = cache if cache is not None else {}  # dict-like; a diskcache.Cache shares it across processes
        self._local = threading.local()
        self._n_after: int | None = None
        self._lock = threading.Lock()

    @classmethod
    def from_dspy_lm(cls, lm: Any, *, cache: Any = None) -> ReferenceScorer:
        """A scorer for the server and model a ``dspy.LM`` (``openai/<model>``) calls."""
        model = lm.model.split("/", 1)[1] if lm.model.startswith("openai/") else lm.model
        return cls(lm.kwargs.get("api_base") or "", model, lm.kwargs.get("api_key"), cache=cache)

    def _post(self, url: str, body: dict) -> dict:
        session = getattr(self._local, "session", None)
        if session is None:
            session = self._local.session = requests.Session()
        r = session.post(url, json=body, headers=self.headers, timeout=self.timeout)
        if r.status_code >= 400:
            raise LikelihoodUnavailable(f"{url} -> HTTP {r.status_code}: {r.text[:300]}")
        return r.json()

    def _count(self, **body: Any) -> int:
        return int(self._post(f"{self.root}/tokenize", {"model": self.model, **body})["count"])

    def n_after(self) -> int:
        """Tokens the chat template puts after an assistant message's text (the
        end-of-turn marker, maybe a newline), measured once on a text-only probe;
        0 if that cannot be told."""
        with self._lock:
            if self._n_after is None:
                probe = [{"role": "system", "content": "s"}, {"role": "user", "content": "u"}]
                answer = "Probe answer."
                prefix = self._count(messages=probe, add_generation_prompt=True)
                full = self._count(messages=[*probe, {"role": "assistant", "content": answer}],
                                   add_generation_prompt=False)
                n = full - prefix - self._count(prompt=answer, add_special_tokens=False)
                self._n_after = n if 0 <= n <= 4 else 0
            return self._n_after

    def probe(self) -> str | None:
        """None if the server can score references, else why not."""
        try:
            self.mean_logprob([{"role": "user", "content": "Say hello."}], "Hello.")
            return None
        except Exception as e:  # noqa: BLE001
            return f"{type(e).__name__}: {e}"

    def _scored(self, messages: Sequence[dict], reference: str) -> list[tuple[str, float, int]]:
        """(text, log-probability, rank) of every token of ``reference`` as the
        assistant's reply to ``messages``, then of the end-of-turn marker."""
        reference = reference.strip()
        n_after = self.n_after()
        body = {
            "model": self.model,
            "messages": [*messages, {"role": "assistant", "content": reference}],
            "max_tokens": 1,
            "temperature": 0.0,
            "prompt_logprobs": 0,
            "add_generation_prompt": False,
            "continue_final_message": n_after == 0,
        }
        out = self._post(f"{self.base_url}/chat/completions", body)
        pl = out.get("prompt_logprobs")
        if not pl:
            raise LikelihoodUnavailable("the server returned no prompt_logprobs")
        n_ref = self._count(prompt=reference, add_special_tokens=False)
        # The reference's tokens and the end-of-turn marker right after them.
        span = pl[len(pl) - n_ref - n_after: len(pl) - max(0, n_after - 1)]
        out_tokens = []
        for item in span:
            if not item:
                raise LikelihoodUnavailable("missing logprob for a reference token")
            info = next(iter(item.values()))
            out_tokens.append((str(info.get("decoded_token") or ""), float(info["logprob"]), int(info.get("rank") or 0)))
        return out_tokens

    def tokens(self, messages: Sequence[dict], reference: str) -> list[tuple[str, float]]:
        """(text, log-probability) of every token of ``reference`` as the
        assistant's reply to ``messages``, then of the end-of-turn marker."""
        return [(t, lp) for t, lp, _ in self._scored(messages, reference)]

    def logprobs(self, messages: Sequence[dict], reference: str) -> list[float]:
        """Log-probability of every token of ``reference`` (and the end-of-turn
        marker) as the assistant's reply to ``messages``."""
        return [lp for _, lp, _ in self._scored(messages, reference)]

    def stats(self, messages: Sequence[dict], reference: str) -> tuple[float, float]:
        """(mean log-probability per token, share of tokens that are the model's
        first choice) of ``reference`` (and the end-of-turn marker), cached."""
        key = "stats:" + hashlib.sha256(json.dumps([self.model, list(messages), reference.strip()],
                                                   ensure_ascii=False, sort_keys=True).encode()).hexdigest()
        hit = self.cache.get(key)
        if hit is not None:
            return float(hit[0]), float(hit[1])
        scored = self._scored(messages, reference)
        value = (sum(lp for _, lp, _ in scored) / len(scored), sum(r == 1 for _, _, r in scored) / len(scored))
        self.cache[key] = value
        return value

    def mean_logprob(self, messages: Sequence[dict], reference: str) -> float:
        """Mean log-probability per token of ``reference`` (and the end-of-turn
        marker) as the assistant's reply to ``messages``, cached."""
        return self.stats(messages, reference)[0]
