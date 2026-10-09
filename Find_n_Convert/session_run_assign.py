"""
session_run_assign.py

Stage 2b: classify scan type, assign session numbers (chronological per
subject) and run numbers (per subject/session/scan type)

"""
import logging
import pandas as pd
from config import SCAN_TYPES

log = logging.getLogger(__name__)


def classify_and_filter(manifest: pd.DataFrame) -> pd.DataFrame:
    """Keep only the 3D anatomical, non-reconstruction series we care about."""
    df = manifest.copy()
    df = df[df["MRAcquisitionType"] == "3D"]
    df = df[df["SeriesDescription"].isin(SCAN_TYPES.keys())]
    df["ScanType"] = df["SeriesDescription"].map(SCAN_TYPES)
    return df


def assign_sessions(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["session"] = pd.NA
    for subject, sub_df in df.groupby("subject"):
        ses_df = (
            sub_df.drop_duplicates(subset=["StudyDate"])
            .sort_values("StudyDate")
            .reset_index()
        )
        for i, date in enumerate(ses_df["StudyDate"], start=1):
            df.loc[(df["subject"] == subject) & (df["StudyDate"] == date), "session"] = f"{i:03}"
    return df



def assign_runs(df: pd.DataFrame) -> pd.DataFrame:
    df = df.sort_values("AcquisitionDateTime").copy()
    df["run"] = (
        df.groupby(["subject", "session", "ScanType"]).cumcount().add(1).astype(str)
    )
 
    # letter suffix when several rows land on the same subject/session/type/run
    group_cols = ["subject", "session", "ScanType", "run"]
    n_missing = df[group_cols].isna().any(axis=1).sum()
    if n_missing:
        raise ValueError(
            f"{n_missing} rows have a missing value in {group_cols} - "
            "resolve subject IDs / sessions before calling assign_runs()"
        )
    suffix = df.groupby(group_cols).cumcount().astype(int).map(lambda x: chr(ord("a") + x))
    group_size = df.groupby(group_cols)["run"].transform("size")
    df.loc[group_size > 1, "run"] = df.loc[group_size > 1, "run"] + suffix[group_size > 1]
 
    return df
