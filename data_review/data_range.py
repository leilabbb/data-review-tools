#!/usr/bin/env python
"""
Created on March 2019

@author: Leila Belabbassi
@brief: This script is used to generate a csv file with data ranges for instruments data on mobile platforms (WFP & Gliders).
Data ranges are calculated for user selected depth-bin size (e.g., bin = 10 dbar).
"""

import functions.plotting as pf
import functions.common as cf
import functions.combine_datasets as cd
import functions.group_by_timerange as gt
import os
from os import listdir
from os.path import isfile, join
import pandas as pd
import itertools
import numpy as np
import xarray as xr
import datetime


def main(url_list, sDir, mDir, zcell_size, zdbar, start_time, end_time):
    """""
    URL : path to instrument data by methods
    sDir : path to the directory on your machine to save files
    plot_type: folder name for a plot type

    """""
    rd_list = []
    ms_list = []
    for uu in url_list:
        elements = uu.split('/')[-2].split('-')
        rd = '-'.join((elements[1], elements[2], elements[3], elements[4]))
        ms = uu.split(rd + '-')[1].split('/')[0]
        if rd not in rd_list:
            rd_list.append(rd)
        if ms not in ms_list:
            ms_list.append(ms)

    ''' 
    separate different instruments
    '''
    for r in rd_list:
        print('\n{}'.format(r))
        subsite = r.split('-')[0]
        array = subsite[0:2]
        main_sensor = r.split('-')[-1]

        # read in the analysis file
        dr_data = cf.refdes_datareview_json(r)

        # get the preferred stream information
        ps_df, n_streams = cf.get_preferred_stream_info(r)

        # get science variable long names from the Data Review Database
        stream_sci_vars = cd.sci_var_long_names(r)
        #stream_vars = cd.var_long_names(r)

        # check if the science variable long names are the same for each stream and initialize empty arrays
        sci_vars_dict0 = cd.sci_var_long_names_check(stream_sci_vars)

        # get the list of data files and filter out collocated instruments and other streams
        datasets = []
        for u in url_list:
            print(u)
            splitter = u.split('/')[-2].split('-')
            rd_check = '-'.join((splitter[1], splitter[2], splitter[3], splitter[4]))
            if rd_check == r:
                udatasets = cf.get_nc_urls([u])
                datasets.append(udatasets)

        datasets = list(itertools.chain(*datasets))
        fdatasets = cf.filter_collocated_instruments(main_sensor, datasets)
        fdatasets = cf.filter_other_streams(r, ms_list, fdatasets)

        fdatasets_final = []
        for ii in range(len(ps_df)):
            for x in fdatasets:
                if ps_df['deployment'][ii] in x and ps_df[0][ii] in x:
                    fdatasets_final.append(x)

        # build dictionary of science data from the preferred dataset for each deployment
        print('\nAppending data from files')
        et = []
        sci_vars_dict = cd.append_science_data(ps_df, n_streams, r, fdatasets_final,
                                                                              sci_vars_dict0, et, start_time, end_time)
        # get end times of deployments
        deployments = []
        end_times = []
        for index, row in ps_df.iterrows():
            deploy = row['deployment']
            deploy_info = cf.get_deployment_information(dr_data, int(deploy[-4:]))
            deployments.append(int(deploy[-4:]))
            end_times.append(pd.to_datetime(deploy_info['stop_date']))

        # '''
        # separate data files by methods
        # '''
        # # for ms in ms_list:
        #     # create data ranges foe preferred data streams
        #     if (ms.split('-')[0]) == (ps_df[0].values[0].split('-')[0]):
        #         fdatasets_sel = [x for x in fdatasets if ms in x]

        # create a dictionary for science variables from analysis file
        # stream_sci_vars_dict = dict()
        # for x in dr_data['instrument']['data_streams']:
        #     dr_ms = '-'.join((x['method'], x['stream_name']))
        #     stream_sci_vars_dict[dr_ms] = dict(vars=dict())
        #     sci_vars = dict()
        #     for y in x['stream']['parameters']:
        #         if y['data_product_type'] == 'Science Data':
        #             sci_vars.update({y['name']: dict(db_units=y['unit'])})
        #     if len(sci_vars) > 0:
        #         stream_sci_vars_dict[dr_ms]['vars'] = sci_vars

        # # initialize an empty data array for science variables in dictionary
        # sci_vars_dict = cd.initialize_empty_arrays(stream_sci_vars_dict, ms)

        # y_unit = []
        # y_name = []
        # # print('\nAppending data from files: {}'.format(ms))
        #
        # # for fd in fdatasets_final:
        #     ds = xr.open_dataset(fd, mask_and_scale=False)
        #     print('\nAppending data file: {}'.format(fd.split('/')[-1]))
        #     fname, subsite, refdes, method, stream, deployment = cf.nc_attributes(fd)
        #     for var in list(sci_vars_dict[ms]['vars'].keys()):
        #         sh = sci_vars_dict[ms]['vars'][var]
        #         if ds[var].units == sh['db_units']:
        #             if ds[var]._FillValue not in sh['fv']:
        #                 sh['fv'].append(ds[var]._FillValue)
        #             if ds[var].units not in sh['units']:
        #                 sh['units'].append(ds[var].units)
        #
        #             # time
        #             t = ds['time'].values
        #             sh['t'] = np.append(sh['t'], t)
        #
        #             # sci variable
        #             z = ds[var].values
        #             sh['values'] = np.append(sh['values'], z)
        #
        #             # add pressure to dictionary of sci vars
        #             if 'MOAS' in subsite:
        #                 if 'CTD' in main_sensor:  # for glider CTDs, pressure is a coordinate
        #                     pressure = 'sci_water_pressure_dbar'
        #                     y = ds[pressure].values
        #                     if ds[pressure].units not in y_unit:
        #                         y_unit.append(ds[pressure].units)
        #                     if ds[pressure].long_name not in y_name:
        #                         y_name.append(ds[pressure].long_name)
        #                 else:
        #                     pressure = 'int_ctd_pressure'
        #                     y = ds[pressure].values
        #                     if ds[pressure].units not in y_unit:
        #                         y_unit.append(ds[pressure].units)
        #                     if ds[pressure].long_name not in y_name:
        #                         y_name.append(ds[pressure].long_name)
        #             else:
        #                 pressure = pf.pressure_var(ds, ds.data_vars.keys())
        #                 y = ds[pressure].values
        #
        #             if len(y[y != 0]) == 0 or sum(np.isnan(y)) == len(y) or len(y[y != ds[pressure]._FillValue]) == 0:
        #                 print('Pressure Array of all zeros or NaNs or fill values - using pressure coordinate')
        #                 pressure = [pressure for pressure in ds.coords.keys() if
        #                             'pressure' in ds.coords[pressure].name]
        #                 y = ds.coords[pressure[0]].values
        #
        #             sh['pressure'] = np.append(sh['pressure'], y)
        #             try:
        #                 ds[pressure].units
        #                 if ds[pressure].units not in y_unit:
        #                     y_unit.append(ds[pressure].units)
        #             except AttributeError:
        #                 print('pressure attributes missing units')
        #                 if 'pressure unit missing' not in y_unit:
        #                     y_unit.append('pressure unit missing')
        #
        #             try:
        #                 ds[pressure].long_name
        #                 if ds[pressure].long_name not in y_name:
        #                     y_name.append(ds[pressure].long_name)
        #             except AttributeError:
        #                 print('pressure attributes missing long_name')
        #                 if 'pressure long name missing' not in y_name:
        #                     y_name.append('pressure long name missing')

        '''
        create a data-ranges table and figure for full data time range
        '''
        # create a folder to save data ranges
        save_dir_stat = os.path.join(mDir, array, subsite)
        cf.create_dir(save_dir_stat)

        save_fdir = os.path.join(sDir, array, subsite, r, 'data_range')
        cf.create_dir(save_fdir)
        stat_df = pd.DataFrame()

        for m, n in sci_vars_dict.items():
            for sv, vinfo in n['vars'].items():
                print(vinfo['var_name'])
                if len(vinfo['t']) < 1:
                    print('no variable data to plot')
                    continue
                else:
                    sv_units = vinfo['units'][0]
                    fv = vinfo['fv'][0]
                    t = vinfo['t']
                    z = vinfo['values']
                    y = vinfo['pressure']
                    if 'Pressure' in sv:
                        y_name = sv
                        y_unit = sv_units

                # Check if the array is all NaNs
                if sum(np.isnan(z)) == len(z):
                    print('Array of all NaNs - skipping plot.')
                    continue
                # Check if the array is all fill values
                elif len(z[z != fv]) == 0:
                    print('Array of all fill values - skipping plot.')
                    continue
                else:
                    dtime, zpressure, ndata = reject_erroneous_data(t, y, z, fill_value)
                    # # reject fill values
                    # fv_ind = z != fv
                    # y_nofv = y[fv_ind]
                    # t_nofv = t[fv_ind]
                    # z_nofv = z[fv_ind]
                    # print(len(z) - len(fv_ind), ' fill values')
                    #
                    # # reject NaNs
                    # nan_ind = ~np.isnan(z_nofv)
                    # t_nofv_nonan = t_nofv[nan_ind]
                    # y_nofv_nonan = y_nofv[nan_ind]
                    # z_nofv_nonan = z_nofv[nan_ind]
                    # print(len(z_nofv) - len(nan_ind), ' NaNs')
                    #
                    # # reject extreme values
                    # ev_ind = cf.reject_extreme_values(z_nofv_nonan)
                    # t_nofv_nonan_noev = t_nofv_nonan[ev_ind]
                    # y_nofv_nonan_noev = y_nofv_nonan[ev_ind]
                    # z_nofv_nonan_noev = z_nofv_nonan[ev_ind]
                    # print(len(z_nofv_nonan) - len(ev_ind), ' Extreme Values', '|1e7|')
                    #
                    # # reject values outside global ranges:
                    # global_min, global_max = cf.get_global_ranges(r, vinfo['var_name'])
                    # if isinstance(global_min, (int, float)) and isinstance(global_max, (int, float)):
                    #     gr_ind = cf.reject_global_ranges(z_nofv_nonan_noev, global_min, global_max)
                    #     t_nofv_nonan_noev_nogr = t_nofv_nonan_noev[gr_ind]
                    #     y_nofv_nonan_noev_nogr = y_nofv_nonan_noev[gr_ind]
                    #     z_nofv_nonan_noev_nogr = z_nofv_nonan_noev[gr_ind]
                    #     print('{} Global ranges [{} - {}]'.format(len(z_nofv_nonan_noev) - len(gr_ind),
                    #                                               global_min, global_max))
                    # else:
                    #     gr_ind = []
                    #     t_nofv_nonan_noev_nogr = t_nofv_nonan_noev
                    #     y_nofv_nonan_noev_nogr = y_nofv_nonan_noev
                    #     z_nofv_nonan_noev_nogr = z_nofv_nonan_noev
                    #     print('{} global ranges [{} - {}]'.format(len(gr_ind), global_min, global_max))


                    # reject suspect data using timestamps
                    Dpath = '{}/{}/{}/{}/{}'.format(sDir, array, subsite, r, 'time_to_exclude')

                    onlyfiles = []
                    for item in os.listdir(Dpath):
                        if not item.startswith('.') and os.path.isfile(os.path.join(Dpath, item)):
                            onlyfiles.append(join(Dpath, item))

                    dre = pd.DataFrame()
                    for nn in onlyfiles:
                        dr = pd.read_csv(nn)
                        dre = dre.append(dr, ignore_index=True)

                    drn = dre.loc[dre['Unnamed: 0'] == vinfo['var_name']]
                    list_time = []
                    for itime in drn.time_to_exclude:
                        ntime = itime.split(', ')
                        list_time.extend(ntime)

                    u_time_list = np.unique(list_time)
                    if len(u_time_list) != 0:
                        t_ex, z_ex, y_ex = reject_suspect_data(dtime, zpressure, ndata, time_to_exclude)
                        # t_nofv_nonan_noev_nogr_nospct = t_nofv_nonan_noev_nogr
                        # y_nofv_nonan_noev_nogr_nospct = y_nofv_nonan_noev_nogr
                        # z_nofv_nonan_noev_nogr_nospct = z_nofv_nonan_noev_nogr
                        # for row in u_time_list:
                        #     ntime = pd.to_datetime(row)
                        #     ne = np.datetime64(ntime)
                        #     ind = np.where((t_nofv_nonan_noev_nogr_nospct != ne), True, False)
                        #     if not ind.any():
                        #         print('{} {}'.format(row, 'is not in data'))
                        #         print(np.unique(ind))
                        #     else:
                        #         t_nofv_nonan_noev_nogr_nospct = t_nofv_nonan_noev_nogr_nospct[ind]
                        #         z_nofv_nonan_noev_nogr_nospct = z_nofv_nonan_noev_nogr_nospct[ind]
                        #         y_nofv_nonan_noev_nogr_nospct = y_nofv_nonan_noev_nogr_nospct[ind]

                    print('{} using {} percentile of data grouped in {} dbar segments'.format(
                        len(zpressure) - len(z_ex), inpercentile,
                        zcell_size))

                    # reject data using portal export
                    t_exp, y_exp, z_exp = cf.time_exclude_portal(subsite, r, t_ex, y_ex, z_ex)
                    print('{} timestamps using visual inspection of data'.format(
                                             len(t_ex) - len(t_exp),inpercentile, zcell_size))

                    # reject an excluded depth range
                    if zdbar is not None:
                        y_ind = y_nofv_nonan_noev_nogr_nospct_nomore < zdbar
                        t_noy = t_nofv_nonan_noev_nogr_nospct_nomore[y_ind]
                        y_noy = y_nofv_nonan_noev_nogr_nospct_nomore[y_ind]
                        z_noy = z_nofv_nonan_noev_nogr_nospct_nomore[y_ind]
                    else:
                        t_noy = t_nofv_nonan_noev_nogr_nospct_nomore
                        y_noy = y_nofv_nonan_noev_nogr_nospct_nomore
                        z_noy = z_nofv_nonan_noev_nogr_nospct_nomore

                    print('{} data in depth range using visual inspection of data'.format(
                        len(t_nofv_nonan_noev_nogr_nospct_nomore) - len(t_noy),
                        inpercentile, zcell_size))

                    if len(y_noy) > 0:
                        if m == 'common_stream_placeholder':
                            sname = '-'.join((vinfo['var_name'], r))
                        else:
                            sname = '-'.join((vinfo['var_name'], r, m))

                        '''
                        create data ranges for non - pressure data only
                        '''

                        if 'pressure' not in vinfo['var_name']:
                            columns = ['tsec', 'dbar', str(vinfo['var_name'])]
                            # create depth ranges
                            min_r = int(round(min(y_noy) - zcell_size))
                            max_r = int(round(max(y_noy) + zcell_size))
                            ranges = list(range(min_r, max_r, zcell_size))

                            # group data by depth
                            groups, d_groups = gt.group_by_depth_range(t_noy, y_noy, z_noy, columns, ranges)

                            print('writing data ranges for {}'.format(vinfo['var_name']))
                            stat_data = groups.describe()[vinfo['var_name']]
                            stat_data.insert(loc=0, column='parameter', value=sv, allow_duplicates=False)
                            t_deploy = deployments[0]
                            for i in range(len(deployments))[1:len(deployments)]:
                                t_deploy = '{}, {}'.format(t_deploy, deployments[i])
                            stat_data.insert(loc=1, column='deployments', value=t_deploy, allow_duplicates=False)

                        stat_df = stat_df.append(stat_data, ignore_index=True)

                        ''''
                        plot full time range free from errors and suspect data
                        '''''

                        clabel = sv + " (" + sv_units + ")"
                        ylabel = y_name[0] + " (" + y_unit[0] + ")"
                        title = ' '.join((deployment, refdes, ms.split('-')[0]))


                        # plot non-erroneous non-suspect data
                        fig, ax, bar = pf.plot_xsection(subsite, t_noy, y_noy, z_noy, clabel, ylabel, inpercentile=None, stdev=None)

                        ax.set_title(title, fontsize=9)
                        leg_text = (
                            'removed {} fill values, {} NaNs, {} Extreme Values (1e7), {} Global ranges [{} - {}]'.format(
                                len(z) - len(fv_ind),
                                len(z) - len(nan_ind),
                                len(z) - len(ev_ind),
                                len(gr_ind),
                                global_min, global_max) + '\n' +
                            ('(black) data average in {} dbar segments'.format(zcell_size)) + '\n' +
                            ('(magenta) upper and lower {} percentile envelope in {} dbar segments'.format(inpercentile,
                                                                                                           zcell_size))
                            + '\n' +
                            ('removed {} in the upper and lower {} percentile of data grouped in {} dbar segments'.format(
                                len(z_nofv_nonan_noev_nogr) - len(z_std), inpercentile, zcell_size)),)

                        ax.legend(leg_text, loc='upper center', bbox_to_anchor=(0.5, -0.17), fontsize=6)
                        fig.tight_layout()
                        sfile = '_'.join(('data_range', sname))
                        pf.save_fig(save_fdir, sfile)

            # write stat file
            stat_df.to_csv('{}/{}_data_ranges.csv'.format(save_dir_stat, r), index=True, float_format='%11.6f')


