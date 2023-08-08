# coding: utf-8
#------------------------------------------------------------------------------------------#
# This file is part of Pyccel which is released under MIT License. See the LICENSE file or #
# go to https://github.com/pyccel/pyccel/blob/master/LICENSE for full license details.     #
#------------------------------------------------------------------------------------------#

from pyccel.decorators import __all__ as pyccel_decorators

from pyccel.ast.builtins   import PythonMin, PythonMax
from pyccel.ast.core       import CodeBlock, Import, Assign, FunctionCall, For, AsName, FunctionAddress
from pyccel.ast.core       import IfSection, FunctionDef, Module, DottedFunctionCall
from pyccel.ast.datatypes  import default_precision
from pyccel.ast.functionalexpr import FunctionalFor
from pyccel.ast.literals   import LiteralTrue, LiteralString
from pyccel.ast.literals   import LiteralInteger, LiteralFloat, LiteralComplex
from pyccel.ast.numpyext   import NumpyShape, NumpySize, numpy_target_swap
from pyccel.ast.numpyext   import NumpyArray, NumpyNonZero
from pyccel.ast.numpyext   import DtypePrecisionToCastFunction
from pyccel.ast.variable   import DottedName, HomogeneousTupleVariable, Variable
from pyccel.ast.utilities  import builtin_import_registry as pyccel_builtin_import_registry
from pyccel.ast.utilities  import decorators_mod

from pyccel.codegen.printing.codeprinter import CodePrinter

from pyccel.errors.errors import Errors
from pyccel.errors.messages import PYCCEL_RESTRICTION_TODO

errors = Errors()

#==============================================================================

# Dictionary mapping imported targets to their aliases used internally by pyccel
# This prevents a mismatch between printed imports and function calls
# The keys are modules from which the target is imported
# The values are a dictionary whose keys are object aliases and whose values
# are the names used in pyccel
import_object_swap = { 'numpy': numpy_target_swap}
import_target_swap = {
        'numpy' : {'double'     : 'float64',
                   'prod'       : 'product',
                   'empty_like' : 'empty',
                   'zeros_like' : 'zeros',
                   'ones_like'  : 'ones',
                   'max'        : 'amax',
                   'min'        : 'amin',
                   'T'          : 'transpose',
                   'full_like'  : 'full',
                   'absolute'   : 'abs'},
        'numpy.random' : {'random' : 'rand'}
        }
import_source_swap = {
        'omp_lib' : 'pyccel.stdlib.internal.openmp'
        }

