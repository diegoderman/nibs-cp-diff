"""
discover_and_extract.py

Stage 1 of the pipeline.

Walks the raw directory and finds every scan SERIES folder. For any series not already in the
manifest, it reads ONE representative dicom file to pull out the header
fields we care about.

"""
import logging
from pathlib import Path

import numpy as np
import pandas as pd
import pydicom

from config import KEY_DCM_HEADERS, MANIFEST_PATH

log = logging.getLogger(__name__)

SKIP_TOKENS = ("pilot", "phantom", "phanthom") # skip the phantoms 
ID_TOKENS = ("nibs",)  # matched case-insensitively


def _load_manifest() -> pd.DataFrame:
    if MANIFEST_PATH.exists():
        return pd.read_csv(MANIFEST_PATH, index_col=False)
    cols = ["raw_path", "sample_dcm_path"] + KEY_DCM_HEADERS
    return pd.DataFrame(columns=cols)


def _pick_representative_file(dcm_files: list) -> Path:
    """Any single slice carries the header fields we want, so just take the
    first one (sorted for determinism)."""
    return sorted(dcm_files)[0]


def _read_headers(dcm_path: Path):
    try:
        ds = pydicom.dcmread(dcm_path, stop_before_pixels=True)
    except Exception as e:
        log.warning("Could not read %s (%s) - skipping series", dcm_path, e)
        return None

    row = {}
    for key in KEY_DCM_HEADERS:
        try:
            value = ds[key].value
            row[key] = "".join(value) if key == "PatientName" else value
        except Exception:
            row[key] = np.nan
    return row


def discover_and_extract(raw_data_dir: Path, subject_filter: str = None) -> pd.DataFrame:
    manifest = _load_manifest()
    known_paths = set(manifest["raw_path"].astype(str))

    new_rows = []
    unrecognised_ids = []

    for patient_dir in sorted(Path(raw_data_dir).iterdir()):
        patient_id = patient_dir.name

        if subject_filter and subject_filter not in patient_id: # teting shortcut
            continue
        if any(tok in patient_id.lower() for tok in SKIP_TOKENS): # skips our pilots/test/etc
            continue

        scans_dir = patient_dir / "SCANS" # all the scans for that subject
        if not scans_dir.exists():
            continue

        for scan_dir in sorted(scans_dir.iterdir()): # skip if we have processed this already
            series_dir = scan_dir / "DICOM"
            if str(series_dir) in known_paths:
                continue  # already in the manifest, nothing to do

            dcm_files = list(series_dir.glob("*.dcm")) # finds my dicoms
            if not dcm_files:
                continue

            rep_file = _pick_representative_file(dcm_files) # read one file not all of dicom stack
            headers = _read_headers(rep_file)
            if headers is None:
                continue

            headers["raw_path"] = str(series_dir) # update spreadsheet 
            headers["sample_dcm_path"] = str(rep_file)
            new_rows.append(headers)

    if unrecognised_ids:
        log.warning("Unrecognised patient folder names (skipped): %s",
                     sorted(set(unrecognised_ids)))

    if new_rows:
        manifest = pd.concat([manifest, pd.DataFrame(new_rows)], ignore_index=True)
        MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)
        manifest.to_csv(MANIFEST_PATH, index=False)
        log.info("Added %d new series to manifest (%d total)", len(new_rows), len(manifest))
    else:
        log.info("No new series found - manifest already up to date (%d total)", len(manifest))

    return manifest
