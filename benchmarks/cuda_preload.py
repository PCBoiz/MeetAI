"""Load the CUDA runtime DLLs before llama_cpp imports, on Windows.

Why this exists, measured rather than assumed. The prebuilt
``llama-cpp-python`` wheel from the cu125 index ships ``ggml-cuda.dll`` with
the CUDA kernels compiled in, but **not** the CUDA runtime itself:
``ggml-cuda.dll`` imports ``cudart64_12.dll`` and ``cublas64_12.dll``, and this
machine has no CUDA toolkit. Worse, ``ggml.dll`` imports ``ggml-cuda.dll``
*statically*, so the wheel cannot load at all - not even for CPU-only work -
until the CUDA runtime is resolvable. The import tables were read directly from
the PE headers to establish that, not guessed from an error message.

``os.add_dll_directory`` was tried first and did **not** work: it does not
reach the transitive imports of a DLL loaded by absolute path. Loading each
dependency explicitly, in dependency order, does work, because once a module is
in the process by name the loader stops searching for it.

The DLLs come from NVIDIA's own PyPI redistributables
(``nvidia-cuda-runtime-cu12``, ``nvidia-cublas-cu12``), which have real
``win_amd64`` wheels. Nothing is installed system-wide and no CUDA toolkit is
needed. Note their licence is ``LicenseRef-NVIDIA-Proprietary``, which is
recorded in the dependency inventory.

A CUDA **12.9** runtime satisfies a binary built against **12.5**. That is
observed on this machine, not inferred from the version numbers.
"""

from __future__ import annotations

import ctypes
import pathlib
import site
import sys

_ORDER = (
    "nvidia/cuda_runtime/bin/cudart64_12.dll",
    "nvidia/cublas/bin/cublasLt64_12.dll",
    "nvidia/cublas/bin/cublas64_12.dll",
)


def preload_cuda() -> tuple[str, ...]:
    """Load the CUDA runtime DLLs. Returns the names actually loaded.

    A no-op off Windows. Missing files are skipped rather than raised on, so a
    CPU-only run still works: the caller finds out from the empty result, and
    llama.cpp reports what backend it actually chose.
    """
    if sys.platform != "win32":
        return ()
    loaded: list[str] = []
    for root in {pathlib.Path(p) for p in site.getsitepackages()}:
        for rel in _ORDER:
            dll = root / rel
            if dll.is_file():
                try:
                    ctypes.CDLL(str(dll))
                except OSError:
                    continue
                loaded.append(dll.name)
    return tuple(loaded)
