import pandas as pd
import json
import re
import os
import logging

imiss = -999999
fmiss = -999999.0
cmiss = 'NULL'

class smart_dict(dict):
    def __init__(self, *args):
        dict.__init__(self, args)

    def __getitem__(self, key):
        val = dict.__getitem__(self, key)
        return val

    def __setitem__(self, key, val):
        dict.__setitem__(self, key, val)

    def __missing__(self, key):
        #key = ''
        if key == '' :
            val = cmiss
        else:
            val = key
        return val


def pub47_record_completeness( record ) :
    s = record.size - sum( record.apply( lambda x: x == cmiss or str(x) == str(fmiss) or str(x) == str(imiss ) ) )
    s = s / record.size
    return s

def pub47_missing_elements( record ) :
    s = record.apply( lambda x: x == cmiss or str(x) == str(fmiss) or str(x) == str(imiss ) )
    return s

def pub47_record_compare( record1, record2 ) :
    s1 = record1.apply( lambda x: x == cmiss or str(x) == str(fmiss) or str(x) == str(imiss ) )
    s2 = record2.apply( lambda x: x == cmiss or str(x) == str(fmiss) or str(x) == str(imiss ) )
    assert (s1.index.values == s2.index.values).all()
    s = ( s1 | s2) | (record1 == record2)
    return s.all()

def pub47_merge_rows( record1, record2 ):
    assert pub47_record_compare( record1, record2 )
    missing1 = pub47_missing_elements( record1 )
    new_record = record1.copy()
    new_record[ missing1 ] = record2[ missing1 ]
    return( new_record )

# function to convert string to integer handling known
# exceptions in pub47 data
def pub47int(X):
    X = X.strip()
    X = X.replace('-','')
    X = X.replace(".00","")
    X = X.replace(".0", "")
    if( X == 'OT' ):
        X = 0
    elif( X == '' or X == 'NA' or X == ' ' or X == 'nan' ):
        X = imiss
    else:
        X = int( X )
    return(X)


# function to convert string to float handling known
# exceptions in pub47 data
#def pub47float(X):
#    # strip white space
#    X = X.strip()
#    X = X.replace('-', '')
#    # convert commas to periods
#    X = X.replace(',','.')
#    # replace double periods to single
#    X = X.replace('..', '.')
#    if( X == '' or X == 'NA'):
#        #X = float('NaN')
#        X = fmiss
#    else:
#        X = float(X)
#    return(X)

def pub47float(X):
    # strip white space
    X = X.strip()
    X = X.replace('-', '')
    # convert commas to periods
    X = X.replace(',','.')
    # replace double periods to single
    X = X.replace('..', '.')
    # replace ' M' with blank
    X = X.replace(' M','')
    # replace 'm' with blank
    X = X.replace('m', '')
    # replace / with .
    X = X.replace('/','.')
    if( X == '' or X == 'NA'):
        #X = float('NaN')
        X = fmiss
    else:
        X = float(X)
    return(X)


# function to convert string to upper case, stripping white space
# and converting missing to common value
def pub47text(X):
    X = X.strip().upper()
    if( X == '' or X == '-' or X == 'NaN' or X == '.' ):
        X = cmiss
    return(X)

# function to convert packed numeric data in pub47
# (used in earlier instrument heights)
def pub47UnpackFloat(X):
    X = X.strip()
    X = X.replace('-', '')
    X = X.replace('I','1')
    # check if value contains only numeric data, use pub47 float if so
    if X.isnumeric() :
        X = pub47float( X )
    else: # unpack
        if(  X == '' or X == 'NA' or X == 'nan' ):
            X = float('NaN')
        else:
            if( X[0] == '{' ):
                X = 100 + float( X[1] )
            else:
                X = (ord( X[0] ) - 54)*10 + float( X[1] )
    return(X)

# dictionary of converters for reading data into pandas data frame
converters = {
    'int': pub47int,
    'int8': pub47int,
    'int16': pub47int,
    'int32': pub47int,
    'float32': pub47float,
    'float': pub47float,
    'object': pub47text,
    'packedFloat': pub47UnpackFloat
}


