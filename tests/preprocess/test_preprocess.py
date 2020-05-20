# coding: utf-8

from pyccel.parser.errors import Errors
from pyccel.parser import Parser
import os
import pytest

base_dir = os.path.dirname(os.path.realpath(__file__))
path_dir = os.path.join(base_dir, 'scripts')

files = sorted(os.listdir(path_dir))
files = [os.path.join(path_dir,f) for f in files if (f.endswith(".py"))]

@pytest.mark.parametrize("f", files)
def test_preprocess(f):
    pyccel = Parser(f)
    pyccel.parse()
    print(pyccel.fst)

    # reset Errors singleton
    errors = Errors()
    errors.reset()

######################
if __name__ == '__main__':
    print('*********************************')
    print('***                           ***')
    print('***     TESTING preprocess    ***')
    print('***                           ***')
    print('*********************************')

    for f in files:
        print('> testing {0}'.format(str(os.path.basename(f))))
        test_preprocess(f)

    print('\n')
