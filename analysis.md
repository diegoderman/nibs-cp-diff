# Input / output path analysis

Where the DICOM -> BIDS code selects its input and output directories, and
what each path is used for. Sections 1-2 describe the original code; line
numbers in `config.py` (+2 from line 12) and `nibs.conf` (+3 from line 16)
have shifted since the debug changes in section 3.1.

There are two independent entry points that both run dcm2niix:

| Entry point | How paths are set | Conversion |
|---|---|---|
| `main_input.sh` (repo root) | sources `config/nibs.conf` (bash variables) | one flat `dcm2niix` call over the whole XNAT archive |
| `Find_n_Convert/pipeline.py` | `from config import ...` -> `Find_n_Convert/config.py` | per-series `dcm2niix` into BIDS layout |

---

## 1. `Find_n_Convert` (Python pipeline)

### 1.1 Where paths are defined - `Find_n_Convert/config.py`

All paths in the Python pipeline come from this file. No other `.py` file
hardcodes a path; they only import these names.

| Line | Variable | Current value | Role |
|---|---|---|---|
| 10 | `RAW_DATA_DIR` | `/mnt/xnat/NIBS-CP/arc001` | **Input root** - raw DICOM archive |
| 11 | `PROJECT_DIR` | `/mnt/projects/NIBS-CP_BIDS/2.0` | **Output root** - everything below derives from it |
| 13 | `BIDS_DIR` | `PROJECT_DIR/Dataset_2.0` | Output - BIDS NIfTI tree |
| 14 | `INFO_DIR` | `PROJECT_DIR/Dataset_info_2.0` | Output/state - bookkeeping CSVs |
| 15 | `REPORT_DIR` | `INFO_DIR/Report` | Output - HTML reports |
| 17 | `MANIFEST_PATH` | `INFO_DIR/scan_manifest.csv` | State (read + write) - every series found |
| 18 | `PROCESSED_PATH` | `INFO_DIR/processed_scans.csv` | State (read + write) - filtered series + session/run/nifti_path |
| 19 | `ID_CORRECTIONS_PATH` | `INFO_DIR/id_corrections.csv` | **Manual input** (optional) - raw_id -> subject |
| 20 | `IDS_NEEDING_REVIEW` | `INFO_DIR/ids_needing_review.csv` | Output - unresolved IDs |
| 22 | `PARTICIPANTS_CSV` | `BIDS_DIR/participants.csv` | Output |
| 23 | `SCAN_OVERVIEW_PATH` | `BIDS_DIR/scan_overview.csv` | Output |
| 25 | `EXTRA_SCANS_PATH` | `INFO_DIR/scans_not_in_master.csv` | Output |
| 26 | `MISSING_MRI_PATH` | `INFO_DIR/missing_mri_scans.csv` | Output |
| 27 | `RAW_MASTER_PATH` | `INFO_DIR/REDCap/NIBSCP-NIBSMRISync_active.csv` | **External input (required)** - REDCap export |
| 28 | `MASTER_EXPECTED_PATH` | `INFO_DIR/master_expected_scans.csv` | Intermediate - written by `clean_master`, read by `build_scan_info` |

`RAW_DATA_DIR` and `PROJECT_DIR` (lines 10-11) are the only two roots. All
other paths are built from them.

### 1.2 Where paths are consumed

| File:line | Uses | Read / write |
|---|---|---|
| `pipeline.py:20,38` | `RAW_DATA_DIR` -> `discover_and_extract()` | read |
| `pipeline.py:41,54,56,66-70,74,79` | `MANIFEST_PATH`, `PROCESSED_PATH` | read + write |
| `discover_and_extract.py:27-28, 99-100` | `MANIFEST_PATH` | read + write |
| `discover_and_extract.py:63-80` | walks `RAW_DATA_DIR` | read (see 1.3) |
| `clean_master.py:65-66` | `RAW_MASTER_PATH` | read |
| `clean_master.py:107-108` | `MASTER_EXPECTED_PATH` | write |
| `id_resolution.py:36-37` | `ID_CORRECTIONS_PATH` | read (skipped if missing) |
| `id_resolution.py:65-66` | `IDS_NEEDING_REVIEW` | write |
| `convert.py:25` | **dcm2niix binary** - bare `"dcm2niix"`, resolved from `$PATH` | exec |
| `convert.py:43-44` | `BIDS_DIR / sub-X/ses-Y/anat` | write (NIfTI) |
| `convert.py:54` | `row["raw_path"]` (absolute path stored in the manifest) | read (DICOM) |
| `convert.py:59` | `PROCESSED_PATH` | write |
| `build_scan_info.py:33` | `MASTER_EXPECTED_PATH` | read |
| `build_scan_info.py:89-90, 94, 102` | `PARTICIPANTS_CSV`, `MISSING_MRI_PATH`, `EXTRA_SCANS_PATH` | write |
| `build_scan_info.py:136-137` | `SCAN_OVERVIEW_PATH` | write |
| `report.py:139-142` | `PARTICIPANTS_CSV`, `SCAN_OVERVIEW_PATH`, `MISSING_MRI_PATH`, `EXTRA_SCANS_PATH` | read |
| `report.py:238-242` | `REPORT_DIR` | write |
| `bids_naming.py:12-13` | `bids_anat_dir()` -> `sub-{sub}/ses-{ses}/anat` | subdir under `BIDS_DIR` |
| `playground.ipynb` (cell 2, 3) | `INFO_DIR/Playground`, `INFO_DIR/missing_mri_scans_investgiate.csv` | scratch notebook, not part of the pipeline |

