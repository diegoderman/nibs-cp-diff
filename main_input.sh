#! /bin/bash

# main script for one-run scripts.

# source config file, paths and parameters will be initialized there
config_path="./config/nibs.conf"
source $config_path

# if source failed, exit with error
if [ $? -ne 0 ]; then
    echo "Error: Check config file: $config_path"
    exit 1
fi



######################################################################
#
# Main script 
#
######################################################################

##### 1. DICOM to BIDS (NIfTI) conversion

$DICOM2NIIX_BIN -f %p_%s -o $NIBS_CP_BIDS $NIBS_CP_XNAT

##### 2. First time participant database creation

NIBS_DB_BASE="$NIBS_DB_DIR/sessions"

if [ -f $NIBS_DB_BASE ]; then
    if [ $VERBOSE -ge 1 ]; then
        echo "First time participant database already exists: ${NIBS_DB_BASE}.csv, skipping creation."
    fi
else
    if [ $VERBOSE -ge 1 ]; then
        echo "Creating first time participant database, reading from $NIBS_XNAT_DIR, and saving in ${NIBS_DB_BASE}.csv"
        $PYTHON_BIN $NIBS_SRC_DIR/first_database.py --output $NIBS_DB_BASE
    fi
fi



 