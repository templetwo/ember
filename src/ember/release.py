"""Offline candidate screening. No record retrieval and no release approval."""
from __future__ import annotations

import re
from pathlib import Path

from .validation import (ROOT, InvalidCorpus, digest, json_loads, parse_jsonl,
                         read_bound_file, validate_schema)

# Shape vocabulary from the mirror's 2026-10-22 credential scanner. Its released
# grant-id class is still a finding here: mirror release is not corpus release.
# No line-wide suppressions: a harmless token_id must not hide a real secret.
SHAPES = {
    "bridge-bearer": r"\bsvs_[A-Za-z0-9_-]{16,}",
    "connector-refresh": r"\bcbr_[A-Za-z0-9_-]{20,}",
    "openai-key": r"\bsk-[A-Za-z0-9_-]{20,}",
    "github-classic": r"\bgh[pousr]_[A-Za-z0-9]{30,}",
    "github-fine-grained": r"\bgithub_pat_[A-Za-z0-9_]{30,}",
    "slack-token": r"\bxox[abprs]-[A-Za-z0-9-]{10,}",
    "aws-key-id": r"\bAKIA[0-9A-Z]{16}\b",
    "xai-key": r"\bxai-[A-Za-z0-9]{20,}",
    "google-key": r"\bAIza[0-9A-Za-z_-]{30,}",
    "anthropic-key": r"\bsk-ant-[A-Za-z0-9_-]{20,}",
    "bearer-header": r"(?i)\bBearer\s+[A-Za-z0-9._~+/=-]{20,}",
    "auth-header": r"(?i)\bAuthorization:\s*\S{20,}",
    "private-key-block": r"-----BEGIN [A-Z ]*PRIVATE KEY-----",
    "jwt": r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}",
    "secret-assignment": r"(?i)\b(?:api[_-]?key|secret|password|passwd|token)\s*[=:]\s*['\"]?[A-Za-z0-9_\-/+.]{16,}",
    "urlsafe-43": r"(?<![A-Za-z0-9_-])[A-Za-z0-9_-]{43}(?![A-Za-z0-9_-])",
    "grant-id": r"\b(?i:token|token_id|arrival|grant)\s+[0-9a-f]{12}\b|\barq_[A-Za-z0-9_-]{20,}",
}
PATTERNS = {name: re.compile(pattern) for name, pattern in SHAPES.items()}
MAX_ESCAPE_LEVELS = 8
MAX_FILE_BYTES = 16 * 1024 * 1024
MAX_NEEDLES = 1024
_ESCAPE = re.compile(r"\\(?:u([dD][89abAB][0-9a-fA-F]{2})\\u([dD][c-fC-F][0-9a-fA-F]{2})|u([0-9a-fA-F]{4})|x([0-9a-fA-F]{2})|([0-7]{1,3})|([\"'\\/bfnrt]))")
_SIMPLE = {'"': '"', "'": "'", "\\": "\\", "/": "/", "b": "\b", "f": "\f",
           "n": "\n", "r": "\r", "t": "\t"}


def _unescape(text: str) -> str:
    def one(match):
        if match[1]:
            return chr(0x10000 + ((int(match[1], 16) - 0xD800) << 10) + int(match[2], 16) - 0xDC00)
        if match[3] or match[4]:
            return chr(int(match[3] or match[4], 16))
        if match[5]:
            return chr(int(match[5], 8))
        return _SIMPLE[match[6]]
    return _ESCAPE.sub(one, text)


def scan_text(text: str, needles: list[str]) -> tuple[list[str], bool]:
    """Rule names only; unfinished decoding can never produce a clean verdict."""
    hits = set()
    for level in range(MAX_ESCAPE_LEVELS + 1):
        hits.update(name for name, pattern in PATTERNS.items() if pattern.search(text))
        normalized = " ".join(text.split())
        hits.update(f"literal-{i + 1}" for i, needle in enumerate(needles) if needle in normalized)
        decoded = _unescape(text)
        if decoded == text:
            return sorted(hits), True
        if level == MAX_ESCAPE_LEVELS:
            return sorted(hits), False
        text = decoded
    raise AssertionError("unreachable")


