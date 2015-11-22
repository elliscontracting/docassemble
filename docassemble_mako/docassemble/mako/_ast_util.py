# mako/_ast_util.py
# Copyright (C) 2006-2015 the Mako authors and contributors <see AUTHORS file>
#
# This module is part of Mako and is released under
# the MIT License: http://www.opensource.org/licenses/mit-license.php

"""
    ast
    ~~~

    The `ast` module helps Python applications to process trees of the Python
    abstract syntax grammar.  The abstract syntax itself might change with
    each Python release; this module helps to find out programmatically what
    the current grammar looks like and allows modifications of it.

    An abstract syntax tree can be generated by passing `ast.PyCF_ONLY_AST` as
    a flag to the `compile()` builtin function or by using the `parse()`
    function from this module.  The result will be a tree of objects whose
    classes all inherit from `ast.AST`.

    A modified abstract syntax tree can be compiled into a Python code object
    using the built-in `compile()` function.

    Additionally various helper functions are provided that make working with
    the trees simpler.  The main intention of the helper functions and this
    module in general is to provide an easy to use interface for libraries
    that work tightly with the python syntax (template engines for example).


    :copyright: Copyright 2008 by Armin Ronacher.
    :license: Python License.
"""
from _ast import *  # noqa
from docassemble.mako.compat import arg_stringname

BOOLOP_SYMBOLS = {
    And: 'and',
    Or: 'or'
}

BINOP_SYMBOLS = {
    Add: '+',
    Sub: '-',
    Mult: '*',
    Div: '/',
    FloorDiv: '//',
    Mod: '%',
    LShift: '<<',
    RShift: '>>',
    BitOr: '|',
    BitAnd: '&',
    BitXor: '^'
}

CMPOP_SYMBOLS = {
    Eq: '==',
    Gt: '>',
    GtE: '>=',
    In: 'in',
    Is: 'is',
    IsNot: 'is not',
    Lt: '<',
    LtE: '<=',
    NotEq: '!=',
    NotIn: 'not in'
}

UNARYOP_SYMBOLS = {
    Invert: '~',
    Not: 'not',
    UAdd: '+',
    USub: '-'
}

ALL_SYMBOLS = {}
ALL_SYMBOLS.update(BOOLOP_SYMBOLS)
ALL_SYMBOLS.update(BINOP_SYMBOLS)
ALL_SYMBOLS.update(CMPOP_SYMBOLS)
ALL_SYMBOLS.update(UNARYOP_SYMBOLS)


def parse(expr, filename='<unknown>', mode='exec'):
    """Parse an expression into an AST node."""
    return compile(expr, filename, mode, PyCF_ONLY_AST)


def to_source(node, indent_with=' ' * 4):
    """
    This function can convert a node tree back into python sourcecode.  This
    is useful for debugging purposes, especially if you're dealing with custom
    asts not generated by python itself.

    It could be that the sourcecode is evaluable when the AST itself is not
    compilable / evaluable.  The reason for this is that the AST contains some
    more data than regular sourcecode does, which is dropped during
    conversion.

    Each level of indentation is replaced with `indent_with`.  Per default this
    parameter is equal to four spaces as suggested by PEP 8, but it might be
    adjusted to match the application's styleguide.
    """
    generator = SourceGenerator(indent_with)
    generator.visit(node)
    return ''.join(generator.result)


def dump(node):
    """
    A very verbose representation of the node passed.  This is useful for
    debugging purposes.
    """
    def _format(node):
        if isinstance(node, AST):
            return '%s(%s)' % (node.__class__.__name__,
                               ', '.join('%s=%s' % (a, _format(b))
                                         for a, b in iter_fields(node)))
        elif isinstance(node, list):
            return '[%s]' % ', '.join(_format(x) for x in node)
        return repr(node)
    if not isinstance(node, AST):
        raise TypeError('expected AST, got %r' % node.__class__.__name__)
    return _format(node)


def copy_location(new_node, old_node):
    """
    Copy the source location hint (`lineno` and `col_offset`) from the
    old to the new node if possible and return the new one.
    """
    for attr in 'lineno', 'col_offset':
        if attr in old_node._attributes and attr in new_node._attributes \
           and hasattr(old_node, attr):
            setattr(new_node, attr, getattr(old_node, attr))
    return new_node


