"""Read in an Ortec SPC file."""

from __future__ import print_function
import os
import struct
import dateutil.parser
import numpy as np
from spectrum_file import SpectrumFile


class SpcFile(SpectrumFile):
    """SPC binary file parser.

    Basic operation is:
        spec = SpcFile(filename)
        spec.read()
        spec.apply_calibration()

    Then the data are in
        spec.data [counts]
        spec.channels
        spec.energies
        spec.energy_bin_widths

    ORTEC's SPC file format is divided into records of 128 bytes each. The
    specifications for what each record should contain can be found on pages
    29--44 of this document:
        http://www.ortec-online.com/download/ortec-software-file-structure-manual.pdf

    In the example file, not all of the records that are supposed to be in
    the files seem to be there, and so this code may depart in some places
    from the specification.

    """

    SPC_FORMAT_BEGINNING = [
        # Record 1
        [
            ['INFTYP', 'H'],
            ['FILTYP', 'H'],
            ['3', 'H'],
            ['4', 'H'],
            ['ACQIRP', 'H'],
            ['SAMDRP', 'H'],
            ['DETDRP', 'H'],
            ['EBRDESC', 'H'],
            ['ANARP1', 'H'],
            ['ANARP2', 'H'],
            ['ANARP3', 'H'],
            ['ANARP4', 'H'],
            ['SRPDES', 'H'],
            ['IEQDESC', 'H'],
            ['GEODES', 'H'],
            ['MPCDESC', 'H'],
            ['CALDES', 'H'],
            ['CALRP1', 'H'],
            ['CALRP2', 'H'],
            ['EFFPRP', 'H'],
            ['ROIRP1', 'H'],
            ['22', 'H'],
            ['23', 'H'],
            ['24', 'H'],
            ['25', 'H'],
            ['26', 'H'],
            ['PERPTR', 'H'],
            ['MAXRCS', 'H'],
            ['LSTREC', 'H'],
            ['EFFPNM', 'H'],
            ['SPCTRP', 'H'],
            ['SPCRCN', 'H'],
            ['SPCCHN', 'H'],
            ['ABSTCH', 'H'],
            ['ACQTIM', 'f'],
            ['ACQTI8', 'd'],
            ['SEQNUM', 'H'],
            ['MCANU', 'H'],
            ['SEGNUM', 'H'],
            ['MCADVT', 'H'],
            ['CHNSRT', 'H'],
            ['RLTMDT', 'f'],
            ['LVTMDT', 'f'],
            ['50', 'H'],
            ['51', 'H'],
            ['52', 'H'],
            ['53', 'H'],
            ['54', 'H'],
            ['55', 'H'],
            ['56', 'H'],
            ['57', 'H'],
            ['58', 'H'],
            ['59', 'H'],
            ['60', 'H'],
            ['61', 'H'],
            ['62', 'H'],
            ['RRSFCT', 'f'],
        ],
        # Unknown Record
        [['Unknown Record 1', '128B'], ],
        # Acquisition Information Record
        [
            ['Default spectrum file name', '16s'],
            ['Date', '12s'],
            ['Time', '10s'],
            ['Live Time', '10s'],
            ['Real Time', '10s'],
            ['59--90', 'B33x'],
            ['Start date of sample collection', '10s'],
            ['Start time of sample collection', '8s'],
            ['Stop date of sample collection', '10s'],
            ['Stop time of sample collection', '8s'],
        ],
        # Sample Description Record
        [['Sample Description', '128s'], ],
        # Detector Description Record
        [['Detector Description', '128s'], ],
        # First Analysis Parameter
        [
            ['Calibration ?', '16f'],
            ['Testing', '64s'],
        ],
        # Unknown Record
        [['Unknown Record 2', '128B'], ],
        # Calibration Description Record
        [['Calibration Description', '128s'], ],
        # Description Record 1
        [['Location Description Record 1', 'x127s'], ],
        # Description Record 2
        [['Location Description Record 2', '128s'], ],
        # Unknown Record
        [['Unknown Record 3', '128B'], ],
        # Unknown Record
        [['Unknown Record 4', '128B'], ],
        # Unknown Record
        [['Unknown Record 5', '128B'], ],
        # Unknown Record
        [['Unknown Record 6', '128B'], ],
        # Empty Record
        [['Empty Record 1', '128B'], ],
        # Empty Record
        [['Empty Record 2', '128B'], ],
        # Empty Record
        [['Empty Record 3', '128B'], ],
        # Empty Record
        [['Empty Record 4', '128B'], ],
        # Empty Record
        [['Empty Record 5', '128B'], ],
        # Hardware Parameters Record 1
        [['Hardware Parameters Record 1', '128s'], ],
        # Hardware Parameters Record 2
        [['Hardware Parameters Record 2', '128s'], ],
    ]

    SPC_FORMAT_END = [
        # Unknown Record
        [['Unknown Record 1', '128B'], ],
        # Unknown Record
        [['Unknown Record 2', '128B'], ],
        # Calibration parameters
        [
            ['Calibration parameter 0', 'f'],
            ['Calibration parameter 1', 'f'],
            ['Calibration parameter 2', 'f116x'],
        ],
    ]

    def __init__(self, filename):
        """Initialize the SPC file."""
        super(SpcFile, self).__init__(filename)
        assert os.path.splitext(self.filename)[1].lower() == '.spc'
        self.metadata = {}

    def read(self, verbose=False):
        """Read in the file."""
        print('SpcFile: Reading file ' + self.filename)
        self.realtime = 0.0
        self.livetime = 0.0
        self.channels = np.array([], dtype=np.float)
        self.data = np.array([], dtype=np.float)
        self.cal_coeff = []
        with open(self.filename, 'rb') as f:
            # read the file in chunks of 128 bytes
            data_records = []
            binary_data = None
            while True:
                if binary_data is not None:
                    data_records.append(binary_data)
                try:
                    binary_data = f.read(128)
                except IOError:
                    raise Exception('Unable to read 128 bytes from file')
                if len(binary_data) < 128:
                    break
            print(
                'Done reading in SPC file.  Number of records: ',
                len(data_records))
            assert len(data_records) == 279 or len(data_records) == 280
            # read record data
            i_rec = 0
            for record_format in self.SPC_FORMAT_BEGINNING:
                if not (len(data_records) == 279 and \
                    record_format[0][0] == 'Location Description Record 2'):
                    binary_data = data_records[i_rec]
                    i_rec += 1
                    fmt = '<'
                    for data_format in record_format:
                        fmt += data_format[1]
                    if verbose:
                        print('')
                        print('')
                        print('-' * 60)
                        print('')
                        print(record_format)
                        print(fmt)
                        print('')
                    data = struct.unpack(fmt, binary_data)
                    if verbose:
                        print('')
                        print(data)
                        print('')
                    for j, data_format in enumerate(record_format):
                        if isinstance(data[j], bytes):
                            self.metadata[data_format[0]] = \
                                data[j].decode('ascii')
                        else:
                            self.metadata[data_format[0]] = data[j]
                        if verbose:
                            print(
                                data_format[0],
                                ': ',
                                self.metadata[
                                    data_format[0]])
            # read spectrum records
            # These records are the spectrum data stored as INTEGER*4
            # numbers beginning with the channel number given and going
            # through the number of channels in the file. They are stored
            # as 64-word records, which gives 32 data channels per record.
            # They are stored sequentially, beginning with the record
            # pointer given.
            i_channel = 0
            for j in range(256):
                binary_data = data_records[i_rec]
                i_rec += 1
                N = struct.unpack('<32I', binary_data)
                # print(': ', N)
                for j, N_j in enumerate(N):
                    self.channels = np.append(self.channels, i_channel)
                    self.data = np.append(self.data, N_j)
                    i_channel += 1
            # read record data
            for record_format in self.SPC_FORMAT_END:
                binary_data = data_records[i_rec]
                i_rec += 1
                fmt = '<'
                for data_format in record_format:
                    fmt += data_format[1]
                if verbose:
                    print('')
                    print('')
                    print('-' * 60)
                    print('')
                    print(record_format)
                    print(fmt)
                    print('')
                data = struct.unpack(fmt, binary_data)
                if verbose:
                    print('')
                    print(data)
                    print('')
                for j, data_format in enumerate(record_format):
                    if isinstance(data[j], bytes):
                        self.metadata[data_format[0]] = data[j].decode('ascii')
                    else:
                        self.metadata[data_format[0]] = data[j]
                    if verbose:
                        print(
                            data_format[0],
                            ': ',
                            self.metadata[
                                data_format[0]])
        # finish the parsing
        self.sample_description = self.metadata['Sample Description']
        self.detector_description = self.metadata['Detector Description']
        print(self.metadata['Start date of sample collection'])
        self.metadata['Start date of sample collection'] = \
            self.metadata['Start date of sample collection'][:-1]
        print(self.metadata['Start date of sample collection'])
        print(self.metadata['Start time of sample collection'])
        self.collection_start = dateutil.parser.parse(
            self.metadata['Start date of sample collection'] + ' ' +
            self.metadata['Start time of sample collection'])
        print(self.collection_start)
        print(self.metadata['Stop date of sample collection'])
        self.metadata['Stop date of sample collection'] = \
            self.metadata['Stop date of sample collection'][:-1]
        print(self.metadata['Stop date of sample collection'])
        print(self.metadata['Stop time of sample collection'])
        self.collection_stop = dateutil.parser.parse(
            self.metadata['Stop date of sample collection'] + ' ' +
            self.metadata['Stop time of sample collection'])
        print(self.collection_stop)
        self.location_description = \
            self.metadata['Location Description Record 1'][3:]
        self.location_description = self.location_description.split(
            '\x00\x00\x00')[0].replace('\x00', '\n')
        if len(data_records) > 279:
            self.location_description += \
                self.metadata['Location Description Record 2'].split(
                    '\x00\x00\x00')[0].replace('\x00', '\n')
        self.hardware_status = (
            self.metadata['Hardware Parameters Record 1'] +
            self.metadata['Hardware Parameters Record 2']).split(
                '\x00\x00\x00')[0].replace('\x00', '\n')
        self.livetime = float(self.metadata['Live Time'])
        self.realtime = float(self.metadata['Real Time'])
        assert self.realtime > 0.0
        assert self.livetime > 0.0
        self.num_channels = len(self.channels)
        try:
            self.cal_coeff = [
                float(self.metadata['Calibration parameter 0']),
                float(self.metadata['Calibration parameter 1']),
                float(self.metadata['Calibration parameter 2']),
            ]
        except KeyError:
            print('Error - calibration parameters not found')


if __name__ == '__main__':
    import glob
    import matplotlib.pyplot as plt

    data_files = glob.glob('samples/*.[Ss][Pp][Cc]')
    plt.figure()
    for data_file in data_files:
        print('')
        print(data_file)
        spec = SpcFile(data_file)
        spec.read()
        spec.apply_calibration()
        print(spec)
        plt.semilogy(
            spec.energies,
            spec.data / spec.energy_bin_widths / spec.livetime,
            label=data_file.split('/')[-1])
        plt.xlabel('Energy (keV)')
        plt.ylabel('Counts/keV/sec')
        plt.xlim(0, 2800)
    plt.legend(prop={'size': 8})
    plt.show()
