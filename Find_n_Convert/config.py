"""
config.py
Central configuration for the NIBS-CP DICOM -> BIDS pipeline.
Edit the paths and lookup tables here; the rest of the pipeline shouldn't
need to change.
"""
from pathlib import Path

# ---- Paths -----------------------------------------------------------
RAW_DATA_DIR = Path("/mnt/xnat/NIBS-CP/arc001")                          # where SCANS/ folders live
PROJECT_DIR  = Path("/mnt/projects/NIBS-CP_BIDS/2.0")

BIDS_DIR     = PROJECT_DIR / "Dataset_2.0"
INFO_DIR     = PROJECT_DIR / "Dataset_info_2.0"
REPORT_DIR     = PROJECT_DIR / "Dataset_info_2.0" / "Report"

MANIFEST_PATH         = INFO_DIR / "scan_manifest.csv"        # raw, append-only, ALL series
PROCESSED_PATH        = INFO_DIR / "processed_scans.csv"      # anatomical subset + session/run/nifti_path
ID_CORRECTIONS_PATH   = INFO_DIR / "id_corrections.csv"       # manually corrected ids
IDS_NEEDING_REVIEW    = INFO_DIR / "ids_needing_review.csv"   # ids to review

PARTICIPANTS_CSV      = BIDS_DIR / "participants.csv"
SCAN_OVERVIEW_PATH    = BIDS_DIR / "scan_overview.csv"

EXTRA_SCANS_PATH      = INFO_DIR / "scans_not_in_master.csv"
MISSING_MRI_PATH       = INFO_DIR / "missing_mri_scans.csv"
RAW_MASTER_PATH = INFO_DIR / "REDCap" / "NIBSCP-NIBSMRISync_active.csv"   #  For sanity checks
MASTER_EXPECTED_PATH  = INFO_DIR / "master_expected_scans.csv"   # who *should* have scans

# ---- DICOM headers to keep --------------------------------------------
KEY_DCM_HEADERS = [
    "PatientName", "PatientID", "StudyDate", "PatientBirthDate",
    "PatientWeight", "PatientSize", "ProtocolName", "MRAcquisitionType",
    "AcquisitionDateTime", "VolumeBasedCalculationTechnique", "SeriesDescription",
]

# ---- Series description -> BIDS modality label -------------------------
# TO-DO: Add diffusion imaging here to find those imaging modalities
SCAN_TYPES = {
    "t1_mprage_sag_p4_iso": "T1",
    "t2_space_sag_p4_iso_HBCD": "T2",
    "wip_SPACE_997_v01_space_997_0.8": "T2_deeplearning",
    "wip_963_mprage_0.8_200": "T1_deeplearning",
    "SAG T1 MPRAGE_tr2200": "T1",
    "t2_space_sag_p4_iso_0,8_latest": "T2",
    "t2_space_sag_p4_iso": "T2",
    "SCANS_cmrr_mbep2d_diff_NIBS-CP40010002600_APref_MB3": "epi",
    "SCANS_cmrr_mbep2d_diff_NIBS-CP40010002600_MB3": "dwi",
}

SUBJECT_PATTERN = r"^NIBSCP\d{3}$"
SESSION_PATTERN = r"^ses-\d{3}$"


DATE_MATCH_TOLERANCE_DAYS = 5 # how many days between scan day and reported scan day (for subject matching in build_scan_info.py)