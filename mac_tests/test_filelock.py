import time
from filelock import FileLock
import pytest
import sys
sys.stdout = sys.stderr

@pytest.mark.parametrize('test_num',range(10))
def test_locking(test_num):
    print(test_num)
    start = time.time()
    with FileLock('.lock_acquisition.lock'):
        end = time.time()
        print(test_num, " waited ", end-start)
        time.sleep(10)
