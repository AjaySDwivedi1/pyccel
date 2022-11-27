from pyccel import cuda
from pyccel.decorators import kernel, device
import numpy as np
import cupy as cp
import math


def div_up(a: 'int', b: 'int') -> 'int':
    return (((a) + (b)-1) // (b))

@device
def cndGPU(d: 'float') -> 'float':
    A1 = 0.31938153
    A2 = -0.356563782
    A3 = 1.781477937
    A4 = -1.821255978
    A5 = 1.330274429
    RSQRT2PI = 0.39894228040143267793994605993438

    K = 1.0 / (1.0 + 0.2316419 * math.fabs(d))
    cnd = RSQRT2PI * math.exp(-0.5 * d * d) * (K * (A1 + K * (A2 + K * (A3 + K * (A4 + K * A5)))))
    if (d > 0):
        cnd = 1.0 - cnd
    return cnd

@device
def BlackScholesBodyGPU(S: 'float', X: 'float', T: 'float', R: 'float', V: 'float'):
    sqrtT = math.sqrt(T)
    d1 = (math.log(S / X) + (R + 0.5 * V * V) * T)
    d2 = d1 - V * sqrtT
    CNDD1 = cndGPU(d1)
    CNDD2 = cndGPU(d2)
    expRT = math.exp(-R * T)
    CallResult = S * CNDD1 - X * expRT * CNDD2
    PutResult = X * expRT * (1.0 - CNDD2) - S * (1.0 - CNDD1)
    return CallResult, PutResult

@kernel
def blackscholesGPU(d_CallResult: 'double[:]', d_PutResult: 'double[:]', d_StockPrice: 'double[:]', d_OptionStrike: 'double[:]', d_OptionYears: 'double[:]', Riskfree: 'double', Volatility: 'double', optn: 'int'):
    opt = cuda.blockDim(0) * cuda.blockIdx(0) + cuda.threadIdx(0)
    pt = opt / 2
    if opt < (optn / 2):
        for i in range(opt, optn, optn/2):
            d_CallResult[i], d_PutResult[i] = BlackScholesBodyGPU(d_StockPrice[i], d_OptionStrike[i], d_OptionYears[i], Riskfree, Volatility)

if __name__ == "__main__":
    opt_n = 20000000
    num_iter = 512
    opt_sz = opt_n * 4
    riskfree = 0.02
    volatility = 0.30

    h_StockPrice = np.empty(opt_n, dtype=np.float64)
    h_OptionStrike = np.empty(opt_n, dtype=np.float64)
    h_OptionYears = np.empty(opt_n, dtype=np.float64)

    for i in range(opt_n):
        h_StockPrice[i] = cuda.random.uniform(5.0, 30.0)
        h_OptionStrike[i] = cuda.random.uniform(1.0, 100.0)
        h_OptionYears[i] = cuda.random.uniform(0.25, 10.0)

    d_CallResult = cp.empty(opt_n, dtype=np.float64)
    d_PutResult = cp.empty(opt_n, dtype=np.float64)

    d_StockPrice = cuda.array(h_StockPrice, memory_location='device')
    d_OptionStrike = cuda.array(h_OptionStrike, memory_location='device')
    d_OptionYears = cuda.array(h_OptionYears, memory_location='device')

    cuda.deviceSynchronize()
    for i in range(num_iter):
        blackscholesGPU[int(div_up(opt_n / 2, 128)), 128](d_CallResult,
                d_PutResult, d_StockPrice, d_OptionStrike,
                d_OptionYears, riskfree, volatility, opt_n)
    cuda.deviceSynchronize()
    h_CallResultGPU = cuda.copy(d_CallResult, 'host')
    cuda.deviceSynchronize()