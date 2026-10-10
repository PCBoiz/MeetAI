"""Assert .gitignore actually blocks what the project says it blocks.

Written because the rules had been fixed twice by hand with nothing to stop a
later edit reopening them. Both fixes were prompted by running
``git check-ignore`` and finding paths that carried audio, reference
transcripts or ASR hypotheses and were committable; a rule nobody tests is a
rule that lasts until the next refactor.

Two directions, and both matter:

- :class:`TestContentCannotBeCommitted` fails if a content-bearing path
  becomes committable. Deleting a rule fails a test, which is what
  ``AGENTS.md`` asks for.
- :class:`TestNeededFilesStayCommittable` fails if a rule grows broad enough
  to swallow something the repository needs. That is not hypothetical: a
  ``benchmarks/*.md`` rule written in one turn would have excluded
  ``benchmarks/README.md``, and ``*.tsv`` means a committed manifest cannot be
  a TSV.

``git check-ignore`` is invoked with an explicit ``-C`` at the repository root
because ``conftest.py`` chdirs every test into a temporary directory.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import ClassVar

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent

CONTENT_BEARING = [
    # Reference transcripts. VIVOS ships its references as prompts.txt, which
    # is why the bare .txt rule exists.
    "prompts.txt",
    "vivos/test/prompts.txt",
    "references.txt",
    "data/fleurs/dev.tsv",
    "manifest.tsv",
    # ASR hypotheses. whisper.cpp writes these next to the input clip by
    # default, in whichever format the flags ask for.
    "hyp.txt",
    "clip.srt",
    "clip.vtt",
    "clip.lrc",
    "clip.csv",
    "hyp.jsonl",
    "benchmarks/asr/hyp.json",
    "benchmarks/results/asr.json",
    "scratch/hyp.json",
    "out/hyp.json",
    "asr.log",
    # Artifact shapes introduced by the S2.2 noise group and the
    # post-processor. Probed after they existed, not guessed.
    "derived.json",
    "asr-run-derived.json",
    "clip-snr10.wav",
    "var/asr/noise/clip-snr5.wav",
    "var/asr/results/asr-x-derived.json",
    "var/asr/manifest-fleurs-noise.json",
    "data/fleurs/dev.tar.gz",
    "data/fleurs/dev.tsv",
    ".bench_asr.lock",
    ".meetai-gpu-benchmark.lock",
    "var/.meetai-gpu-benchmark.lock",
    # Audio, and the archives speech corpora actually arrive in.
    "clip.wav",
    "clip.mp3",
    "clip.flac",
    "clip.opus",
    "dev.tar.gz",
    "corpus.zip",
    "clips.tar",
    "archive.7z",
    # Weights and unaudited native blobs.
    "weights.gguf",
    "model.safetensors",
    "ggml-small.bin",
    "whisper-cli.exe",
    "ggml-cuda.dll",
    # Secrets.
    ".env",
    "token.json",
    "credentials.json",
]

MUST_STAY_COMMITTABLE = [
    "README.md",
    "AGENTS.md",
    "pyproject.toml",
    "PROJECT_STATE.md",
    "benchmarks/README.md",
    "benchmarks/bench_asr.py",
    "benchmarks/measure.py",
    "benchmarks/make_noise_group.py",
    "benchmarks/postprocess_asr.py",
    "tests/test_noise_group.py",
    "docs/plan.md",
    "docs/research/asr-report.md",
    "docs/adr/0005-nhanh-cuda-12-va-duong-llama-cpp.md",
    "src/meetai/policy.py",
    "tests/test_gitignore.py",
    "tests/corpus/authority_vi.py",
]


def _git() -> str | None:
    """Absolute path of git, so the executable that runs is the one found."""
    return shutil.which("git")


def is_ignored(path: str) -> bool:
    """Whether git would ignore this path, asked at the repository root."""
    executable = _git()
    if executable is None:
        pytest.skip("git khong co tren PATH")
    # Fixed argument list, no shell; `path` comes from the tables above.
    result = subprocess.run(  # noqa: S603
        [executable, "-C", str(REPO_ROOT), "check-ignore", "-q", "--no-index", path],
        capture_output=True,
        check=False,
    )
    # 0 = ignored, 1 = not ignored, 128 = error.
    if result.returncode not in (0, 1):
        pytest.fail(f"git check-ignore failed for {path}: rc={result.returncode}")
    return result.returncode == 0


pytestmark = pytest.mark.skipif(_git() is None, reason="git khong co tren PATH")


class TestContentCannotBeCommitted:
    """Every path here would carry audio, transcripts, hypotheses or secrets."""

    @pytest.mark.parametrize("path", CONTENT_BEARING)
    def test_pathis_ignored(self, path: str) -> None:
        assert is_ignored(path), (
            f"{path} commit duoc. Day la duong ro noi dung: them rule vao "
            ".gitignore thay vi bo case nay."
        )


class TestNeededFilesStayCommittable:
    """A rule that swallows something the repository needs is also a bug."""

    @pytest.mark.parametrize("path", MUST_STAY_COMMITTABLE)
    def test_path_is_not_ignored(self, path: str) -> None:
        assert not is_ignored(path), (
            f"{path} bi .gitignore chan. Mot rule qua rong vua an mat file "
            "repo can commit."
        )


def _ignored_index_aware(path: str) -> bool:
    """Whether git ignores this path, respecting the index.

    Without ``--no-index``, a tracked file is never reported as ignored, which
    is the correct question for :class:`TestNoTrackedFileIsIgnored`.
    """
    executable = _git()
    if executable is None:
        pytest.skip("git khong co tren PATH")
    result = subprocess.run(  # noqa: S603
        [executable, "-C", str(REPO_ROOT), "check-ignore", "-q", path],
        capture_output=True,
        check=False,
    )
    return result.returncode == 0


class TestThePromptExceptionStaysNarrow:
    """``benchmarks/prompts/*.txt`` is the one hole in the bare ``.txt`` rule.

    It exists because a pinned benchmark prompt is **configuration**: hashing it
    into an artifact is pointless if the file itself is not in history. But the
    bare ``.txt`` rule is there because VIVOS ships its reference transcripts as
    ``prompts.txt``, so an exception in the wrong place would uningnore exactly
    the content-shaped text the rule was added for.

    These tests hold both halves: the prompt directory is visible, and nothing
    else with a ``.txt`` name is.
    """

    DATA_SHAPED: ClassVar[list[str]] = [
        "prompts.txt",
        "data/vivos/test/prompts.txt",
        "var/asr/references.txt",
        "hyp.txt",
        "benchmarks/references.txt",
        "benchmarks/prompts/../transcript.txt",
    ]

    def test_a_pinned_prompt_is_committable(self) -> None:
        assert not is_ignored("benchmarks/prompts/s23-v2-intent-guidance.txt")

    @pytest.mark.parametrize("path", DATA_SHAPED)
    def test_the_exception_does_not_reach_reference_text(self, path: str) -> None:
        assert is_ignored(path), path

    def test_the_prompt_directory_holds_only_prompts(self) -> None:
        """The exception is safe only while the claim about the directory is.

        A reference transcript dropped in here would be committable, so the
        directory's contents are checked rather than trusted. Prompts are the
        harness's own text; anything else belongs somewhere ignored.
        """
        directory = REPO_ROOT / "benchmarks" / "prompts"
        if not directory.is_dir():
            return
        for entry in sorted(directory.iterdir()):
            assert entry.is_file(), f"{entry.name}: chi chua file, khong thu muc"
            assert entry.suffix == ".txt", entry.name
            assert "prompt" in entry.name or entry.name.startswith("s2"), (
                f"{entry.name}: ten phai noi ro day la prompt cua mot cau hinh"
            )


class TestNoTrackedFileIsIgnored:
    """The regression that matters most: a new rule hiding tracked history.

    Checked against the real index rather than a list, so it keeps working as
    the repository grows.
    """

    def test_every_tracked_file_stays_visible(self) -> None:
        executable = _git()
        if executable is None:
            pytest.skip("git khong co tren PATH")
        listing = subprocess.run(  # noqa: S603
            [executable, "-C", str(REPO_ROOT), "ls-files"],
            capture_output=True,
            text=True,
            check=False,
        )
        if listing.returncode != 0:
            pytest.skip("khong doc duoc git index")
        tracked = [line for line in listing.stdout.splitlines() if line.strip()]
        assert tracked, "git ls-files rong - test nay se pass vo nghia"

        # Deliberately NOT --no-index here. `--no-index` asks "would a
        # pattern match this name", which is what the probes above need for
        # paths that do not exist. For a file that is already tracked the
        # question is different: git keeps tracking it whatever .gitignore
        # says, so the honest check is the index-aware one. Using --no-index
        # reported every tracked file matching any new pattern as a
        # regression - including uv.lock against a `*.lock` rule, which is a
        # real over-broad rule but is caught by MUST_STAY_COMMITTABLE, not
        # here.
        ignored = [path for path in tracked if _ignored_index_aware(path)]
        assert not ignored, f"file da tracked nhung bi ignore: {ignored[:10]}"
