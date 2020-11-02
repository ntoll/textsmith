"""
Built-in functions of the scripting language.
"""
from functools import reduce, wraps


def check_args(required_args):
    """
    Ensure that the wrapped function is passed "required_args" number of
    arguments.
    """

    def arg_decorator(func):
        @wraps(func)
        def wrapper(context, *args, **kwargs):
            actual_args = len(args)
            if actual_args != required_args:
                fname = func.__name__.replace("_", "")
                msg = (
                    f"The '{fname}' function requires {required_args} "
                    f"arguments, ({actual_args} given)."
                )
                raise TypeError(msg)
            else:
                return func(context, *args)

        return wrapper

    return arg_decorator


def _len(context, *args):
    """
    Return the length of a collection:

    (len '(1 2 3))
    3
    (len "hello")
    5
    """
    return len(args[0])


def _add(context, *args):
    """
    Sum together all the arguments:

    (+ 1 2 3 4)
    10

    (All the arguments must be numeric.)
    """
    return sum(args)


def _subtract(context, *args):
    """
    Starting from the initial value, subtract all subsequent
    arguments.

    (- 10 5 2)
    3

    (All the arguments must be numeric.)
    """
    return reduce(lambda x, y: x - y, args)


def _multiply(context, *args):
    """
    Multiply all the arguments:

    (* 2 3 4)
    24

    (All the arguments must be numeric.)
    """
    return reduce(lambda x, y: x * y, args)


def _divide(context, *args):
    """
    Divide the first argument (numerator) by the second argument
    (de-numerator).

    (/ 10 2)
    5

    (All the arguments must be numeric. Always returns a float.)
    """
    return args[0] / args[1]


def _modulo(context, *args):
    """
    Give the remainder from a division (modulo).

    (% 10 3)
    1

    (There must only be two numeric arguments.)
    """
    if len(args) == 2:
        return args[0] % args[1]
    else:
        raise SyntaxError("Wrong number of arguments for modulo.")


def _lt(context, *args):
    """
    Indicate if the first argument is less than the second argument.

    (< 10 100)
    true

    """
    if len(args) == 2:
        return args[0] < args[1]
    else:
        raise TypeError("Wrong number of arguments for less than.")


def _gt(context, *args):
    if len(args) == 2:
        return args[0] > args[1]
    else:
        raise TypeError("Wrong number of arguments for greater than.")


def _eq(context, *args):
    if len(args) == 2:
        return args[0] == args[1]
    else:
        raise TypeError("Wrong number of arguments for equality.")


def _ne(context, *args):
    if len(args) == 2:
        return args[0] != args[1]
    else:
        raise TypeError("Wrong number of arguments for not equals.")


def _gteq(context, *args):
    if len(args) == 2:
        return args[0] >= args[1]
    else:
        raise TypeError(
            "Wrong number of arguments for greater than or " "equal to."
        )


def _lteq(context, *args):
    if len(args) == 2:
        return args[0] <= args[1]
    else:
        raise TypeError("Wrong number of arguments for less than or equal to.")


def _and(context, *args):
    return bool(reduce(lambda x, y: x and y, args))


def _or(context, *args):
    return bool(reduce(lambda x, y: x or y, args))


def _not(context, *args):
    if len(args) == 1:
        return not bool(args[0])
    else:
        raise TypeError("Wrong number of arguments for not.")


def _delete(context, *args):
    if len(args == 1):
        del context[args[0]]
    else:
        raise TypeError("Wrong number of arguments for delete.")


def _in(context, *args):
    if len(args) == 2:
        return args[1] in args[1]
    else:
        raise TypeError("Wrong number of arguments for in.")


def _slice(context, *args):
    """"""


def _first(context, *args):
    """
    Return the first element of a list or string.

    (= mylist '(0 1 2 3 4))
    (first mylist)
    0

    (first "hello")
    "h"
    """


def _last(context, *args):
    """
    Return the last element of a list or string.

    (= mylist '(0 1 2 3 4))
    (last mylist)
    4

    (last "hello")
    "o"
    """


def _body(context, *args):
    """
    Return all the elements of a list or string after the first element.

    (= mylist '(0 1 2 3 4))
    (body mylist)
    (1 2 3 4)

    (body "hello")
    "ello"
    """


def _item(context, *args):
    """
    Return the element at the specified position in a list or string.
    NOTE: position starts counting from 0 (zero).

    (= mylist '(0 1 2 3 4))
    (item 0 mylist)
    0

    (item 0 "hello")
    "h"
    """


def _help(context, *args):
    if not args:
        # Display general help.
        return """This is some general help."""
    elif len(args) == 1:
        # Display help on a function.
        if callable(args[0]):
            return args[0].__doc__


def _context(context, *args):
    """
    Return the current context.
    """
    local_context = dict(context)
    for k in BUILTINS:
        del local_context[k]
    return local_context


def _source(context, *args):
    """
    Return a string representation of the source code of a user defined
    function.
    """
    if len(args) == 1:
        if callable(args[0]):
            if hasattr(args[0], "__source__"):
                return args[0].__source__


BUILTINS = {
    # Boolean values
    "true": True,
    "false": False,
    # Converting between types
    "int": int,
    "float": float,
    "str": str,
    "bool": bool,
    # Arithmetic
    "+": _add,
    "-": _subtract,
    "*": _multiply,
    "/": _divide,
    "%": _modulo,
    "<": _lt,
    ">": _gt,
    "==": _eq,
    "!=": _ne,
    ">=": _gteq,
    "<=": _lteq,
    # Logic
    "and": _and,
    "or": _or,
    "not": _not,
    # Context
    "del": _delete,
    "in": _in,
    # Collections
    "len": _len,
    "slice": _slice,
    "first": _first,
    "last": _last,
    "body": _body,
    "item": _item,
    # Help
    "help": _help,
    "context": _context,
    "source": _source,
}
"""
    # Conditional
    "COND": _cond,
    # Loop
    "iter": _iter,
    # Try
    "try": _try,
    # Random
    "randint": _randint,
    "randfloat": _randfloat,
    "randchoice": _randchoice,
    # String
    "capitalize": _capitalize,
    "endswith": _endswith,
    "find": _find,
    "format": _format,
    "isalpha": _isalpha,
    "isfloat": _isfloat,
    "isint": _isint,
    "islower": _islower,
    "isnumeric": _isnumeric,
    "isupper": _isupper,
    "join": _join,
    "lower": _lower,
    "replace": _replace,
    "split": _split,
    "splitlines": _splitlines,
    "startswith": _startswith,
    "strip": _strip,
    "swapcase": _swapcase,
    "title": _title,
    "upper": _upper,
"""