### 1.3 Expected raw-data layout (`discover_and_extract.py:63-80`)

```
RAW_DATA_DIR/
  <patient_dir>/            # e.g. NIBS-CP085_01  (line 63)
    SCANS/                  # line 71
      <n>/                  # numbered series, Siemens order (line 75)
        DICOM/              # line 76  <- required
          *.dcm             # line 80  <- only files ending in .dcm are found
```

- So `RAW_DATA_DIR` must be the folder **containing** `NIBS-CP085_01`, i.e.
  `debug_rawdata/`, not `debug_rawdata/NIBS-CP085_01/SCANS`.
- Each series must have a `DICOM/` subfolder with `.dcm` files. Series
  without one are skipped silently. Check this on the cluster copy (see 3.2).
- The subject ID comes from the `PatientName` DICOM header
  (`id_resolution.py:61`), not from the folder name.
- `--subject` filters on the **folder name** (`discover_and_extract.py:66`).
  For this debug data use `--subject NIBS-CP085`. `NIBSCP085`, the form the
  README suggests, won't match.

### 1.4 Stage order and what each stage needs

```
discover : clean_master (needs RAW_MASTER_PATH)  -> discover_and_extract (RAW_DATA_DIR)
           -> resolve_subject_ids (ID_CORRECTIONS_PATH optional)
process  : MANIFEST_PATH -> classify/sessions/runs -> PROCESSED_PATH
convert  : PROCESSED_PATH -> dcm2niix -> BIDS_DIR/sub-*/ses-*/anat
report   : PROCESSED_PATH + MASTER_EXPECTED_PATH -> participants/overview CSVs -> REPORT_DIR
```

### 1.5 Working directory

Modules import each other as top-level modules (`from config import ...`), so
`pipeline.py` must be run from inside `Find_n_Convert/`. The paths are
currently absolute, so the working directory doesn't affect them.

---

## 2. Shell entry point (`main_input.sh` + `config/nibs.conf`)

### 2.1 `config/nibs.conf`

| Line | Variable | Current value | Role |
|---|---|---|---|
| 6-8 | hostname guard | exits unless `$HOSTNAME` ends in `.drcmr` | - |
| 17 | `NIBS_CP_XNAT` | `/mnt/xnat/NIBS-CP/arc001` | **Input** - raw DICOM archive |
| 18 | `NIBS_CP_PROJ` | `/mnt/projects/NIBS-CP` | base for the dcm2niix path |
| 20 | `NIBS_CP_BIDS` | `/mnt/projects/NIBS-CP_BIDS` | **Output** - NIfTI |
| 23 | `DIFF_PIPELINE_DIR` | `/mnt/projects/NIBS-CP/nibs-cp-diff` | repo location on the cluster |
| 24-25 | `DIFF_SRC_DIR`, `DIFF_CONFIG_DIR` | `$DIFF_PIPELINE_DIR/src`, `/config` | `src/` doesn't exist in this repo |
| 28 | `PYTHON_BIN` | `$DIFF_PIPELINE_DIR/env/bin/python` | conda env (git-ignored) |
| 30 | `DICOM2NIIX_BIN` | `${NIBS_CP_PROJ}/Code/dcm2niix` = `/mnt/projects/NIBS-CP/Code/dcm2niix` | **dcm2niix binary (original path)** |
| 34 | `NIBS_DB_DIR` | `$DIFF_PIPELINE_DIR/db` | output for step 2 of `main_input.sh` |

### 2.2 `main_input.sh`

| Line | What |
|---|---|
| 6-7 | sources `./config/nibs.conf` - relative, so must be run from the repo root |
| 25 | `$DICOM2NIIX_BIN -f %i_%p_%s -o $NIBS_CP_BIDS $NIBS_CP_XNAT` - **the only active I/O line** |
| 27 | `exit 0` - everything below is unreachable |
| 30-41 | (dead) DB creation, uses `NIBS_DB_DIR` and `NIBS_SRC_DIR` (undefined - the conf defines `DIFF_SRC_DIR`) and `first_database.py` (not in repo) |

