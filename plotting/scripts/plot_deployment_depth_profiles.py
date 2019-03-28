#!/usr/bin/env python
"""
Created on Feb 2019

@author: Leila Belabbassi
@brief: This script is used to create depth-profile plots for instruments data on mobile platforms (WFP & Gliders).
Each plot contain data from one deployment.
"""

import os
import pandas as pd
import xarray as xr
import numpy as np
import matplotlib.cm as cm
import datetime as dt
import functions.common as cf
import functions.plotting as pf
import functions.combine_datasets as cd
import matplotlib.pyplot as plt
import functions.group_by_timerange as gt


def main(url_list, sDir, plot_type, deployment_num, start_time, end_time, method_num, zdbar):

    for i, u in enumerate(url_list):
        print('\nUrl {} of {}: {}'.format(i + 1, len(url_list), u))
        elements = u.split('/')[-2].split('-')
        r = '-'.join((elements[1], elements[2], elements[3], elements[4]))
        ms = u.split(r + '-')[1].split('/')[0]
        subsite = r.split('-')[0]
        array = subsite[0:2]
        main_sensor = r.split('-')[-1]

        # read URL to get data
        datasets = cf.get_nc_urls([u])
        datasets_sel = cf.filter_collocated_instruments(main_sensor, datasets)

        # get sci data review list
        dr_data = cf.refdes_datareview_json(r)

        ps_df, n_streams = cf.get_preferred_stream_info(r)

        # get end times of deployments
        deployments = []
        end_times = []
        for index, row in ps_df.iterrows():
            deploy = row['deployment']
            deploy_info = cf.get_deployment_information(dr_data, int(deploy[-4:]))
            deployments.append(int(deploy[-4:]))
            end_times.append(pd.to_datetime(deploy_info['stop_date']))

        # create a dictionary for science variables from analysis file
        stream_sci_vars_dict = dict()
        for x in dr_data['instrument']['data_streams']:
            dr_ms = '-'.join((x['method'], x['stream_name']))
            if ms == dr_ms:
                stream_sci_vars_dict[dr_ms] = dict(vars=dict())
                sci_vars = dict()
                for y in x['stream']['parameters']:
                    if y['data_product_type'] == 'Science Data':
                        sci_vars.update({y['name']: dict(db_units=y['unit'])})
                if len(sci_vars) > 0:
                    stream_sci_vars_dict[dr_ms]['vars'] = sci_vars

        for ii, d in enumerate(datasets_sel):
            print('\nDataset {} of {}: {}'.format(ii + 1, len(datasets_sel), d))
            with xr.open_dataset(d, mask_and_scale=False) as ds:
                ds = ds.swap_dims({'obs': 'time'})

            fname, subsite, refdes, method, stream, deployment = cf.nc_attributes(d)

            if method_num is not None:
                if method != method_num:
                    print(method_num, method)
                    continue


            if deployment_num is not None:
                if int(deployment.split('0')[-1]) is not deployment_num:
                    print(type(int(deployment.split('0')[-1])), type(deployment_num))
                    continue

            if start_time is not None and end_time is not None:
                ds = ds.sel(time=slice(start_time, end_time))
                if len(ds['time'].values) == 0:
                    print('No data to plot for specified time range: ({} to {})'.format(start_time, end_time))
                    continue
                stime = start_time.strftime('%Y-%m-%d')
                etime = end_time.strftime('%Y-%m-%d')
                ext = stime + 'to' + etime  # .join((ds0_method, ds1_method
                save_dir = os.path.join(sDir, array, subsite, refdes, plot_type, ms.split('-')[0], deployment, ext)
            else:
                save_dir = os.path.join(sDir, array, subsite, refdes, plot_type, ms.split('-')[0], deployment)

            cf.create_dir(save_dir)

            # initialize an empty data array for science variables in dictionary
            sci_vars_dict = cd.initialize_empty_arrays(stream_sci_vars_dict, ms)
            y_unit = []
            y_name = []
            for var in list(sci_vars_dict[ms]['vars'].keys()):
                sh = sci_vars_dict[ms]['vars'][var]
                if ds[var].units == sh['db_units']:
                    if ds[var]._FillValue not in sh['fv']:
                        sh['fv'].append(ds[var]._FillValue)
                    if ds[var].units not in sh['units']:
                        sh['units'].append(ds[var].units)

                    sh['t'] = np.append(sh['t'], ds['time'].values) # t = ds['time'].values
                    sh['values'] = np.append(sh['values'], ds[var].values)  # z = ds[var].values

                    if 'MOAS' in subsite:
                        if 'CTD' in main_sensor:  # for glider CTDs, pressure is a coordinate
                            pressure = 'sci_water_pressure_dbar'
                            y = ds[pressure].values
                        else:
                            pressure = 'int_ctd_pressure'
                            y = ds[pressure].values
                    else:
                        pressure = pf.pressure_var(ds, ds.data_vars.keys())
                        y = ds[pressure].values

                    if len(y[y != 0]) == 0 or sum(np.isnan(y)) == len(y) or len(y[y != ds[pressure]._FillValue]) == 0:
                        print('Pressure Array of all zeros or NaNs or fill values - using pressure coordinate')
                        pressure = [pressure for pressure in ds.coords.keys() if 'pressure' in ds.coords[pressure].name]
                        y = ds.coords[pressure[0]].values

                    sh['pressure'] = np.append(sh['pressure'], y)

                    try:
                        ds[pressure].units
                        if ds[pressure].units not in y_unit:
                            y_unit.append(ds[pressure].units)
                    except AttributeError:
                        print('pressure attributes missing units')
                        if 'pressure unit missing' not in y_unit:
                            y_unit.append('pressure unit missing')

                    try:
                        ds[pressure].long_name
                        if ds[pressure].long_name not in y_name:
                            y_name.append(ds[pressure].long_name)
                    except AttributeError:
                        print('pressure attributes missing long_name')
                        if 'pressure long name missing' not in y_name:
                            y_name.append('pressure long name missing')

            for m, n in sci_vars_dict.items():
                for sv, vinfo in n['vars'].items():
                    print(sv)
                    if len(vinfo['t']) < 1:
                        print('no variable data to plot')
                    else:
                        sv_units = vinfo['units'][0]
                        fv = vinfo['fv'][0]
                        t0 = pd.to_datetime(min(vinfo['t'])).strftime('%Y-%m-%dT%H:%M:%S')
                        t1 = pd.to_datetime(max(vinfo['t'])).strftime('%Y-%m-%dT%H:%M:%S')
                        colors = cm.rainbow(np.linspace(0, 1, len(vinfo['t'])))
                        t = vinfo['t']
                        z = vinfo['values']
                        y = vinfo['pressure']

                        title = ' '.join((deployment, r, ms.split('-')[0]))

                    # Check if the array is all NaNs
                    if sum(np.isnan(z)) == len(z):
                        print('Array of all NaNs - skipping plot.')
                        continue

                    # Check if the array is all fill values
                    elif len(z[z != fv]) == 0:
                        print('Array of all fill values - skipping plot.')
                        continue

                    else:
                        # reject fill values
                        fv_ind = z != fv
                        t__nofv = t[fv_ind]
                        y_nofv = y[fv_ind]
                        c_nofv = colors[fv_ind]
                        z_nofv = z[fv_ind]
                        print(len(z) - len(fv_ind), ' fill values')

                        # reject NaNs
                        nan_ind = ~np.isnan(z_nofv)
                        t_nofv_nonan = t__nofv[nan_ind]
                        c_nofv_nonan = c_nofv[nan_ind]
                        y_nofv_nonan = y_nofv[nan_ind]
                        z_nofv_nonan = z_nofv[nan_ind]
                        print(len(z) - len(nan_ind), ' NaNs')

                        # reject extreme values
                        ev_ind = cf.reject_extreme_values(z_nofv_nonan)
                        t_nofv_nonan_noev = t_nofv_nonan[ev_ind]
                        c_nofv_nonan_noev = c_nofv_nonan[ev_ind]
                        y_nofv_nonan_noev = y_nofv_nonan[ev_ind]
                        z_nofv_nonan_noev = z_nofv_nonan[ev_ind]
                        print(len(z) - len(ev_ind), ' Extreme Values', '|1e7|')

                        # reject values outside global ranges:
                        global_min, global_max = cf.get_global_ranges(r, sv)
                        # platform not in qc-table (parad_k_par)
                        # global_min = 0
                        # global_max = 2500
                        if isinstance(global_min, (int, float)) and isinstance(global_max, (int, float)):
                            gr_ind = cf.reject_global_ranges(z_nofv_nonan_noev, global_min, global_max)
                            t_nofv_nonan_noev_nogr = t_nofv_nonan_noev[gr_ind]
                            y_nofv_nonan_noev_nogr = y_nofv_nonan_noev[gr_ind]
                            z_nofv_nonan_noev_nogr = z_nofv_nonan_noev[gr_ind]
                            print(len(z_nofv_nonan_noev) - len(gr_ind),
                                  ' Global ranges for : {} - {}'.format(global_min, global_max))
                        else:
                            t_nofv_nonan_noev_nogr = t_nofv_nonan_noev
                            y_nofv_nonan_noev_nogr = y_nofv_nonan_noev
                            z_nofv_nonan_noev_nogr = z_nofv_nonan_noev
                            print('No global ranges: {} - {}'.format(global_min, global_max))

                        # reject values outside 3 STD in data groups
                        columns = ['tsec', 'dbar', str(sv)]
                        bin_size = 10
                        min_r = int(round(min(y_nofv_nonan_noev_nogr) - bin_size))
                        max_r = int(round(max(y_nofv_nonan_noev_nogr) + bin_size))
                        ranges = list(range(min_r, max_r, bin_size))
                        groups, d_groups = gt.group_by_depth_range(t_nofv_nonan_noev_nogr, y_nofv_nonan_noev_nogr,
                                                                   z_nofv_nonan_noev_nogr, columns, ranges)


                        y_avg, n_avg, n_min, n_max, n0_std, n1_std, l_arr , time_exclude= [], [], [], [], [], [], [], []
                        tm = 1
                        for ii in range(len(groups)):
                            nan_ind = d_groups[ii + tm].notnull()
                            xtime = d_groups[ii + tm][nan_ind]
                            colors = cm.rainbow(np.linspace(0, 1, len(xtime)))
                            ypres = d_groups[ii + tm + 1][nan_ind]
                            nval = d_groups[ii + tm + 2][nan_ind]
                            tm += 2

                            l_arr.append(len(nval))  # count of data to filter out small groups
                            y_avg.append(ypres.mean())
                            n_avg.append(nval.mean())
                            n_min.append(nval.min())
                            n_max.append(nval.max())
                            n_std = 3
                            n0_std.append(nval.mean() + n_std * nval.std())
                            n1_std.append(nval.mean() - n_std * nval.std())

                            indg = nval > (nval.mean() + (3 * nval.std()))
                            gtime = xtime[indg]
                            if len(gtime) != 0:
                                time_exclude.append(pd.to_datetime(gtime.min()).strftime('%Y-%m-%d'))
                                time_exclude.append(pd.to_datetime(gtime.max()).strftime('%Y-%m-%d'))

                            indl = nval < (nval.mean() - (3 * nval.std()))
                            ltime = xtime[indl]
                            if len(ltime) != 0:
                                time_exclude.append(pd.to_datetime(ltime.min()).strftime('%Y-%m-%d'))
                                time_exclude.append(pd.to_datetime(ltime.max()).strftime('%Y-%m-%d'))


                        print(np.unique(time_exclude))

                    if len(z_nofv_nonan_noev) > 0:
                        if m == 'common_stream_placeholder':
                            sname = '-'.join((r, sv))
                        else:
                            sname = '-'.join((r, m, sv))

                    xlabel = sv + " (" + sv_units + ")"
                    ylabel = y_name[0] + " (" + y_unit[0] + ")"
                    clabel = 'Time'


                    # Plot all data
                    fig, ax = pf.plot_profiles(z_nofv_nonan_noev_nogr, y_nofv_nonan_noev_nogr, t_nofv_nonan_noev_nogr,
                                               ylabel, xlabel, clabel, end_times, deployments, stdev=None)

                    ax.set_title((title + '\n' + t0 + ' - ' + t1), fontsize=9)
                    ax.plot(n_avg, y_avg, '-k')
                    ax.fill_betweenx(y_avg, n0_std, n1_std, color='m', alpha=0.2)

                    pf.save_fig(save_dir, sname)


                    # Plot data for a selected depth range
                    if zdbar is not None:
                        y_ind = y_nofv_nonan_noev_nogr < zdbar
                        t_y = t_nofv_nonan_noev_nogr[y_ind]
                        y_y = y_nofv_nonan_noev_nogr[y_ind]
                        z_y = z_nofv_nonan_noev_nogr[y_ind]

                        fig, ax = pf.plot_profiles(z_y, y_y, t_y,
                                                   ylabel, xlabel, clabel, end_times, deployments, stdev=None)
                        ax.set_title((title + '\n' + t0 + ' - ' + t1), fontsize=9)

                        sfile = '_'.join((sname, 'rmdepthrange'))
                        pf.save_fig(save_dir, sfile)

                    # plot data with excluded time range removed
                    dr = pd.read_csv('https://datareview.marine.rutgers.edu/notes/export')
                    drn = dr.loc[dr.type == 'exclusion']

                    if len(drn) != 0:
                        subsite_node = '-'.join((subsite, r.split('-')[1]))
                        drne = drn.loc[drn.reference_designator.isin([subsite, subsite_node, r])]

                        if len(drne) != 0:
                            t_ex = t_nofv_nonan_noev_nogr
                            y_ex = y_nofv_nonan_noev_nogr
                            z_ex = z_nofv_nonan_noev_nogr
                            for ij, row in drne.iterrows():
                                sdate = cf.format_dates(row.start_date)
                                edate = cf.format_dates(row.end_date)
                                ts = np.datetime64(sdate)
                                te = np.datetime64(edate)
                                if t_ex.max() < ts:
                                    continue
                                elif t_ex.min() > te:
                                    continue
                                else:
                                    ind = np.where((t_ex < ts) | (t_ex > te), True, False)
                                    if len(ind) != 0:
                                        t_ex = t_ex[ind]
                                        z_ex = z_ex[ind]
                                        y_ex = y_ex[ind]
                                        print(len(ind), 'timestamps in: {} - {}'.format(sdate, edate))

                            fig, ax = pf.plot_profiles(z_ex, y_ex, t_ex,
                                                       ylabel, xlabel, clabel, end_times, deployments, stdev=None)
                            ax.set_title((title + '\n' + t0 + ' - ' + t1), fontsize=9)
                            leg_text = ('excluded suspect data',)
                            ax.legend(leg_text, loc='best', fontsize=6)

                            sfile = '_'.join((sname, 'rmsuspectdata'))
                            pf.save_fig(save_dir, sfile)
                    else:
                        print(len(z_ex), 'no time ranges excluded -  Empty Array', drn)