if __name__ == '__main__':
    '''
        define time range: 
        set to None if plotting all data
        set to dt.datetime(yyyy, m, d, h, m, s) for specific dates
        '''
    start_time = None  # dt.datetime(2014, 12, 1)
    end_time = None  # dt.datetime(2015, 5, 2)

    '''
    define filters standard deviation, percentile, depth range
    '''
    n_std = None
    inpercentile = 5
    zdbar = None

    '''
    define the depth cell_size for data grouping 
    '''
    zcell_size = 10

    '''
        define plot type, save-directory name and URL where data files live 
    '''
    mainP = '/Users/leila/Documents/NSFEduSupport/'
    mDir = mainP + 'github/data-review-tools/data_review/data_ranges'
    sDir = mainP + 'review/figures'
    url_list = ['https://opendap.oceanobservatories.org/thredds/catalog/ooi/lgarzio@marine.rutgers.edu/20181213T021222-CE09OSPM-WFP01-04-FLORTK000-recovered_wfp-flort_sample/catalog.html',
                'https://opendap.oceanobservatories.org/thredds/catalog/ooi/lgarzio@marine.rutgers.edu/20181213T021350-CE09OSPM-WFP01-04-FLORTK000-telemetered-flort_sample/catalog.html']

    main(url_list, sDir, mDir, zcell_size, zdbar, start_time, end_time)
