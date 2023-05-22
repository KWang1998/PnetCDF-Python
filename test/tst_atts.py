import math
import subprocess
import sys
import unittest
import os
import tempfile
import warnings
import math

import numpy as np
from collections import OrderedDict
from numpy.random.mtrand import uniform
from utils import validate_nc_file
from mpi4py import MPI
import pncpy

# test attribute creation
FILE_NAME = 'tst_atts.nc'
VAR_NAME="dummy_var"
DIM1_NAME="x"
DIM1_LEN=2
DIM2_NAME="y"
DIM2_LEN=3
DIM3_NAME="z"
DIM3_LEN=25
STRATT = 'string attribute'
EMPTYSTRATT = ''
INTATT = 1
FLOATATT = math.pi
SEQATT = np.arange(10)

comm = MPI.COMM_WORLD
rank = comm.Get_rank()
size = comm.Get_size()


#ATTDICT = {'stratt':STRATT,'floatatt':FLOATATT,'seqatt':SEQATT,
#           'stringseqatt':''.join(STRINGSEQATT), # changed in issue #770
#           'emptystratt':EMPTYSTRATT,'intatt':INTATT}
ATTDICT = {'stratt':STRATT,'floatatt':FLOATATT,'seqatt':SEQATT,
           'emptystratt':EMPTYSTRATT,'intatt':INTATT}

class VariablesTestCase(unittest.TestCase):

    def setUp(self):
        if (len(sys.argv) == 2) and os.path.isdir(sys.argv[1]):
            self.file_path = os.path.join(sys.argv[1], FILE_NAME)
        else:
            self.file_path = FILE_NAME
        self._file_format = "64BIT_DATA"
        with pncpy.File(self.file_path,'w', format = self._file_format) as f:
            # try to set a dataset attribute with one of the reserved names.
            f.put_att('file_format','netcdf5_format')
            # test attribute renaming
            f.stratt_tmp = STRATT
            f.renameAttribute('stratt_tmp','stratt')
            f.emptystratt = EMPTYSTRATT
            f.floatatt = FLOATATT
            f.intatt = INTATT
            f.seqatt = SEQATT
            # sequences of strings converted to a single string.
            f.def_dim(DIM1_NAME, DIM1_LEN)
            f.def_dim(DIM2_NAME, DIM2_LEN)
            f.def_dim(DIM3_NAME, DIM3_LEN)

            v = f.def_var(VAR_NAME, pncpy.NC_DOUBLE, (DIM1_NAME,DIM2_NAME,DIM3_NAME))
            # try to set a variable attribute with one of the reserved names.
            v.put_att('ndim','three')
            v.setncatts({'foo': 1})
            v.setncatts(OrderedDict(bar=2))
            v.stratt_tmp = STRATT
            v.renameAttribute('stratt_tmp','stratt')
            v.emptystratt = EMPTYSTRATT
            v.intatt = INTATT
            v.floatatt = FLOATATT
            v.seqatt = SEQATT
            # try set the attribute "_FillValue" to set the fill value of netCDF fill value 
            v._FillValue = -999.
            f.foo = np.array('bar','S')
            f.foo = np.array('bar','U')
        assert validate_nc_file(self.file_path) == 0
        


    def tearDown(self):
        # Remove the temporary files
        if (rank == 0) and not((len(sys.argv) == 2) and os.path.isdir(sys.argv[1])):
            os.remove(self.file_path)
    
    def test_file_attr_dict_(self):
        with pncpy.File(self.file_path, 'r') as f:
            # check __dict__ method for accessing all netCDF attributes.

            for key,val in ATTDICT.items():
                if type(val) == np.ndarray:
                    assert f.__dict__[key].tolist() == val.tolist()
                else:
                    assert f.__dict__[key] == val
    def test_attr_access(self):
        with pncpy.File(self.file_path, 'r') as f:
            v = f.variables[VAR_NAME]
            # check accessing individual attributes.
            assert f.intatt == INTATT
            assert f.floatatt == FLOATATT
            assert f.stratt == STRATT
            assert f.emptystratt == EMPTYSTRATT
            # check accessing variable individual attributes.
            assert v.intatt == INTATT
            assert v.floatatt == FLOATATT
            assert v.stratt == STRATT
            assert v.seqatt.tolist() == SEQATT.tolist()
            assert v.get_att('ndim') == 'three'
            assert v.get_att('foo') == 1
            assert v.get_att('bar') == 2
            assert v._FillValue == -999.

    def test_var_attr_dict_(self):
        with pncpy.File(self.file_path, 'r') as f:
            v = f.variables[VAR_NAME]

            # variable attributes.
            # check __dict__ method for accessing all netCDF attributes.
            for key,val in ATTDICT.items():
                if type(val) == np.ndarray:
                    assert v.__dict__[key].tolist() == val.tolist()
                else:
                    assert v.__dict__[key] == val


if __name__ == '__main__':
    suite = unittest.TestSuite()
    suite.addTest(VariablesTestCase("test_file_attr_dict_"))
    suite.addTest(VariablesTestCase("test_attr_access"))
    suite.addTest(VariablesTestCase("test_var_attr_dict_"))
    runner = unittest.TextTestRunner()
    result = runner.run(suite)
    if not result.wasSuccessful():
        sys.exit(1)

