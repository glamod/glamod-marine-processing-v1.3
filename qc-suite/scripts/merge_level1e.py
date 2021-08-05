from dateutil.relativedelta import relativedelta
import datetime as dt
import pandas as pd
import numpy as np
import argparse
from pathlib import Path
import sys


def main(argv):
    # get arguments to process
    parser = argparse.ArgumentParser(description='Merge monthly MOQC tracking files')
    parser.add_argument('-index', dest='index', type=int, required=True, help='Month to process, 1 = Jan 1978')
    parser.add_argument('-cdmpath', dest = 'cdmpath', required=True)
    parser.add_argument('-source', dest='source', required=True)
    args = parser.parse_args()
    imonth = args.index - 1
    # generate list of months
    mm = np.arange(444)
    dates = list(dt.datetime(1978, 1, 1) + relativedelta(months=m) for m in mm)
    # now get month to process
    year = dates[imonth].year
    month = dates[imonth].month

    # get list of files to concatenate
    cdm_path = args.cdmpath # '/gws/nopw/j04/c3s311a_lot2/data/marine/r092019/ICOADS_R3.0.0T/'
    input_level = 'level1e/'
    output_level = 'level1f/'
    siddck = '063-714/'
    # tracking_path = '/gws/nopw/j04/c3s311a_lot2/data/marine/r092019/MetOffice_Tracking_QC_Merged/'
    tracking_path = args.source # cdm_path + './metoffice_qc/dbuoy_track/merged/'
    release_no = 'release_4.0' # need to change this to an argument
    sub_issue_no = '000000'
    cdmfile = 'header-{:4d}-{:02d}-{}-{}.psv'.format(year, month, release_no, sub_issue_no)
    trackfile = '{:4d}-{:02d}.csv'.format(year, month)

    infile = cdm_path + input_level + siddck + cdmfile
    outfile = cdm_path + output_level + siddck + cdmfile
    print(infile)
    if Path(infile).is_file():

        infile = pd.read_csv(infile, dtype='object', low_memory=False, sep='|')
        output_fields = list(infile.columns)
        infile = infile.assign(cdmuid=infile['report_id'])
        infile = infile.set_index('cdmuid')
        print( tracking_path + trackfile )
        if Path(tracking_path + trackfile).is_file():
            trackdata = pd.read_csv(tracking_path + trackfile, dtype='object', low_memory=False)
            uid = trackdata['UID'].apply(lambda x: 'ICOADS-30-{}'.format(x))
            trackdata = trackdata.assign(cdmuid=uid)
            trackdata = trackdata.set_index('cdmuid')
            qcfields = ['drf_agr', 'drf_spd', 'drf_tail1', 'drf_tail2', 'drf_bias', 'drf_noise', 'drf_short']
            # convert qc fields to int
            for fld in qcfields:
                trackdata[fld] = trackdata[fld].apply(lambda x: int(x))
            qcflag = trackdata.loc[:, qcfields].apply(sum, axis=1)
            trackdata = trackdata.assign(cdmtrack=qcflag)

            infile = infile.merge(trackdata, left_index=True, right_index=True, how='left', suffixes=(False, False))

            infile.at[infile['cdmtrack'] == 0, 'location_quality'] = 0
            infile.at[infile['cdmtrack'] > 0, 'location_quality'] = 1
            infile.at[infile['cdmtrack'] > 0, 'report_quality'] = 1
            infile.at[infile['cdmtrack'].isna(), 'location_quality'] = 3

            message = ';{}. Buoy tracking flags merged'.format(dt.datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
        else:
            message = ';{}. Buoy tracking - no tracking files for month'.format(
                dt.datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
            infile['location_quality'] = 3

        infile['history'] = infile['history'].apply(lambda x: x + message)

        infile.loc[:, output_fields].to_csv(outfile, index=False, sep='|', na_rep='null')
    else:
        print('{} not found'.format(infile))


if __name__ == '__main__':
    main(sys.argv[1:])