class PythonCodePrinter(CodePrinter):
    """
    A printer for printing code in Python.

    A printer to convert Pyccel's AST to strings of Python code.
    As for all printers the navigation of this file is done via _print_X
    functions.

    Parameters
    ----------
    filename : str
        The name of the file being pyccelised.
    """
    printmethod = "_pycode"
    language = "python"

    _default_settings = {
        'tabwidth': 4,
    }

    def __init__(self, filename):
        errors.set_target(filename, 'file')
        super().__init__()
        self._additional_imports = {}
        self._aliases = {}
        self._ignore_funcs = []

    def _indent_codestring(self, lines):
        tab = " "*self._default_settings['tabwidth']
        if lines == '':
            return lines
        else:
            # lines ends with \n
            return tab+lines.strip('\n').replace('\n','\n'+tab)+'\n'

    def _format_code(self, lines):
        return lines

    def get_additional_imports(self):
        """return the additional imports collected in printing stage"""
        imports = [i for tup in self._additional_imports.values() for i in tup[1]]
        return imports

    def insert_new_import(self, source, target, alias = None):
        """ Add an import of an object which may have been
        added by pyccel and therefore may not have been imported
        """
        if alias and alias!=target:
            target = AsName(target, alias)
        import_obj = Import(source, target)
        source = str(source)
        src_info = self._additional_imports.setdefault(source, (set(), []))
        if any(i not in src_info[0] for i in import_obj.target):
            src_info[0].update(import_obj.target)
            src_info[1].append(import_obj)

    def _find_functional_expr_and_iterables(self, expr):
        """
        Traverse through the loop representing a FunctionalFor or GeneratorComprehension
        to extract the central expression and the different iterable objects

        Parameters
        ----------
        expr : FunctionalFor

        Returns
        -------
        body      : PyccelAstNode
                    The expression inside the for loops
        iterables : list of Iterables
                    The iterables over which the for loops iterate
        """
        dummy_var = expr.index
        iterables = []
        body = expr.loops[1]
        while not isinstance(body, Assign):
            if isinstance(body, CodeBlock):
                body = list(body.body)
                while isinstance(body[0], FunctionalFor):
                    func_for = body.pop(0)
                    # Replace the temporary assign value with the FunctionalFor expression
                    # so the loop is printed inline
                    for b in body:
                        b.substitute(func_for.lhs, func_for)
                if len(body) > 1:
                    # Ensure all assigns assign to the dummy we are searching for and do not introduce unexpected variables
                    if any(not(isinstance(b, Assign) and b.lhs is dummy_var) for b in body[1:]):
                        raise NotImplementedError("Pyccel has introduced unnecessary statements which it cannot yet disambiguate in the python printer")
                body = body[0]
            elif isinstance(body, For):
                iterables.append(body.iterable)
                body = body.body
            elif isinstance(body, FunctionalFor):
                body, it = self._find_functional_expr_and_iterables(body)
                iterables.extend(it)
            else:
                raise NotImplementedError(f"Type {type(body)} not handled in a FunctionalFor")
        return body, iterables

    #----------------------------------------------------------------------

    def _print_Header(self, expr):
        return ''

    def _print_tuple(self, expr):
        fs = ', '.join(self._print(f) for f in expr)
        return f'({fs})'

    def _print_NativeBool(self, expr):
        return 'bool'

    def _print_NativeInteger(self, expr):
        return 'int'

    def _print_NativeFloat(self, expr):
        return 'float'

    def _print_NativeComplex(self, expr):
        return 'complex'

    def _print_Variable(self, expr):
        return self._print(expr.name)

    def _print_DottedVariable(self, expr):
        rhs_code = self._print_Variable(expr)
        lhs_code = self._print(expr.lhs)
        return f"{lhs_code}.{rhs_code}"

    def _print_FunctionDefArgument(self, expr):
        name = self._print(expr.name)
        type_annotation = ''
        default = ''

        if expr.annotation:
            type_annotation = f' : {expr.annotation}'

        if expr.has_default:
            if isinstance(expr.value, FunctionDef):
                default = f' = {self._print(expr.value.name)}'
            else:
                default = f' = {self._print(expr.value)}'

        return f'{name}{type_annotation}{default}'

    def _print_FunctionCallArgument(self, expr):
        if expr.keyword:
            return f'{expr.keyword} = {self._print(expr.value)}'
        else:
            return self._print(expr.value)

    def _print_Idx(self, expr):
        return self._print(expr.name)

    def _print_IndexedElement(self, expr):
        indices = expr.indices
        if isinstance(indices, (tuple, list)):
            # this a fix since when having a[i,j] the generated code is a[(i,j)]
            if len(indices) == 1 and isinstance(indices[0], (tuple, list)):
                indices = indices[0]

            indices = [self._print(i) for i in indices]
            if isinstance(expr.base, HomogeneousTupleVariable):
                indices = ']['.join(i for i in indices)
            else:
                indices = ','.join(i for i in indices)
        else:
            errors.report(PYCCEL_RESTRICTION_TODO, symbol=expr,
                severity='fatal')

        base = self._print(expr.base)
        return f'{base}[{indices}]'

    def _print_Interface(self, expr):
        # TODO: Improve. See #885
        func = expr.functions[0]
        if not isinstance(func, FunctionAddress):
            func.rename(expr.name)
        return self._print(func)

    def _print_FunctionDef(self, expr):
        self.set_scope(expr.scope)
        name       = self._print(expr.name)
        imports    = ''.join(self._print(i) for i in expr.imports)
        interfaces = ''.join(self._print(i) for i in expr.interfaces if not i.is_argument)
        functions  = [f for f in expr.functions if not any(f in i.functions for i in expr.interfaces)]
        functions  = ''.join(self._print(f) for f in functions)
        body    = self._print(expr.body)
        body    = self._indent_codestring(body)
        args    = ', '.join(self._print(i) for i in expr.arguments)

        imports    = self._indent_codestring(imports)
        functions  = self._indent_codestring(functions)
        interfaces = self._indent_codestring(interfaces)

        doc_string = self._print(expr.doc_string) if expr.doc_string else ''
        doc_string = self._indent_codestring(doc_string)

        body = ''.join([doc_string, functions, interfaces, imports, body])

        code = (f'def {name}({args}):\n'
                f'{body}\n')
        decorators = expr.decorators
        if decorators:
            if decorators['template']:
                # Eliminate template_dict because it is useless in the printing
                expr.decorators['template'] = expr.decorators['template']['decorator_list']
            else:
                expr.decorators.pop('template')
            for n,f in decorators.items():
                if n in pyccel_decorators:
                    self.insert_new_import(DottedName('pyccel.decorators'), AsName(decorators_mod[n], n))
                # TODO - All decorators must be stored in a list
                if not isinstance(f, list):
                    f = [f]
                dec = ''
                for func in f:
                    if isinstance(func, FunctionCall):
                        args = func.args
                    elif func == n:
                        args = []
                    else:
                        args = [LiteralString(a) for a in func]
                    if n == 'types' and len(args)==0:
                        continue
                    if args:
                        args = ', '.join(self._print(i) for i in args)
                        dec += f'@{n}({args})\n'

                    else:
                        dec += f'@{n}\n'

                code = dec + code
        headers = expr.headers
        if headers:
            headers = self._print(headers)
            code = f'{headers}\n{code}'

        self.exit_scope()
        return code

    def _print_FunctionAddress(self, expr):
        return expr.name

    def _print_Return(self, expr):

        if expr.stmt:
            assigns = {i.lhs: i.rhs for i in expr.stmt.body if isinstance(i, Assign)}
            prelude = ''.join([self._print(i) for i in expr.stmt.body if not isinstance(i, Assign)])
        else:
            assigns = {}
            prelude = ''
        expr_return_vars = [assigns.get(a,a) for a in expr.expr]

        return_vars_str = ','.join(self._print(i) for i in expr_return_vars)

        return prelude+f'return {return_vars_str}\n'

    def _print_Program(self, expr):
        mod_scope = self.scope
        self.set_scope(expr.scope)
        imports  = ''.join(self._print(i) for i in expr.imports)
        body     = self._print(expr.body)
        imports += ''.join(self._print(i) for i in self.get_additional_imports())

        body = imports+body
        body = self._indent_codestring(body)

        self.exit_scope()
        if mod_scope:
            self.set_scope(mod_scope)
        return ('if __name__ == "__main__":\n'
                f'{body}\n')


    def _print_AsName(self, expr):
        name = self._print(expr.name)
        target = self._print(expr.target)
        if name == target:
            return name
        else:
            return f'{name} as {target}'

    def _print_PythonTuple(self, expr):
        args = ', '.join(self._print(i) for i in expr.args)
        if len(expr.args) == 1:
            args += ','
        return '('+args+')'

    def _print_PythonList(self, expr):
        args = ', '.join(self._print(i) for i in expr.args)
        return '['+args+']'

    def _print_PythonBool(self, expr):
        return f'bool({self._print(expr.arg)})'

    def _print_PythonInt(self, expr):
        name = 'int'
        if expr.precision != -1:
            type_name = name + str(expr.precision*8)
            cls       = type(expr)
            name = self._aliases.get(cls, type_name)
            if name == type_name:
                self.insert_new_import(
                        source = 'numpy',
                        target = AsName(cls, name))
        return f'{name}({self._print(expr.arg)})'

    def _print_PythonFloat(self, expr):
        name = 'float'
        if expr.precision != -1:
            type_name = name + str(expr.precision*8)
            cls       = type(expr)
            name = self._aliases.get(cls, type_name)
            if name == type_name:
                self.insert_new_import(
                        source = 'numpy',
                        target = AsName(cls, name))
        return f'{name}({self._print(expr.arg)})'

    def _print_PythonComplex(self, expr):
        name = self._aliases.get(type(expr), expr.name)
        if expr.is_cast:
            return f'{name}({self._print(expr.internal_var)})'
        else:
            return f'{name}({self._print(expr.real)}, {self._print(expr.imag)})'

    def _print_NumpyComplex(self, expr):
        if expr.precision != -1:
            cls       = type(expr)
            name = self._aliases.get(cls, expr.name)
            if name == expr.name:
                self.insert_new_import(
                        source = 'numpy',
                        target = AsName(cls, expr.name))
        else:
            name = 'complex'
        if expr.is_cast:
            return f'{name}({self._print(expr.internal_var)})'
        else:
            return f'{name}({self._print(expr.real)}+{self._print(expr.imag)}*1j)'

    def _print_Iterable(self, expr):
        return self._print(expr.iterable)

    def _print_PythonRange(self, expr):
        start = self._print(expr.start)
        stop  = self._print(expr.stop )
        step  = self._print(expr.step )
        return f'range({start}, {stop}, {step})'

    def _print_PythonEnumerate(self, expr):
        elem = self._print(expr.element)
        if expr.start == 0:
            return f'enumerate({elem})'
        else:
            start = self._print(expr.start)
            return f'enumerate({elem},{start})'

    def _print_PythonMap(self, expr):
        func = self._print(expr.func.name)
        args = self._print(expr.func_args)
        return f'map({func}, {args})'

    def _print_PythonReal(self, expr):
        return f'({self._print(expr.internal_var)}).real'

    def _print_PythonImag(self, expr):
        return f'({self._print(expr.internal_var)}).imag'

    def _print_PythonConjugate(self, expr):
        return f'({self._print(expr.internal_var)}).conjugate()'

    def _print_PythonPrint(self, expr):
        args = ', '.join(self._print(a) for a in expr.expr)
        return f'print({args})\n'

    def _print_PyccelArrayShapeElement(self, expr):
        arg = self._print(expr.arg)
        index = self._print(expr.index)
        expected_name = NumpyShape.name
        name = self._aliases.get(NumpyShape, expected_name)
        if name == expected_name:
            self.insert_new_import(
                    source = 'numpy',
                    target = AsName(type(expr), expected_name))
        return f'{name}({arg})[{index}]'

    def _print_PyccelArraySize(self, expr):
        arg = self._print(expr.arg)
        expected_name = NumpySize.name
        name = self._aliases.get(NumpySize, expected_name)
        if name == expected_name:
            self.insert_new_import(
                    source = 'numpy',
                    target = AsName(type(expr), expected_name))
        return f'{name}({arg})'

    def _print_Comment(self, expr):
        txt = self._print(expr.text)
        return f'# {txt} \n'

    def _print_CommentBlock(self, expr):
        txt = '\n'.join(self._print(c) for c in expr.comments)
        return f'"""{txt}"""\n'

    def _print_Assert(self, expr):
        condition = self._print(expr.test)
        return f"assert {condition}\n"

    def _print_EmptyNode(self, expr):
        return ''

    def _print_DottedName(self, expr):
        return '.'.join(self._print(n) for n in expr.name)

    def _print_FunctionCall(self, expr):
        if expr.funcdef in self._ignore_funcs:
            return ''
        if expr.interface:
            func_name = expr.interface_name
        else:
            func_name = expr.func_name
        args = expr.args
        if isinstance(expr, DottedFunctionCall):
            args = args[1:]
        args_str = ', '.join(self._print(i) for i in args)
        code = f'{func_name}({args_str})'
        if expr.funcdef.results:
            return code
        else:
            return code+'\n'

    def _print_Import(self, expr):
        mod = expr.source_module
        init_func_name = ''
        free_func_name = ''
        if mod:
            init_func = mod.init_func
            if init_func:
                init_func_name = init_func.name
            free_func = mod.free_func
            if free_func:
                free_func_name = free_func.name

        if isinstance(expr.source, AsName):
            source = self._print(expr.source.name)
        else:
            source = self._print(expr.source)

        source = import_source_swap.get(source, source)

        target = [t for t in expr.target if not isinstance(t.object, Module)]

        if not target:
            return f'import {source}\n'
        else:
            if source in import_object_swap:
                target = [AsName(import_object_swap[source].get(i.object,i.object), i.target) for i in target]
            if source in import_target_swap:
                # If the source contains multiple names which reference the same object
                # check if the target is referred to by another name in pyccel.
                # Print the name used by pyccel (either the value from import_target_swap
                # or the original name from the import
                target = [AsName(i.object, import_target_swap[source].get(i.target,i.target)) for i in target]

            target = list(set(target))
            if source in pyccel_builtin_import_registry:
                self._aliases.update([(pyccel_builtin_import_registry[source][t.name].cls_name, t.target) for t in target if t.name != t.target])

            if expr.source_module:
                if expr.source_module.init_func:
                    self._ignore_funcs.append(expr.source_module.init_func)
                if expr.source_module.free_func:
                    self._ignore_funcs.append(expr.source_module.free_func)
            target = [self._print(t) for t in target if t.name not in (init_func_name, free_func_name)]
            target = ', '.join(target)
            return f'from {source} import {target}\n'

    def _print_CodeBlock(self, expr):
        if len(expr.body)==0:
            return 'pass\n'
        else:
            code = ''.join(self._print(c) for c in expr.body)
            return code

    def _print_For(self, expr):
        self.set_scope(expr.scope)
        iterable = self._print(expr.iterable)
        target   = expr.target
        if not isinstance(target,(list, tuple)):
            target = [target]
        target = ','.join(self._print(i) for i in target)
        body   = self._print(expr.body)
        body   = self._indent_codestring(body)
        code   = (f'for {target} in {iterable}:\n'
                f'{body}')

        self.exit_scope()
        return code

    def _print_FunctionalFor(self, expr):
        body, iterators = self._find_functional_expr_and_iterables(expr)
        lhs = self._print(expr.lhs)
        body = self._print(body.rhs)
        for_loops = ' '.join(f'for {self._print(idx)} in {self._print(iters)}'
                        for idx, iters in zip(expr.indices, iterators))

        name = self._aliases.get(type(expr),'array')
        if name == 'array':
            self.insert_new_import(
                    source = 'numpy',
                    target = AsName(NumpyArray, 'array'))

        return f'{lhs} = {name}([{body} {for_loops}])\n'

    def _print_GeneratorComprehension(self, expr):
        body, iterators = self._find_functional_expr_and_iterables(expr)

        rhs = body.rhs
        if isinstance(rhs, (PythonMax, PythonMin)):
            args = rhs.args[0]
            if body.lhs in args:
                args = [a for a in args if a != body.lhs]
                if len(args)==1:
                    rhs = args[0]
                else:
                    rhs = type(body.rhs)(*args)

        body = self._print(rhs)
        for_loops = ' '.join(f'for {self._print(idx)} in {self._print(iters)}'
                        for idx, iters in zip(expr.indices, iterators))

        if expr.get_user_nodes(FunctionalFor):
            return f'{expr.name}({body} {for_loops})'
        else:
            lhs = self._print(expr.lhs)
            return f'{lhs} = {expr.name}({body} {for_loops})\n'

    def _print_While(self, expr):
        cond = self._print(expr.test)
        self.set_scope(expr.scope)
        body = self._indent_codestring(self._print(expr.body))
        self.exit_scope()
        return f'while {cond}:\n{body}'

    def _print_Break(self, expr):
        return 'break\n'

    def _print_Continue(self, expr):
        return 'continue\n'

    def _print_Assign(self, expr):
        lhs = expr.lhs
        rhs = expr.rhs

        lhs_code = self._print(lhs)
        rhs_code = self._print(rhs)
        if isinstance(rhs, Variable) and rhs.rank>1 and rhs.order != lhs.order:
            return f'{lhs_code} = {rhs_code}.T\n'
        else:
            return f'{lhs_code} = {rhs_code}\n'

    def _print_AliasAssign(self, expr):
        lhs = expr.lhs
        rhs = expr.rhs

        lhs_code = self._print(lhs)
        rhs_code = self._print(rhs)
        if isinstance(rhs, Variable) and rhs.order!= lhs.order:
            return f'{lhs_code} = {rhs_code}.T\n'
        else:
            return f'{lhs_code} = {rhs_code}\n'

    def _print_AugAssign(self, expr):
        lhs = self._print(expr.lhs)
        rhs = self._print(expr.rhs)
        op  = self._print(expr.op)
        return f'{lhs} {op}= {rhs}\n'

    def _print_PythonRange(self, expr):
        name = self._aliases.get(type(expr), expr.name)
        start = self._print(expr.start)
        stop  = self._print(expr.stop)
        step  = self._print(expr.step)
        return f'{name}({start}, {stop}, {step})'

    def _print_Allocate(self, expr):
        return ''

    def _print_Deallocate(self, expr):
        return ''

    def _print_NumpyArray(self, expr):
        dtype = self._print(expr.dtype)
        if expr.precision != default_precision[str(expr.dtype)]:
            factor = 16 if dtype == 'complex' else 8
            dtype += str(expr.precision*factor)

        name  = self._aliases.get(type(expr), expr.name)
        arg   = self._print(expr.arg)
        dtype = f"dtype={dtype}"
        order = f"order='{expr.order}'" if expr.order else ''
        args  = ', '.join(a for a in [arg, dtype, order] if a)
        return f"{name}({args})"

    def _print_NumpyAutoFill(self, expr):
        func_name = self._aliases.get(type(expr), expr.name)

        dtype = self._print(expr.dtype)
        if expr.precision != default_precision[str(expr.dtype)]:
            factor = 16 if dtype == 'complex' else 8
            dtype += str(expr.precision*factor)

        shape = self._print(expr.shape)
        dtype = f"dtype={dtype}"
        order = f"order='{expr.order}'" if expr.order else ''
        args  = ', '.join(a for a in [shape, dtype, order] if a)
        return f"{func_name}({args})"

    def _print_NumpyLinspace(self, expr):
        name = self._aliases.get(type(expr), expr.name)
        dtype = self._print(expr.dtype)
        factor = 16 if dtype == 'complex' else 8
        dtype += str(expr.precision*factor)

        start = self._print(expr.start)
        stop = self._print(expr.stop)
        num = self._print(expr.num)
        endpoint = self._print(expr.endpoint)

        return f"{name}({start}, {stop}, num={num}, endpoint={endpoint}, dtype='{dtype}')"

    def _print_NumpyMatmul(self, expr):
        name = self._aliases.get(type(expr), expr.name)
        return f"{name}({self._print(expr.a)}, {self._print(expr.b)})"


    def _print_NumpyFull(self, expr):
        name = self._aliases.get(type(expr), expr.name)
        dtype = self._print(expr.dtype)
        if expr.precision != default_precision[str(expr.dtype)]:
            factor = 16 if dtype == 'complex' else 8
            dtype += str(expr.precision*factor)

        shape      = self._print(expr.shape)
        fill_value = self._print(expr.fill_value)
        dtype      = f"dtype={dtype}"
        order      = f"order='{expr.order}'" if expr.order else ''
        args       = ', '.join(a for a in [shape, fill_value, dtype, order] if a)
        return f"{name}({args})"

    def _print_NumpyArange(self, expr):
        name = self._aliases.get(type(expr), expr.name)
        start = self._print(expr.start)
        stop  = self._print(expr.stop)
        step  = self._print(expr.step)
        dtype = self._print(expr.dtype)
        return f"{name}({start}, {stop}, {step}, dtype={dtype})"

    def _print_PyccelInternalFunction(self, expr):
        name = self._aliases.get(type(expr),expr.name)
        args = ', '.join(self._print(a) for a in expr.args)
        return f"{name}({args})"

    def _print_NumpyArray(self, expr):
        name = self._aliases.get(type(expr),'array')
        if name == 'array':
            self.insert_new_import(
                    source = 'numpy',
                    target = AsName(NumpyArray, 'array'))
        arg = self._print(expr.arg)
        return f"{name}({arg})"

    def _print_NumpyRandint(self, expr):
        name = self._aliases.get(type(expr), expr.name)
        if expr.low:
            args = self._print(expr.low) + ", "
        else:
            args = ""
        args += self._print(expr.high)
        if expr.rank != 0:
            size = self._print(expr.shape)
            args += f", size = {size}"
        return f"{name}({args})"

    def _print_NumpyNorm(self, expr):
        name = self._aliases.get(type(expr), expr.name)
        axis = self._print(expr.axis) if expr.axis else None
        if axis:
            return  f"{name}({self._print(expr.python_arg)},axis={axis})"
        return  f"{name}({self._print(expr.python_arg)})"

    def _print_NumpyNonZero(self, expr):
        name = self._aliases.get(type(expr),'nonzero')
        if name == 'nonzero':
            self.insert_new_import(
                    source = 'numpy',
                    target = AsName(NumpyNonZero, 'nonzero'))
        arg = self._print(expr.array)
        return f"{name}({arg})"

    def _print_NumpyCountNonZero(self, expr):
        name = self._aliases.get(type(expr),'count_nonzero')
        if name == 'count_nonzero':
            self.insert_new_import(
                    source = 'numpy',
                    target = AsName(NumpyNonZero, 'count_nonzero'))

        axis_arg = expr.axis

        arr = self._print(expr.array)
        axis = '' if axis_arg is None else (self._print(axis_arg) + ', ')
        keep_dims = 'keepdims = ' + self._print(expr.keep_dims)

        arg = f'{arr}, {axis}{keep_dims}'

        return f"{name}({arg})"

    def _print_Slice(self, expr):
        start = self._print(expr.start) if expr.start else ''
        stop  = self._print(expr.stop)  if expr.stop  else ''
        step  = self._print(expr.step)  if expr.step  else ''
        return f'{start}:{stop}:{step}'

    def _print_Nil(self, expr):
        return 'None'

    def _print_Pass(self, expr):
        return 'pass\n'

    def _print_PyccelIs(self, expr):
        lhs = self._print(expr.lhs)
        rhs = self._print(expr.rhs)
        return f'{lhs} is {rhs}'

    def _print_PyccelIsNot(self, expr):
        lhs = self._print(expr.lhs)
        rhs = self._print(expr.rhs)
        return f'{lhs} is not {rhs}'

    def _print_If(self, expr):
        lines = []
        for i, (c, e) in enumerate(expr.blocks):
            if i == 0:
                lines.append(f"if {self._print(c)}:\n")

            elif i == len(expr.blocks) - 1 and isinstance(c, LiteralTrue):
                lines.append("else:\n")

            else:
                lines.append(f"elif {self._print(c)}:\n")

            if isinstance(e, CodeBlock):
                body = self._indent_codestring(self._print(e))
                lines.append(body)
            else:
                lines.append(self._print(e))
        return "".join(lines)

    def _print_IfTernaryOperator(self, expr):
        cond = self._print(expr.cond)
        value_true = self._print(expr.value_true)
        value_false = self._print(expr.value_false)
        return f'{value_true} if {cond} else {value_false}'

    def _print_Literal(self, expr):
        dtype = expr.dtype
        precision = expr.precision

        if not isinstance(expr, (LiteralInteger, LiteralFloat, LiteralComplex)) or \
                precision == -1:
            return repr(expr.python_value)
        else:
            cast_func = DtypePrecisionToCastFunction[dtype.name][precision]
            type_name = cast_func.__name__.lower()
            is_numpy  = type_name.startswith('numpy')
            cast_name = cast_func.name
            name = self._aliases.get(cast_func, cast_name)
            if is_numpy and name == cast_name:
                self.insert_new_import(
                        source = 'numpy',
                        target = AsName(cast_func, cast_name))
            return f'{name}({repr(expr.python_value)})'

    def _print_Print(self, expr):
        args = []
        for f in expr.expr:
            if isinstance(f, str):
                args.append(f"'{f}'")

            elif isinstance(f, tuple):
                for i in f:
                    args.append(self._print(i))

            else:
                args.append(self._print(f))

        fs = ', '.join(i for i in args)

        return f'print({fs})\n'

    def _print_Module(self, expr):
        self.set_scope(expr.scope)
        # Print interface functions (one function with multiple decorators describes the problem)
        imports  = ''.join(self._print(i) for i in expr.imports)
        interfaces = ''.join(self._print(i) for i in expr.interfaces)
        # Collect functions which are not in an interface
        funcs = [f for f in expr.funcs if not (any(f in i.functions for i in expr.interfaces) \
                        or f is expr.init_func or f is expr.free_func)]
        funcs = ''.join(self._print(f) for f in funcs)
        classes = ''.join(self._print(c) for c in expr.classes)

        init_func = expr.init_func
        if init_func:
            self._ignore_funcs.append(init_func)
            # Collect initialisation body
            init_if = init_func.get_attribute_nodes(IfSection)[0]
            # Remove boolean from init_body
            init_body = init_if.body.body[:-1]
            init_body = ''.join(self._print(l) for l in init_body)
        else:
            init_body = ''

        free_func = expr.free_func
        if free_func:
            self._ignore_funcs.append(free_func)

        imports += ''.join(self._print(i) for i in self.get_additional_imports())

        body = ''.join((interfaces, funcs, classes, init_body))

        if expr.program:
            expr.program.remove_import(expr.name)
            prog = self._print(expr.program)
        else:
            prog = ''

        self.exit_scope()
        return (f'{imports}\n'
                f'{body}'
                f'{prog}')

    def _print_PyccelPow(self, expr):
        base = self._print(expr.args[0])
        e    = self._print(expr.args[1])
        return f'{base} ** {e}'

    def _print_PyccelAdd(self, expr):
        return ' + '.join(self._print(a) for a in expr.args)

    def _print_PyccelMinus(self, expr):
        return ' - '.join(self._print(a) for a in expr.args)

    def _print_PyccelMul(self, expr):
        return ' * '.join(self._print(a) for a in expr.args)

    def _print_PyccelDiv(self, expr):
        return ' / '.join(self._print(a) for a in expr.args)

    def _print_PyccelMod(self, expr):
        return '%'.join(self._print(a) for a in expr.args)

    def _print_PyccelFloorDiv(self, expr):
        return '//'.join(self._print(a) for a in expr.args)

    def _print_PyccelAssociativeParenthesis(self, expr):
        return f'({self._print(expr.args[0])})'

    def _print_PyccelUnary(self, expr):
        return '+' + self._print(expr.args[0])

    def _print_PyccelUnarySub(self, expr):
        return '-' + self._print(expr.args[0])

    def _print_PyccelAnd(self, expr):
        return ' and '.join(self._print(a) for a in expr.args)

    def _print_PyccelOr(self, expr):
        return ' or '.join(self._print(a) for a in expr.args)

    def _print_PyccelEq(self, expr):
        lhs = self._print(expr.args[0])
        rhs = self._print(expr.args[1])
        return f'{lhs} == {rhs} '

    def _print_PyccelNe(self, expr):
        lhs = self._print(expr.args[0])
        rhs = self._print(expr.args[1])
        return f'{lhs} != {rhs} '

    def _print_PyccelLt(self, expr):
        lhs = self._print(expr.args[0])
        rhs = self._print(expr.args[1])
        return f'{lhs} < {rhs}'

    def _print_PyccelLe(self, expr):
        lhs = self._print(expr.args[0])
        rhs = self._print(expr.args[1])
        return f'{lhs} <= {rhs}'

    def _print_PyccelGt(self, expr):
        lhs = self._print(expr.args[0])
        rhs = self._print(expr.args[1])
        return f'{lhs} > {rhs}'

    def _print_PyccelGe(self, expr):
        lhs = self._print(expr.args[0])
        rhs = self._print(expr.args[1])
        return f'{lhs} >= {rhs}'

    def _print_PyccelNot(self, expr):
        a = self._print(expr.args[0])
        return f'not {a}'

    def _print_PyccelInvert(self, expr):
        return '~' + self._print(expr.args[0])

    def _print_PyccelRShift(self, expr):
        lhs = self._print(expr.args[0])
        rhs = self._print(expr.args[1])
        return f'{lhs} >> {rhs}'

    def _print_PyccelLShift(self, expr):
        lhs = self._print(expr.args[0])
        rhs = self._print(expr.args[1])
        return f'{lhs} << {rhs}'

    def _print_PyccelBitXor(self, expr):
        lhs = self._print(expr.args[0])
        rhs = self._print(expr.args[1])
        return f'{lhs} ^ {rhs}'

    def _print_PyccelBitOr(self, expr):
        lhs = self._print(expr.args[0])
        rhs = self._print(expr.args[1])
        return f'{lhs} | {rhs}'

    def _print_PyccelBitAnd(self, expr):
        lhs = self._print(expr.args[0])
        rhs = self._print(expr.args[1])
        return f'{lhs} & {rhs}'

    def _print_Duplicate(self, expr):
        return f'{self._print(expr.val)} * {self._print(expr.length)}'

    def _print_Concatenate(self, expr):
        return ' + '.join(self._print(a) for a in expr.args)

    def _print_PyccelSymbol(self, expr):
        return expr

    def _print_PythonType(self, expr):
        return f'type({self._print(expr.arg)})'
    
    #-----------------Class Printer---------------------------------

    def _print_ClassDef(self, expr):
        classDefName = 'class {}({}):'.format(expr.name,', '.join(self._print(arg) for arg in  expr.superclasses))
        methods = ''.join(self._print(method) for method in expr.methods)
        methods = self._indent_codestring(methods)
        interfaces = ''.join(self._print(method) for method in expr.interfaces)
        interfaces = self._indent_codestring(interfaces)
        classDef = '\n'.join([classDefName, methods, interfaces]) + '\n'
        return classDef

    def _print_ConstructorCall(self, expr):
        cls_name = expr.funcdef.cls_name
        cls_variable = expr.cls_variable
        args = ', '.join(self._print(arg) for arg in expr.args[1:])
        return f"{cls_variable} = {cls_name}({args})\n"

    def _print_Del(self, expr):
        return ''.join(f'del {var}\n' for var in expr.variables)

    #------------------OmpAnnotatedComment Printer------------------

    def _print_OmpAnnotatedComment(self, expr):
        clauses = ''
        if expr.combined:
            clauses = ' ' + expr.combined

        omp_expr = f'#$omp {expr.name}'
        clauses += str(expr.txt)
        omp_expr = f'{omp_expr}{clauses}\n'

        return omp_expr

    def _print_Omp_End_Clause(self, expr):
        omp_expr = str(expr.txt)
        omp_expr = f'#$omp {omp_expr}\n'
        return omp_expr

#==============================================================================
def pycode(expr, assign_to=None, **settings):
    """ Converts an expr to a string of Python code
    Parameters
    ==========
    expr : Expr
        A SymPy expression.
    fully_qualified_modules : bool
        Whether or not to write out full module names of functions
        (``math.sin`` vs. ``sin``). default: ``True``.
    Examples
    ========
    >>> from sympy import tan, Symbol
    >>> from sympy.printing.pycode import pycode
    >>> pycode(tan(Symbol('x')) + 1)
    'math.tan(x) + 1'
    """
    return PythonCodePrinter(settings).doprint(expr, assign_to)
