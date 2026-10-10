"""Build an accent-stratified manifest from VietMed test. S2.2 exploratory probe.

VietMed is the only Vietnamese corpus found that is simultaneously permissively
licensed, ungated, transcript-bearing and **accent-labelled per speaker**. This
builds a manifest that groups its test split by accent so WER can be reported
per accent group.

**Everything about this probe is exploratory, and the reasons are structural
rather than fixable by more effort:**

- **8 kHz, measured not assumed.** Every one of 500 sampled files reports
  8000 Hz mono in its Vorbis identification header. FLEURS is 16 kHz. Telephone
  bandwidth is a different acoustic condition, so a VietMed number is **its own
  benchmark** and must never be presented as a slice of the FLEURS run.
- **Medical domain.** Doctor-patient consultations, lectures, podcasts and news.
  That is a real distribution mismatch for a general meeting assistant.
- **One accent group is unmeasurable.** North Central Coast has 21 utterances in
  the whole test split. It is carried so the gap is visible, and reported as
  under-powered rather than as a rate.
- **Accent co-varies with recording condition.** The metadata has a
  ``Rec. Condition`` column with seven values, and at a few hundred utterances
  per accent cell the two cannot be de-confounded. A per-accent table here
  measures accent *and* recording condition together.
- **An MIT tag is not a rights audit.** The license tag covers the authors'
  contribution; the underlying audio was collected from public sources under a
  fair-use argument. Local evaluation is the mildest use; redistribution is not,
  and nothing is redistributed here.

Stdlib only. The metadata ships as ``.xlsx``, which is a zip of XML, so it is
read with ``zipfile`` + ``ElementTree`` rather than by adding a spreadsheet
dependency. The transcript ships as a Python-literal list of dicts, read with
``ast.literal_eval`` - **not** ``eval``.
"""

from __future__ import annotations

import argparse
import ast
import json
import pathlib
import xml.etree.ElementTree as ET
import zipfile
from collections import Counter, defaultdict

NS = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
_T = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}t"


def read_metadata(path: pathlib.Path) -> dict[str, dict[str, str]]:
    """``speaker_id -> {accent, rec_condition, role, gender, split}``.

    The sheet uses merged cells for ``Audio Name`` and ``Rec. Condition``, so a
    blank means "same as the row above" and the values are forward-filled. Not
    doing so silently drops the recording condition for most rows, which is the
    column needed to show the accent/condition confound.
    """
    archive = zipfile.ZipFile(path)
    shared: list[str] = []
    if "xl/sharedStrings.xml" in archive.namelist():
        # Stdlib ET on a 53 KB local file whose SHA-256 is recorded in the
        # artifact ledger. defusedxml would be a new dependency for a file
        # this project pins by hash and never fetches at run time.
        root = ET.fromstring(archive.read("xl/sharedStrings.xml"))  # noqa: S314
        for si in root.findall("m:si", NS):
            shared.append("".join(t.text or "" for t in si.iter(_T)))

    sheet = next(n for n in archive.namelist() if n.startswith("xl/worksheets/sheet"))
    rows = ET.fromstring(archive.read(sheet)).findall(".//m:row", NS)  # noqa: S314

    def value(cell: ET.Element) -> str:
        node = cell.find("m:v", NS)
        if node is None or node.text is None:
            return ""
        if cell.get("t") == "s" and node.text.isdigit():
            return shared[int(node.text)]
        return node.text

    header = [value(c) for c in rows[0].findall("m:c", NS)]
    index = {name: i for i, name in enumerate(header) if name}
    out: dict[str, dict[str, str]] = {}
    carried: dict[str, str] = {}

    for row in rows[1:]:
        cells = [value(c) for c in row.findall("m:c", NS)]
        if not any(cells):
            continue

        def field(name: str, cells: list[str] = cells) -> str:
            i = index.get(name)
            return cells[i] if i is not None and i < len(cells) else ""

        for merged in ("Audio Name", "Rec. Condition"):
            got = field(merged)
            if got:
                carried[merged] = got

        speaker = field("Speaker ID")
        if not speaker:
            continue
        out[speaker] = {
            "accent": field("Accent"),
            "rec_condition": carried.get("Rec. Condition", ""),
            "role": field("Role"),
            "gender": field("Gender"),
            "split": field("Train"),
            "audio_name": carried.get("Audio Name", ""),
        }
    return out


