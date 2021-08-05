import pandas as pd
import json
import datetime as dt
from dateutil.relativedelta import relativedelta
import argparse
import sys
from soundex import *
from pub47 import smart_dict, cmiss, fmiss, imiss
import os

pd.options.display.width = 0

def record_completeness( record ) :
    s = record.size - sum( record.apply( lambda x: x == cmiss or x == str(fmiss) or x == str(imiss ) ) )
    s = s / record.size
    return s

def bad_number( input ):
    try:
        int( input )
        return False
    except:
        return True

def main(argv):
    parser = argparse.ArgumentParser(description='Extract monthly edition of Pub47 for specified month and output' +
                                     ' for merge with observations in CDM')
    parser.add_argument("-config", dest="config", required=False, \
                        default="config.json", help="JSON file containing configuration settings")
    parser.add_argument("-schema", dest="schema", required=True, \
                        help="JSON file containing schema for master file", default=None)
    parser.add_argument("-index", dest="index", required=True,\
                        default=None, type=int, help="Index of month to process, month 1 = Jan 1970")


    args = parser.parse_args()
    config_file = args.config
    idx = args.index - 1

    with open(config_file) as cf:
        config = json.load(cf)

    map_path = config['config_path'] + './cdm_mapping/'
    outputpath = config['output_path']

    # load data
    metadata = pd.read_csv(outputpath + './master/master_all.csv', sep='|', low_memory=False, dtype='object')

    # drop rows with missing IDs
    metadata = metadata.loc[ ~ pd.isnull( metadata.callsign) ]

    metadata['meteorological_vessel_type'] =  metadata['meteorological_vessel_type'].fillna(-1)
    metadata['meteorological_vessel_type'] = metadata['meteorological_vessel_type'].astype( int )

    # make sure columns are as we expect
    map_file = args.schema #+ "./master.json"
    fmiss = -999999.
    imiss = -1

    with open(map_file) as m:
        mapping = json.load( m )

    output_fields = list( map(lambda x: x['name'], mapping['fields']) )
    output_fields.append('sx')
    output_fields.append('completeness')

    numeric_columns = list()


    # some bad data appear to creeping through to this point, we need to do a quick fix
    bad_anDC2 = metadata['anemometer2_distance_centreline'].str.match(r'[a-zA-Z]') == True
    metadata.at[ bad_anDC2 , 'anemometer1_side' ] = metadata.loc[ bad_anDC2, 'anemometer2_distance_centreline' ]
    metadata.at[ bad_anDC2, 'anemometer2_distance_centreline' ] = pd.np.nan 

    for column in metadata:
        fieldInfo = None
        for field in mapping['fields']:
            if field['name'] == column :
                fieldInfo = field
                # convert column to type specified by column_type if numeric (int or float)
                if (fieldInfo['kind'] == 'int') :
                    bad_values = metadata[column].apply( lambda x: bad_number(x) )
                    metadata.at[ bad_values, column ] = imiss
                    metadata[column].replace(cmiss, str(imiss) ,inplace=True)
                    metadata[column].replace('-999999.0', str(imiss), inplace=True)
                    metadata = metadata.astype( { column : 'float' } )
                    metadata = metadata.astype({ column : 'int' })
                elif (fieldInfo['kind'] == 'float'):
                    metadata[column].replace(cmiss, str(fmiss), inplace=True)
                    metadata = metadata.astype({column: 'float'})
                    metadata[column].replace(fmiss,pd.np.nan,inplace=True)
                    numeric_columns.append( column )
                elif (fieldInfo['kind'] == 'object'):
                    metadata[column].replace('-999999.0', cmiss, inplace=True)
                break

    # now convert valid to / from to dates
    metadata['valid_from'] = pd.to_datetime( metadata['valid_from'] )
    metadata['valid_to'] = pd.to_datetime(metadata['valid_to'])

    # add fields for instrument IDs
    records_with_thermometer = (~ metadata['thermometer1_height'].isna()) | \
                               (metadata['thermometer1_exposure'] != cmiss) | \
                               (metadata['thermometer1_type'] != cmiss) | \
                               (metadata['thermometer1_make_model'] != cmiss) | \
                               (metadata['thermometer1_scale'] != cmiss)

    records_with_hygrometer = (metadata['hygrometer1_exposure'] != cmiss) | \
                              (metadata['hygrometer1_type'] != cmiss)

    records_with_sea_thermometer = (metadata['sst1_method'] != cmiss) | \
                                   ( ~ metadata['sst1_depth'].isna() )

    records_with_barometer = (~ metadata['barometer1_height'].isna()) | \
                             (metadata['barometer1_type'] != cmiss) | \
                             (metadata['barometer1_make_model'] != cmiss) | \
                             (metadata['barometer1_location'] != cmiss ) | \
                             (metadata['barometer1_units'] != cmiss ) | \
                             (metadata['barometer1_calibration_date'] != cmiss)

    records_with_anemometer = (~ metadata['anemometer1_height_loadline'].isna()) | \
                              (~ metadata['anemometer1_height_deck'].isna()) | \
                              (~ metadata['anemometer1_distance_bow'].isna()) | \
                              (~ metadata['anemometer1_distance_centreline'].isna()) | \
                              (metadata['anemometer1_side'] != cmiss) | \
                              (metadata['anemometer1_location'] != cmiss) | \
                              (metadata['anemometer1_type'] != cmiss) | \
                              (metadata['anemometer1_make_model'] != cmiss) | \
                              (metadata['anemometer1_calibration_date'] != cmiss)

    metadata = metadata.assign( thermometer1_id = '')
    metadata = metadata.assign( hygrometer1_id = '')
    metadata = metadata.assign( sea_thermometer1_id = '')
    metadata = metadata.assign( barometer1_id = '')
    metadata = metadata.assign( anemometer1_id = '')
    metadata = metadata.assign( platH = metadata['windwave_observing_height'] )
    metadata = metadata.assign( anemH = metadata['anemometer1_height_loadline' ] )

    metadata.at[ records_with_thermometer, 'thermometer1_id'] = metadata.loc[ records_with_thermometer ,  :].apply(
        lambda x: '{}-{}-TH1'.format(x['uid'], x['record_number'])  , axis = 1)
    metadata.at[ records_with_hygrometer, 'hygrometer1_id'] = metadata.loc[ records_with_hygrometer ,  :].apply(
        lambda x: '{}-{}-HY1'.format(x['uid'], x['record_number'])  , axis = 1)
    metadata.at[ records_with_sea_thermometer, 'sea_thermometer1_id'] = metadata.loc[ records_with_sea_thermometer ,  :].apply(
        lambda x: '{}-{}-ST1'.format(x['uid'], x['record_number'])  , axis = 1)
    metadata.at[ records_with_barometer, 'barometer1_id'] = metadata.loc[ records_with_barometer ,  :].apply(
        lambda x: '{}-{}-BM1'.format(x['uid'], x['record_number'])  , axis = 1)
    metadata.at[ records_with_anemometer, 'anemometer1_id'] = metadata.loc[ records_with_anemometer ,  :].apply(
        lambda x: '{}-{}-AN1'.format(x['uid'], x['record_number']) , axis = 1)


    # apply final mappings between code tables

    # 'meteorological_vessel_type':'vsslM', -> station_configuration_codes
    columns = ["observing_frequency","automation","recruiting_country","vessel_type"]
    for column in columns:
        map_file = map_path + "./" + column + '.json'
        assert os.path.isfile(map_file)
        with open(map_file) as m:
            mapping = json.load(m)
        # mapping data stored as list of dicts (unfortunately), need to convert to single dict
        # (sub-class returns key if not in dict)
        m = smart_dict()
        for item in mapping['map']:
            for key in item:
                m[key] = item[key]
        metadata[column] = metadata[column].map(m)


    mm = pd.np.arange( 780 )
    dates = list( dt.datetime( 1956, 1 , 1) + relativedelta( months = m ) for m in mm )
    d = dates[idx]

    print('\n{}'.format(d))
    row = metadata.loc[ ( d >= metadata['valid_from'] ) & ( d < metadata['valid_to']  ) ,:  ].copy()
    #if row.shape[0] == 0:
    #    continue
    dup_ids = row['callsign'].value_counts()
    dup_ids = list( dup_ids.index.values[ dup_ids > 1 ] )
    if len(dup_ids) > 0 and cmiss in dup_ids:
        dup_ids.remove(cmiss)
    dups = len(dup_ids) > 0
    dup_mask = row['callsign'].apply( lambda x: x in dup_ids )
    unique_rows = row.loc[ ~dup_mask,].copy()
    rejects     = row.loc[ dup_mask,].copy()
    dcount = 0
    if dups :
        print( '{} / {}'.format(len( dup_ids ) , row.shape[0]) )
        for dup in dup_ids :
            dcount += 1
            if int( 10.0 * dcount / len(dup_ids) ) % 10 == 0 :
                print('.', end='')
            highest_vos_class = min(row.loc[ row['callsign'] == dup ,'meteorological_vessel_type'] )
            best_duplicate = row.loc[ (row['callsign'] == dup) & (row['meteorological_vessel_type'] == highest_vos_class) , : ]
            # check we only have 1 'best' duplicate, if not reject lines
            if best_duplicate.shape[0] > 1 :
                latest_valid_from = max( best_duplicate['valid_from'] )
                best_duplicate = best_duplicate.loc[  best_duplicate['valid_from'] == latest_valid_from ]
            if best_duplicate.shape[0] == 1 :
                # add best duplicate to unique rows and drop from rejects
                unique_rows = pd.concat( [unique_rows, best_duplicate ], ignore_index= True, sort = False )
                rejects = rejects.drop( best_duplicate.index )

    # reject any row with callsign == MSNG
    msng_callsign = unique_rows.loc[  unique_rows['callsign'] == cmiss , ]
    rejects = pd.concat( [rejects, unique_rows.loc[  msng_callsign.index , ] ], ignore_index= True, sort = False)
    unique_rows = unique_rows.drop(  msng_callsign.index  )

    field_map = {'callsign':'call', 'record_number':'record', 'name':'name', 'observing_frequency':'freq', \
                'meteorological_vessel_type':'vsslM', 'vessel_type':'vssl', 'automation':'automation', \
                'recruiting_country':'rcnty', 'valid_from':'valid_from', 'valid_to':'valid_to', 'uid':'uid', \
                'thermometer1_height':'thmH1', 'platH':'platH', 'barometer1_height':'brmH1', 'anemH':'anmH', \
                'anemometer1_height_loadline':'anHL1', 'windwave_observing_height':'wwH', 'sst1_depth':'sstD1', \
                'thermometer1_id':'th1', 'hygrometer1_id':'hy1', 'sea_thermometer1_id':'st1', \
                'barometer1_id':'bm1', 'anemometer1_id':'an1'}

    unique_rows = unique_rows.rename( columns =  field_map )

    # final check to ensure no duplicated call signs
    assert ( ~(unique_rows.loc[ : , 'call'].value_counts() > 1).any() )
    to_write = unique_rows.loc[ :,list( field_map.values() )]
    #print( unique_rows.loc[ :,list( field_map.values() )] )
    to_write.to_csv( outputpath + './monthly/{}.csv'.format(d.strftime('%Y-%m-%d')), index = False, sep = '|' )
    #print( rejects )

if __name__ == '__main__':
    main(sys.argv[1:])
