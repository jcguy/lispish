#!/usr/bin/env python3


import re
from typing import Any, Callable, Optional, TextIO, Union
from typing_extensions import override
from io import IOBase, StringIO
import sys


program = "(begin (define a 1) (define b 2) (+ a b))"


def assertType(obj: Any, type_: type) -> None:
    if not isinstance(obj, type_):
        raise TypeError(f"Value {obj} is not of type {type_}")


class Token(str):
    pass


class Expression:
    value: Any
    token: Any

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}[{self.value}]"


class Atom(Expression):
    def __init__(self, *_):
        raise NotImplementedError("Don't construct Atoms")

    @staticmethod
    def of(token: Union[str, int]):
        try:
            return Number(token)
        except ValueError:
            assertType(token, str)
            assert isinstance(token, str)
            return Symbol(token)


class List(Expression, list):
    @override
    def __repr__(self) -> str:
        inside = " ".join(repr(i) for i in self)
        return f"({inside})"


class Symbol(Atom, str):
    def __init__(self, token: str):
        assertType(token, str)
        self.token = token
        self.value = str(token)


class Number(Atom, int):
    def __init__(self, token: Union[int, str]):
        self.value = int(token)
        self.token = str(token)


class Environment:
    def __init__(
        self,
        params: list[Symbol] = [],
        args: list[Expression] = [],
        outer: Optional["Environment"] = None,
    ):
        for param in params:
            assertType(param, Symbol)
        for arg in args:
            assertType(arg, Expression)
        if outer:
            assertType(outer, Environment)

        self.env: dict[Symbol, Expression] = dict()

        for param, arg in zip(params, args):
            self.env[param] = arg

        self.outer = outer

    def update(self, mappings: dict[Symbol, Expression]) -> None:
        for sym, exp in mappings.items():
            assertType(sym, Symbol)
            assertType(exp, Expression)
            self[sym] = exp

    def __repr__(self) -> str:
        return str(self.env)

    def __getitem__(self, sym: Symbol) -> Expression:
        assertType(sym, Symbol)
        if sym in self.env:
            return self.env[sym]
        elif self.outer:
            return self.outer[sym]
        else:
            raise ValueError(f"Undefined symbol: {sym}")

    def __setitem__(self, sym: Symbol, exp: Expression) -> None:
        assertType(sym, Symbol)
        assertType(exp, Expression)
        self.env[sym] = exp


class Procedure(Atom):
    def __init__(self, params: list[Symbol], body: Expression, env: Environment):
        for param in params:
            assertType(param, Symbol)
        assertType(body, Expression)
        assertType(env, Environment)

        self.params = params
        self.body = body
        self.env = env

    def __call__(self, args: list[Expression]) -> Expression:
        return eval_(self.body, Environment(self.params, args, self.env))

    def __repr__(self) -> str:
        return f"#<procedure of {len(self.params)} arguments>"


class BuiltinProcedure(Procedure):
    def __init__(self, callable: Callable):
        assertType(callable, Callable)
        self.callable = callable

    def __call__(self, args: list[Expression]) -> Expression:
        return Atom.of(self.callable(*args))

    def __repr__(self) -> str:
        return repr(self.callable)


class InStream:
    TOKEN_REGEX = re.compile(r"""\s*([()]|"(?:[\\].|[^\\"])*"|;.*|[^\s('"`,;)]*)(.*)""")
    EOF_TOKEN = Token("#<eof-object>")

    def __init__(self, f: TextIO):
        self.f = f
        self.line: Optional[str] = None

    def next(self) -> Token:
        while True:
            if not self.line:
                self.line = self.f.readline()
            if not self.line:
                return InStream.EOF_TOKEN
            match = re.match(InStream.TOKEN_REGEX, self.line)
            if match:
                token, self.line = match.groups()
                if token:
                    return Token(token)


EOF_SYMBOL = Symbol(InStream.EOF_TOKEN)


def read(stream: InStream) -> Expression:
    def read_ahead(token) -> Expression:
        if token == "(":
            L: List = List()
            while True:
                token = stream.next()
                if token == ")":
                    return L
                else:
                    L.append(read_ahead(token))
        elif token == ")":
            raise SyntaxError("Unexpected )")
        elif token is InStream.EOF_TOKEN:
            raise SyntaxError("Unexpected EOF in list")
        else:
            return Atom.of(token)

    token = stream.next()
    return EOF_SYMBOL if token is InStream.EOF_TOKEN else read_ahead(token)


DEFINE = Symbol("define")
BEGIN = Symbol("begin")
NIL = Symbol("nil")


def apply_(proc: Expression, args: list[Expression]) -> Expression:
    if not isinstance(proc, Procedure):
        raise TypeError(f"Not a procedure: {proc}")

    return proc(args)


def eval_(exp: Optional[Expression], env: Environment) -> Expression:
    if not exp:
        raise ValueError("Can't evaluate nothing")

    if isinstance(exp, Symbol):
        return env[exp]
    elif isinstance(exp, Number):
        return exp
    elif not isinstance(exp, List):
        raise TypeError(f"Unknown type: {exp}")

    first, *rest = exp
    if first == DEFINE:
        assert len(rest) == 2
        sym, val = rest
        env[sym] = val
        return NIL
    elif first == BEGIN:
        inner = Environment(outer=env)
        values = list(map(lambda x: eval_(x, inner), rest))
        return values[-1]
    else:
        return apply_(eval_(first, env), list(map(lambda x: eval_(x, env), rest)))


global_env = Environment()
global_env[Symbol("+")] = BuiltinProcedure(lambda a, b: a + b)


def repl(prompt="ish>") -> None:
    stream = InStream(sys.stdin)
    while True:
        try:
            if prompt:
                print(prompt, end=" ")
            print(eval_(read(stream), global_env))
        except Exception as e:
            print(f"{type(e).__name__}: {e}")


def main() -> None:
    stream = InStream(StringIO(program, "\n"))
    print(read(stream))
    print(eval_(read(InStream(StringIO(program, None))), global_env))


main()
