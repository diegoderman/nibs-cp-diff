#! /bin/bash

# main script for one-run scripts.

# source config file, paths and parameters will be initialized there
config_path="./config/nibs.conf"
source $config_path

##### 0. First time participant database creation

python3.9 $NIBS_SRC_DIR/first_database.py --config $config_path

######################################################################
#
# Main script 
#
######################################################################

 