# NIBS-CP DICOM -> BIDS pipeline

## Stages

Can be run all at once, or one at a time. 
Some manual steps required to check IDs which are poorly formatted

```bash
python pipeline.py --stage all
python pipeline.py --stage discover   # find + read headers for new series only
python pipeline.py --stage process    # resolve IDs, assign sessions/runs
python pipeline.py --stage convert    # dcm2niix for anything not yet converted
python pipeline.py --stage report    # writes a report and saves out csv of what has been done
```

Use `--subject NIBSCP047` on `discover`/`all` to restrict a test run to one
subject before trusting it on the full dataset.


## Steps

disover: goes through all the unseen files on arc. Once run it will tell you if any IDs need reviewing. 
          Review here: IDS_NEEDING_REVIEW. Use MANIFEST_PATH to help understand the IDS

process: works out the IDS (using the manual corrections)

convert: converts to .nii and works out the partipant list. To be up to date, download latest REDCap and add here: RAW_MASTER_PATH

report: makes the latest reports of the dataset, including what is missing: REPORT_DIR


## To-Do:

Add diffusion imaging: 
            All imaging types are stored in scan_manifest.csv. Currently, I filter by structural scans types given in SCAN_TYPES. 
            To add diffusion, SCAN_TYPES in config needs updating and new BIDS naming directory (bids_naming.py)

