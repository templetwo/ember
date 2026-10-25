"""Validate reviewed pairs and manifest-bound inputs, without retrieving records."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker
from referencing import Registry, Resource

SCHEMAS = Path(__file__).parent / "schemas"
ROOT = Path(__file__).resolve().parents[2]


class InvalidCorpus(ValueError):
    """An input is unsuitable for a reproducible P0 run."""


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def json_loads(data: str | bytes):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise InvalidCorpus("duplicate JSON key")
            result[key] = value
        return result

    def nonfinite(_):
        raise InvalidCorpus("non-finite JSON number")

    return json.loads(data, object_pairs_hook=unique, parse_constant=nonfinite)


def validator(name: str) -> Draft202012Validator:
    resources = []
    for path in SCHEMAS.glob("*.schema.json"):
        schema = json_loads(path.read_bytes())
        Draft202012Validator.check_schema(schema)
        resources.append((schema["$id"], Resource.from_contents(schema)))
    registry = Registry().with_resources(resources)
    schema = json_loads((SCHEMAS / f"{name}.schema.json").read_bytes())
    # Registry has no network retriever. Unknown references fail closed.
    return Draft202012Validator(schema, registry=registry, format_checker=FormatChecker())


def validate_schema(name: str, value):
    errors = sorted(validator(name).iter_errors(value), key=lambda e: str(list(e.path)))
    if errors:
        # Do not echo private row values in CLI errors.
        raise InvalidCorpus(f"{name} schema violation at {list(errors[0].path)}")


def timestamp(value: str) -> datetime:
    result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if result.tzinfo is None:
        raise InvalidCorpus("timestamps need an explicit timezone")
    return result


def validate_decision(decision: dict, evidence: list[dict]):
    validate_schema("decision", decision)
    present = {item["claim_id"] for item in evidence}
    if not set(decision["cited_claim_ids"]).issubset(present):
        raise InvalidCorpus("cited claim is absent from evidence window")


def validate_pair(pair: dict, evidence_max_chars: int):
    validate_schema("pair", pair)
    evidence = pair["evidence"]
    ids = [item["claim_id"] for item in evidence]
    if len(ids) != len(set(ids)):
        raise InvalidCorpus("duplicate evidence claim id")
    if pair["review"]["label_source_claim_id"] in ids:
        raise InvalidCorpus("label source must stay outside the pre-decision evidence")
    if not set(pair["source_claim_ids"]).issubset(ids):
        raise InvalidCorpus("pair source claim is absent from evidence window")
    if not pair["target"]["cited_claim_ids"]:
        raise InvalidCorpus("every training target needs its record receipt")
    validate_decision(pair["target"], evidence)
    if len(render_evidence(evidence)) > evidence_max_chars:
        raise InvalidCorpus("evidence exceeds budget; silent clipping is forbidden")
    if any(timestamp(item["recorded_at"]) > timestamp(pair["recorded_at"]) for item in evidence):
        raise InvalidCorpus("evidence postdates the pair's recorded decision")


def render_evidence(evidence: list[dict]) -> str:
    """Use already reviewed query windows. This function never selects or clips them."""
    return "\n\n".join(f"[{e['claim_id']}] {e['recorded_at']}\n{e['text']}" for e in evidence)


def linked_claim_ids(pair: dict) -> set[str]:
    """Split exclusions include later label provenance without rendering it."""
    return {e["claim_id"] for e in pair["evidence"]} | {pair["review"]["label_source_claim_id"]}


def read_bound_file(base: Path, spec: dict, max_bytes: int | None = None) -> bytes:
    relative = Path(spec["path"])
    if relative.is_absolute() or ".." in relative.parts:
        raise InvalidCorpus("manifest paths must stay below its directory")
    base = base.resolve()
    path = (base / relative).resolve()
    if not path.is_relative_to(base):
        raise InvalidCorpus("manifest file escapes its directory")
    with path.open("rb") as stream:
        data = stream.read() if max_bytes is None else stream.read(max_bytes + 1)
    if max_bytes is not None and len(data) > max_bytes:
        raise InvalidCorpus("bound file exceeds scan limit")
    if digest(data) != spec["sha256"]:
        raise InvalidCorpus("manifest file hash mismatch")
    return data


def parse_jsonl(data: bytes) -> list[dict]:
    if not data.strip():
        raise InvalidCorpus("empty dataset")
    rows = []
    for line in data.decode("utf-8").splitlines():
        if not line.strip():
            raise InvalidCorpus("blank dataset row")
        rows.append(json_loads(line))
    return rows


def validate_split(train: list[dict], heldout: list[dict], freeze_at: str, evidence_max_chars: int,
                   robot_stop_claim_ids=()):
    if not train or not heldout:
        raise InvalidCorpus("both train and heldout must be nonempty")
    cut = timestamp(freeze_at)
    reserved = set(robot_stop_claim_ids)
    all_ids = set()
    claim_sets = []
    input_sets = []
    for split, rows in (("train", train), ("heldout", heldout)):
        claims, inputs = set(), set()
        for pair in rows:
            validate_pair(pair, evidence_max_chars)
            if pair["pair_class"] != "observed-stop":
                raise InvalidCorpus("first cut admits observed-stop pairs only")
            if pair["pair_id"] in all_ids:
                raise InvalidCorpus("duplicate pair id")
            all_ids.add(pair["pair_id"])
            robot = pair["holdout"] == "robot_stop"
            linked_ids = linked_claim_ids(pair)
            if reserved & linked_ids and (split == "train" or not robot):
                raise InvalidCorpus("reserved robot stop must be explicitly held out")
            if robot and not reserved.intersection(linked_ids):
                raise InvalidCorpus("robot stop is absent from the reserved claim list")
            before = timestamp(pair["recorded_at"]) < cut
            if split == "train" and (robot or not before):
                raise InvalidCorpus("held-out event in training split")
            if split == "heldout" and before and not robot:
                raise InvalidCorpus("pre-cut event in temporal heldout")
            claims.update(linked_ids)
            inputs.add(" ".join(pair["situation"].casefold().split()))
        claim_sets.append(claims)
        input_sets.append(inputs)
    if claim_sets[0] & claim_sets[1]:
        raise InvalidCorpus("claim/evidence overlap across splits")
    if not reserved.issubset(claim_sets[1]):
        raise InvalidCorpus("reserved robot stop is missing from heldout")
    if input_sets[0] & input_sets[1]:
        raise InvalidCorpus("duplicate situation across splits")
    labels = [p["target"]["decision"] for p in train]
    for label in validator("decision").schema["properties"]["decision"]["enum"]:
        if labels.count(label) * 4 < len(labels):
            raise InvalidCorpus("training decision class is below one quarter")
    # Both classes are necessary for a defined balanced-accuracy denominator.
    for rows in (train, heldout):
        classes = {p["target"]["decision"] == "OPEN" for p in rows}
        if len(classes) != 2:
            raise InvalidCorpus("OPEN and stop labels are both required in each split")


def load_manifest(path: Path):
    manifest_bytes = path.read_bytes()
    manifest = json_loads(manifest_bytes)
    validate_schema("manifest", manifest)
    base = path.parent
    review = manifest["release_review"]
    exclusions = (ROOT / "docs/corpus-exclusions.md").read_bytes()
    if digest(exclusions) != review["exclusions_sha256"]:
        raise InvalidCorpus("exclusions block hash mismatch; recut instead of patching")
    policy = read_bound_file(base, review["policy"])
    receipt = json_loads(read_bound_file(base, review["receipt"]))
    expected = {name: item["sha256"] for name, item in manifest["corpus"].items()}
    if (receipt.get("status") != "passed" or receipt.get("corpus_sha256") != expected
            or receipt.get("policy_sha256") != digest(policy)
            or receipt.get("exclusions_sha256") != digest(exclusions)
            or receipt.get("reader") != review["reader"]):
        raise InvalidCorpus("release receipt does not bind this corpus, policy, exclusions, and reader")
    rows = {name: parse_jsonl(read_bound_file(base, item)) for name, item in manifest["corpus"].items()}
    validate_split(rows["train"], rows["heldout"], manifest["freeze_at"], manifest["constraints"]["evidence_max_chars"], manifest["robot_stop_claim_ids"])
    return manifest, rows, digest(manifest_bytes)