def fix_missing_locations(node):
    """
    Some nodes require a line number and the column offset.  Without that
    information the compiler will abort the compilation.  Because it can be
    a dull task to add appropriate line numbers and column offsets when
    adding new nodes this function can help.  It copies the line number and
    column offset of the parent node to the child nodes without this
    information.

    Unlike `copy_location` this works recursive and won't touch nodes that
    already have a location information.
    """
    def _fix(node, lineno, col_offset):
        if 'lineno' in node._attributes:
            if not hasattr(node, 'lineno'):
                node.lineno = lineno
            else:
                lineno = node.lineno
        if 'col_offset' in node._attributes:
            if not hasattr(node, 'col_offset'):
                node.col_offset = col_offset
            else:
                col_offset = node.col_offset
        for child in iter_child_nodes(node):
            _fix(child, lineno, col_offset)
    _fix(node, 1, 0)
    return node


def increment_lineno(node, n=1):
    """
    Increment the line numbers of all nodes by `n` if they have line number
    attributes.  This is useful to "move code" to a different location in a
    file.
    """
    for node in zip((node,), walk(node)):
        if 'lineno' in node._attributes:
            node.lineno = getattr(node, 'lineno', 0) + n


def iter_fields(node):
    """Iterate over all fields of a node, only yielding existing fields."""
    # CPython 2.5 compat
    if not hasattr(node, '_fields') or not node._fields:
        return
    for field in node._fields:
        try:
            yield field, getattr(node, field)
        except AttributeError:
            pass


def get_fields(node):
    """Like `iter_fiels` but returns a dict."""
    return dict(iter_fields(node))


def iter_child_nodes(node):
    """Iterate over all child nodes or a node."""
    for name, field in iter_fields(node):
        if isinstance(field, AST):
            yield field
        elif isinstance(field, list):
            for item in field:
                if isinstance(item, AST):
                    yield item


def get_child_nodes(node):
    """Like `iter_child_nodes` but returns a list."""
    return list(iter_child_nodes(node))


def get_compile_mode(node):
    """
    Get the mode for `compile` of a given node.  If the node is not a `mod`
    node (`Expression`, `Module` etc.) a `TypeError` is thrown.
    """
    if not isinstance(node, mod):
        raise TypeError('expected mod node, got %r' % node.__class__.__name__)
    return {
        Expression: 'eval',
        Interactive: 'single'
    }.get(node.__class__, 'expr')


def get_docstring(node):
    """
    Return the docstring for the given node or `None` if no docstring can be
    found.  If the node provided does not accept docstrings a `TypeError`
    will be raised.
    """
    if not isinstance(node, (FunctionDef, ClassDef, Module)):
        raise TypeError("%r can't have docstrings" % node.__class__.__name__)
    if node.body and isinstance(node.body[0], Str):
        return node.body[0].s


def walk(node):
    """
    Iterate over all nodes.  This is useful if you only want to modify nodes in
    place and don't care about the context or the order the nodes are returned.
    """
    from collections import deque
    todo = deque([node])
    while todo:
        node = todo.popleft()
        todo.extend(iter_child_nodes(node))
        yield node


class NodeVisitor(object):

    """
    Walks the abstract syntax tree and call visitor functions for every node
    found.  The visitor functions may return values which will be forwarded
    by the `visit` method.

    Per default the visitor functions for the nodes are ``'visit_'`` +
    class name of the node.  So a `TryFinally` node visit function would
    be `visit_TryFinally`.  This behavior can be changed by overriding
    the `get_visitor` function.  If no visitor function exists for a node
    (return value `None`) the `generic_visit` visitor is used instead.

    Don't use the `NodeVisitor` if you want to apply changes to nodes during
    traversing.  For this a special visitor exists (`NodeTransformer`) that
    allows modifications.
    """

    def get_visitor(self, node):
        """
        Return the visitor function for this node or `None` if no visitor
        exists for this node.  In that case the generic visit function is
        used instead.
        """
        method = 'visit_' + node.__class__.__name__
        return getattr(self, method, None)

    def visit(self, node):
        """Visit a node."""
        f = self.get_visitor(node)
        if f is not None:
            return f(node)
        return self.generic_visit(node)

    def generic_visit(self, node):
        """Called if no explicit visitor function exists for a node."""
        for field, value in iter_fields(node):
            if isinstance(value, list):
                for item in value:
                    if isinstance(item, AST):
                        self.visit(item)
            elif isinstance(value, AST):
                self.visit(value)


