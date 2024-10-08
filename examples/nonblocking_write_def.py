#
# Copyright (C) 2024, Northwestern University and Argonne National Laboratory
# See COPYRIGHT notice in top-level directory.
#

"""
This example is the same as nonblocking_write.py expect all nonblocking
write requests (calls to iput and bput) are posted in define mode.
It creates a netcdf file in CDF-5 format and writes a number of
3D integer non-record variables. The measured write bandwidth is reported
at the end. Usage: (for example)

To run:
  mpiexec -n num_processes nonblocking_write_def.py [filename] [len]

  where len decides the size of each local array, which is len x len x len.
  So, each non-record variable is of size len*len*len * nprocs * sizeof(int)
  All variables are partitioned among all processes in a 3D
  block-block-block fashion. Below is an example standard output from
  command:

  mpiexec -n 32 python3 nonblocking_write_def.py tmp/test1.nc -l 100

  MPI hint: cb_nodes        = 2
  MPI hint: cb_buffer_size  = 16777216
  MPI hint: striping_factor = 32
  MPI hint: striping_unit   = 1048576
  Local array size 100 x 100 x 100 integers, size = 3.81 MB
  Global array size 400 x 400 x 200 integers, write size = 0.30 GB
  procs    Global array size  exec(sec)  write(MB/s)
  -------  ------------------  ---------  -----------
    32     400 x  400 x  200     6.67       45.72
"""

import sys, os, argparse, inspect
import numpy as np
from mpi4py import MPI
import pnetcdf

def parse_help():
    help_flag = "-h" in sys.argv or "--help" in sys.argv
    if help_flag and rank == 0:
        help_text = (
            "Usage: {} [-h] | [-q] [file_name]\n"
            "       [-h] Print help\n"
            "       [-q] Quiet mode (reports when fail)\n"
            "       [-l len] size of each dimension of the local array\n"
            "       [filename] (Optional) output netCDF file name\n"
        ).format(sys.argv[0])
        print(help_text)
    return help_flag


def pnetcdf_io(file_name, length):
    NDIMS = 3
    NUM_VARS = 10

    if verbose and rank == 0:
        print("Number of variables = ", NUM_VARS)
        print("Number of dimensions = ", NDIMS)

    # set subarray access pattern
    starts = np.zeros(NDIMS, dtype=np.int32)
    counts = np.zeros(NDIMS, dtype=np.int32)
    gsizes = np.zeros(NDIMS, dtype=np.int32)
    buf = []

    psizes = MPI.Compute_dims(nprocs, NDIMS)
    starts[0] = rank % psizes[0]
    starts[1] = (rank // psizes[1]) % psizes[1]
    starts[2] = (rank // (psizes[0] * psizes[1])) % psizes[2]

    bufsize = 1
    for i in range(NDIMS):
        gsizes[i] = length * psizes[i]
        starts[i] *= length
        counts[i] = length
        bufsize *= length

    # Allocate buffer and initialize with non-zero numbers
    for i in range(NUM_VARS):
        buf.append(np.empty(bufsize, dtype=np.int32))
        for j in range(bufsize):
            buf[i][j] = rank * i + 123 + j

    # Create the file
    f = pnetcdf.File(filename = filename,
                     mode = 'w',
                     format = "NC_64BIT_DATA",
                     comm = comm,
                     info = None)

    # Define dimensions
    dims = []
    for i in range(NDIMS):
        dim = f.def_dim(chr(ord('x')+i), gsizes[i])
        dims.append(dim)

    # Define variables
    vars = []
    for i in range(NUM_VARS):
        var = f.def_var("var{}".format(i), pnetcdf.NC_INT, dims)
        vars.append(var)

    # Write one variable at a time
    for i in range(NUM_VARS):
        vars[i].iput_var(buf[i], start = starts, count = counts)

    # exit define mode and enter data mode
    f.enddef()

    # commit posted nonblocking requests
    f.wait_all(num = pnetcdf.NC_REQ_ALL)

    # use nonblocking bput APIs
    # First, calculate the amount of space required
    bbufsize = bufsize * NUM_VARS * np.dtype(np.int32).itemsize
    f.attach_buff(bbufsize)

    # call bput for writing to one variable at a time
    reqs = []
    for i in range(NUM_VARS):
        req_id = vars[i].bput_var(buf[i], start = starts, count = counts)
        reqs.append(req_id)
        # can safely change contents or free up the buf[i] here

    # wait for the nonblocking I/O to complete
    req_errs = [None] * NUM_VARS
    f.wait_all(NUM_VARS, reqs, req_errs)

    # check errors
    for i in range(NUM_VARS):
        if pnetcdf.strerrno(req_errs[i]) != "NC_NOERR":
            print(f"Error on request {i}:",  pnetcdf.strerror(req_errs[i]))

    # detach the temporary buffer
    f.detach_buff()

    # close the file
    f.close()


if __name__ == "__main__":
    comm = MPI.COMM_WORLD
    rank = comm.Get_rank()
    nprocs = comm.Get_size()

    if parse_help():
        MPI.Finalize()
        sys.exit(1)

    # get command-line arguments
    args = None
    parser = argparse.ArgumentParser()
    parser.add_argument("dir", nargs="?", type=str, help="(Optional) output netCDF file name",\
                         default = "testfile.nc")
    parser.add_argument("-q", help="Quiet mode (reports when fail)", action="store_true")
    parser.add_argument("-l", help="Size of each dimension of the local array\n")
    args = parser.parse_args()

    verbose = False if args.q else True

    length = 10
    if args.l and int(args.l) > 0:
       length = int(args.l)

    filename = args.dir

    if verbose and rank == 0:
        print("{}: example of nonblocking APIs in define mode".format(os.path.basename(__file__)))

    try:
        pnetcdf_io(filename, length)
    except BaseException as err:
        print("Error: type:", type(err), str(err))
        raise

    MPI.Finalize()