def read_transcript(path: pathlib.Path) -> list[dict[str, object]]:
    """Parse the Python-literal list of dicts with ``ast.literal_eval``.

    ``literal_eval`` rather than ``eval``: this file is third-party data, and
    the project's own rule is that data is never executed.
    """
    return list(ast.literal_eval(path.read_text(encoding="utf-8")))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--metadata", default="data/vietmed/Metadata_labeled_medical.xlsx"
    )
    parser.add_argument("--transcript", default="data/vietmed/test_transcript.txt")
    parser.add_argument("--clip-root", default="var/asr/vietmed/test_audio")
    parser.add_argument(
        "--per-group",
        type=int,
        default=100,
        help="utterances per accent group. A stratified cap keeps the probe "
        "affordable and keeps groups comparable; the cap is reported.",
    )
    parser.add_argument("--out", default="var/asr/manifest-vietmed-accent.json")
    args = parser.parse_args()

    meta = read_metadata(pathlib.Path(args.metadata))
    utterances = read_transcript(pathlib.Path(args.transcript))
    root = pathlib.Path(args.clip_root)

    by_accent: dict[str, list[dict[str, object]]] = defaultdict(list)
    missing_speaker = 0
    missing_audio = 0

    for utt in utterances:
        speaker = str(utt.get("speaker_name", ""))
        info = meta.get(speaker)
        if info is None or not info["accent"]:
            missing_speaker += 1
            continue
        rel = str(utt.get("file", ""))
        clip = root / rel
        if not clip.is_file():
            missing_audio += 1
            continue
        by_accent[info["accent"]].append(
            {
                "id": f"vietmed-{rel.replace('/', '-').removesuffix('.ogg')}",
                "file": rel,
                "reference": str(utt.get("text", "")),
                "duration_s": float(utt.get("duration") or 0.0),
                "accent": info["accent"],
                "rec_condition": info["rec_condition"],
                "role": info["role"],
                "gender": info["gender"],
                "speaker": speaker,
                # Block for the bootstrap: utterances from one speaker are not
                # independent, so resampling must be by speaker.
                "block": speaker,
            }
        )

    clips: list[dict[str, object]] = []
    group_sizes: dict[str, dict[str, int]] = {}
    for accent, items in sorted(by_accent.items()):
        # Round-robin across speakers rather than a contiguous prefix.
        # Measured reason: the prefix put ONE recording condition in each
        # accent group (Tel 100 / Lectures 121 / Podcast 100 / Talkshow 100),
        # because utterances are ordered by speaker. A per-accent table built
        # on that would compare recording conditions as much as accents.
        # Round-robin is still deterministic, so no seed is needed.
        per_speaker: dict[str, list[dict[str, object]]] = defaultdict(list)
        for item in items:
            per_speaker[str(item["speaker"])].append(item)
        chosen = []
        speakers = sorted(per_speaker)
        position = 0
        while len(chosen) < args.per_group:
            added = False
            for speaker in speakers:
                bucket = per_speaker[speaker]
                if position < len(bucket) and len(chosen) < args.per_group:
                    chosen.append(bucket[position])
                    added = True
            if not added:
                break
            position += 1
        clips.extend(chosen)
        group_sizes[accent] = {"available": len(items), "used": len(chosen)}

    manifest = {
        "group": "vietmed_accent",
        "clip_root": str(root).replace("\\", "/"),
        "license": "MIT (HF dataset tag) - paper states CC BY 4.0; CONFLICT UNRESOLVED",
        "license_branch": "permissive",
        "license_caveat": (
            "An MIT tag covers the authors' contribution and is NOT a rights "
            "audit of the underlying audio, which was collected from public "
            "sources under a fair-use argument. Local evaluation only; nothing "
            "is redistributed."
        ),
        "dataset": "leduckhai/VietMed",
        "dataset_revision": "cc7980cd1392d2d85cf1c692b1d96e8581fc7eec",
        "audio_format": "OGG/Vorbis, mono, 8000 Hz - MEASURED from the Vorbis "
        "identification header on 500 files, not taken from the paper",
        "exploratory": True,
        "limits": [
            "8 kHz telephone band. FLEURS is 16 kHz. NOT comparable; this is its "
            "own benchmark.",
            "Medical domain (consultations, lectures, podcasts, news). A real "
            "distribution mismatch for a general meeting assistant.",
            "Accent co-varies with rec_condition (7 classes); at a few hundred "
            "utterances per cell they cannot be de-confounded. A per-accent "
            "table measures accent AND recording condition.",
            "North Central Coast has 21 utterances in the whole test split and "
            "is reported as under-powered, not as a rate.",
            "Accent labels are annotator-assigned perceptual labels; the authors "
            "state they could not subdivide the North accent, so 'North' is a "
            "coarse bucket by their own admission.",
            "Overlap is present in VietMed but NOT labelled, so it is an "
            "uncontrolled confound inside these accent cells.",
            "Does NOT evidence Vietnamese accent coverage in general.",
        ],
        "per_group_cap": args.per_group,
        "group_sizes": group_sizes,
        "skipped_no_accent_label": missing_speaker,
        "skipped_missing_audio": missing_audio,
        "clips": clips,
    }
    out = pathlib.Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"speakers with accent labels: {len(meta)}")
    print(f"utterances parsed          : {len(utterances)}")
    print(f"skipped (no accent label)  : {missing_speaker}")
    print(f"skipped (audio missing)    : {missing_audio}")
    print(f"per-group cap              : {args.per_group}")
    for accent, sizes in sorted(group_sizes.items(), key=lambda kv: -kv[1]["available"]):
        flag = "  <-- UNDER-POWERED" if sizes["available"] < 50 else ""
        print(
            f"  {accent:22} available={sizes['available']:5} used={sizes['used']:4}{flag}"
        )
    print(f"clips in manifest          : {len(clips)}")
    print(
        f"rec_condition spread       : "
        f"{dict(Counter(str(c['rec_condition']) for c in clips))}"
    )
    print(f"manifest: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
