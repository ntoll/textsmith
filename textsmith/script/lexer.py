"""
The txtsmith lexer.
"""
from sly import Lexer


class TxtSmithLexer(Lexer):
    tokens = {
        "INT",
        "FLOAT",
        "STRING",
        "SYMBOL",
        "ASSIGN",
        "DEFINE",
    }

    ignore = " \t"
    ignore_comment = r"\#.*"

    # Simple tokens
    literals = {"(", ")", "{", "}", ":", "'", ",", "."}

    # Complex tokens

    # Floats must come before integers.
    @_(r"-?\d+\.\d+(e-?\d+)?")
    def FLOAT(self, t):
        """
        Real numbers (expressed as floating point).
        """
        t.value = float(t.value)
        return t

    @_(r"-?\d+")
    def INT(self, t):
        """
        Integers (whole numbers).
        """
        t.value = int(t.value)
        return t

    @_(r'"([^\\"]+|\\"|\\\\)*"')  # I think this is right ...
    def STRING(self, t):
        """
        Strings of characters.
        """
        t.value = t.value[1:-1]
        return t

    @_(r"\n+")
    def ignore_newline(self, t):
        """
        Track line numbers.
        """
        self.lineno += t.value.count("\n")

    SYMBOL = r'[^0-9(){}:"\',\.][^(){}:"\',\.\ \t\n]*'
    SYMBOL["="] = "ASSIGN"
    SYMBOL["def"] = "DEFINE"

    def error(self, t):
        """
        Error reporting.
        """
        raise SyntaxError(f"Line {self.lineno}: Bad character {t.value[0]}")


lexer = TxtSmithLexer()
