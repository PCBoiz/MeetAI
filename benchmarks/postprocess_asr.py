"""Derive RTF and per-class error tables from a finished ASR results file. S2.2.

Post-processing rather than re-running, for two reasons that are both about not
spending GPU time to recover a number that is already on disk:

- **RTF.** The clean FLEURS pass recorded ``wall_s`` per clip but reported
  ``rtf: null``, because it loaded its modules before the duration fix and
  stdlib :mod:`wave` cannot read FLEURS' 32-bit float WAV. The durations are in
  FLEURS' own TSV as ``num_samples``, so RTF is recoverable exactly.
- **Per-class tables.** The pass stored each hypothesis, and the references are
  in the TSV, so classes can be tagged and attributed without transcribing
  anything again.

Reads only. Writes a derived JSON next to the input, under ``var/`` which is
git-ignored. Prints ASCII: clip ids, counts and rates, never reference or
hypothesis text.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import statistics
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

from refusals import missing_artifact
from scoring import (
    EMPTY,
    Counts,
    TokenClass,
    bootstrap_syer,
    character_counts,
    fold_diacritics,
    score_classes,
    score_failed_utterance,
    score_utterance,
    syllables,
)


def load_tsv(path: pathlib.Path) -> dict[str, tuple[str, float]]:
    """``file_name -> (raw_transcription, duration_seconds)``.

    Column indices are explicit because the TSV has seven columns and no
    header, and column 4 is a character-level string the dataset loader
    discards - indexing from the end would silently pick it up.
    """
    out: dict[str, tuple[str, float]] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        parts = line.split("\t")
        if len(parts) != 7:
            continue
        try:
            duration = int(parts[5]) / 16000.0
        except ValueError:
            continue
        out[parts[1]] = (parts[2], duration)
    return out


def percentile(values: list[float], fraction: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, int(fraction * (len(ordered) - 1)))]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--results", required=True, type=pathlib.Path)
    parser.add_argument("--tsv", required=True, type=pathlib.Path)
    parser.add_argument("--manifest", required=True, type=pathlib.Path)
    args = parser.parse_args()

    # The role, not the path: this message is quoted into reports, and the
    # loop never said which of the three was missing anyway.
    for role, path in (
        ("results-json", args.results),
        ("reference-tsv", args.tsv),
        ("manifest", args.manifest),
    ):
        if not path.is_file():
            print(missing_artifact(role), file=sys.stderr)
            return 2

    payload = json.loads(args.results.read_text(encoding="utf-8"))
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    tsv = load_tsv(args.tsv)
    by_file = {c["id"]: c["file"] for c in manifest["clips"]}

    pooled = EMPTY
    pooled_char = EMPTY
    pooled_folded = EMPTY
    per_utterance: list[Counts] = []
    rtfs: list[float] = []
    walls: list[float] = []
    durations: list[float] = []
    class_acc: dict[TokenClass, dict[str, int]] = {
        cls: {"N": 0, "S": 0, "D": 0, "I": 0, "boundary_I": 0} for cls in TokenClass
    }
    failures: dict[str, int] = {}
    missing_duration = 0
    missing_reference = 0
    scored = 0

    for clip in payload["clips"]:
        if clip.get("non_speech"):
            continue
        name = by_file.get(clip["id"])
        if name is None or name not in tsv:
            missing_reference += 1
            continue
        reference, duration = tsv[name]
        hypothesis = clip.get("hypothesis", "")
        failed = bool(clip.get("timed_out")) or clip.get("returncode") != 0

        if failed or not syllables(hypothesis):
            counts = score_failed_utterance(reference)
            kind = (
                "timeout"
                if clip.get("timed_out")
                else ("nonzero_exit" if failed else "empty_output")
            )
            failures[kind] = failures.get(kind, 0) + 1
        else:
            counts, _ = score_utterance(reference, hypothesis)
            for cls, result in score_classes(reference, hypothesis).items():
                acc = class_acc[cls]
                acc["N"] += result.ref_tokens
                acc["S"] += result.substitutions
                acc["D"] += result.deletions
                acc["I"] += result.insertions_interior
                acc["boundary_I"] += result.boundary_ambiguous_insertions

        pooled = pooled.plus(counts)
        pooled_char = pooled_char.plus(character_counts(reference, hypothesis))
        pooled_folded = pooled_folded.plus(
            score_utterance(fold_diacritics(reference), fold_diacritics(hypothesis))[0]
        )
        per_utterance.append(counts)
        scored += 1

        wall = clip.get("wall_s")
        if duration > 0 and isinstance(wall, (int, float)):
            rtfs.append(float(wall) / duration)
            walls.append(float(wall))
            durations.append(duration)
        else:
            missing_duration += 1

    interval = bootstrap_syer(
        per_utterance,
        blocks=["fleurs_vi_dev"] * len(per_utterance),
        replicates=2000,
        seed=7,
    )
    interval_utt = bootstrap_syer(per_utterance, replicates=2000, seed=7)

    derived = {
        "source_results": args.results.name,
        "source_tsv": args.tsv.name,
        "dataset_revision": manifest.get("dataset_revision"),
        "license": manifest.get("license"),
        "license_branch": manifest.get("license_branch"),
        "model": payload["summary"]["model"],
        "scoring_contract": payload["summary"]["scoring_contract"],
        "denominators": {
            "clips_in_manifest": len(manifest["clips"]),
            "clips_in_results": len(payload["clips"]),
            "clips_scored": scored,
            "clips_missing_reference": missing_reference,
            "clips_missing_duration": missing_duration,
            "ref_tokens": pooled.ref_tokens,
            "audio_seconds": round(sum(durations), 1),
        },
        "headline": {
            "S": pooled.substitutions,
            "D": pooled.deletions,
            "I": pooled.insertions,
            "N": pooled.ref_tokens,
            "syer": pooled.syer,
            "ier": pooled.insertion_rate,
            "cer": pooled_char.syer,
            "syer_folded_diagnostic_only": pooled_folded.syer,
            "folded_gap_pp": (
                (pooled.syer - pooled_folded.syer) * 100
                if pooled.syer is not None and pooled_folded.syer is not None
                else None
            ),
            "ci95_bootstrap_block_recording": interval,
            "ci95_bootstrap_per_utterance": interval_utt,
            "bootstrap_seed": 7,
            "bootstrap_replicates": 2000,
        },
        "failures": failures,
        "rtf": {
            "n": len(rtfs),
            # Aggregate RTF is the RATIO OF TOTALS, for the same reason SyER is
            # a micro-average: the mean of per-clip ratios over-weights short
            # clips, whose fixed per-clip model load is a larger share of their
            # wall time. Both are reported because they differ measurably here
            # (0.315 vs 0.346) and quoting one as "the" RTF would hide which
            # question was answered.
            "aggregate_total_wall_over_total_audio": (
                sum(walls) / sum(durations) if durations else None
            ),
            "mean_of_per_clip_ratios": statistics.fmean(rtfs) if rtfs else None,
            "p50": percentile(rtfs, 0.50),
            "p95": percentile(rtfs, 0.95),
            "min": min(rtfs) if rtfs else None,
            "max": max(rtfs) if rtfs else None,
            "note": (
                "Wall time per clip divided by clip duration. Includes model "
                "load every clip, because the harness invokes whisper-cli once "
                "per clip - that is the sequential cost, not a steady-state "
                "streaming figure."
            ),
        },
        "wall_s": {
            "n": len(walls),
            "p50": percentile(walls, 0.50),
            "p95": percentile(walls, 0.95),
            "total": round(sum(walls), 1),
        },
        "per_class": {
            cls.value: {
                **class_acc[cls],
                "rate": (
                    (class_acc[cls]["S"] + class_acc[cls]["D"] + class_acc[cls]["I"])
                    / class_acc[cls]["N"]
                    if class_acc[cls]["N"]
                    else None
                ),
            }
            for cls in TokenClass
        },
        "limits": [
            "SyER is syllable-level (whitespace tokens). Vietnamese writes "
            "syllables separated by spaces, so a token is a syllable not a word.",
            "Headline is NFC, case-sensitive, punctuation-to-space, NO diacritic "
            "folding. The folded figure is a diagnostic; the gap is the "
            "diacritic-plus-case error mass.",
            "The proper_noun class is a CAPITALISATION HEURISTIC, not annotation. "
            "Vietnamese given names are ordinary common nouns, and index 0 is "
            "never tagged, so this denominator under-counts real names.",
            "CI is a bootstrap over utterances. FLEURS dev is one corpus so the "
            "block variant collapses to a single block and is NOT a "
            "between-recording interval.",
            "RTF includes per-clip model load. It is a sequential-invocation "
            "figure, not a streaming one.",
            "FLEURS is read speech, one speaker per clip, no overlapping speech. "
            "It cannot evidence the 'noi chong' axis of spec B-1, and accent "
            "coverage is narrow.",
        ],
    }

    target = args.results.with_name(args.results.stem + "-derived.json")
    target.write_text(json.dumps(derived, indent=2, ensure_ascii=True), encoding="utf-8")
    print(json.dumps(derived, indent=2, ensure_ascii=True))
    print(f"\nwritten: {target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
