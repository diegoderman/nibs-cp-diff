"""
bids_naming.py - BIDS filename / directory helpers.
"""
from typing import Optional


def bids_filename(sub: str, ses: str, run: str, modality: str, acq: Optional[str] = None) -> str:
    acq_part = f"_acq-{acq}" if acq else ""
    return f"sub-{sub}_ses-{ses}{acq_part}_run-{run}_{modality}"


def bids_anat_dir(sub: str, ses: str) -> str:
    return f"sub-{sub}/ses-{ses}/anat"
