# pylint: disable=missing-function-docstring, disable=unused-variable, missing-module-docstring

import cupy as cp
from pyccel.decorators import kernel, types
from pyccel import cuda

@kernel
@types('int[:]', 'int[:]')
def func(a, b):
    i = cuda.threadIdx(0) + cuda.blockIdx(0) * cuda.blockDim(0)
    print("Hello World! ", a[i], b[i])

if __name__ == '__main__':
    threads_per_block = 32
    n_blocks = 1
    arr1 = cp.ravel([[1,2],[1,3]])
    arr2 = cp.ravel([1,2,3,4])
    cuda.synchronize()
    func[n_blocks, threads_per_block](arr1, arr2)
    cuda.synchronize()
