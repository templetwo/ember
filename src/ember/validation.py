"""Validate reviewed pairs and manifest-bound inputs, without retrieving records."""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

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


def eastern_day_floor(event_date: str) -> datetime:
    return datetime.fromisoformat(event_date).replace(tzinfo=ZoneInfo("America/New_York")).astimezone(timezone.utc)


def validate_decision(decision: dict, evidence: list[dict]):
    validate_schema("decision", decision)
    present = {normalize_claim_id(item["claim_id"]) for item in evidence}
    if not {normalize_claim_id(cid) for cid in decision["cited_claim_ids"]}.issubset(present):
        raise InvalidCorpus("cited claim is absent from evidence window")


def normalize_claim_id(value: str) -> str:
    """Comparison form only; never rewrite reviewed row bytes."""
    normalized = "".join(value.split()).casefold()
    if not normalized:
        raise InvalidCorpus("claim id is blank after normalization")
    return normalized


def reject_review_reference(pair: dict, claim_id: str, role: str):
    label = normalize_claim_id(claim_id)
    # Every >=12-character prefix includes the first 12 characters. Search
    # substrings without a word boundary, including longer rendered identifiers.
    needles = [label]
    if re.fullmatch(r"[0-9a-f]{12,}", label):
        needles.append(label[:12])
    texts = [pair["situation"], pair["target"]["rationale"]]
    texts.extend(e["text"] for e in pair["evidence"])
    texts.extend(e["claim_id"] for e in pair["evidence"])
    texts.extend(pair["source_claim_ids"])
    texts.extend(pair["target"]["cited_claim_ids"])
    if any(needle in "".join(text.split()).casefold() for text in texts for needle in needles):
        raise InvalidCorpus(f"{role} reference appears in model-facing content")


def reject_label_reference(pair: dict):
    reject_review_reference(pair, pair["review"]["label_source_claim_id"], "label source")


def decision_flags(pair: dict) -> list[str]:
    """Derive disagreements; an author cannot clear them with a class label."""
    act_stop = pair["review"]["observed_act"] == "stop"
    target_stop = pair["target"]["decision"] != "OPEN"
    if act_stop and not target_stop:
        return ["over-stop"]
    if target_stop and not act_stop:
        return ["hindsight-stop"]
    return []


def validate_pair(pair: dict, evidence_max_chars: int):
    validate_schema("pair", pair)
    evidence = pair["evidence"]
    ids = [normalize_claim_id(item["claim_id"]) for item in evidence]
    if len(ids) != len(set(ids)):
        raise InvalidCorpus("duplicate evidence claim id")
    if normalize_claim_id(pair["review"]["label_source_claim_id"]) in ids:
        raise InvalidCorpus("label source must stay outside the pre-decision evidence")
    reject_label_reference(pair)
    if pair["recorded_at_precision"] == "clock":
        proof = pair["review"]["decision_claim_id"]
        if normalize_claim_id(proof) in ids:
            raise InvalidCorpus("clock decision record must stay outside the evidence")
        reject_review_reference(pair, proof, "clock decision")
    if pair["pair_class"] == "observed-decision" and decision_flags(pair):
        raise InvalidCorpus("observed act disagrees with the target decision")
    if not {normalize_claim_id(cid) for cid in pair["source_claim_ids"]}.issubset(ids):
        raise InvalidCorpus("pair source claim is absent from evidence window")
    if not pair["target"]["cited_claim_ids"]:
        raise InvalidCorpus("every training target needs its record receipt")
    validate_decision(pair["target"], evidence)
    if len(render_evidence(evidence)) > evidence_max_chars:
        raise InvalidCorpus("evidence exceeds budget; silent clipping is forbidden")
    decision = timestamp(pair["recorded_at"])
    precision = pair["recorded_at_precision"]
    if precision == "clock":
        if normalize_claim_id(pair["review"]["decision_claim_id"]) == normalize_claim_id(pair["review"]["label_source_claim_id"]):
            raise InvalidCorpus("label source cannot be the clock decision proof")
        for zone in (timezone.utc, ZoneInfo("America/New_York")):
            local = decision.astimezone(zone)
            if (local.hour, local.minute, local.second, local.microsecond) == (0, 0, 0, 0):
                raise InvalidCorpus("clock precision cannot assert an exact UTC or Eastern midnight")
    if precision == "day":
        if decision != eastern_day_floor(pair["review"]["event_date"]):
            raise InvalidCorpus("day precision must use the resolved Eastern event-date midnight")
        if any(timestamp(item["recorded_at"]) >= decision for item in evidence):
            raise InvalidCorpus("day precision requires evidence strictly before the lower bound")
    if precision == "bounded-by-records":
        bounds = pair["review"]["decision_time_bounds"]
        ids = [normalize_claim_id(bounds[k]) for k in ("start_claim_id", "end_claim_id")]
        if len(set(ids)) != 2 or normalize_claim_id(pair["review"]["label_source_claim_id"]) in ids:
            raise InvalidCorpus("decision window needs two distinct bounding claims apart from the label")
        if timestamp(bounds["end_at"]) <= decision:
            raise InvalidCorpus("decision window must end after its start")
    if any(timestamp(item["recorded_at"]) > decision for item in evidence):
        raise InvalidCorpus("evidence postdates the pair's recorded decision")