class NodeTransformer(NodeVisitor):

    """
    Walks the abstract syntax tree and allows modifications of nodes.

    The `NodeTransformer` will walk the AST and use the return value of the
    visitor functions to replace or remove the old node.  If the return
    value of the visitor function is `None` the node will be removed
    from the previous location otherwise it's replaced with the return
    value.  The return value may be the original node in which case no
    replacement takes place.

    Here an example transformer that rewrites all `foo` to `data['foo']`::

        class RewriteName(NodeTransformer):

            def visit_Name(self, node):
                return copy_location(Subscript(
                    value=Name(id='data', ctx=Load()),
                    slice=Index(value=Str(s=node.id)),
                    ctx=node.ctx
                ), node)

    Keep in mind that if the node you're operating on has child nodes
    you must either transform the child nodes yourself or call the generic
    visit function for the node first.

    Nodes that were part of a collection of statements (that applies to
    all statement nodes) may also return a list of nodes rather than just
    a single node.

    Usually you use the transformer like this::

        node = YourTransformer().visit(node)
    """

    def generic_visit(self, node):
        for field, old_value in iter_fields(node):
            old_value = getattr(node, field, None)
            if isinstance(old_value, list):
                new_values = []
                for value in old_value:
                    if isinstance(value, AST):
                        value = self.visit(value)
                        if value is None:
                            continue
                        elif not isinstance(value, AST):
                            new_values.extend(value)
                            continue
                    new_values.append(value)
                old_value[:] = new_values
            elif isinstance(old_value, AST):
                new_node = self.visit(old_value)
                if new_node is None:
                    delattr(node, field)
                else:
                    setattr(node, field, new_node)
        return node


