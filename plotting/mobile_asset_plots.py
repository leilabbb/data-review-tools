#!/usr/bin/env python
"""
Created on Apr 11 2019 by Lori Garzio
@brief This is a wrapper script that imports tools to plot data for mobile assets (profilers and gliders.
@usage
sDir: location to save summary output
f: file containing THREDDs urls with .nc files to analyze. The column containing the THREDDs urls must be labeled
'outputUrl' (e.g. an output from one of the data_download scripts)
start_time: optional start time to limit plotting time range
end_time: optional end time to limit plotting time range
preferred_only: if set to 'yes', only plots the preferred data for a deployment. Options are 'yes' or 'no'
"""

import pandas as pd
import datetime as dt
import scripts
import data_review.scripts

sDir = '/Users/lgarzio/Documents/OOI/DataReviews'
mDir = '/Users/lgarzio/Documents/repo/OOI/ooi-data-lab/data-review-tools/data_review/data_ranges'
f = '/Users/lgarzio/Documents/OOI/DataReviews/CE/CE05MOAS/data_request_summary_gl319_copy.csv'
start_time = None  # dt.datetime(2016, 9, 1, 0, 0, 0)  # optional, set to None if plotting all data
end_time = None  # dt.datetime(2016, 10, 1, 0, 0, 0)  # optional, set to None if plotting all data
preferred_only = 'yes'  # options: 'yes', 'no'

zdbar = None  # remove data below this depth for analysis and plotting
n_std = None
inpercentile = .5

zcell_size = 10  # depth cell size for data grouping
deployment_num = None  # 3

ff = pd.read_csv(f)
url_list = ff['outputUrl'].tolist()
url_list = [u for u in url_list if u not in 'no_output_url']

scripts.map_gliders.main(url_list, sDir, 'glider_track', start_time, end_time, deployment_num)
scripts.plot_profile_xsection.main(url_list, sDir, deployment_num, start_time, end_time, preferred_only, n_std, inpercentile, zcell_size)
scripts.plot_profile_xsection_rm_suspect_data.main(url_list, sDir, deployment_num, start_time, end_time, preferred_only, zdbar, n_std, inpercentile, zcell_size)
data_review.scripts.mobile_data_range.main(url_list, sDir, mDir, zcell_size, zdbar, start_time, end_time)