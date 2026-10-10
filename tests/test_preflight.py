"""Tests for the VRAM preflight. No GPU, no model, no benchmark.

Every case supplies a :class:`VramState` directly, so the arithmetic and the
refusal are tested without touching the device. The one function that does read
the GPU is covered only for its fail-closed behaviour on unparseable output.
"""

from __future__ import annotations

import pytest
from benchmarks.preflight import (
    ATTRIBUTABLE_PEAK_MIB,
    OBSERVED_PEAK_DEVICE_MIB,
    REQUIRED_FREE_MIB,
    SPIKE_MARGIN,
    TOTAL_VRAM_MIB,
    PreflightRefused,
    VramState,
    require_headroom,
)


class TestTheBudgetMatchesTheArtifacts:
    """The constants have to stay traceable, or the margin is just a number."""

    def test_the_attributable_peak_is_the_recorded_subtraction(self) -> None:
        assert ATTRIBUTABLE_PEAK_MIB == OBSERVED_PEAK_DEVICE_MIB - 853
        assert ATTRIBUTABLE_PEAK_MIB == 2819

    def test_the_requirement_is_the_peak_plus_the_margin(self) -> None:
        assert int(ATTRIBUTABLE_PEAK_MIB * (1 + SPIKE_MARGIN)) == REQUIRED_FREE_MIB
        assert REQUIRED_FREE_MIB == 4228

    def test_every_recorded_run_would_have_passed(self) -> None:
        """The margin must not refuse the machine's normal state.

        Idle readings from the four artifacts. A preflight that refuses a
        healthy machine gets bypassed, so this is the cost side of the margin
        and it is asserted rather than assumed.
        """
        for idle in (853, 760, 841, 752):
            state = VramState(total_mib=TOTAL_VRAM_MIB, used_mib=idle)
            assert state.fits, idle

    def test_a_loaded_desktop_is_refused(self) -> None:
        """The other side: ~1.9 GB already in use leaves too little."""
        state = VramState(total_mib=TOTAL_VRAM_MIB, used_mib=1950)
        assert not state.fits
        with pytest.raises(PreflightRefused, match="khong du VRAM"):
            require_headroom(state)

    def test_the_margin_is_not_so_large_it_always_refuses(self) -> None:
        """A preflight that never passes teaches people to force past it."""
        assert REQUIRED_FREE_MIB < TOTAL_VRAM_MIB


class TestRefusalIsFailClosed:
    def test_exactly_at_the_threshold_passes(self) -> None:
        state = VramState(
            total_mib=TOTAL_VRAM_MIB, used_mib=TOTAL_VRAM_MIB - REQUIRED_FREE_MIB
        )
        assert require_headroom(state) is state

    def test_one_mib_short_refuses(self) -> None:
        state = VramState(
            total_mib=TOTAL_VRAM_MIB, used_mib=TOTAL_VRAM_MIB - REQUIRED_FREE_MIB + 1
        )
        with pytest.raises(PreflightRefused):
            require_headroom(state)

    def test_the_refusal_is_an_exception_not_a_falsy_return(self) -> None:
        """So a caller cannot proceed by ignoring a return value.

        ``if preflight(...)`` is the shape that fails open when someone
        forgets the ``if``; an exception has no such shape.
        """
        import inspect

        source = inspect.getsource(require_headroom)
        assert "raise PreflightRefused" in source
        assert "return False" not in source

    def test_an_unreadable_gpu_refuses_rather_than_assuming(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A run that cannot be measured is a run whose failure cannot be attributed."""
        import benchmarks.preflight as preflight

        monkeypatch.setattr(preflight, "nvidia_smi", lambda fields: [])
        with pytest.raises(PreflightRefused, match="khong doc duoc VRAM"):
            preflight.read_vram()

    def test_garbage_from_nvidia_smi_refuses(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import benchmarks.preflight as preflight

        monkeypatch.setattr(preflight, "nvidia_smi", lambda fields: ["N/A", "N/A"])
        with pytest.raises(PreflightRefused, match="khong parse duoc"):
            preflight.read_vram()


class TestMetadataIsHonestAboutWhatItMeasured:
    def test_the_metadata_names_the_wddm_limitation(self) -> None:
        """A reader must not take ``used_mib`` for "used by the benchmark"."""
        state = VramState(total_mib=TOTAL_VRAM_MIB, used_mib=800)
        meta = state.metadata()
        assert meta["per_process_vram"] == "unavailable under WDDM"
        assert meta["required_free_mib"] == REQUIRED_FREE_MIB
        assert meta["spike_margin"] == SPIKE_MARGIN

    def test_there_is_no_per_process_field(self) -> None:
        from dataclasses import fields

        names = {f.name for f in fields(VramState)}
        assert "process_mib" not in names
        assert names == {"total_mib", "used_mib"}


class TestNoGpuWorkHappensHere:
    """Structural: this module must not be able to start a model.

    The directive is explicit that no agent and no preflight runs GPU work, so
    the absence is checked rather than reviewed.
    """

    def test_the_module_launches_nothing(self) -> None:
        import ast
        import pathlib

        source = (
            pathlib.Path(__file__).resolve().parent.parent / "benchmarks" / "preflight.py"
        ).read_text(encoding="utf-8")
        tree = ast.parse(source)
        called = {
            node.func.attr
            for node in ast.walk(tree)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
        } | {
            node.func.id
            for node in ast.walk(tree)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
        }
        for forbidden in ("Popen", "run", "check_output", "system", "spawn"):
            assert forbidden not in called, forbidden

    def test_it_imports_no_model_runtime(self) -> None:
        import pathlib
        import re

        source = (
            pathlib.Path(__file__).resolve().parent.parent / "benchmarks" / "preflight.py"
        ).read_text(encoding="utf-8")
        roots = {
            name.split(".")[0]
            for name in re.findall(r"^\s*(?:from|import)\s+([\w.]+)", source, re.M)
        }
        assert not roots & {"subprocess", "llama_cpp", "torch", "transformers"}