if __name__ == '__main__':
    pd.set_option('display.width', 320, "display.max_columns", 10)  # for display in pycharm console
    sDir = '/Users/leila/Documents/NSFEduSupport/review/figures'
    plot_type = 'profile_plots'
    '''
        time option: 
        set to None if plotting all data
        set to dt.datetime(yyyy, m, d, h, m, s) for specific dates
    '''
    start_time = None
    end_time = None
    method_num = 'recovered_wfp' #telemetered'
    deployment_num = 7
    zdbar = None
    # url_list = ['https://opendap.oceanobservatories.org/thredds/catalog/ooi/lgarzio@marine.rutgers.edu/20181213T021208-CE09OSPM-WFP01-02-DOFSTK000-telemetered-dofst_k_wfp_instrument/catalog.html']
    # url_list = ['https://opendap.oceanobservatories.org/thredds/catalog/ooi/lgarzio@marine.rutgers.edu/20181213T021154-CE09OSPM-WFP01-02-DOFSTK000-recovered_wfp-dofst_k_wfp_instrument_recovered/catalog.html']
    url_list = ['https://opendap.oceanobservatories.org/thredds/catalog/ooi/lgarzio@marine.rutgers.edu/20181213T021635-CE09OSPM-WFP01-05-PARADK000-recovered_wfp-parad_k__stc_imodem_instrument_recovered/catalog.html']
    # url_list = ['https://opendap.oceanobservatories.org/thredds/catalog/ooi/lgarzio@marine.rutgers.edu/20181213T021122-CE09OSPM-WFP01-03-CTDPFK000-recovered_wfp-ctdpf_ckl_wfp_instrument_recovered/catalog.html']
    main(url_list, sDir, plot_type, deployment_num, start_time, end_time, method_num, zdbar)