def render_evidence(evidence: list[dict]) -> str:
    """Use already reviewed query windows. This function never selects or clips them."""
    return "\n\n".join(f"[{e['claim_id']}] {e['recorded_at']}\n{e['text']}" for e in evidence)


def linked_claim_ids(pair: dict) -> set[str]:
    """Split exclusions include later label provenance without rendering it."""
    result = {normalize_claim_id(e["claim_id"]) for e in pair["evidence"]} | {normalize_claim_id(pair["review"]["label_source_claim_id"])}
    bounds = pair["review"].get("decision_time_bounds")
    if bounds:
        result.update(normalize_claim_id(bounds[k]) for k in ("start_claim_id", "end_claim_id"))
    result.update(normalize_claim_id(cid) for cid in pair["review"].get("event_date_claim_ids", []))
    if "decision_claim_id" in pair["review"]:
        result.add(normalize_claim_id(pair["review"]["decision_claim_id"]))
    return result


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
                   robot_stop_claim_ids=(), *, pair_classes=("observed-decision",)):
    if not train or not heldout:
        raise InvalidCorpus("both train and heldout must be nonempty")
    cut = timestamp(freeze_at)
    reserved = {normalize_claim_id(cid) for cid in robot_stop_claim_ids}
    # First-cut policy stays fixed. The actual row-admission test below consumes
    # the manifest value rather than a second hardcoded class comparison.
    if list(pair_classes) != ["observed-decision"]:
        raise InvalidCorpus("first cut must admit observed-decision only")
    admitted_classes = set(pair_classes)
    all_ids = set()
    claim_sets = []
    input_sets = []
    for split, rows in (("train", train), ("heldout", heldout)):
        claims, inputs = set(), set()
        for pair in rows:
            validate_pair(pair, evidence_max_chars)
            decision = timestamp(pair["recorded_at"])
            if pair["recorded_at_precision"] == "day" and abs(
                    (decision.astimezone(ZoneInfo("America/New_York")).date()
                     - cut.astimezone(ZoneInfo("America/New_York")).date()).days) <= 1:
                raise InvalidCorpus("day precision is too close to the freeze day")
            if pair["recorded_at_precision"] == "bounded-by-records" and decision < cut <= timestamp(pair["review"]["decision_time_bounds"]["end_at"]):
                raise InvalidCorpus("decision window crosses the freeze")
            if pair["pair_class"] not in admitted_classes:
                raise InvalidCorpus("pair class is outside the first cut manifest")
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


