import gzip
import argparse
import configparser
import json
import sys
from imma_noc import *
from datetime import datetime
import pandas as pd
from pathlib import Path


def main(argv):
    """
    """

    print('########################')
    print('Running preprocessing')
    print('########################')

    parser = argparse.ArgumentParser(description='Marine QC system, preprocessing program')
    parser.add_argument('-schema', type=str, help='Schema file defining IMMA format')
    parser.add_argument('-code_tables', type=str, help='Path to code tables')
    parser.add_argument('-source', type=str, help='Path to source data files', required=True)
    parser.add_argument('-corrections', type=str, help='Path to NOC correction data files', required=True)
    parser.add_argument('-destination', type=str, help='Path to output directory', required=True)
    parser.add_argument('-jobs', type=str, default='jobs.json', help='name of job file')
    parser.add_argument('-job_index', type=int, default=0, help='job index')

    args = parser.parse_args()

    jobfile = args.jobs
    jobindex = args.job_index - 1

    icoads_dir = args.source
    out_dir = args.destination

    with open(jobfile) as fp:
        jobs = json.load(fp)

    year1 = jobs['jobs'][jobindex]['year1']
    month1 = jobs['jobs'][jobindex]['month1']
    
    input_schema =  args.schema
    code_tables = args.code_tables

    verbose = True  # need set to read as arg in future

    readyear = year1
    readmonth = month1

    #icoads_dir = '/gws/nopw/j04/c3s311a_lot2/data/level0/marine/sub_daily_data/IMMA1_R3.0.0T/'
    filename = icoads_dir + 'IMMA1_R3.0.0T_{:04d}-{:02d}'.format(readyear, readmonth)
    #filename = icoads_dir + 'IMMA1_R3.0.1T_{:04d}-{:02d}'.format(readyear, readmonth)
    #out_dir = '/gws/nopw/j04/c3s311a_lot2/data/level0/marine/sub_daily_data/IMMA1_R3.0.0T-QC-test/'

    print('Input file is {}'.format(filename))
    print('Running from {} {}'.format(readmonth, readyear))
    print('')

    print('ICOADS directory = {}'.format(icoads_dir))
    print('Output to {}'.format(out_dir))
    print('')

    ###### dyb - new code ######
    noc_path = args.corrections # '/gws/nopw/j04/c3s311a_lot2/data/marine/r092019/ICOADS_R3.0.0T/level1b/linkage/origin_r092019_000000/'

    # load duplicates flags
    dup_path = noc_path + '/DUP_FILES/'
    dup_file = '{:4d}-{:02d}.txt.gz'.format(readyear, readmonth)
    dup_flags = pd.read_csv(dup_path + dup_file, sep='|', header=None, names=['uid', 'dup_flag', 'dups'],
                            dtype='object', compression='gzip')
    dup_flags = dup_flags.set_index('uid')
        
    # now need to read 2nd dup file (if it exists)
    dup_path = noc_path + '/DUP_FILES_ID/'
    dup_file = '{:4d}-{:02d}.txt.gz'.format(readyear, readmonth)
    if Path(dup_path + dup_file).is_file():
        dup_flags2 = pd.read_csv(dup_path + dup_file, sep='|', header=None, names=['uid', 'dup_flag', 'dups'],
                                 dtype='object', compression='gzip')
        dup_flags2 = dup_flags2.set_index('uid')
        # update main dup flags data frame
        dup_flags.at[dup_flags2.index, 'dup_flag'] = dup_flags2.loc[
            dup_flags2.index, 'dup_flag']  # replace previous flag with new one
        dup_flags.at[dup_flags2.index, 'dups'] = dup_flags.loc[dup_flags2.index, 'dups'] + dup_flags2.loc[
            dup_flags2.index, 'dups']  # add additional duplicates
    else:
        print( "WARN ({}) .... File {} not found".format(datetime.now().time().isoformat(timespec='milliseconds'), dup_file) )
    
    # load id corrections
    id_path = noc_path + 'CHANGED_IDS_UPDATE2/'
    id_file = '{:4d}-{:02d}.txt.gz'.format(readyear, readmonth)
    id_flags = pd.read_csv(id_path + id_file, sep='|', header=None,
                           names=['uid', 'new_id', 'id_flag'], dtype='object', quotechar=None, quoting=3,
                           compression='gzip')

    id_flags = id_flags.set_index('uid')

    # load date / time and location corrections
    st_path = noc_path + 'CHANGED_DATEPOS/'
    st_file = '{:4d}-{:02d}.txt.gz'.format(readyear, readmonth)
    st_flags = pd.read_csv(st_path + st_file, sep='|', header=None,
                           names=['uid', 'new_date', 'date_flag', 'new_lat', 'lat_flag', 'new_lon', 'lon_flag'],
                           dtype='object', compression='gzip')
    st_flags = st_flags.set_index('uid')

    # extract year, month, day and hour from new date
    st_flags = st_flags.assign(new_yr=st_flags['new_date'].apply(lambda x: int(x[0:4])))
    st_flags = st_flags.assign(new_mo=st_flags['new_date'].apply(lambda x: int(x[5:7])))
    st_flags = st_flags.assign(new_dy=st_flags['new_date'].apply(lambda x: int(x[8:10])))
    st_flags = st_flags.assign(
        new_hr=st_flags['new_date'].apply(lambda x: float(x[11:13]) + float(x[14:16]) / 60.0))

    print('Loading {}'.format(filename))
    imma_obj = imma(schema=input_schema, code_tables=code_tables,
                    sections=['core', 'ATTM1', 'ATTM98'], lower=True)

    nblocks = 0

    tic = datetime.now()

    block_size = 100000
    if verbose:
        print('')
        print('INFO ({}) .... Block {} processing ....'.format(
            datetime.now().time().isoformat(timespec='milliseconds'), nblocks))

    while imma_obj.loadImma(filename, sections=['core', ' 1', '98'], verbose=verbose, block_size=block_size):
        # set index on dataframe
        new_idx = 'ICOADS-30-' + imma_obj.data['attm98.uid']
        imma_obj.data = imma_obj.data.set_index(new_idx)

        # merge duplicate flags
        if verbose:
            print('INFO ({}) .... Merging duplicate flags'.format(
                datetime.now().time().isoformat(timespec='milliseconds')))
        imma_obj.data = imma_obj.data.merge(dup_flags, how='left', left_index=True, right_index=True,
                                            suffixes=(False, False))

        # Need to replace NaNs in dup_flag column with 4s (nans introduced on merge)
        imma_obj.data[['dup_flag']] = imma_obj.data[['dup_flag']].fillna(4)

        # For drifters we have not run the duplicate flagging so dup flags for drifters will be 4 - we need to repalce this with the IRF flag
        imma_obj.data.at[
            (imma_obj.data['attm1.pt'] == 7) & (imma_obj.data['attm98.irf'] == 1), 'dup_flag'] = 0  # unique
        imma_obj.data.at[(imma_obj.data['attm1.pt'] == 7) & (
                    imma_obj.data['attm98.irf'] != 1), 'dup_flag'] = 3  # worst duplicate

        # now convert back to int because python and pandas likes to change the type arbitrarily
        imma_obj.data = imma_obj.data.astype({'dup_flag': 'int32'})

        # apply corrections to ID
        if verbose:
            print('INFO ({}) .... Applying ID corrections'.format(
                datetime.now().time().isoformat(timespec='milliseconds')))
        id_idx = imma_obj.data.index.intersection(id_flags.index)
        if id_idx.size > 0:
            imma_obj.data.at[id_idx.values, 'core.id'] = id_flags.loc[id_idx, 'new_id']

        # apply corrections to yr, mo, dy, hr, lat and lon
        if verbose:
            print('INFO ({}) .... Applying location, date and time corrections'.format(
                datetime.now().time().isoformat(timespec='milliseconds')))
        id_idx = imma_obj.data.index.intersection(st_flags.index)
        if id_idx.size > 0:
            imma_obj.data.at[id_idx, 'core.yr'] = st_flags.loc[id_idx, 'new_yr']
            imma_obj.data.at[id_idx, 'core.mo'] = st_flags.loc[id_idx, 'new_mo']
            imma_obj.data.at[id_idx, 'core.dy'] = st_flags.loc[id_idx, 'new_dy']
            imma_obj.data.at[id_idx, 'core.hr'] = st_flags.loc[id_idx, 'new_hr']
            imma_obj.data.at[id_idx, 'core.lat'] = st_flags.loc[id_idx, 'new_lat']
            imma_obj.data.at[id_idx, 'core.lon'] = st_flags.loc[id_idx, 'new_lon']
            imma_obj.data.at[id_idx, 'date'] = st_flags.loc[id_idx, 'new_date']

        # exclude bad rows and rows we dont otherwise want to process
        # -----------------------------------------------------------
        # bad data (that didn't validate against IMMA schema)       
        
        bad_data = imma_obj.data['bad_data']
        # ship only
        ship = [imiss, 0, 1, 2, 3, 4, 5, 7]
        ship_mask = imma_obj.data['attm1.pt'].apply(lambda x: x in ship)

        # Duplicate  flags
        dups_to_use = [0, 1, 4]
        dup_field = 'dup_flag'

        duplicate_mask = imma_obj.data[dup_field].apply(lambda x: x in dups_to_use)

        # get land locked flag
        landlocked = imma_obj.data[ 'attm1.lz' ].apply( lambda x: x == 1)

        # feedback to user
        if verbose:
            print('INFO ({}) .... {} Good records'.format(
                datetime.now().time().isoformat(timespec='milliseconds'), sum(~bad_data)))
            print('INFO ({}) .... {} Ship and drifting buoy reports'.format(
                datetime.now().time().isoformat(timespec='milliseconds'), sum(ship_mask)))
            pt_counts = imma_obj.data[(ship_mask)].groupby('attm1.pt')['attm1.pt'].count()
            for ptidx in pt_counts.index.values:
                print('............................... {:2d}: {}'.format(ptidx, pt_counts[ptidx]))
            print('INFO ({}) .... Excluded platforms:'.format(
                datetime.now().time().isoformat(timespec='milliseconds')))
            pt_counts = imma_obj.data[(~ship_mask)].groupby('attm1.pt')['attm1.pt'].count()
            for ptidx in pt_counts.index.values:
                print('............................... {:2d}: {}'.format(ptidx, pt_counts[ptidx]))
            print(
                'INFO ({}) .... {} Duplicates'.format(datetime.now().time().isoformat(timespec='milliseconds'),
                                                      sum(~duplicate_mask)))
            print(
                'INFO ({}) .... {} Landlocked reports'.format(datetime.now().time().isoformat(timespec='milliseconds'),
                                                      sum(landlocked)))                                                      
            print('INFO ({}) .... {} Reports selected'.format(
                datetime.now().time().isoformat(timespec='milliseconds'),
                sum(((~ bad_data) & ship_mask & duplicate_mask))))

        # now apply masking to data frame
        imma_obj.data = imma_obj.data[((~ bad_data) & ship_mask & duplicate_mask & (~landlocked) ) ]
        
        if imma_obj.data.shape[0] > 0 :
            if verbose:
                print('INFO ({}) .... Sorting by id, date'.format(
                    datetime.now().time().isoformat(timespec='milliseconds')))
            # now apply sort into id, date order as above corrections can move obs out of data order
            imma_obj.data = imma_obj.data.sort_values([ 'date', 'core.id' ], axis=0, ascending=True)
            imma_obj.data = imma_obj.data.reset_index(drop=True)

            # drop unused / wanted columns and rename others
            variable_map = {"core.yr": "YR", "core.mo": "MO", "core.dy": "DY", "core.hr": "HR",
                            "core.lat": "LAT", "core.lon": "LON", "core.ds": "DS", "core.vs": "VS", "core.id": "ID",
                            "core.at": "AT", "core.sst": "SST", "core.dpt": "DPT", "attm1.dck": "DCK","core.slp":"SLP",
                            "attm1.sid": "SID",
                            "attm1.pt": "PT", "attm98.uid": "UID", "core.w": "W", "core.d": "D",
                            "attm98.irf": "IRF",
                            "bad_data": "bad_data"
                            }

            imma_obj.data.rename(columns=variable_map, inplace=True)
            imma_obj.data = imma_obj.data.loc[:, list(variable_map.values())].copy()
            outfiles = imma_obj.data.apply( lambda x: '{:04d}-{:02d}-{:04d}-{:02d}.csv'.format(x['YR'],x['MO'],readyear, readmonth) ,
                                            axis = 1  )

            imma_obj.data = imma_obj.data.assign( outfile = outfiles )
            outfiles = imma_obj.data['outfile'].unique()
            for of in outfiles:
                path = out_dir + of 
                if Path( path  ).exists():
                    head = False
                else:
                    head = True
                with open( path, 'a') as fh:
                    imma_obj.data.loc[ imma_obj.data['outfile'] == of, :].to_csv( fh, index=False, sep='|', header = head  )

        duration = (datetime.now() - tic).total_seconds() 
        tic = datetime.now()
        if verbose:
            if block_size is None :
                nread = imma_obj.number_records
            else :
                nread = min( block_size, imma_obj.number_records )
            print( 'INFO ({}) .... Block {} processed: {} records read, {} selected. ({} seconds)'.format(
                datetime.now().time().isoformat(timespec='milliseconds'), nblocks , nread, len(imma_obj.data.index ), duration ) )
            print('')
            nblocks += 1                    
            print( 'INFO ({}) .... Block {} processing ....'.format(datetime.now().time().isoformat(timespec='milliseconds'), nblocks)) 

if __name__ == '__main__':
    main(sys.argv[1:])
