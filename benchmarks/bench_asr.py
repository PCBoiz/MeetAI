"""Run whisper.cpp over a clip manifest and score it. S2.2.

Takes a JSON manifest of clips. A clip whose ``reference`` is the empty string
is **non-speech**: its correct output is nothing at all, so it is scored by
:func:`scoring.non_speech_output_rate` and never pooled into SyER, whose
denominator would be zero.

Three rules this script exists to enforce, each of which is easy to get wrong
in the flattering direction:

**Failures count, with the denominator unchanged.** A timeout, a crash, a
non-zero exit or an empty hypothesis against a non-empty reference scores every
reference token as a deletion - 100% for that utterance. Dropping the clip
instead would improve the number silently, which is the one thing the
acceptance criteria name explicitly.

**Except for non-speech, where empty output is the correct answer.** A blanket
"empty output is a failure" rule would punish correct silence handling and make
the hallucination number unreadable. The asymmetry is keyed on whether the
*reference* is empty, not the hypothesis.

**Terminal output is ASCII and carries no transcript.** whisper.cpp prints the
transcript to stdout and has no flag to stop it, so stdout is always captured
and never passed through. Hypotheses are Vietnamese meeting-shaped text; they
go to a UTF-8 file under ``var/`` which is git-ignored, and the console gets
clip ids and counts.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import subprocess
import sys
import time
import wave

# Two inserts: this directory for the sibling modules, and the repository
# root because `preflight` imports `benchmarks.measure` by package path and
# sys.path[0] is this directory when the file is run as a script.
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
sys.path.insert(1, str(pathlib.Path(__file__).resolve().parent.parent))

from benchmarks.artifacts import artifact_path
from benchmarks.preflight import (
    PreflightRefused,
    require_asr_cpu_preflight,
    require_egress_isolation,
)
from benchmarks.refusals import missing_artifact
from gpulock import GpuBenchmarkBusyError, gpu_benchmark_lock
from scoring import (
    SCORING_CONTRACT,
    GroupResult,
    bootstrap_syer,
    character_counts,
    fold_diacritics,
    non_speech_output_rate,
    score_failed_utterance,
    score_utterance,
    syllables,
)

WHISPER = pathlib.Path("var/whispercpp/b5454/Release/whisper-cli.exe")


def clip_seconds(path: pathlib.Path, declared: float | None = None) -> float:
    """Duration in seconds, preferring the manifest over the file header.

    The manifest wins because stdlib :mod:`wave` **cannot read these clips**:
    FLEURS ships mono 16 kHz **32-bit IEEE float** WAV, and `wave` raises
    ``unknown format: 3`` on anything that is not integer PCM. Reading the
    header first returned 0.0 for every FLEURS clip, which silently made every
    RTF ``None`` - a missing number rather than a wrong one, but missing for a
    criterion that asks for it.

    FLEURS' own TSV carries ``num_samples``, so the manifest can state the
    duration without decoding audio at all. The header is the fallback, for
    the integer-PCM clips the generator produces.
    """
    if declared and declared > 0:
        return declared
    try:
        with wave.open(str(path), "rb") as handle:
            return handle.getnframes() / float(handle.getframerate())
    except (OSError, wave.Error):
        return 0.0


def transcribe(
    clip: pathlib.Path,
    model: pathlib.Path,
    *,
    language: str,
    threads: int,
    use_gpu: bool,
    timeout: int,
) -> tuple[str, dict[str, object]]:
    """Return (hypothesis, metadata). Never raises on a failed clip."""
    command = [
        str(WHISPER),
        "-m",
        str(model),
        "-f",
        str(clip),
        "-l",
        language,
        "-nt",
        "-t",
        str(threads),
    ]
    if not use_gpu:
        command.append("-ng")

    started = time.perf_counter()
    try:
        done = subprocess.run(  # noqa: S603
            command, capture_output=True, text=True, timeout=timeout, check=False
        )
        elapsed = time.perf_counter() - started
        meta: dict[str, object] = {
            "returncode": done.returncode,
            "timed_out": False,
            "wall_s": round(elapsed, 3),
            "used_gpu": "loaded CUDA backend" in done.stderr,
            # Recorded because several of these directly determine the
            # hallucination number, and a result without them is not traceable.
            "cpu_backend": next(
                (
                    line.split("from")[-1].strip().rsplit("\\", maxsplit=1)[-1]
                    for line in done.stderr.splitlines()
                    if "loaded CPU backend" in line
                ),
                None,
            ),
        }
        return done.stdout.strip(), meta
    except subprocess.TimeoutExpired:
        return "", {
            "returncode": -1,
            "timed_out": True,
            "wall_s": round(time.perf_counter() - started, 3),
            "used_gpu": None,
            "cpu_backend": None,
        }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", required=True, type=pathlib.Path)
    parser.add_argument("--model", required=True, type=pathlib.Path)
    parser.add_argument("--label", default="")
    parser.add_argument("--language", default="vi")
    parser.add_argument("--threads", type=int, default=4)
    parser.add_argument("--cpu", action="store_true", help="pass -ng, CPU only")
    parser.add_argument("--timeout", type=int, default=600)
    parser.add_argument("--limit", type=int, default=0)
    args = parser.parse_args()

    # `--cpu` appends `-ng`, which makes this a model run with no GPU - so the
    # owner's decision to refuse every CPU run until a threshold is approved
    # applies here too. A separate gate from the LLM one: 4438 MiB describes
    # Qwen3-4B, and no ASR host-RAM figure has ever been measured.
    if args.cpu:
        try:
            require_asr_cpu_preflight()
        except PreflightRefused as exc:
            print(f"preflight tu choi: {exc}", file=sys.stderr)
            return 3

    # The role, not the path: this message is quoted into reports, and the
    # loop never said which of the three was missing anyway.
    for role, path in (
        ("whisper-binary", WHISPER),
        ("manifest", args.manifest),
        ("asr-model", args.model),
    ):
        if not path.is_file():
            print(missing_artifact(role), file=sys.stderr)
            return 2

    # One lock for every MeetAI GPU benchmark: the GPU is the shared
    # resource, so an ASR pass and a co-residency pass overlapping is as
    # damaging as two ASR passes.
    # S2.1 decision #5: no native model binary starts without OS-level
    # egress isolation. Placed AFTER the artifact checks and immediately
    # before the native work, which the refusal-leak matrix is what
    # established: putting it first made seven artifact branches
    # unreachable, and those branches are the more diagnostic refusal.
    # The gate only has to precede anything that *runs*; a stat call
    # spawns nothing. Reported separately from the RAM gates - "not
    # enough RAM" sends an operator to close applications, this sends
    # them to configure isolation.
    try:
        require_egress_isolation()
    except PreflightRefused as exc:
        print(f"egress tu choi: {exc}", file=sys.stderr)
        return 4

    try:
        with gpu_benchmark_lock():
            return _run(args)
    except GpuBenchmarkBusyError as busy:
        print(str(busy), file=sys.stderr)
        return 5


def _run(args: argparse.Namespace) -> int:
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    clips = manifest["clips"]
    if args.limit:
        clips = clips[: args.limit]

    speech = GroupResult(name=manifest.get("group", "speech"))
    non_speech_hyps: list[str] = []
    non_speech_durations: list[float] = []
    non_speech_ids: list[str] = []
    per_clip: list[dict[str, object]] = []
    blocks: list[str] = []

    for entry in clips:
        clip_path = pathlib.Path(manifest["clip_root"]) / entry["file"]
        reference = entry.get("reference", "")
        duration = clip_seconds(clip_path, entry.get("duration_s"))

        if not clip_path.is_file():
            speech.note_failure("missing_clip")
            print(f"  MISSING clip={entry['id']}")
            continue

        hypothesis, meta = transcribe(
            clip_path,
            args.model,
            language=args.language,
            threads=args.threads,
            use_gpu=not args.cpu,
            timeout=args.timeout,
        )
        failed = bool(meta["timed_out"]) or meta["returncode"] != 0
        wall_s = meta["wall_s"]
        is_non_speech = not syllables(reference)

        record: dict[str, object] = {
            "id": entry["id"],
            "duration_s": round(duration, 3),
            "rtf": (
                round(float(wall_s) / duration, 3)
                if duration and isinstance(wall_s, int | float)
                else None
            ),
            **meta,
            # Hypothesis text lives in this file, which is under var/ and
            # git-ignored. It is never printed.
            "hypothesis": hypothesis,
            "hypothesis_tokens": len(syllables(hypothesis)),
            "non_speech": is_non_speech,
        }

        if is_non_speech:
            # An empty hypothesis here is correct, so a failed run is still a
            # failure but an empty output is not.
            if failed:
                speech.note_failure("run_error_non_speech")
            non_speech_hyps.append("" if failed else hypothesis)
            non_speech_durations.append(duration)
            non_speech_ids.append(str(entry["id"]))
            print(
                f"  clip={entry['id']:28} non_speech "
                f"out_tokens={record['hypothesis_tokens']:3} "
                f"rtf={record['rtf']} rc={meta['returncode']}"
            )
        else:
            if failed or not syllables(hypothesis):
                counts = score_failed_utterance(reference)
                speech.note_failure(
                    "timeout"
                    if meta["timed_out"]
                    else ("nonzero_exit" if failed else "empty_output")
                )
            else:
                counts, _ = score_utterance(reference, hypothesis)
            speech.add(
                counts,
                char=character_counts(reference, hypothesis),
                folded=score_utterance(
                    fold_diacritics(reference), fold_diacritics(hypothesis)
                )[0],
            )
            blocks.append(str(entry.get("block", entry["id"])))
            record["counts"] = {
                "S": counts.substitutions,
                "D": counts.deletions,
                "I": counts.insertions,
                "N": counts.ref_tokens,
            }
            print(
                f"  clip={entry['id']:28} N={counts.ref_tokens:4} "
                f"S={counts.substitutions:3} D={counts.deletions:3} "
                f"I={counts.insertions:3} rtf={record['rtf']}"
            )
        per_clip.append(record)

    non_speech = non_speech_output_rate(non_speech_hyps, non_speech_durations)
    interval = bootstrap_syer(speech.per_utterance, blocks=blocks or None)

    summary: dict[str, object] = {
        "label": args.label or args.model.stem,
        "scoring_contract": SCORING_CONTRACT,
        "model": args.model.name,
        "manifest": args.manifest.name,
        "manifest_license": manifest.get("license"),
        "license_branch": manifest.get("license_branch"),
        "device": "cpu" if args.cpu else "gpu",
        "language": args.language,
        "threads": args.threads,
        "speech": {
            "utterances": speech.utterances,
            "N": speech.counts.ref_tokens,
            "S": speech.counts.substitutions,
            "D": speech.counts.deletions,
            "I": speech.counts.insertions,
            "syer": speech.counts.syer,
            "ier": speech.counts.insertion_rate,
            "cer": speech.char_counts.syer,
            # Diagnostic only, never a headline. The folded figure lowercases
            # AND strips diacritics, so the gap against the headline mixes two
            # causes; it is reported because the combined gap is still the
            # diacritic-plus-case error mass, and a headline that forgave
            # either would hide the error class this project cares about most.
            "syer_folded_diagnostic_only": speech.folded_counts.syer,
            "syer_ci95_bootstrap_over_utterances": interval,
            "failures": speech.failures,
        },
        "non_speech": {
            "clips": non_speech.clips,
            "clips_with_output": non_speech.clips_with_output,
            "output_rate": non_speech.output_rate,
            "hallucinated_tokens": non_speech.total_hallucinated_tokens,
            "tokens_per_minute": non_speech.tokens_per_minute,
            "audio_seconds": non_speech.total_audio_seconds,
            "clip_ids": non_speech_ids,
        },
        "limits": [
            "SyER is syllable-level: Vietnamese writes syllables separated by "
            "spaces, so a whitespace token is a syllable, not a word.",
            "Diacritics are NOT folded for the headline. The folded figure is a "
            "diagnostic; the gap between them is the diacritic error mass.",
            "The CI is a bootstrap over utterances, not a Wilson interval: SyER "
            "is not a proportion and can exceed 1, and errors cluster within an "
            "utterance.",
            "Non-speech is reported per clip, never pooled into SyER.",
        ],
    }

    out_dir = artifact_path("asr", "results")
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%d-%H%M%S")
    target = out_dir / f"asr-{summary['label']}-{summary['device']}-{stamp}.json"
    target.write_text(
        json.dumps({"summary": summary, "clips": per_clip}, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    print()
    print(f"  {speech.render()}")
    print(f"  non_speech: {non_speech.render()}")
    if speech.failures:
        print(f"  failures: {speech.failures}")
    # ensure_ascii=True for anything that reaches a console.
    print(json.dumps(summary, indent=2, ensure_ascii=True))
    print(f"\nwritten: {target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
