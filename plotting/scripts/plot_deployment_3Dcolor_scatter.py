#!/usr/bin/env python
"""
Created on Feb 2019

@author: Leila Belabbassi
@brief: This script is used to create 3-D color scatter plots for instruments data on mobile platforms (WFP & Gliders).
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


def main(url_list, sDir, plot_type, deployment_num, start_time, end_time):

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

        # initialize an empty data array for science variables in dictionary
        sci_vars_dict = cd.initialize_empty_arrays(stream_sci_vars_dict, ms)
        y_unit = []
        y_name = []
        for ii, d in enumerate(datasets_sel):
            print('\nDataset {} of {}: {}'.format(ii + 1, len(datasets_sel), d))
            with xr.open_dataset(d, mask_and_scale=False) as ds:
                ds = ds.swap_dims({'obs': 'time'})

            if start_time is not None and end_time is not None:
                ds = ds.sel(time=slice(start_time, end_time))
                if len(ds['time'].values) == 0:
                    print('No data to plot for specified time range: ({} to {})'.format(start_time, end_time))
                    continue

            fname, subsite, refdes, method, stream, deployment = cf.nc_attributes(d)
            save_dir = os.path.join(sDir, array, subsite, refdes, plot_type, deployment)

            if deployment_num is not None:
                if int(deployment.split('0')[-1]) is not deployment_num:
                    print(type(int(deployment.split('0')[-1])), type(deployment_num))
                    continue

            cf.create_dir(save_dir)

            for var in list(sci_vars_dict[ms]['vars'].keys()):
                sh = sci_vars_dict[ms]['vars'][var]
                if ds[var].units == sh['db_units']:
                    if ds[var]._FillValue not in sh['fv']:
                        sh['fv'].append(ds[var]._FillValue)
                    if ds[var].units not in sh['units']:
                        sh['units'].append(ds[var].units)

                    sh['t'] = np.append(sh['t'], ds['time'].values) #t = ds['time'].values
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

                    sh['pressure'] = np.append(sh['pressure'], y)

                    if ds[pressure].units not in y_unit:
                        y_unit.append(ds[pressure].units)
                    if ds[pressure].long_name not in y_name:
                        y_name.append(ds[pressure].long_name)

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
                        t = vinfo['t']
                        z = vinfo['values']
                        y = vinfo['pressure']

                        title = ' '.join((deployment, r, ms.split('-')[0]))

                    # Check if the array is all NaNs
                    if sum(np.isnan(z)) == len(z):
                        print('Array of all NaNs - skipping plot.')

                    # Check if the array is all fill values
                    elif len(z[z != fv]) == 0:
                        print('Array of all fill values - skipping plot.')

                    else:
                        # reject fill values
                        fv_ind = z != fv
                        y_nofv = y[fv_ind]
                        t_nofv = t[fv_ind]
                        z_nofv = z[fv_ind]
                        print(len(z) - len(fv_ind), ' fill values')

                        # reject NaNs
                        nan_ind = ~np.isnan(z)
                        t_nofv_nonan = t_nofv[nan_ind]
                        y_nofv_nonan = y_nofv[nan_ind]
                        z_nofv_nonan = z_nofv[nan_ind]
                        print(len(z) - len(nan_ind), ' NaNs')

                        # reject extreme values
                        ev_ind = cf.reject_extreme_values(z_nofv_nonan)
                        t_nofv_nonan_noev = t_nofv_nonan[ev_ind]
                        y_nofv_nonan_noev = y_nofv_nonan[ev_ind]
                        z_nofv_nonan_noev = z_nofv_nonan[ev_ind]
                        print(len(z) - len(ev_ind), ' Extreme Values', '|1e7|')

                    if len(y_nofv_nonan_noev) > 0:
                        if m == 'common_stream_placeholder':
                            sname = '-'.join((r, sv))
                        else:
                            sname = '-'.join((r, m, sv))


                    # Plot all data
                    clabel = sv + " (" + sv_units + ")"
                    ylabel = y_name[0] + " (" + y_unit[0] + ")"
                    print(clabel, ylabel)
                    fig, ax = pf.plot_xsection(subsite, t_nofv_nonan_noev, y_nofv_nonan_noev, z_nofv_nonan_noev,
                                               clabel, ylabel, stdev=None)
                    ax.set_title((title + '\n' + t0 + ' - ' + t1), fontsize=9)
                    pf.save_fig(save_dir, sname)

                    # Plot data with outliers removed
                    fig, ax = pf.plot_xsection(subsite, t, y, z, clabel, ylabel, stdev=5)
                    ax.set_title((title + '\n' + t0 + ' - ' + t1), fontsize=9)
                    sfile = '_'.join((sname, 'rmoutliers'))
                    pf.save_fig(save_dir, sfile)


if __name__ == '__main__':
    pd.set_option('display.width', 320, "display.max_columns", 10)  # for display in pycharm console
    sDir = '/Users/leila/Documents/NSFEduSupport/review/figures'
    url_list = [
        'https://opendap.oceanobservatories.org/thredds/catalog/ooi/leila.ocean@gmail.com/20181217T161432-CE09OSPM-WFP01-03-CTDPFK000-recovered_wfp-ctdpf_ckl_wfp_instrument_recovered/catalog.html']
    # 'https://opendap.oceanobservatories.org/thredds/catalog/ooi/leila.ocean@gmail.com/20181217T161444-CE09OSPM-WFP01-03-CTDPFK000-telemetered-ctdpf_ckl_wfp_instrument/catalog.html'
    plot_type = 'xsection_plots'
    start_time = None  # dt.datetime(2016, 6, 1, 0, 0, 0)  # optional, set to None if plotting all data
    end_time = None    # dt.datetime(2017, 10, 1, 0, 0, 0)  # optional, set to None if plotting all data
    deployment_num = 7
    main(url_list, sDir, plot_type, deployment_num, start_time, end_time)