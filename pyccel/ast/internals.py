# -*- coding: utf-8 -*-
#------------------------------------------------------------------------------------------#
# This file is part of Pyccel which is released under MIT License. See the LICENSE file or #
# go to https://github.com/pyccel/pyccel/blob/master/LICENSE for full license details.     #
#------------------------------------------------------------------------------------------#
"""
File containing basic classes which are used throughout pyccel.
To avoid circular imports this file should only import from basic, datatypes, and literals
"""
from .basic     import Basic, PyccelAstNode, Immutable
from .datatypes import NativeInteger, default_precision
from .literals  import LiteralInteger

__all__ = (
    'PyccelInternalFunction',
    'PyccelArraySize'
)


class PyccelInternalFunction(PyccelAstNode):
    """ Abstract class used by function calls
    which are translated to Pyccel objects
    """
    _attribute_nodes = ('_args',)
    def __init__(self, *args):
        self._args   = tuple(args)
        super().__init__()

    @property
    def args(self):
        """ The arguments passed to the function
        """
        return self._args

    @property
    def is_elemental(self):
        """ Indicates whether the function should be
        called elementwise for an array argument
        """
        return False


class PyccelArraySize(PyccelInternalFunction):
    """
    Class representing a call to a function which would
    return the shape of an object in a given dimension

    Parameters
    ==========
    arg   : PyccelAstNode
            A PyccelAstNode of unknown shape
    index : int
            The dimension along which the shape is
            provided
    """
    _attribute_nodes = ('_arg', '_index')

    def __init__(self, arg, index):
        if not isinstance(arg, (list,
                                tuple,
                                PyccelAstNode)):
            raise TypeError('Unknown type of  %s.' % type(arg))
        if isinstance(index, int):
            index = LiteralInteger(index)
        elif not isinstance(index, PyccelAstNode):
            raise TypeError('Unknown type of  %s.' % type(index))

        self._arg   = arg
        self._index = index
        self._dtype = NativeInteger()
        self._rank  = 0
        self._shape = ()
        self._precision = default_precision['integer']
        super().__init__()

    @property
    def arg(self):
        """ Object whose size is investigated
        """
        return self._arg

    @property
    def index(self):
        """ Dimension along which the size is calculated
        """
        return self._index

    def __str__(self):
        return 'Shape({},{})'.format(str(self.arg), str(self.index))

    def __eq__(self, other):
        if isinstance(other, PyccelArraySize):
            return self.arg == other.arg and self.index == other.index
        else:
            return False

class Slice(Basic):

    """Represents a slice in the code.

    Parameters
    ----------
    start : PyccelSymbol or int
        starting index

    stop : PyccelSymbol or int
        ending index

    step : PyccelSymbol or int default None

    Examples
    --------
    >>> from pyccel.ast.internals import Slice, symbols
    >>> start, end, step = symbols('start, stop, step', integer=True)
    >>> Slice(start, stop)
    start : stop
    >>> Slice(None, stop)
     : stop
    >>> Slice(start, None)
    start :
    >>> Slice(start, stop, step)
    start : stop : step
    """
    _attribute_nodes = ('_start','_stop','_step')

    def __init__(self, start, stop, step = None):
        self._start = start
        self._stop = stop
        self._step = step
        super().__init__()
        if PyccelAstNode.stage == 'syntactic':
            return
        if start is not None and not (hasattr(start, 'dtype') and isinstance(start.dtype, NativeInteger)):
            raise TypeError('Slice start must be Integer or None')
        if stop is not None and not (hasattr(stop, 'dtype') and isinstance(stop.dtype, NativeInteger)):
            raise TypeError('Slice stop must be Integer or None')
        if step is not None and not (hasattr(step, 'dtype') and isinstance(step.dtype, NativeInteger)):
            raise TypeError('Slice step must be Integer or None')

    @property
    def start(self):
        """ Index where the slicing of the object starts
        """
        return self._start

    @property
    def stop(self):
        """ Index until which the slicing takes place
        """
        return self._stop

    @property
    def step(self):
        """ The difference between each index of the
        objects in the slice
        """
        return self._step

    def __str__(self):
        if self.start is None:
            start = ''
        else:
            start = str(self.start)
        if self.stop is None:
            stop = ''
        else:
            stop = str(self.stop)
        return '{0} : {1}'.format(start, stop)

class PyccelSymbol(str, Immutable):
    """Symbolic placeholder for a Python variable, which has a name but no type yet.
    This is very generic, and it can also represent a function or a module.

    Parameters
    ----------
    name : String
        name of the symbol

    Examples
    --------
    >>> from pyccel.ast.internals import PyccelSymbol
    >>> x = PyccelSymbol('x')
    x
    """

def symbols(names):
    """
    Transform strings into instances of PyccelSymbol class.

    function returns a sequence of symbols with names taken
    from argument, which can be a comma delimited
    string

    Parameters
    ----------
    name : String
        comma delimited string

    Return
    ----------
    Tuple :
        tuple of instances of PyccelSymbol
    Examples
    --------
    >>> from pyccel.ast.internals import symbols
    >>> x, y, z = symbols('x,y,z')
    (x, y, z)
    """
    names = names.split(',')
    symbols = [PyccelSymbol(name.strip()) for name in names]
    return tuple(symbols)
