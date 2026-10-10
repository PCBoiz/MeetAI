"""Re-score a finished S2.3 run from its saved generations.

The model's output is the expensive part and the scoring is the part that gets
corrected, so the two are separable on purpose. This reads the per-case
generations the harness wrote and recomputes every metric, leaving the
measured latency, memory and environment rows exactly as they were.

Why it exists rather than re-running: the first run scored two correct
refusals as authority violations, because the forbidden-shape check matched
"cam ket" inside "khong co cam ket nao". That is a scoring defect. Re-running
the model would also have changed the generations - same seed or not, a
re-measured wall clock and a re-sampled GPU trace are different data - and
then the corrected number could not be compared with the original. Re-scoring
changes exactly one thing.

The output artifact records that it is derived, which artifact it came from,
and the scorer version, so a derived table is never mistaken for a measurement.
"""

from __future__ import annotations

import argparse
import hashlib
import inspect
import json
import pathlib
from dataclasses import asdict

from benchmarks import policy_scoring
from benchmarks.policy_scoring import (
    FORBIDDEN_FIELD_SHAPES,
    HARNESS_CONFIDENCE,
    REQUIRED_KEYS,
    VALID_DECISIONS,
    CaseResult,
    FailureKind,
    parse_response,
    score_case,
    summarise,
)
from tests.corpus.llm_policy_vi import CORPUS

from meetai.response import SpeechAct


def scorer_fingerprint() -> str:
    """SHA-256 of the scoring module's source.

    Cheap and exact. A derived table that says which scorer produced it can be
    regenerated; one that says "the current scorer" cannot.
    """
    return hashlib.sha256(inspect.getsource(policy_scoring).encode("utf-8")).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact", default="var/bench/llm-policy-s23.json")
    parser.add_argument("--generations", default="var/probe/llm-policy")
    parser.add_argument("--out", default="var/bench/llm-policy-s23-rescored.json")
    args = parser.parse_args()

    source = pathlib.Path(args.artifact)
    original = json.loads(source.read_text(encoding="utf-8"))
    generations = pathlib.Path(args.generations)

    by_id = {case.case_id: case for case in CORPUS.cases}
    previous = {entry["case_id"]: entry for entry in original["cases"]}

    results: list[CaseResult] = []
    changed: list[str] = []
    missing: list[str] = []

    for case_id, entry in previous.items():
        case = by_id.get(case_id)
        if case is None:
            missing.append(case_id)
            continue
        path = generations / f"{case_id}.out.txt"
        if not path.is_file():
            missing.append(case_id)
            continue
        # The recorded failure kind is preserved: it describes what the
        # process did, which re-scoring cannot observe and must not invent.
        recorded = next(kind for kind in FailureKind if kind.value == entry["failure"])
        parsed = parse_response(path.read_text(encoding="utf-8"), failure=recorded)
        result = score_case(case, parsed)
        results.append(result)

        before = {
            "structural": tuple(entry["structural"]),
            "grounding": tuple(entry["grounding"]),
            "abstention": tuple(entry["abstention"]),
            "authority": tuple(entry["authority"]),
            "injection": tuple(entry["injection"]),
        }
        after = {
            "structural": result.structural,
            "grounding": result.grounding,
            "abstention": result.abstention,
            "authority": result.authority,
            "injection": result.injection,
        }
        if before != after:
            changed.append(case_id)
            for axis in sorted(before):
                if before[axis] != after[axis]:
                    print(f"  {case_id:18} {axis:11} {list(before[axis])}")
                    print(f"  {'':18} {'->':11} {list(after[axis])}")

    if missing:
        print(f"CANH BAO: thieu generation cho {len(missing)} case: {missing}")

    metrics = summarise(results)
    derived = {
        **{
            key: value
            for key, value in original.items()
            if key not in {"metrics", "cases", "scoring"}
        },
        "derived_from": str(source).replace("\\", "/"),
        "derived": True,
        "derivation_note": (
            "Metrics recomputed from the saved generations of the run named "
            "in derived_from. Latency, memory and environment rows are "
            "carried over unchanged - they were measured there, not here."
        ),
        "scoring": {
            "scorer_sha256": scorer_fingerprint(),
            "harness_confidence": HARNESS_CONFIDENCE,
            "required_keys": sorted(REQUIRED_KEYS),
            "valid_decisions": sorted(VALID_DECISIONS),
            "valid_intents": sorted(act.value for act in SpeechAct),
            "forbidden_field_shapes": list(FORBIDDEN_FIELD_SHAPES),
            "authority_source": "meetai.authority.evaluate_response",
            "llm_judge_used": False,
            "grammar_used": False,
            "model_confidence_collected": False,
        },
        "rescore": {
            "cases_rescored": len(results),
            "cases_changed": changed,
            "cases_missing_generation": missing,
        },
        "metrics": {
            name: {
                "hits": metric.hits,
                "denominator": metric.denominator,
                "rate": metric.rate,
            }
            for name, metric in metrics.items()
        },
        "cases": [
            {
                **{
                    key: value
                    for key, value in asdict(result).items()
                    if key != "failure"
                },
                "failure": result.failure.value,
                "wall_s": previous[result.case_id]["wall_s"],
                "returncode": previous[result.case_id]["returncode"],
                "generation_chars": previous[result.case_id]["generation_chars"],
                "llama_prompt_tps": previous[result.case_id]["llama_prompt_tps"],
                "llama_gen_tps": previous[result.case_id]["llama_gen_tps"],
            }
            for result in results
        ],
    }

    out = pathlib.Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(derived, indent=2, ensure_ascii=False), encoding="utf-8")

    print("")
    print(f"rescored {len(results)} case, {len(changed)} case doi ket qua")
    print("--- per-axis rates, each with its own denominator ---")
    original_metrics = original.get("metrics", {})
    for name, metric in metrics.items():
        rate = "n/a" if metric.rate is None else f"{metric.rate * 100:5.1f}%"
        was = original_metrics.get(name, {})
        delta = ""
        if was and was.get("hits") != metric.hits:
            delta = f"  (truoc: {was['hits']}/{was['denominator']})"
        print(f"  {name:22} {metric.hits:3}/{metric.denominator:<3} {rate}{delta}")
    print(f"artifact: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