def validate_source_index(rows: dict, index: dict):
    """Bind reviewed windows to metadata; never retrieve source bodies or names."""
    validate_schema("source_index", index)
    by_row, by_claim = {}, {}
    for item in index["rows"]:
        rid = item["source_row_id"]
        if rid in by_row:
            raise InvalidCorpus("duplicate source row in metadata index")
        by_row[rid] = item
        by_claim.setdefault(normalize_claim_id(item["claim_id"]), []).append(item)

    def checked(item, cid, *, evidence=False):
        if item is None or normalize_claim_id(item["claim_id"]) != normalize_claim_id(cid):
            raise InvalidCorpus("source row and claim do not match the metadata index")
        if item["source_utc"] is None or item["timestamp_basis"] == "unresolved-vault-import" or item["review_holds"]:
            raise InvalidCorpus("source chronology or eligibility remains held")
        screen = item["name_screen"]
        if (screen["status"] not in ("no-person-named", "public-record-only")
                or not screen["reader"].strip() or not screen["receipt"].strip()
                or (screen["status"] == "public-record-only" and not screen["public_record_refs"])):
            raise InvalidCorpus("source name screen is pending or held")
        if evidence and item["seed_backfill"]:
            raise InvalidCorpus("seed backfill cannot supply earlier evidence or a decision bound")
        return timestamp(item["source_utc"])

    for split in rows.values():
        for pair in split:
            validate_schema("pair", pair)
            for e in pair["evidence"]:
                stamp = checked(by_row.get(e["source_row_id"]), e["claim_id"], evidence=True)
                if stamp != timestamp(e["recorded_at"]):
                    raise InvalidCorpus("evidence timestamp differs from the chronology sidecar")
            label = by_row.get(pair["review"]["label_source_row_id"])
            label_filed_at = checked(label, pair["review"]["label_source_claim_id"])
            if pair["recorded_at_precision"] == "clock":
                cid = pair["review"]["decision_claim_id"]
                matches = by_claim.get(normalize_claim_id(cid), [])
                if len(matches) != 1:
                    raise InvalidCorpus("clock decision proof is absent or ambiguous in source index")
                if checked(matches[0], cid, evidence=True) != timestamp(pair["recorded_at"]):
                    raise InvalidCorpus("clock decision differs from resolved source timestamp")
            if pair["recorded_at_precision"] == "day":
                day = label.get("decision_day_review")
                if (not day or not day["reader"].strip() or not day["receipt"].strip()
                        or day["event_date"] != pair["review"]["event_date"]
                        or {normalize_claim_id(cid) for cid in day["claim_ids"]}
                           != {normalize_claim_id(cid) for cid in pair["review"]["event_date_claim_ids"]}):
                    raise InvalidCorpus("Eastern event date lacks its matching source-review receipt")
                if eastern_day_floor(day["event_date"]) > label_filed_at:
                    raise InvalidCorpus("Eastern event date is later than the label filing")
                for cid in day["claim_ids"]:
                    matches = by_claim.get(normalize_claim_id(cid), [])
                    if len(matches) != 1:
                        raise InvalidCorpus("event-date basis is absent or ambiguous")
                    checked(matches[0], cid, evidence=True)
            bounds = pair["review"].get("decision_time_bounds")
            if bounds:
                for key, expected in (("start_claim_id", pair["recorded_at"]), ("end_claim_id", bounds["end_at"])):
                    matches = by_claim.get(normalize_claim_id(bounds[key]), [])
                    if len(matches) != 1:
                        raise InvalidCorpus("decision bound is absent or ambiguous in source index")
                    if checked(matches[0], bounds[key], evidence=True) != timestamp(expected):
                        raise InvalidCorpus("decision bound differs from resolved source timestamp")


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
    source_index_raw = read_bound_file(base, manifest["source_index"])
    expected = {name: item["sha256"] for name, item in manifest["corpus"].items()}
    if (receipt.get("status") != "passed" or receipt.get("corpus_sha256") != expected
            or receipt.get("source_index_sha256") != digest(source_index_raw)
            or receipt.get("policy_sha256") != digest(policy)
            or receipt.get("exclusions_sha256") != digest(exclusions)
            or receipt.get("reader") != review["reader"]):
        raise InvalidCorpus("release receipt does not bind this corpus, source index, policy, exclusions, and reader")
    rows = {name: parse_jsonl(read_bound_file(base, item)) for name, item in manifest["corpus"].items()}
    validate_source_index(rows, json_loads(source_index_raw))
    validate_split(rows["train"], rows["heldout"], manifest["freeze_at"], manifest["constraints"]["evidence_max_chars"],
                   manifest["robot_stop_claim_ids"], pair_classes=manifest["constraints"]["pair_classes"])
    return manifest, rows, digest(manifest_bytes)
