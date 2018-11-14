#!/usr/bin/env python
"""
Created on Feb 2 2017 by Mike Smith
Modified on Oct 8 2018 by Lori Garzio
@brief Automated analysis of .nc files from a THREDDs server. Provides a json output by reference designator.
sDir: location to save summary output
url: list of THREDDs urls containing .nc files to analyze.
"""

import os
import xarray as xr
import pandas as pd
import re
import numpy as np
from collections import OrderedDict
import json
import datetime as dt
from datetime import timedelta
import netCDF4 as nc
import functions.common as cf
import functions.plotting as pf


def compare_lists(list1, list2):
    match = []
    unmatch = []
    for i in list1:
        if i in list2:
            match.append(i)
        else:
            unmatch.append(i)
    return match, unmatch


def eliminate_common_variables(list):
    # time is in this list because it doesn't show up as a variable in an xarray ds
    common = ['quality_flag', 'provenance', 'id', 'deployment', 'obs', 'lat', 'lon']
    regex = re.compile(r'\b(?:%s)\b' % '|'.join(common))
    list = [s for s in list if not regex.search(s)]
    return list


def get_deployment_information(data, deployment):
    d_info = [x for x in data['instrument']['deployments'] if x['deployment_number'] == deployment]
    if d_info:
        return d_info[0]
    else:
        return None


def insert_into_dict(d, key, value):
    if key not in d:
        d[key] = [value]
    else:
        d[key].append(value)
    return d


