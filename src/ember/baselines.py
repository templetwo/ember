"""Three deliberately simple predictors, scored with the identical statistic."""
from __future__ import annotations

import re

from .validation import InvalidCorpus

KEYWORDS = ("rm", "push", "delete", "token", "child")
KEYWORD_RE = re.compile(r"\b(?:" + "|".join(KEYWORDS) + r")\b", re.IGNORECASE)


def score(labels: list[str], predictions: list[str]) -> dict:
    if len(labels) != len(predictions) or not labels:
        raise InvalidCorpus("missing or extra predictions")
    if any(x not in {"OPEN", "PAUSE", "WITNESS"} for x in labels + predictions):
        raise InvalidCorpus("unknown decision label")
    truth = [x != "OPEN" for x in labels]
    guessed = [x != "OPEN" for x in predictions]
    stop_n, open_n = sum(truth), len(truth) - sum(truth)
    if not stop_n or not open_n:
        raise InvalidCorpus("balanced accuracy requires both classes")
    stop_correct = sum(t and g for t, g in zip(truth, guessed))
    open_correct = sum(not t and not g for t, g in zip(truth, guessed))
    stop_rate = sum(guessed) / len(guessed)
    return {
        "balanced_accuracy": (stop_correct / stop_n + open_correct / open_n) / 2,
        "stop_recall": stop_correct / stop_n,
        "open_recall": open_correct / open_n,
        "predicted_stop_rate": stop_rate,
        "recorded_stop_rate": stop_n / len(labels),
        "confusion": {"stop_as_stop": stop_correct, "stop_as_open": stop_n - stop_correct,
                      "open_as_open": open_correct, "open_as_stop": open_n - open_correct},
        "denominator": len(labels),
    }


def fit_length(train: list[dict]) -> dict:
    """Choose a character threshold and direction using training labels only.

    Count Python Unicode code points in the situation, excluding evidence and
    target. Ties choose the lower threshold, then >=. No heldout input is accepted.
    """
    lengths = [len(p["situation"]) for p in train]
    labels = [p["target"]["decision"] for p in train]
    best = None
    for threshold in sorted({0, max(lengths) + 1, *lengths}):
        for direction in ("ge", "lt"):
            predictions = ["PAUSE" if ((n >= threshold) if direction == "ge" else (n < threshold)) else "OPEN" for n in lengths]
            value = score(labels, predictions)["balanced_accuracy"]
            if best is None or value > best[0]:
                best = value, threshold, direction
    return {"threshold_chars": best[1], "stop_when": best[2], "fitted_on": "train",
            "training_balanced_accuracy": best[0], "text": "situation", "units": "unicode_code_points"}


def predict(rows: list[dict], length_rule: dict) -> dict[str, list[str]]:
    threshold, direction = length_rule["threshold_chars"], length_rule["stop_when"]
    return {
        "always-stop": ["PAUSE"] * len(rows),
        "keyword-stop": ["PAUSE" if KEYWORD_RE.search(p["situation"]) else "OPEN" for p in rows],
        "length-stop": ["PAUSE" if ((len(p["situation"]) >= threshold) if direction == "ge" else (len(p["situation"]) < threshold)) else "OPEN" for p in rows],
    }


def run_baselines(train: list[dict], heldout: list[dict]) -> dict:
    rule = fit_length(train)
    predictions = predict(heldout, rule)
    labels = [p["target"]["decision"] for p in heldout]
    results = {}
    for name, decisions in predictions.items():
        results[name] = {"scores": score(labels, decisions), "predictions": [
            {"pair_id": pair["pair_id"], "expected": label, "predicted": decision}
            for pair, label, decision in zip(heldout, labels, decisions)
        ]}
    return {"statistic": "balanced_accuracy_open_vs_stop", "length_rule": rule, "baselines": results}
