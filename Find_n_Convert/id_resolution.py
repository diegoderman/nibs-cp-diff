"""
id_resolution.py

Stage 2a: turn raw PatientName / PatientID values into clean BIDS subject
IDs (NIBSCPxxx), using:
  1. a few automatic regex-based fixes for known patterns, and
  2. a manual lookup table (id_corrections.csv) for anything that isn't
     automatically fixable.

Nothing here calls input() - the pipeline runs unattended every few months,
so anything that can't be resolved is written to ids_needing_review.csv for
a human to fill in (and copy into id_corrections.csv) before the next run.
"""
import logging
import re

import pandas as pd

from config import SUBJECT_PATTERN, ID_CORRECTIONS_PATH, IDS_NEEDING_REVIEW

log = logging.getLogger(__name__)


def _auto_fix(raw_id: str) -> str:
    pid = raw_id
    if pid[:7] == "NIBS-CP":
        pid = "NIBSCP" + pid[7:]
    if "_" in pid:
        pid = pid.split("_")[0]
    if "nibs-cp" in pid.lower():
        pid = "NIBSCP" + pid.lower().split("nibs-cp")[1]
    return pid


def _load_corrections() -> dict:
    if ID_CORRECTIONS_PATH.exists():
        corr = pd.read_csv(ID_CORRECTIONS_PATH, index_col=False)
        return dict(zip(corr["raw_id"], corr["subject"]))
    return {}


def resolve_subject_ids(manifest: pd.DataFrame) -> pd.DataFrame: # load in manifest scan folder
    corrections = _load_corrections()
    unresolved = []

    def resolve(raw_id):
        if pd.isna(raw_id):
            unresolved.append(raw_id)
            return pd.NA
        if re.match(SUBJECT_PATTERN, raw_id):
            return raw_id
        if raw_id in corrections:
            return corrections[raw_id]
        fixed = _auto_fix(raw_id)
        if re.match(SUBJECT_PATTERN, fixed):
            return fixed
        unresolved.append(raw_id)
        return pd.NA

    manifest = manifest.copy()
    manifest["subject"] = manifest["PatientName"].apply(resolve)

    if unresolved:
        review_df = pd.DataFrame({"raw_id": sorted(set(map(str, unresolved))), "subject": ""})
        IDS_NEEDING_REVIEW.parent.mkdir(parents=True, exist_ok=True)
        review_df.to_csv(IDS_NEEDING_REVIEW, index=False)
        log.warning(
            "%d subject IDs could not be resolved automatically. "
            "Fill in %s (raw_id -> correct subject) and merge it into %s, then re-run.",
            len(set(unresolved)), IDS_NEEDING_REVIEW, ID_CORRECTIONS_PATH,
        )

    return manifest
