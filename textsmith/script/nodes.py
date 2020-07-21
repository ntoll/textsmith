"""
Custom node types for parsing txtsmith.
"""


class Quoted:
    """
    Represents quoted node[s] which must NOT be evaluated.
    """

    def __init__(self, data):
        self.data = data


class Assign:
    """
    Represents an assignment of a value to a symbol.
    """

    def __repr__(self):
        return "Assign()"


class Define:
    """
    Represents the definition of a function.
    """

    def __repr__(self):
        return "Define()"


class Access:
    """
    Represents access to a key in a dictionary.
    """

    def __init__(self, object_name, attribute):
        self.object_name = object_name
        self.attribute = attribute

    def __repr__(self):
        return f"Access({self.object_name}, {self.attribute})"


class Symbol:
    """
    Represents a symbol with a given name.
    """

    def __init__(self, name):
        self.name = name

    def __hash__(self):
        return id(self.name)

    def __eq__(self, other):
        return self.name == other.name

    def __repr__(self):
        return f'Symbol("{self.name}")'
