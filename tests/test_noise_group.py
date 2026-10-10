"""Tests for the noise-group generator (S2.2).

Runs without the corpus: every fixture is synthesised in-process, so these
assert the SNR contract rather than any property of FLEURS. The generator
exists because spec B-1 asks for WER by noise condition, and "with noise" is
meaningless unless the SNR definition is stated and correct.
"""

from __future__ import annotations

import array
import math
import struct
import sys
import wave
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "benchmarks"))

from make_noise_group import (
    lcg_noise,
    mix_at_snr,
    read_wav_any,
    rms,
    write_pcm16,
)

RATE = 16000


def _speech_like(seconds: float = 1.0, amplitude: float = 0.1) -> list[float]:
    """A deterministic tone standing in for speech. Not speech, and the tests
    below only use it as a signal with a known RMS."""
    return [
        amplitude * math.sin(2 * math.pi * 220 * t / RATE)
        for t in range(int(RATE * seconds))
    ]


def _write_float32(path: Path, samples: list[float]) -> None:
    """Write a 32-bit IEEE float WAV, the format FLEURS ships and stdlib
    ``wave`` refuses to open."""
    data = array.array("f", samples).tobytes()
    header = b"RIFF" + struct.pack("<I", 36 + len(data)) + b"WAVE"
    header += b"fmt " + struct.pack("<IHHIIHH", 16, 3, 1, RATE, RATE * 4, 4, 32)
    header += b"data" + struct.pack("<I", len(data))
    path.write_bytes(header + data)


class TestReadsBothFormats:
    """stdlib wave cannot open the corpus at all, which is why this exists."""

    def test_stdlib_wave_really_cannot_read_float32(self, tmp_path: Path) -> None:
        """Pins the reason this reader exists. If stdlib gains float support
        this fails and the hand-rolled path can be reconsidered."""
        target = tmp_path / "f32.wav"
        _write_float32(target, _speech_like(0.1))
        with pytest.raises(wave.Error), wave.open(str(target), "rb"):
            pass

    def test_reads_float32(self, tmp_path: Path) -> None:
        samples = _speech_like(0.25)
        target = tmp_path / "f32.wav"
        _write_float32(target, samples)
        read, rate = read_wav_any(target)
        assert rate == RATE
        assert len(read) == len(samples)
        assert read[:8] == pytest.approx(samples[:8], abs=1e-6)

    def test_reads_pcm16(self, tmp_path: Path) -> None:
        samples = _speech_like(0.25)
        target = tmp_path / "pcm16.wav"
        write_pcm16(target, samples)
        read, rate = read_wav_any(target)
        assert rate == RATE
        assert read[:8] == pytest.approx(samples[:8], abs=1e-3)

    def test_refuses_unsupported_format(self, tmp_path: Path) -> None:
        """Raises rather than guessing, and the message names shape not data."""
        target = tmp_path / "bad.wav"
        target.write_bytes(b"NOTRIFF" + b"\0" * 40)
        with pytest.raises(ValueError) as excinfo:
            read_wav_any(target)
        assert "RIFF" in str(excinfo.value)

    def test_refuses_stereo(self, tmp_path: Path) -> None:
        data = array.array("f", _speech_like(0.05)).tobytes()
        header = b"RIFF" + struct.pack("<I", 36 + len(data)) + b"WAVE"
        header += b"fmt " + struct.pack("<IHHIIHH", 16, 3, 2, RATE, RATE * 8, 8, 32)
        header += b"data" + struct.pack("<I", len(data))
        target = tmp_path / "stereo.wav"
        target.write_bytes(header + data)
        with pytest.raises(ValueError):
            read_wav_any(target)


class TestSnrIsWhatItClaims:
    """A noise group whose SNR is approximate measures nothing."""

    @pytest.mark.parametrize("target_db", [30.0, 20.0, 10.0, 5.0, 0.0])
    def test_measured_snr_matches_the_target(self, target_db: float) -> None:
        speech = _speech_like(1.0)
        mixed = mix_at_snr(speech, target_db, seed=1234567)
        noise = [m - s for m, s in zip(mixed, speech, strict=True)]
        measured = 20 * math.log10(rms(speech) / rms(noise))
        assert measured == pytest.approx(target_db, abs=0.05)

    def test_lower_snr_adds_more_noise(self) -> None:
        speech = _speech_like(0.5)
        quiet = [m - s for m, s in zip(mix_at_snr(speech, 20.0, 1), speech, strict=True)]
        loud = [m - s for m, s in zip(mix_at_snr(speech, 5.0, 1), speech, strict=True)]
        assert rms(loud) > rms(quiet)

    def test_deterministic_for_a_seed(self) -> None:
        speech = _speech_like(0.2)
        assert mix_at_snr(speech, 10.0, seed=99) == mix_at_snr(speech, 10.0, seed=99)

    def test_silent_input_is_returned_unchanged(self) -> None:
        """No speech means no SNR to hit; adding scaled noise would be a
        division by zero dressed up as a measurement."""
        silence = [0.0] * 1000
        assert mix_at_snr(silence, 10.0, seed=1) == silence

    def test_noise_generator_is_deterministic(self) -> None:
        assert lcg_noise(50, seed=7) == lcg_noise(50, seed=7)
        assert lcg_noise(50, seed=7) != lcg_noise(50, seed=8)


class TestWriteRoundTrip:
    def test_unclipped_audio_keeps_its_level(self, tmp_path: Path) -> None:
        """Rescaling only on overflow, so an unclipped clip keeps the SNR that
        was set rather than being quietly normalised."""
        samples = _speech_like(0.2, amplitude=0.1)
        target = tmp_path / "out.wav"
        write_pcm16(target, samples)
        read, _ = read_wav_any(target)
        assert rms(read) == pytest.approx(rms(samples), rel=1e-2)

    def test_output_is_pcm16_mono(self, tmp_path: Path) -> None:
        target = tmp_path / "out.wav"
        write_pcm16(target, _speech_like(0.1))
        with wave.open(str(target), "rb") as handle:
            assert handle.getnchannels() == 1
            assert handle.getsampwidth() == 2
            assert handle.getframerate() == RATE