def controls() -> int:
    """Synthetic matcher controls; never corpus rows and never printed."""
    values = {
        "bridge-bearer": "svs_" + "a" * 20,
        "connector-refresh": "cbr_" + "a" * 24,
        "openai-key": "sk-" + "a" * 24,
        "github-classic": "ghp_" + "a" * 32,
        "github-fine-grained": "github_pat_" + "a" * 32,
        "slack-token": "xoxb-" + "a" * 16,
        "aws-key-id": "AKIA" + "A" * 16,
        "xai-key": "xai-" + "a" * 24,
        "google-key": "AIza" + "a" * 32,
        "anthropic-key": "sk-ant-" + "a" * 24,
        "bearer-header": "Bearer " + "a" * 24,
        "auth-header": "Authorization: " + "a" * 24,
        "private-key-block": "-----BEGIN " + "RSA PRIVATE KEY-----",
        "jwt": "eyJ" + "a" * 12 + "." + "a" * 12 + "." + "a" * 12,
        "secret-assignment": "password = " + "a" * 20,
        "urlsafe-43": "a" * 43,
        "grant-id": "Grant " + "a" * 12,
    }
    if values.keys() != PATTERNS.keys():
        raise InvalidCorpus("candidate scanner control coverage mismatch")
    variants = {
        "bridge-bearer": "svs_" + "bZ09_-" * 4,
        "connector-refresh": "cbr_" + "bZ09_-" * 4,
        "openai-key": "sk-" + "bZ09_-" * 4,
        "github-classic": "ghr_" + "bZ09" * 8,
        "github-fine-grained": "github_pat_" + "bZ09_" * 7,
        "slack-token": "xoxp-" + "bZ09-" * 4,
        "aws-key-id": "AKIA" + "B09Z" * 4,
        "xai-key": "xai-" + "bZ09" * 6,
        "google-key": "AIza" + "bZ09_-" * 6,
        "anthropic-key": "sk-ant-" + "bZ09_-" * 4,
        "bearer-header": "bEaReR " + "bZ09._~+/=-" * 3,
        "auth-header": "aUtHoRiZaTiOn: " + "bZ09./_-" * 3,
        "private-key-block": "-----BEGIN " + "EC PRIVATE KEY-----",
        "jwt": "eyJ" + "bZ09_-" * 2 + "." + "bZ09_-" * 2 + "." + "bZ09_-" * 2,
        "secret-assignment": "API_KEY: '" + "bZ09_-/+." * 3,
        "urlsafe-43": "bZ09_-" * 7 + "b",
        "grant-id": "arq_" + "bZ09_-" * 4,
    }
    for name, value in values.items():
        for example in (value, variants[name]):
            hits, complete = scan_text(example, [])
            if name not in hits or not complete:
                raise InvalidCorpus("candidate scanner positive control failed")
    for clean in ("", "Ordinary review prose without credentials.", "svs_short", "Grant abc", "Bearer short"):
        hits, complete = scan_text(clean, [])
        if hits or not complete:
            raise InvalidCorpus("candidate scanner negative control failed")
    return len(values)


def _bound(base: Path, spec: dict) -> bytes:
    return read_bound_file(base, spec, max_bytes=MAX_FILE_BYTES)


def scan_candidate(path: Path) -> dict:
    checked = controls()
    with path.open("rb") as stream:
        raw = stream.read(MAX_FILE_BYTES + 1)
    if len(raw) > MAX_FILE_BYTES:
        raise InvalidCorpus("candidate descriptor exceeds scan limit")
    candidate = json_loads(raw)
    validate_schema("candidate", candidate)
    base = path.parent
    exclusions = digest((ROOT / "docs/corpus-exclusions.md").read_bytes())
    if candidate["exclusions_sha256"] != exclusions:
        raise InvalidCorpus("candidate exclusions hash mismatch")
    policy = json_loads(_bound(base, candidate["policy"]))
    if not isinstance(policy, dict) or policy.get("scope") != "private-training":
        raise InvalidCorpus("candidate policy must declare private-training scope")
    needles = json_loads(_bound(base, candidate["needles"]))
    if (not isinstance(needles, list) or len(needles) > MAX_NEEDLES
            or any(not isinstance(n, str) or not n.strip() for n in needles)):
        raise InvalidCorpus("candidate needles must be a bounded list of nonblank strings")
    needles = [" ".join(n.split()) for n in needles]
    for needle in needles:
        hits, complete = scan_text(needle, [needle])
        if "literal-1" not in hits or not complete:
            raise InvalidCorpus("candidate literal control failed")
    findings, counts, hashes = {}, {}, {}
    for split, spec in candidate["corpus"].items():
        # Scan filename first: token-named files are not opened.
        path_hits, complete = scan_text(spec["path"], [])
        if path_hits or not complete:
            raise InvalidCorpus("candidate filename requires review; file not opened")
        data = _bound(base, spec)
        rows = parse_jsonl(data)
        if any(not isinstance(row, dict) or not row for row in rows):
            raise InvalidCorpus("candidate rows must be nonempty JSON objects")
        counts[split] = len(rows)
        hashes[split] = digest(data)
        hits, complete = scan_text(data.decode("utf-8"), needles)
        findings[split] = {"rules": hits, "complete": complete}
    complete = all(item["complete"] for item in findings.values())
    status = "incomplete" if not complete else "blocked" if any(item["rules"] for item in findings.values()) else "clear"
    return {
        "schema_version": "0.1", "run_kind": "p0-candidate-scan", "scope": "private-training",
        "status": status, "release_review": "pending", "candidate_sha256": digest(raw),
        "corpus_sha256": hashes, "policy_sha256": candidate["policy"]["sha256"],
        "needles_sha256": candidate["needles"]["sha256"], "exclusions_sha256": exclusions,
        "reader": candidate["reader"], "row_counts": counts, "findings": findings,
        "controls": {"credential_shapes": checked, "literal_needles": len(needles)},
        "limits": {"file_bytes": MAX_FILE_BYTES, "escape_levels": MAX_ESCAPE_LEVELS},
        "limitations": [
            "Clear means no configured literal or credential-shape match, not release approval.",
            "Policy bytes are bound; only their scope is interpreted by this scanner.",
            "No source retrieval, drawer lookup, name replacement, or corpus rewriting occurs.",
            "Source eligibility, letters, semantic review, time cut, and split validation remain separate.",
        ],
    }
