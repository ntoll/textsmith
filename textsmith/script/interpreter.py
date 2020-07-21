"""
The interpreter for the txtsmith language.
"""
from .lexer import lexer
from .parser import parser
from .nodes import Quoted, Assign, Define, Access, Symbol
from .core import BUILTINS


def run(source, context=None):
    """
    Run the passed-in fragment of source code with the given context.
    """
    if context is None:
        context = {}
    context.update(BUILTINS)
    tokens = lexer.tokenize(source)
    parsed = parser.parse(tokens)
    return evaluate(parsed, context, source)


def evaluate(parsed, context, source=""):
    """
    Takes parsed code and returns the following:

    Given an assignment, update the context to the associated value and return
    that value.

    Given a definition, update the context to the associated callable and
    return None.

    Given a accessor, return the value of the attribute on the referenced
    object.

    Given an integer, float, string, a quoted value or something callable, just
    return it.

    Given a symbol, do a lookup, and return the result.

    Given a list, if it's empty, return None, otherwise treat it as a function
    call.
    """
    if (
        isinstance(parsed, int)
        or isinstance(parsed, float)
        or isinstance(parsed, str)
        or callable(parsed)
    ):
        return parsed
    elif isinstance(parsed, dict):
        return {k.name: evaluate(v, context) for (k, v) in parsed.items()}
    elif isinstance(parsed, Quoted):
        return parsed.data
    elif isinstance(parsed, Symbol):
        return context[parsed.name]
    elif isinstance(parsed, list):
        if parsed == []:
            return None
        elif isinstance(parsed[0], Assign):
            return evaluate_assign(parsed, context)
        elif isinstance(parsed[0], Define):
            return evaluate_define(parsed, context, source)
        elif isinstance(parsed[0], Access):
            return evaluate_accessor(parsed[0], context)
        else:
            return evaluate_call(parsed, context)


def evaluate_assign(parsed, context):
    """
    (= foo 2)
    2

    The symbol foo now evaluates to the integer 2. Assignment is not lazy.
    """
    if (
        not (len(parsed) == 2 and isinstance(parsed[1], Access))
        and len(parsed) != 3
    ):
        raise SyntaxError("Not enough arguments for assignment.")
    item = parsed[1]
    if isinstance(item, Access):
        # Recursive lookup to get the the correct dictionary.
        dict_object = context[item.object_name]
        new_args = [None,] + item.attribute
        return evaluate_assign(new_args, dict_object)
    elif isinstance(item, Symbol):
        value = evaluate(parsed[2], context)
        context[item.name] = value
        return value
    else:
        raise SyntaxError("Cannot assign to a non-symbol.")


def evaluate_define(parsed, context, source=""):
    """
    (def foo "help text" (parameters) statements)

    Create a new user defined function and assign its name to the resulting
    callable in the context.
    """
    if len(parsed) < 4:
        raise SyntaxError("Not enough arguments to define a function.")
    if not isinstance(parsed[1], Symbol):
        raise SyntaxError("Cannot name a function with a non-symbol.")
    name = parsed[1].name
    if name in BUILTINS:
        raise TypeError("Cannot redefine a builtin function.")
    doc = "A user defined function without any documentation."
    parameters = []
    statements = []
    if isinstance(parsed[2], str):
        # Optional docstring.
        doc = parsed[2]
        parameters = parsed[3]
        statements = parsed[4:]
    elif isinstance(parsed[2], list):
        # No docstring.
        parameters = parsed[2]
        statements = parsed[3:]
    else:
        raise SyntaxError("Wrong sorts of arguments for function definition.")
    new_function = create_function(name, doc, parameters, statements, source)
    context[name] = new_function


def evaluate_accessor(parsed, context):
    """
    (= foo {bar: 1})
    (foo.bar)
    1
    """
    dict_object = context[parsed.object_name]
    if not isinstance(dict_object, dict):
        raise TypeError(f"Unknown attribute '{parsed.object_name}'.")
    attribute = parsed.attribute[0]
    if isinstance(attribute, Access):
        # Recursive access into sub-dictionaries
        return evaluate_accessor(attribute, dict_object)
    if not isinstance(attribute, Symbol):
        raise SyntaxError("Attributes must be symbols.")
    return dict_object[attribute.name]


def evaluate_call(parsed, context):
    """
    (fn args...)

    Evaluate the function to reduce it to something callable. Then, apply the
    function to the given arguments, if any, and return the result.
    """
    name = parsed[0]
    fn = evaluate(name, context)
    if not callable(fn):
        raise TypeError(f"'{name.name}' is not callable.")
    args = [evaluate(p, context) for p in parsed[1:]]  # Evaluate args.
    return fn(context, *args)


def create_function(name, doc, parameters, statements, source):
    """
    Return a user-defined function as a closure.
    """
    # Pre-flight checks...
    if not isinstance(parameters, list):
        raise SyntaxError("Function parameters must be a list.")
    if not isinstance(statements, list):
        raise SyntaxError("Invalid function statement[s].")
    if not statements:
        raise SyntaxError("A function must have one or more statements.")
    for param in parameters:
        if not isinstance(param, Symbol):
            raise TypeError("Function parameters must be symbols.")
    for statement in statements:
        if not isinstance(statement, list):
            raise TypeError("Function statements must be executable lists.")

    def closure(context, *args):
        para_length = len(parameters)
        args_length = len(args)
        if not para_length == args_length:
            raise TypeError(
                f"Function '{name}' takes {para_length} arguments "
                f"({args_length} given)."
            )
        call_context = dict(context)
        for i, parameter in enumerate(parameters):
            call_context[parameter.name] = evaluate(args[i], context)
        for statement in statements:
            result = evaluate(statement, call_context)
        return result

    closure.__doc__ = doc
    if source:
        closure.__source__ = source
    return closure