class pub47schema:
    column_name = list()
    column_type = dict()
    column_converter = dict()
    column_code_table = dict()
    column_valid_min = dict()
    column_valid_max = dict()
    code_tables = dict()
    column_widths = list() # why list, not dict?
    format = ''
    split_fields = dict()
    recruiting_country = ''
    duplicate_check = list()
    version = ''

    def __init__(self, schemapath = None, schema = None):
        self.column_name = list()
        self.column_type = dict()
        self.column_converter = dict()
        self.column_code_table = dict()
        self.column_valid_min = dict()
        self.column_valid_max = dict()
        self.code_tables = dict()
        self.column_widths = list()  # why list, not dict?
        self.format = ''
        self.split_fields = dict()
        self.recruiting_country = ''
        self.duplicate_check = list()
        self.version = ''
        if schemapath is not None and schema is not None:
            self.load( schemapath, schema)
        return None

    def load(self,schemapath, schema):
        schema_file = '{}./{}/{}.json'.format( schemapath, schema, schema)
        with open(schema_file) as s:
            file_schema = json.load(s)
        self.format = file_schema['format']
        self.recruiting_country = file_schema['recruiting_country']
        self.duplicate_check = file_schema['duplicate_check']
        self.version = file_schema['version']
        for list_item in file_schema['content']:
            column = list_item['name']
            self.column_name.append( column )
            self.column_type[ column ] = list_item['column_type']
            self.column_converter[ column ] = converters[list_item['column_type']]
            self.column_widths.append(  list_item['field_length'] )
            self.column_code_table[ column ] = list_item['code_table' ]
            self.column_valid_min[column] = list_item['valid_min']
            self.column_valid_max[column] = list_item['valid_max']
            if list_item['code_table'] is not None :
                codefile = '{}./{}/code_tables/{}.csv'.format( schemapath, schema, list_item['code_table'])
                try:
                    codes = pd.read_csv( codefile, sep='\t', index_col = False )
                    self.code_tables[list_item['code_table']] = codes.copy()
                except FileNotFoundError:
                    logging.warning(" Code table {} not found for field {}".format( list_item['code_table'],
                                                                                    list_item['name']))
                except:
                    logging.error(" Unable to read code table {}".format( list_item['code_table'] ) )
                    raise
            if 'split' in list_item:
                self.split_fields[ list_item['name'] ] = list_item['split']
        return True

# function to load pub47 data based on schema file
def pub47load(schema, data_file, map_path = None):
    # steps
    # 1) Load data and basic validation
    # 2) Map input for known errors and initial homgenisation
    # 3) Split columns flagged to be split
    # 4) Remap input

    print('Loading {}'.format(data_file ))
    # ===============================================
    # Load data
    # ===============================================
    if schema.format == 'fixed':
        # first read file with everything as object
        input_data = pd.read_fwf(data_file, names= schema.column_name, header=None, index_col=False,
                                 dtype='object', widths=schema.column_widths,
                                 error_bad_lines=False, warn_bad_lines=True, encoding="ISO-8859-1")
        # Now check we can convert all columns to expected type, if not
        # message giving column name and element that fails
        for column in input_data:
            converter = schema.column_converter[ column ]
            for i, x in enumerate(input_data[column]):
                try:
                    converter(str(x))
                except ValueError:
                    print(" Error processing " + data_file)
                    print("Bad value for " + column + " at line " + str(i))
                    print(input_data.iloc[i])
                    raise
        # next read data applying converters
        input_data = pd.read_fwf(data_file, names=schema.column_name, header=None,
                                 index_col=False, converters=schema.column_converter,
                                 widths= schema.column_widths,
                                 error_bad_lines=False, warn_bad_lines=True, encoding="ISO-8859-1")
    else:
        # first read file with everything as object
        input_data = pd.read_csv(data_file, names=schema.column_name, sep=';', header=None, index_col=False,
                                 dtype='object',error_bad_lines=False, warn_bad_lines=True,
                                 encoding="ISO-8859-1")
        # Now check we can convert all columns to expected type, if not
        # message giving column name and element that fails
        for column in input_data:
            converter = schema.column_converter[ column ]
            for i, x in enumerate(input_data[column]):
                try:
                    converter(str(x))
                except ValueError:
                    print(" Error processing " + data_file)
                    print("Bad value for " + column + " at line " + str(i))
                    print(input_data.iloc[i])
                    raise
        # next read data applying converters
        input_data = pd.read_csv(data_file, names=schema.column_name, sep=';', header=None,
                                 index_col=False, converters=schema.column_converter,
                                 error_bad_lines=False, warn_bad_lines=True, encoding="ISO-8859-1")

    # Apply mapping, split, then reapply mappings
    # ========================
    # Apply mapping to columns
    # ========================
    for column in input_data:
        dictKey = re.sub( '[0-9]','',column)
        # check if mapping file exists
        map_file = map_path + dictKey.lower() + '.json'
        if os.path.isfile(map_file):
            with open(map_file) as m:
                mapping = json.load(m)
            # mapping data stored as list of dicts (unfortunately), need to convert to single dict
            # (sub-class returns key if not in dict)
            m = smart_dict()
            for item in mapping['map']:
                for key in item:
                    m[key] = item[key]
            input_data[column] = input_data[column].map(m)
        else:
            print( "No mapping file for {}".format(dictKey) )
    # ===============================================
    # Check if any columns need splitting
    # (some early data contain multiple values in single field)
    # ===============================================
    for column in input_data:
        dictKey = re.sub('[0-9]', '', column)
        if column in schema.split_fields:
            print( "splitting {}".format(column))
            values = input_data.apply(lambda x: re.split( schema.split_fields[column], str(x[column])), axis=1)  # space or comma
            nfields = max(values.apply(len))
            # pad values so all the same length
            values = pd.Series(map(lambda x: x + [cmiss] * (nfields - len(x)), values))
            values = pd.DataFrame.from_dict(dict(zip(values.index, values.values))).T
            field_index = list(range(nfields))
            field_names = list(map(lambda x: dictKey + str(x + 1), field_index))
            values.rename(dict(zip(field_index, field_names)), axis='columns', inplace=True)
            input_data.drop(columns=column, inplace=True)
            schema.column_name.remove( column )
            for c in values:
                kwargs = {c: values[c]}
                input_data = input_data.assign(**kwargs)
                schema.column_name.append( c )
                schema.column_type[ c ] = schema.column_type[ column ]
                schema.column_converter[c] = schema.column_converter[column]
                schema.column_code_table[c] = schema.column_code_table[column]
                schema.column_valid_min[c] = schema.column_valid_min[column]
                schema.column_valid_max[c] = schema.column_valid_max[column]
    # ========================
    # Apply mapping to columns
    # ========================
    for column in input_data:
        dictKey = re.sub('[0-9]', '', column)
        # check if mapping file exists
        map_file = map_path + dictKey.lower() + '.json'
        if os.path.isfile( map_file ):
            #print( 'Loading field mappings from ' + map_file )
            with open(map_file) as m:
                mapping = json.load(m)
            # mapping data stored as list of dicts (unfortunately), need to convert to single dict
            # (sub-class returns key if not in dict)
            m = smart_dict()
            for item in mapping['map']:
                for key in item:
                    m[key] = item[key]
            input_data[ column ] = input_data[ column ].map( m )
        else:
            print( "No mapping file for {}".format(dictKey) )
    # non-simple mappings
    andc_fields = { 'anDC1':'anSC1', 'anDC2':'anSC2' }
    for input_field in andc_fields:
        output_field = andc_fields[ input_field ]
        if (input_field in input_data) and (not (output_field in input_data) ):
            schema.column_code_table[ output_field ] = None
            schema.column_type[output_field] = 'object'
            new_field = {output_field: None}
            input_data = input_data.assign( **new_field )
            input_data.at[:,output_field] = input_data[input_field].apply(lambda x: None if x is None else
                                                                     ('PORT' if (('P' in x) | ('p' in x) ) else
                                                                     ('STARBOARD' if (('S' in x) | ('s' in x)) else None)))
            input_data.at[:,input_field] = input_data[input_field].apply(lambda x: None if x is None else
                                                                         ''.join(filter(lambda y: (y.isdigit()) | (y == '.'), x)))
            # replace empty strings with None
            input_data.at[:, input_field] = input_data[input_field].apply(lambda x: None if x == '' else x)
            # now convert to float
            ind = input_data[input_field].apply( lambda x: False if x is None else True )
            #print( input_data.loc[ ind , input_field] )
            input_data[input_field] = input_data[input_field].astype( float )
            schema.column_type[ input_field ] = 'float'