class SourceGenerator(NodeVisitor):

    """
    This visitor is able to transform a well formed syntax tree into python
    sourcecode.  For more details have a look at the docstring of the
    `node_to_source` function.
    """

    def __init__(self, indent_with):
        self.result = []
        self.indent_with = indent_with
        self.indentation = 0
        self.new_lines = 0

    def write(self, x):
        if self.new_lines:
            if self.result:
                self.result.append('\n' * self.new_lines)
            self.result.append(self.indent_with * self.indentation)
            self.new_lines = 0
        self.result.append(x)

    def newline(self, n=1):
        self.new_lines = max(self.new_lines, n)

    def body(self, statements):
        self.new_line = True
        self.indentation += 1
        for stmt in statements:
            self.visit(stmt)
        self.indentation -= 1

    def body_or_else(self, node):
        self.body(node.body)
        if node.orelse:
            self.newline()
            self.write('else:')
            self.body(node.orelse)

    def signature(self, node):
        want_comma = []

        def write_comma():
            if want_comma:
                self.write(', ')
            else:
                want_comma.append(True)

        padding = [None] * (len(node.args) - len(node.defaults))
        for arg, default in zip(node.args, padding + node.defaults):
            write_comma()
            self.visit(arg)
            if default is not None:
                self.write('=')
                self.visit(default)
        if node.vararg is not None:
            write_comma()
            self.write('*' + arg_stringname(node.vararg))
        if node.kwarg is not None:
            write_comma()
            self.write('**' + arg_stringname(node.kwarg))

    def decorators(self, node):
        for decorator in node.decorator_list:
            self.newline()
            self.write('@')
            self.visit(decorator)

    # Statements

    def visit_Assign(self, node):
        self.newline()
        for idx, target in enumerate(node.targets):
            if idx:
                self.write(', ')
            self.visit(target)
        self.write(' = ')
        self.visit(node.value)

    def visit_AugAssign(self, node):
        self.newline()
        self.visit(node.target)
        self.write(BINOP_SYMBOLS[type(node.op)] + '=')
        self.visit(node.value)

    def visit_ImportFrom(self, node):
        self.newline()
        self.write('from %s%s import ' % ('.' * node.level, node.module))
        for idx, item in enumerate(node.names):
            if idx:
                self.write(', ')
            self.write(item)

    def visit_Import(self, node):
        self.newline()
        for item in node.names:
            self.write('import ')
            self.visit(item)

    def visit_Expr(self, node):
        self.newline()
        self.generic_visit(node)

    def visit_FunctionDef(self, node):
        self.newline(n=2)
        self.decorators(node)
        self.newline()
        self.write('def %s(' % node.name)
        self.signature(node.args)
        self.write('):')
        self.body(node.body)

    def visit_ClassDef(self, node):
        have_args = []

        def paren_or_comma():
            if have_args:
                self.write(', ')
            else:
                have_args.append(True)
                self.write('(')

        self.newline(n=3)
        self.decorators(node)
        self.newline()
        self.write('class %s' % node.name)
        for base in node.bases:
            paren_or_comma()
            self.visit(base)
        # XXX: the if here is used to keep this module compatible
        #      with python 2.6.
        if hasattr(node, 'keywords'):
            for keyword in node.keywords:
                paren_or_comma()
                self.write(keyword.arg + '=')
                self.visit(keyword.value)
            if getattr(node, "starargs", None):
                paren_or_comma()
                self.write('*')
                self.visit(node.starargs)
            if getattr(node, "kwargs", None):
                paren_or_comma()
                self.write('**')
                self.visit(node.kwargs)
        self.write(have_args and '):' or ':')
        self.body(node.body)

    def visit_If(self, node):
        self.newline()
        self.write('if ')
        self.visit(node.test)
        self.write(':')
        self.body(node.body)
        while True:
            else_ = node.orelse
            if len(else_) == 1 and isinstance(else_[0], If):
                node = else_[0]
                self.newline()
                self.write('elif ')
                self.visit(node.test)
                self.write(':')
                self.body(node.body)
            else:
                self.newline()
                self.write('else:')
                self.body(else_)
                break

    def visit_For(self, node):
        self.newline()
        self.write('for ')
        self.visit(node.target)
        self.write(' in ')
        self.visit(node.iter)
        self.write(':')
        self.body_or_else(node)

    def visit_While(self, node):
        self.newline()
        self.write('while ')
        self.visit(node.test)
        self.write(':')
        self.body_or_else(node)

    def visit_With(self, node):
        self.newline()
        self.write('with ')
        self.visit(node.context_expr)
        if node.optional_vars is not None:
            self.write(' as ')
            self.visit(node.optional_vars)
        self.write(':')
        self.body(node.body)

    def visit_Pass(self, node):
        self.newline()
        self.write('pass')

    def visit_Print(self, node):
        # XXX: python 2.6 only
        self.newline()
        self.write('print ')
        want_comma = False
        if node.dest is not None:
            self.write(' >> ')
            self.visit(node.dest)
            want_comma = True
        for value in node.values:
            if want_comma:
                self.write(', ')
            self.visit(value)
            want_comma = True
        if not node.nl:
            self.write(',')

    def visit_Delete(self, node):
        self.newline()
        self.write('del ')
        for idx, target in enumerate(node):
            if idx:
                self.write(', ')
            self.visit(target)

    def visit_TryExcept(self, node):
        self.newline()
        self.write('try:')
        self.body(node.body)
        for handler in node.handlers:
            self.visit(handler)

    def visit_TryFinally(self, node):
        self.newline()
        self.write('try:')
        self.body(node.body)
        self.newline()
        self.write('finally:')
        self.body(node.finalbody)

    def visit_Global(self, node):
        self.newline()
        self.write('global ' + ', '.join(node.names))

    def visit_Nonlocal(self, node):
        self.newline()
        self.write('nonlocal ' + ', '.join(node.names))

    def visit_Return(self, node):
        self.newline()
        self.write('return ')
        self.visit(node.value)

    def visit_Break(self, node):
        self.newline()
        self.write('break')

    def visit_Continue(self, node):
        self.newline()
        self.write('continue')

    def visit_Raise(self, node):
        # XXX: Python 2.6 / 3.0 compatibility
        self.newline()
        self.write('raise')
        if hasattr(node, 'exc') and node.exc is not None:
            self.write(' ')
            self.visit(node.exc)
            if node.cause is not None:
                self.write(' from ')
                self.visit(node.cause)
        elif hasattr(node, 'type') and node.type is not None:
            self.visit(node.type)
            if node.inst is not None:
                self.write(', ')
                self.visit(node.inst)
            if node.tback is not None:
                self.write(', ')
                self.visit(node.tback)

    # Expressions

    def visit_Attribute(self, node):
        self.visit(node.value)
        self.write('.' + node.attr)

    def visit_Call(self, node):
        want_comma = []

        def write_comma():
            if want_comma:
                self.write(', ')
            else:
                want_comma.append(True)

        self.visit(node.func)
        self.write('(')
        for arg in node.args:
            write_comma()
            self.visit(arg)
        for keyword in node.keywords:
            write_comma()
            self.write(keyword.arg + '=')
            self.visit(keyword.value)
        if getattr(node, "starargs", None):
            write_comma()
            self.write('*')
            self.visit(node.starargs)
        if getattr(node, "kwargs", None):
            write_comma()
            self.write('**')
            self.visit(node.kwargs)
        self.write(')')

    def visit_Name(self, node):
        self.write(node.id)

    def visit_NameConstant(self, node):
        self.write(str(node.value))

    def visit_arg(self, node):
        self.write(node.arg)

    def visit_Str(self, node):
        self.write(repr(node.s))

    def visit_Bytes(self, node):
        self.write(repr(node.s))

    def visit_Num(self, node):
        self.write(repr(node.n))

    def visit_Tuple(self, node):
        self.write('(')
        idx = -1
        for idx, item in enumerate(node.elts):
            if idx:
                self.write(', ')
            self.visit(item)
        self.write(idx and ')' or ',)')

    def sequence_visit(left, right):
        def visit(self, node):
            self.write(left)
            for idx, item in enumerate(node.elts):
                if idx:
                    self.write(', ')
                self.visit(item)
            self.write(right)
        return visit

    visit_List = sequence_visit('[', ']')
    visit_Set = sequence_visit('{', '}')
    del sequence_visit

    def visit_Dict(self, node):
        self.write('{')
        for idx, (key, value) in enumerate(zip(node.keys, node.values)):
            if idx:
                self.write(', ')
            self.visit(key)
            self.write(': ')
            self.visit(value)
        self.write('}')

    def visit_BinOp(self, node):
        self.write('(')
        self.visit(node.left)
        self.write(' %s ' % BINOP_SYMBOLS[type(node.op)])
        self.visit(node.right)
        self.write(')')

    def visit_BoolOp(self, node):
        self.write('(')
        for idx, value in enumerate(node.values):
            if idx:
                self.write(' %s ' % BOOLOP_SYMBOLS[type(node.op)])
            self.visit(value)
        self.write(')')

    def visit_Compare(self, node):
        self.write('(')
        self.visit(node.left)
        for op, right in zip(node.ops, node.comparators):
            self.write(' %s ' % CMPOP_SYMBOLS[type(op)])
            self.visit(right)
        self.write(')')

    def visit_UnaryOp(self, node):
        self.write('(')
        op = UNARYOP_SYMBOLS[type(node.op)]
        self.write(op)
        if op == 'not':
            self.write(' ')
        self.visit(node.operand)
        self.write(')')

    def visit_Subscript(self, node):
        self.visit(node.value)
        self.write('[')
        self.visit(node.slice)
        self.write(']')

    def visit_Slice(self, node):
        if node.lower is not None:
            self.visit(node.lower)
        self.write(':')
        if node.upper is not None:
            self.visit(node.upper)
        if node.step is not None:
            self.write(':')
            if not (isinstance(node.step, Name) and node.step.id == 'None'):
                self.visit(node.step)

    def visit_ExtSlice(self, node):
        for idx, item in node.dims:
            if idx:
                self.write(', ')
            self.visit(item)

    def visit_Yield(self, node):
        self.write('yield ')
        self.visit(node.value)

    def visit_Lambda(self, node):
        self.write('lambda ')
        self.signature(node.args)
        self.write(': ')
        self.visit(node.body)

    def visit_Ellipsis(self, node):
        self.write('Ellipsis')

    def generator_visit(left, right):
        def visit(self, node):
            self.write(left)
            self.visit(node.elt)
            for comprehension in node.generators:
                self.visit(comprehension)
            self.write(right)
        return visit

    visit_ListComp = generator_visit('[', ']')
    visit_GeneratorExp = generator_visit('(', ')')
    visit_SetComp = generator_visit('{', '}')
    del generator_visit

    def visit_DictComp(self, node):
        self.write('{')
        self.visit(node.key)
        self.write(': ')
        self.visit(node.value)
        for comprehension in node.generators:
            self.visit(comprehension)
        self.write('}')

    def visit_IfExp(self, node):
        self.visit(node.body)
        self.write(' if ')
        self.visit(node.test)
        self.write(' else ')
        self.visit(node.orelse)

    def visit_Starred(self, node):
        self.write('*')
        self.visit(node.value)

    def visit_Repr(self, node):
        # XXX: python 2.6 only
        self.write('`')
        self.visit(node.value)
        self.write('`')

    # Helper Nodes

    def visit_alias(self, node):
        self.write(node.name)
        if node.asname is not None:
            self.write(' as ' + node.asname)

    def visit_comprehension(self, node):
        self.write(' for ')
        self.visit(node.target)
        self.write(' in ')
        self.visit(node.iter)
        if node.ifs:
            for if_ in node.ifs:
                self.write(' if ')
                self.visit(if_)

    def visit_excepthandler(self, node):
        self.newline()
        self.write('except')
        if node.type is not None:
            self.write(' ')
            self.visit(node.type)
            if node.name is not None:
                self.write(' as ')
                self.visit(node.name)
        self.write(':')
        self.body(node.body)
