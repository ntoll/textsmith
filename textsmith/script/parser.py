"""
Parser for txtsmith.
"""
from sly import Parser
from .lexer import TxtSmithLexer
from .nodes import Quoted, Assign, Define, Access, Symbol


class TxtSmithParser(Parser):
    tokens = TxtSmithLexer.tokens

    # Grammar rules and actions.
    @_('"(" nodes ")"')
    def list(self, p):
        return p.nodes

    @_('"\'" node')
    def quoted(self, p):
        return Quoted(p.node)

    @_('"," node')
    def unquoted(self, p):
        if isinstance(p.node, Quoted):
            return p.node.data
        else:
            raise TypeError(f"Cannot unquote {p.node}")

    @_('"{" pairs "}"')
    def dict(self, p):
        return {k: v for (k, v) in p.pairs}

    @_("pair pairs")
    def pairs(self, p):
        return [p.pair] + p.pairs

    @_("empty")
    def pairs(self, p):
        return []

    @_("node nodes")
    def nodes(self, p):
        return [p.node] + p.nodes

    @_("ASSIGN nodes")
    def nodes(self, p):
        return [Assign()] + p.nodes

    @_("DEFINE nodes")
    def nodes(self, p):
        return [Define()] + p.nodes

    @_('SYMBOL "." nodes')
    def nodes(self, p):
        return [Access(p[0], p[2])]

    @_("empty")
    def nodes(self, p):
        return []

    @_('SYMBOL ":" node')
    def pair(self, p):
        return (Symbol(p.SYMBOL), p.node)

    @_("INT")
    def node(self, p):
        return p.INT

    @_("FLOAT")
    def node(self, p):
        return p.FLOAT

    @_("STRING")
    def node(self, p):
        return p.STRING

    @_("SYMBOL")
    def node(self, p):
        return Symbol(p.SYMBOL)

    @_("list")
    def node(self, p):
        return p.list

    @_("quoted")
    def node(self, p):
        return p.quoted

    @_("unquoted")
    def node(self, p):
        return p.unquoted

    @_("dict")
    def node(self, p):
        return p.dict

    @_("")
    def empty(self, p):
        pass

    def error(self, p):
        msg = (
            f'Cannot parse {p.type} (with value "{p.value}") on line '
            f"{p.lineno}, character {p.index}."
        )
        raise SyntaxError(msg)


parser = TxtSmithParser()
