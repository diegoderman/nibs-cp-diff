"""
convert.py

Stage 3: run dcm2niix for every manifest row that doesn't have a nifti_path
yet, writing BIDS-named output into Dataset/sub-*/ses-*/anat/.

Only ever reads from raw_path - originals are never touched or deleted.
"""
import logging
import subprocess
from pathlib import Path

import pandas as pd

from bids_naming import bids_anat_dir, bids_filename
from config import (
    BIDS_DIR, PROCESSED_PATH
)

log = logging.getLogger(__name__)


def run_dcm2niix(input_path: Path, output_dir: Path, filename: str) -> None:
    cmd = [
        "dcm2niix",
        "-z", "y",
        "-o", str(output_dir),
        "-f", filename,
        str(input_path),
    ]
    subprocess.run(cmd, check=True)


def convert_all(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    if "nifti_path" not in df.columns:
        df["nifti_path"] = pd.NA

    todo = df[df["nifti_path"].isna() & df["subject"].notna() & df["session"].notna()]
    log.info("Converting %d scans", len(todo))

    for idx, row in todo.iterrows():
        out_dir = BIDS_DIR / bids_anat_dir(row["subject"], row["session"])
        out_dir.mkdir(parents=True, exist_ok=True)

        if "deeplearning" in str(row["ScanType"]):
            name = bids_filename(row["subject"], row["session"], row["run"],
                                  f"{row['ScanType'][:2]}w", acq="deeplearning")
        else:
            name = bids_filename(row["subject"], row["session"], row["run"],
                                  f"{row['ScanType']}w")

        try:
            run_dcm2niix(Path(row["raw_path"]), out_dir, name)
            df.loc[idx, "nifti_path"] = str(out_dir / name)
        except subprocess.CalledProcessError as e:
            log.error("dcm2niix failed for %s: %s", row["raw_path"], e)

    df.to_csv(PROCESSED_PATH, index=False)
    return df



