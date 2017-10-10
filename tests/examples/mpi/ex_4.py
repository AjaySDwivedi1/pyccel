# coding: utf-8

from pyccel.mpi import *

ierr = mpi_init()

comm = mpi_comm_world
size = comm.size
rank = comm.rank

if rank == 0:
    partner = 1

if rank == 1:
    partner = 0

msg = rank + 1000
val = -1
tag = 1234
ierr = comm.sendrecv (msg, partner, tag, val, partner, tag)

print('I, process ', rank, ', I received', val, ' from process ', partner)

ierr = mpi_finalize()
