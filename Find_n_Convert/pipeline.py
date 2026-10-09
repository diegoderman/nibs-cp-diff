"""
pipeline.py

Entry point. Run periodically (e.g. every few months) as new scans come in:

    python pipeline.py --stage all

Each stage only processes what hasn't been processed yet, so re-running is
cheap and never touches already-converted data. Raw DICOMs are only ever
read, never modified or deleted.

Use --subject to restrict the discover stage to one subject while testing
changes (mirrors the old TEST_FLAG approach, without hardcoding it in).
"""
import argparse
import logging

import pandas as pd

from config import RAW_DATA_DIR, MANIFEST_PATH,PROCESSED_PATH
from discover_and_extract import discover_and_extract
from id_resolution import resolve_subject_ids
from session_run_assign import classify_and_filter, assign_sessions, assign_runs
from convert import convert_all
from clean_master import clean_master
from build_scan_info import build_participants_csv,build_scan_overview
from report import generate_report
 

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)


def main(stage: str, subject_filter: str = None):

    if stage in ("discover", "all"):
        clean_master() # get up-to-date with the master
        discover_and_extract(RAW_DATA_DIR, subject_filter=subject_filter)

        # Find the incorrection IDs
        manifest = pd.read_csv(MANIFEST_PATH, index_col=False)
        manifest = resolve_subject_ids(manifest)
        n_unresolved = manifest["subject"].isna().sum()
        if n_unresolved:
            log.warning(
                "%d scans have an unresolved subject ID and will be skipped until "
                "fixed in id_corrections.csv (see ids_needing_review.csv)",
                n_unresolved,
            )

    if stage in ("process", "all"):

        # Only looking at the resolved veresions = the repeat from before after manual input
        manifest = pd.read_csv(MANIFEST_PATH, index_col=False)
        manifest = resolve_subject_ids(manifest)
        manifest.to_csv(MANIFEST_PATH, index=False) # keep the FULL raw manifest intact,
                                                    # now with subject filled in where possible


        resolved = manifest[manifest["subject"].notna()]
        df = classify_and_filter(resolved)
        df = assign_sessions(df)
        df = assign_runs(df)
 
        # carry over any nifti_path already recorded from a previous convert run
        if PROCESSED_PATH.exists():
            prev = pd.read_csv(PROCESSED_PATH, index_col=False)
            if "nifti_path" in prev.columns:
                df = df.merge(prev[["raw_path", "nifti_path"]], on="raw_path", how="left")
        df.to_csv(PROCESSED_PATH, index=False)
 

    if stage in ("convert", "all"):
        processed = pd.read_csv(PROCESSED_PATH, index_col=False)
        convert_all(processed)


    if stage in ("report", "all"):  
        processed = pd.read_csv(PROCESSED_PATH, index_col=False)      
        participants = build_participants_csv(processed)
        build_scan_overview(processed, participants)
        generate_report()

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--stage",
        choices=["discover", "process", "convert", "report", "all"],
        default="all",
    )
    parser.add_argument("--subject", default=None, help="Restrict discovery to one subject ID (testing)")
    args = parser.parse_args()
    main(args.stage, subject_filter=args.subject)
