"""
clean_master.py

Turns the raw REDCap export (long format: one row per subject per
`redcap_event_name`, e.g. a screening event plus one row per MRI visit)
into the clean master sheet the rest of the pipeline expects: one row per
*completed* MRI visit, with subject, date at mri, age at mri, sex, group.

Why this works the way it does:
- Demographic fields (birthday, sex, group) are only populated on the
  screening event row in the raw export, not on the MRI visit rows. We
  broadcast them across every row for that subject using ffill+bfill
  within each subject's group - this doesn't need to know the exact
  string used for the screening event, it just fills every row from
  whichever single row actually has the value.
- Age is computed here from mri_date - birthday, rather than trusting the
  raw `alder_mr` field, so it stays correct and consistent even if that
  field is sometimes blank or entered inconsistently.
- Only rows where nibscp_mri_scan_complete == MRI_COMPLETE_VALUE are kept
  in the output - screening-only rows and not-yet-scanned visits are
  dropped.
- This is a full, stateless rebuild every time - there's no "already
  processed" tracking here (unlike the DICOM side of the pipeline). Since
  the raw export is a small spreadsheet, not thousands of scan folders,
  it's cheap to just regenerate MASTER_EXPECTED_PATH from scratch whenever
  you have a new export. Re-run this any time redcap_raw_export.csv changes.

Output columns are named to match what convert.py's MASTER_COLUMN_MAP
already expects ("date at mri", "age at mri") so nothing downstream needs
to change.
"""
import logging

import pandas as pd

from config import (RAW_MASTER_PATH, MASTER_EXPECTED_PATH)

log = logging.getLogger(__name__)

DEMOGRAPHIC_COLS = ["birthday", "sex", "group"] ## check
MRI_COMPLETE_VALUE = 2  # value of nibscp_mri_scan_complete meaning "scan was performed"


# Raw REDCap column -> internal working name, used only within clean_master.py
REDCAP_COLUMN_MAP = {
    "record_id": "subject",
    "barn_birthday": "birthday",
    "barn_cp_kontrol": "group",
    "barn_gender": "sex",
    "dato_2": "mri_date",
    "nibscp_mri_scan_complete": "mri_scan_complete"
}


def _broadcast_demographics(df: pd.DataFrame) -> pd.DataFrame:
    """Fill birthday/sex/group across every row for a subject, regardless of
    which single row in the raw export actually had them populated."""
    df = df.copy()
    df[DEMOGRAPHIC_COLS] = (
        df.groupby("subject")[DEMOGRAPHIC_COLS].transform(lambda s: s.ffill().bfill())
    )
    return df


def clean_master(raw_path=RAW_MASTER_PATH) -> pd.DataFrame:
    df = pd.read_csv(raw_path, index_col=False)
    df = df.rename(columns=REDCAP_COLUMN_MAP)

    missing_cols = [c for c in ["subject", "birthday", "sex", "group", "mri_date",
                                 "mri_scan_complete"] if c not in df.columns]
    if missing_cols:
        raise ValueError(
            f"Expected columns missing after rename: {missing_cols}. "
            "Check REDCAP_COLUMN_MAP in config.py matches your export's actual headers."
        )

    df = _broadcast_demographics(df)

    df["mri_scan_complete"] = pd.to_numeric(df["mri_scan_complete"], errors="coerce")
    df = df[df["mri_scan_complete"] == MRI_COMPLETE_VALUE].copy()

    df["birthday"] = pd.to_datetime(df["birthday"], format="mixed", errors="coerce")
    df["mri_date"] = pd.to_datetime(df["mri_date"], format="mixed", errors="coerce")

    n_bad_dates = df["birthday"].isna().sum() + df["mri_date"].isna().sum()
    if n_bad_dates:
        log.warning("%d birthday/mri_date values could not be parsed - "
                     "those rows will have a missing age_at_mri", n_bad_dates)

    df["age_at_mri"] = (df["mri_date"] - df["birthday"]).dt.days / 30.44  # months
    df["subject"] = [ a.replace("-","") for a in df["subject"]]


    keep_cols = ["subject", "mri_date", "age_at_mri", "sex", "group",
                 "redcap_event_name"]
    keep_cols = [c for c in keep_cols if c in df.columns]
    out = df[keep_cols].sort_values(["subject", "mri_date"]).reset_index(drop=True)

    n_missing_demo = out[["sex", "group"]].isna().any(axis=1).sum()
    if n_missing_demo:
        log.warning(
            "%d completed-MRI rows are still missing sex/group after broadcasting - "
            "check that subject has a screening row with those fields filled in",
            n_missing_demo,
        )

    MASTER_EXPECTED_PATH.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(MASTER_EXPECTED_PATH, index=False)
    log.info("Wrote cleaned master sheet with %d completed MRI visits to %s",
              len(out), MASTER_EXPECTED_PATH)
    return out


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    clean_master()