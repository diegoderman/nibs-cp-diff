"""
build_scan_info.py

Stage 4: save out the demographic and partipatns information
"""
import logging
import subprocess
from pathlib import Path

import pandas as pd

from bids_naming import bids_anat_dir, bids_filename
from config import (
    MASTER_EXPECTED_PATH,PARTICIPANTS_CSV, MISSING_MRI_PATH, DATE_MATCH_TOLERANCE_DAYS,SCAN_OVERVIEW_PATH,EXTRA_SCANS_PATH
)

log = logging.getLogger(__name__)



def build_participants_csv(converted: pd.DataFrame) -> pd.DataFrame:
    """
    Build a session-level participants.csv (subject, session, age_at_mri,
    sex, group, has_mri) from the master "who should have scans" sheet,
    cross-checked against what's actually been converted.
 
 
    `has_mri` is False for any master-sheet visit with no scan within the
    tolerance window - that's your "missing" list. Those rows are also
    written separately to MISSING_MRI_PATH for a quick glance. A

    """
    master = pd.read_csv(MASTER_EXPECTED_PATH, index_col=False)
    master["mri_date"] = pd.to_datetime(master["mri_date"])
 
    # informational only: which numbered visit this is for the subject,
    # in case a visit is missing entirely and you want to know which one
    vists_lu = {"baseline_arm_1":1,"11_month_follow_up_arm_1":2,"24_month_follow_up_arm_1":3}
    master = master.sort_values(["subject", "mri_date"])
    master = master.replace({"redcap_event_name":vists_lu})
    master = master.rename(columns={"redcap_event_name":"expected_session"})

    # look at one session per subject - drop if no nifit path was made (e,g, not converted)
    scans = converted.dropna(subset=["nifti_path"])[["subject", "session", "StudyDate"]].drop_duplicates()
    scans["StudyDate"] = pd.to_datetime(scans["StudyDate"].astype(str), format="%Y%m%d", errors="coerce")
    scans = scans.dropna(subset=["StudyDate"])


    # MERGING THE MASTER AND SCANS TO FIND BEST FIT:
    # merge_asof needs both frames sorted by the match key, matched within `by` groups
    # this merges on the left, so if anything in scans isn't in master, it get skips. Therefore we do it in two stesp
    # Pass 1: master -> scans (finds has_mri for each expected visit)
    tol = pd.Timedelta(days=DATE_MATCH_TOLERANCE_DAYS)
    master_matched = pd.merge_asof(
        master.sort_values("mri_date"),
        scans.sort_values("StudyDate"),
        left_on="mri_date", right_on="StudyDate",
        by="subject", direction="nearest", tolerance=tol,
    )
    master_matched["has_mri"] = master_matched["session"].notna()
    master_matched["on_REDCap"] = True
 
    # Pass 2: scans -> master (finds scans with NO matching master visit)
    scan_matched = pd.merge_asof(
        scans.sort_values("StudyDate"),
        master[["subject", "mri_date"]].sort_values("mri_date"),
        left_on="StudyDate", right_on="mri_date",
        by="subject", direction="nearest", tolerance=tol,
    )
    unmatched_scans = scan_matched[scan_matched["mri_date"].isna()].copy()
    unmatched_scans["has_mri"] = True
    unmatched_scans["on_REDCap"] = False
    for col in ("age_at_mri", "sex", "group","expected_session"):
        unmatched_scans[col] = pd.NA
 
    master_matched["date_diff_days"] = (
        master_matched["StudyDate"] - master_matched["mri_date"]
    ).dt.days
    unmatched_scans["date_diff_days"] = pd.NA

    # SAVE OUT THE
    out_cols = ["subject", "session", "expected_session","mri_date","age_at_mri", "sex", "group", "has_mri","on_REDCap"]

    participants = pd.concat(
        [master_matched[out_cols], unmatched_scans[out_cols]], ignore_index=True
    ).sort_values(["subject", "mri_date"])


    PARTICIPANTS_CSV.parent.mkdir(parents=True, exist_ok=True)
    participants.to_csv(PARTICIPANTS_CSV, index=False)
 

    missing = participants[(~participants["has_mri"]) & (participants["on_REDCap"])]
    missing.to_csv(MISSING_MRI_PATH, index=False)
    if len(missing):
        log.warning(
            "%d expected visits have no converted MRI scan within %d days - see %s",
            len(missing), DATE_MATCH_TOLERANCE_DAYS, MISSING_MRI_PATH,
        )
 
    extra = participants[~participants["on_REDCap"]]
    extra.to_csv(EXTRA_SCANS_PATH, index=False)
    if len(extra):
        log.warning(
            "%d converted scans have no matching entry in the master sheet - see %s",
            len(extra), EXTRA_SCANS_PATH,
        )
 

    return participants


def build_scan_overview(converted: pd.DataFrame, participants: pd.DataFrame) -> pd.DataFrame:
    """
    One row per scan (subject, session, run, ScanType), with sex/age_at_mri/
    group merged in from participants.csv - a flat "what does everyone
    actually have" list, saved to BIDS_DIR/scan_overview.csv.
 
    Includes every scan in the processed manifest, whether or not it's been
    converted to nifti yet (i.e. reflects what's been found/classified, not
    just what's been successfully run through dcm2niix).
    """
    demo = participants[["subject", "session","expected_session", "age_at_mri", "sex", "group"]].drop_duplicates()

    converted=converted.dropna(subset=["nifti_path"])
    overview = (
        converted[["subject", "session", "run", "ScanType"]]
        .dropna(subset=["subject", "session"])
        .drop_duplicates()
        .merge(demo, on=["subject", "session"], how="left")
    )
 
    out_cols = ["subject", "session","expected_session", "run", "ScanType", "sex", "age_at_mri", "group"]
    overview = overview[out_cols].sort_values(["subject", "session", "ScanType", "run"])
 
    SCAN_OVERVIEW_PATH.parent.mkdir(parents=True, exist_ok=True)
    overview.to_csv(SCAN_OVERVIEW_PATH, index=False)
    log.info("Wrote scan overview (%d rows) to %s", len(overview), SCAN_OVERVIEW_PATH)
 
    return overview