Line 25 recursively converts the whole input tree into one flat output folder,
named `<PatientID>_<Protocol>_<Series>`. This is **not** BIDS. The BIDS
layout comes only from the Python pipeline.

---

## 3. Summary for the debug setup

### 3.1 Lines changed (step 3)

Only the input and output roots were changed. Every derived path
(`BIDS_DIR`, `INFO_DIR`, `REPORT_DIR`, `RAW_MASTER_PATH`,
`MASTER_EXPECTED_PATH`, ...) is still defined relative to `PROJECT_DIR`.

| File:line | Variable | Debug value |
|---|---|---|
| `Find_n_Convert/config.py:11` | `REPO_DIR` (new) | `Path(__file__).resolve().parents[1]` |
| `Find_n_Convert/config.py:12` | `RAW_DATA_DIR` | `REPO_DIR/debug_rawdata` |
| `Find_n_Convert/config.py:13` | `PROJECT_DIR` | `REPO_DIR/debug_preprocessing/debug_nifti` |
| `config/nibs.conf:17` | `REPO_DIR` (new) | parent of the conf file's own directory |
| `config/nibs.conf:20` | `NIBS_CP_XNAT` | `$REPO_DIR/debug_rawdata` |
| `config/nibs.conf:23` | `NIBS_CP_BIDS` | `$REPO_DIR/debug_preprocessing/debug_nifti` |

The original values are kept as `# DEBUG:` comments next to the changes.
Because `REPO_DIR` is derived rather than hardcoded, the paths work from the
cluster clone wherever it lives.

dcm2niix is unchanged in both entry points:

- `main_input.sh` uses `DICOM2NIIX_BIN` (`nibs.conf:33`) =
  `/mnt/projects/NIBS-CP/Code/dcm2niix`.
- `convert.py:25` calls bare `"dcm2niix"`, which is looked up on `$PATH`.
  `environment.yml:6` installs dcm2niix into the conda env, so this is
  normally the env's copy. It is not necessarily the same binary or version
  as `DICOM2NIIX_BIN`.

Resulting layout:

```
debug_rawdata/NIBS-CP085_01/SCANS/<n>/DICOM/*.dcm              input
debug_preprocessing/debug_nifti/
  Dataset_2.0/sub-*/ses-*/anat/...                             BIDS_DIR (Python pipeline)
  Dataset_2.0/participants.csv, scan_overview.csv
  Dataset_info_2.0/                                            INFO_DIR
    REDCap/NIBSCP-NIBSMRISync_active.csv                       must be placed here by hand
    scan_manifest.csv, processed_scans.csv, master_expected_scans.csv, ...
    Report/                                                    REPORT_DIR
  <PatientID>_<Protocol>_<Series>.nii                          main_input.sh output (flat)
```

### 3.2 Components not available in the debug setup

| Component | Path | Effect if missing |
|---|---|---|
| REDCap export | `RAW_MASTER_PATH` = `debug_nifti/Dataset_info_2.0/REDCap/NIBSCP-NIBSMRISync_active.csv` | Will be supplied at that path. If it is absent, the **`discover` stage crashes** at `pipeline.py:37` (`clean_master()` -> `FileNotFoundError`) before any DICOM is read, and `report` also fails (needs `MASTER_EXPECTED_PATH`). |
| `id_corrections.csv` | `ID_CORRECTIONS_PATH` | Fine - skipped. IDs that can't be auto-fixed go to `ids_needing_review.csv`. |
| `DICOM/` subfolder with `*.dcm` | inside each `SCANS/<n>/` | Can't verify from here (data is cluster-only). If the series contain DICOMs directly, or the files don't end in `.dcm`, nothing is discovered. |
| `src/`, `first_database.py`, `env/` | `nibs.conf:24,28`, `main_input.sh:39` | Only used by dead code after `exit 0`. `env/` must be created on the cluster. |

### 3.3 Observations relevant to diffusion (outside the path task)

- `session_run_assign.py:18` keeps only `MRAcquisitionType == "3D"`. Diffusion
  EPI is 2D, so the `dwi`/`epi` entries added to `SCAN_TYPES`
  (`config.py:47-48`) are filtered out before conversion.
- The diffusion keys in `config.py:47-48` start with `SCANS_`. Check that this
  matches the real `SeriesDescription` header value.
- `convert.py:43` always writes to `anat/`, and `convert.py:51` names files
  `{ScanType}w`, so diffusion would become `anat/..._dwiw`. BIDS expects
  `dwi/..._dwi` and `fmap/..._epi`. The README to-do already mentions this
  (`bids_naming.py`).
