import os
import sys
import argparse
import json
import glob
from pathlib import Path

# number of lines to store in each cache
maxLines = 1000
# columns for resepective variables
dckIdx = range(118, 121)
sidIdx = range(121, 124)
platformTypeIdx = range(124, 126)
callsignIdx = range(34, 43)
yearIdx = range(0, 4)
monthIdx = range(4, 6)
dayIdx = range(6, 8)
hourIdx = range(8, 12)
latitudeIdx = range(12, 17)
longitudeIdx = range(17, 23)


def get_cell(lon, lat, xmin, xmax, xstep, ymin, ymax, ystep):
    nx = int((xmax - xmin) // xstep)
    xind = int((lon - xmin) // xstep)
    yind = int((lat - ymin) // ystep)
    cell = nx * yind + xind
    x1 = xind * xstep
    x2 = (xind + 1) * xstep
    y1 = yind * ystep
    y2 = (yind + 1) * ystep
    cell = {"id": cell, "xmin": x1, "xmax": x2, "ymin": y1, "ymax": y2, "count": 0}
    return cell


# class to store info for each source / deck
class deck_store():
    def __init__(self, tag, basepath, filename):
        Path("{}/{}".format(basepath, tag)).mkdir(parents=True, exist_ok=True)
        self.outfile = "{}/{}/{}".format(basepath, tag, os.path.basename(filename))
        self.count = 0
        self.linecache = list()
        self.fh = open(self.outfile, 'w')
        self.summary = dict()
        self.summary['bbox'] = dict()
        self.summary['bbox']['minLongitude'] = 360
        self.summary['bbox']['maxLongitude'] = -360
        self.summary['bbox']['minLatitude'] = 90
        self.summary['bbox']['maxLatitude'] = -90
        self.summary['callsigns'] = dict()
        self.summary['platforms'] = dict()
        self.summary['year'] = dict()
        self.summary['dck'] = dict()

    def set_path(self, tag, basepath, filename):
        outfile = "{}/{}/{}".format(basepath, tag, os.path.basename(filename))
        if self.outfile != outfile:
            self.close()
            self.outfile = outfile
            self.fh = open(self.outfile, 'w')

    def add_line(self, line):
        # extract the data we're going to use when summarising deck
        latitude = float(line[latitudeIdx.start: latitudeIdx.stop]) * 0.01
        longitude = float(line[longitudeIdx.start: longitudeIdx.stop]) * 0.01
        if longitude >= 180:
            longitude = longitude - 360
        year = int(line[yearIdx.start: yearIdx.stop])
        dck = line[dckIdx.start: dckIdx.stop]
        platform = line[platformTypeIdx.start: platformTypeIdx.stop]
        callsign = line[callsignIdx.start: callsignIdx.stop]
        cell = get_cell(longitude, latitude, -180, 180, 5, -90, 90, 5)

        if callsign in self.summary['callsigns']:
            self.summary['callsigns'][callsign] += 1
        else:
            self.summary['callsigns'][callsign] = 1

        if platform in self.summary['platforms']:
            self.summary['platforms'][platform] += 1
        else:
            self.summary['platforms'][platform] = 1

        if year in self.summary['year']:
            self.summary['year'][year]['count'] += 1
        else:
            self.summary['year'][year] = dict()
            self.summary['year'][year]['count'] = 1

        if cell['id'] not in self.summary['year'][year]:
            self.summary['year'][year][cell['id']] = cell
        self.summary['year'][year][cell['id']]['count'] += 1

        if dck in self.summary['dck']:
            self.summary['dck'][dck] += 1
        else:
            self.summary['dck'][dck] = 1

        self.linecache.append(line)
        self.count += 1

        # add summary statistics

        self.summary['bbox']['minLatitude'] = min(self.summary['bbox']['minLatitude'], latitude)
        self.summary['bbox']['maxLatitude'] = max(self.summary['bbox']['maxLatitude'], latitude)

        # add summary statistics

        self.summary['bbox']['minLongitude'] = min(self.summary['bbox']['minLongitude'], longitude)
        self.summary['bbox']['maxLongitude'] = max(self.summary['bbox']['maxLongitude'], longitude)

        if (len(self.linecache) == maxLines):
            self.writeCache()

    def writeCache(self):
        self.fh.writelines(self.linecache)
        self.linecache = list()

    def close(self):
        self.writeCache()
        self.fh.close()


def main(argv):
    parser = argparse.ArgumentParser(description="Script to split ICOADS IMMA files as specified in split.json")
    parser.add_argument("-config", dest="config", required=False, help="Name of configuration file",
                        default="config.json")

    # load configuration
    with open('config.json') as fh:
        config = json.load(fh)

    # get number of directories to process
    npaths = len(config["data-path"])

    # iterate over paths
    for pathIdx in range(npaths):
        # get list of files to process
        infiles = sorted(glob.glob("{}/IMMA1_R3.0.0*".format(config["data-path"][pathIdx])))
        # get number of files
        nfiles = len(infiles)
        # initialise dictionary to store data
        decks = dict()
        # now iterate over files
        for idx in range(nfiles):
            # get current file to process
            infile = infiles[idx]
            print("Processing {}".format(infile))
            fh = open(infile, 'r', encoding="cp1252")

            for line in fh.readlines():
                # get source Id and deck
                dck = int(line[dckIdx.start: dckIdx.stop])
                sid = int(line[sidIdx.start: sidIdx.stop])
                # set tag for data
                tag = "{:03d}-{:03d}".format(sid, dck)
                # Initialise deck or update output path
                if tag not in decks:
                    decks[tag] = deck_store(tag, config['output-path'][pathIdx], infile)
                else:
                    decks[tag].set_path(tag, config['output-path'][pathIdx], infile)
                # add ICOADS record to deck
                decks[tag].add_line(line)
            fh.close()

    # now make sure all files are closed and write summaries to file
    for dck in decks:
        with open("{}.json".format(dck), 'w') as ofh:
            json.dump(decks[dck].summary, ofh)
        decks[dck].close()


if __name__ == '__main__':
    main(sys.argv)