def main(sDir, url_list):
    reviewlist = pd.read_csv(
        'https://raw.githubusercontent.com/data-edu-ooi/data-review-tools/master/review_list/data_review_list.csv')

    rd_list = []
    for uu in url_list:
        elements = uu.split('/')[-2].split('-')
        rd = '-'.join((elements[1], elements[2], elements[3], elements[4]))
        if rd not in rd_list:
            rd_list.append(rd)

    json_file_list = []
    for r in rd_list:
        print('\n{}'.format(r))
        data = OrderedDict(deployments=OrderedDict())
        save_dir = os.path.join(sDir, r.split('-')[0], r)
        cf.create_dir(save_dir)

        # Deployment location test
        deploy_loc_test = cf.deploy_location_check(r)
        data['location_comparison'] = deploy_loc_test

        for u in url_list:
            splitter = u.split('/')[-2].split('-')
            rd_check = '-'.join((splitter[1], splitter[2], splitter[3], splitter[4]))
            catalog_rms = '-'.join((r, splitter[-2], splitter[-1]))

            # complete the analysis by reference designator
            if rd_check == r:
                udatasets = cf.get_nc_urls([u])

                # check for the OOI 1.0 datasets for review
                rl_filtered = reviewlist.loc[
                    (reviewlist['Reference Designator'] == r) & (reviewlist['status'] == 'for review')]
                review_deployments = rl_filtered['deploymentNumber'].tolist()
                review_deployments_int = ['deployment%04d' % int(x) for x in review_deployments]
                for rev_dep in review_deployments_int:
                    rdatasets = [s for s in udatasets if rev_dep in s]
                    if len(rdatasets) > 0:
                        datasets = []
                        for dss in rdatasets:  # filter out collocated data files
                            if catalog_rms in dss.split('/')[-1].split('_20')[0]:
                                datasets.append(dss)

                        notes = []
                        time_ascending = ''
                        if len(datasets) == 1:
                            ds = xr.open_dataset(datasets[0], mask_and_scale=False)
                            ds = ds.swap_dims({'obs': 'time'})
                            fname, subsite, refdes, method, data_stream, deployment = cf.nc_attributes(datasets[0])
                        else:
                            ds = xr.open_mfdataset(datasets, mask_and_scale=False)
                            ds = ds.swap_dims({'obs': 'time'})
                            ds = ds.chunk({'time': 100})
                            fname, subsite, refdes, method, data_stream, deployment = cf.nc_attributes(datasets[0])
                            fname = fname.split('_20')[0]
                            notes.append('multiple deployment .nc files')
                            # when opening multiple datasets, don't check that the timestamps are in ascending order
                            time_ascending = 'not_tested'

                        print('\nAnalyzing file: {}'.format(fname))

                        # Get info from the data review database
                        dr_data = cf.refdes_datareview_json(refdes)
                        stream_vars = cf.return_stream_vars(data_stream)
                        sci_vars = cf.return_science_vars(data_stream)
                        deploy_info = get_deployment_information(dr_data, int(deployment[-4:]))

                        # Grab deployment Variables
                        deploy_start = str(deploy_info['start_date'])
                        deploy_stop = str(deploy_info['stop_date'])
                        deploy_lon = deploy_info['longitude']
                        deploy_lat = deploy_info['latitude']
                        deploy_depth = deploy_info['deployment_depth']

                        # Calculate days deployed
                        if deploy_stop != 'None':
                            r_deploy_start = pd.to_datetime(deploy_start).replace(hour=0, minute=0, second=0)
                            if deploy_stop.split('T')[1] == '00:00:00':
                                r_deploy_stop = pd.to_datetime(deploy_stop)
                            else:
                                r_deploy_stop = (pd.to_datetime(deploy_stop) + timedelta(days=1)).replace(hour=0, minute=0, second=0)
                            n_days_deployed = (r_deploy_stop - r_deploy_start).days
                        else:
                            n_days_deployed = None

                        # Add reference designator to dictionary
                        try:
                            data['refdes']
                        except KeyError:
                            data['refdes'] = refdes

                        deployments = data['deployments'].keys()
                        data_start = pd.to_datetime(min(ds['time'].data)).strftime('%Y-%m-%dT%H:%M:%S')
                        data_stop = pd.to_datetime(max(ds['time'].data)).strftime('%Y-%m-%dT%H:%M:%S')

                        # Add deployment and info to dictionary and initialize delivery method sub-dictionary
                        if deployment not in deployments:
                            data['deployments'][deployment] = OrderedDict(deploy_start=deploy_start,
                                                                          deploy_stop=deploy_stop,
                                                                          n_days_deployed=n_days_deployed,
                                                                          lon=deploy_lon,
                                                                          lat=deploy_lat,
                                                                          deploy_depth=deploy_depth,
                                                                          method=OrderedDict())

                        # Add delivery methods to dictionary and initialize stream sub-dictionary
                        methods = data['deployments'][deployment]['method'].keys()
                        if method not in methods:
                            data['deployments'][deployment]['method'][method] = OrderedDict(
                                stream=OrderedDict())

                        # Add streams to dictionary and initialize file sub-dictionary
                        streams = data['deployments'][deployment]['method'][method]['stream'].keys()

                        if data_stream not in streams:
                            data['deployments'][deployment]['method'][method]['stream'][
                                data_stream] = OrderedDict(file=OrderedDict())

                        # Get a list of data gaps >1 day
                        time_df = pd.DataFrame(ds['time'].data, columns=['time'])
                        gap_list = cf.timestamp_gap_test(time_df)

                        # Calculate the sampling rate to the nearest second
                        time_df['diff'] = time_df['time'].diff().astype('timedelta64[s]')
                        rates_df = time_df.groupby(['diff']).agg(['count'])
                        n_diff_calc = len(time_df) - 1
                        rates = dict(n_unique_rates=len(rates_df), common_sampling_rates=dict())
                        for i, row in rates_df.iterrows():
                            percent = (float(row['time']['count']) / float(n_diff_calc))
                            if percent > 0.1:
                                rates['common_sampling_rates'].update({int(i): '{:.2%}'.format(percent)})

                        if len(rates['common_sampling_rates']) == 1:
                            if float(list(rates['common_sampling_rates'].values())[0].strip('%')) > 75.00:
                                sampling_rt_sec = list(rates['common_sampling_rates'].keys())[0]
                            else:
                                sampling_rt_sec = 'no consistent sampling rate: {}'.format(rates['common_sampling_rates'])
                        else:
                            sampling_rt_sec = 'no consistent sampling rate: {}'.format(rates['common_sampling_rates'])

                        # Check that the timestamps in the file are unique
                        time = ds['time']
                        len_time = time.__len__()
                        len_time_unique = np.unique(time).__len__()
                        if len_time == len_time_unique:
                            time_test = 'pass'
                        else:
                            time_test = 'fail'

                        # Check that the timestamps in the file are in ascending order
                        if time_ascending != 'not_tested':
                            # convert time to number
                            time_in = [dt.datetime.utcfromtimestamp(np.datetime64(x).astype('O')/1e9) for x in
                                       ds['time'].values]
                            time_data = nc.date2num(time_in, 'seconds since 1900-01-01')

                            # Create a list of True or False by iterating through the array of time and checking
                            # if every time stamp is increasing
                            result = [(time_data[k + 1] - time_data[k]) > 0 for k in range(len(time_data) - 1)]

                            # Print outcome of the iteration with the list of indices when time is not increasing
                            if result.count(True) == len(time) - 1:
                                time_ascending = 'pass'
                            else:
                                ind_fail = {k: time_in[k] for k, v in enumerate(result) if v is False}
                                time_ascending = 'fail: {}'.format(ind_fail)

                        # Count the number of days for which there is at least 1 timestamp
                        n_days = len(np.unique(time.data.astype('datetime64[D]')))

                        # Compare variables in file to variables in Data Review Database
                        ds_variables = list(ds.data_vars.keys()) + list(ds.coords.keys())
                        #ds_variables = [k for k in ds]
                        ds_variables = eliminate_common_variables(ds_variables)
                        ds_variables = [x for x in ds_variables if 'qc' not in x]
                        [_, unmatch1] = compare_lists(stream_vars, ds_variables)
                        [_, unmatch2] = compare_lists(ds_variables, stream_vars)

                        # Check deployment pressure from asset management against pressure variable in file
                        press = pf.pressure_var(ds, ds_variables)

                        # calculate mean pressure from data, excluding outliers +/- 3 SD
                        try:
                            pressure = ds[press]
                            num_dims = len(pressure.dims)
                            if num_dims > 1:
                                print('variable has more than 1 dimension')
                                press_outliers = 'not calculated: variable has more than 1 dimension'
                                pressure_mean = np.nanmean(pressure.data)

                            else:
                                if len(pressure) > 1:
                                    # reject NaNs
                                    p_nonan = pressure[~np.isnan(pressure)]

                                    # reject fill values
                                    p_nonan_nofv = p_nonan[p_nonan != pressure._FillValue]

                                    if len(p_nonan_nofv) > 0:
                                        [press_outliers, pressure_mean, _, pressure_max, _, _] = cf.variable_statistics(p_nonan_nofv.data, 3)
                                    else:
                                        press_outliers = None
                                        pressure_mean = None

                                else:  # if there is only 1 data point
                                    press_outliers = 0
                                    pressure_mean = round(ds[press].data.tolist()[0], 4)

                            try:
                                pressure_units = pressure.units
                            except AttributeError:
                                pressure_units = 'no units attribute for pressure'

                            if not deploy_depth:
                                pressure_diff = None
                            elif not pressure_mean:
                                pressure_diff = None
                            else:
                                if pressure_units == '0.001 dbar':
                                    pressure_max = pressure_max / 1000
                                    pressure_mean = pressure_mean / 1000
                                    notes.append('pressure converted from 0.001 dbar to dbar for pressure comparison')
                                if 'WFP' in refdes.split('-')[1]:
                                    pressure_diff = round(pressure_max - deploy_depth, 4)
                                else:
                                    pressure_diff = round(pressure_mean - deploy_depth, 4)

                        except KeyError:
                            press = 'no seawater pressure in file'
                            pressure_diff = None
                            pressure_mean = None
                            pressure_max = None
                            press_outliers = None
                            pressure_units = None

                        # Add files and info to dictionary
                        filenames = data['deployments'][deployment]['method'][method]['stream'][data_stream][
                            'file'].keys()

                        if fname not in filenames:
                            data['deployments'][deployment]['method'][method]['stream'][data_stream]['file'][
                                fname] = OrderedDict(
                                file_downloaded=pd.to_datetime(splitter[0]).strftime('%Y-%m-%dT%H:%M:%S'),
                                file_coordinates=list(ds.coords.keys()),
                                sampling_rate_seconds=sampling_rt_sec,
                                sampling_rate_details=rates,
                                data_start=data_start,
                                data_stop=data_stop,
                                time_gaps=gap_list,
                                unique_timestamps=time_test,
                                n_timestamps=len_time,
                                n_days=n_days,
                                notes=notes,
                                ascending_timestamps=time_ascending,
                                pressure_comparison=dict(pressure_mean=pressure_mean, units=pressure_units,
                                                         num_outliers=press_outliers, diff=pressure_diff,
                                                         pressure_max=pressure_max, variable=press),
                                vars_in_file=ds_variables,
                                vars_not_in_file=[x for x in unmatch1 if 'time' not in x],
                                vars_not_in_db=unmatch2,
                                sci_var_stats=OrderedDict())

                        # calculate statistics for science variables, excluding outliers +/- 5 SD
                        for sv in sci_vars:
                            print(sv)
                            try:
                                var = ds[sv]
                                fv = str(var._FillValue)
                                num_dims = len(var.dims)
                                if num_dims > 1:
                                    print('variable has more than 1 dimension')
                                    num_outliers = None
                                    mean = None
                                    vmin = None
                                    vmax = None
                                    sd = None
                                    n_stats = 'variable has more than 1 dimension'
                                    var_units = var.units
                                    n_nan = None
                                    n_fv = None
                                    fv = None
                                else:
                                    # reject NaNs
                                    var_nonan = var[~np.isnan(var)]
                                    n_nan = len(var) - len(var_nonan)

                                    # reject fill values
                                    var_nonan_nofv = var_nonan[var_nonan != var._FillValue]
                                    n_fv = len(var) - n_nan - len(var_nonan_nofv)

                                    if len(var_nonan_nofv) > 1:
                                        [num_outliers, mean, vmin, vmax, sd, n_stats] = cf.variable_statistics(var_nonan_nofv.data, 5)
                                    elif len(var_nonan_nofv) == 1:
                                        num_outliers = 0
                                        mean = round(var_nonan_nofv.data.tolist()[0], 4)
                                        vmin = None
                                        vmax = None
                                        sd = None
                                        n_stats = 1
                                    else:
                                        num_outliers = None
                                        mean = None
                                        vmin = None
                                        vmax = None
                                        sd = None
                                        n_stats = 0

                                    var_units = var.units

                            except KeyError:
                                num_outliers = None
                                mean = None
                                vmin = None
                                vmax = None
                                sd = None
                                n_stats = 'variable not found in file'
                                var_units = None
                                n_nan = None
                                n_fv = None
                                fv = None

                            data['deployments'][deployment]['method'][method]['stream'][data_stream][
                                'file'][
                                fname]['sci_var_stats'][sv] = dict(n_outliers=num_outliers, mean=mean, min=vmin,
                                                                   max=vmax, stdev=sd, n_stats=n_stats, units=var_units,
                                                                   n_nans=n_nan, n_fillvalues=n_fv, fill_value=fv)

        sfile = os.path.join(save_dir, '{}-file_analysis.json'.format(r))
        with open(sfile, 'w') as outfile:
            json.dump(data, outfile)

        json_file_list.append(str(sfile))

    return json_file_list

if __name__ == '__main__':
    sDir = '/Users/lgarzio/Documents/repo/OOI/data-edu-ooi/data-review-tools/data_review/output'
    url_list = ['https://opendap.oceanobservatories.org/thredds/catalog/ooi/lgarzio@marine.rutgers.edu/20181001T150658-GP03FLMA-RIM01-02-CTDMOG040-recovered_host-ctdmo_ghqr_sio_mule_instrument/catalog.html',
                'https://opendap.oceanobservatories.org/thredds/catalog/ooi/lgarzio@marine.rutgers.edu/20181001T150707-GP03FLMA-RIM01-02-CTDMOG040-recovered_inst-ctdmo_ghqr_instrument_recovered/catalog.html']

    main(sDir, url_list)