#    # anemometer1_side
#    if 'anDC1' in input_data:
#        if 'anSC1' in input_data:
#            output_field = 'anSC1'
#        else:
#            output_field = 'anemometer1_side'
#            schema.column_code_table[ output_field ] = None
#            schema.column_type[output_field] = 'object'
#        #print('parsing anemometer1 side')
#        input_data.at[:,output_field] = cmiss
#        print(  input_data['anDC1'] )
#        input_data.at[input_data['anDC1'].str.contains('P'), output_field] = 'PORT'
#        input_data.at[input_data['anDC1'].str.contains('p'), output_field] = 'PORT'
#        input_data.at[ (input_data['anDC1'].str.contains('S')) & ( (input_data['anDC1'].astype(str) != cmiss)), output_field] = 'STARBOARD'
#        input_data.at[ (input_data['anDC1'].str.contains('s')) & ( (input_data['anDC1'].astype(str) != cmiss)), output_field] = 'STARBOARD'
#        input_data['anDC1'] = input_data['anDC1'].apply( lambda x: ''.join( filter(lambda y: (y.isdigit()) | (y == '.'), x) ) )
#    # anemometer2_side
#    if 'anDC2' in input_data:
#        if 'anSC2' in input_data:
#            output_field = 'anSC2'
#        else:
#            output_field = 'anemometer2_side'
#            schema.column_code_table[output_field] = None
#            schema.column_type[output_field] = 'object'
#        #print('parsing anemometer2 side')
#        input_data.at[:, output_field] = cmiss
#        input_data.at[input_data['anDC2'].str.contains('P'), output_field] = 'PORT'
#        input_data.at[input_data['anDC2'].str.contains('p'), output_field] = 'PORT'
#        input_data.at[ (input_data['anDC2'].str.contains('S')) & ( (input_data['anDC2'].astype(str) != cmiss)), output_field] = 'STARBOARD'
#        input_data.at[ (input_data['anDC2'].str.contains('s')) & ( (input_data['anDC2'].astype(str) != cmiss)), output_field] = 'STARBOARD'
#        input_data['anDC2'] = input_data['anDC2'].apply( lambda x: ''.join( filter(lambda y: (y.isdigit()) | (y == '.'), x) ) )

    return input_data
