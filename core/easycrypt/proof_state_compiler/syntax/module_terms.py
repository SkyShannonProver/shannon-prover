"""Shared parser and unifier for qualified EasyCrypt procedure terms."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Union


@dataclass(frozen=True)
class ModuleName:
    name: str


@dataclass(frozen=True)
class ModuleApply:
    function: "ModuleTerm"
    arguments: tuple["ModuleTerm", ...]


@dataclass(frozen=True)
class ModuleSelect:
    base: "ModuleTerm"
    field: str


ModuleTerm = Union[ModuleName, ModuleApply, ModuleSelect]


# ``EcPath`` prints identities rooted in EasyCrypt's top namespace with this
# marker.  This is upstream syntax, not an eval theorem/module name.
_EASYCRYPT_TOP_ROOT = "Top"


@dataclass(frozen=True)
class ProcedureTerm:
    module: ModuleTerm
    procedure: str


class ModuleTermParseError(ValueError):
    pass


class _Parser:
    def __init__(self, text: str) -> None:
        self.text = text
        self.index = 0

    def parse(self) -> ModuleTerm:
        term = self._parse_term()
        self._space()
        if self.index != len(self.text):
            raise ModuleTermParseError(
                f"unexpected module syntax at {self.text[self.index:]!r}"
            )
        return term

    def _parse_term(self) -> ModuleTerm:
        term: ModuleTerm = ModuleName(self._identifier())
        while True:
            self._space()
            if self._take("("):
                arguments = []
                self._space()
                if not self._take(")"):
                    while True:
                        arguments.append(self._parse_term())
                        self._space()
                        if self._take(")"):
                            break
                        if not self._take(","):
                            raise ModuleTermParseError(
                                "expected ',' or ')' in module application"
                            )
                term = ModuleApply(term, tuple(arguments))
                continue
            if self._take("."):
                term = ModuleSelect(term, self._identifier())
                continue
            return term

    def _identifier(self) -> str:
        self._space()
        start = self.index
        if self.index >= len(self.text):
            raise ModuleTermParseError("expected identifier")
        first = self.text[self.index]
        if not (first.isalpha() or first == "_"):
            raise ModuleTermParseError("expected identifier")
        self.index += 1
        while self.index < len(self.text):
            char = self.text[self.index]
            if not (char.isalnum() or char in {"_", "'"}):
                break
            self.index += 1
        return self.text[start:self.index]

    def _space(self) -> None:
        while self.index < len(self.text) and self.text[self.index].isspace():
            self.index += 1

    def _take(self, token: str) -> bool:
        self._space()
        if self.text.startswith(token, self.index):
            self.index += len(token)
            return True
        return False


def parse_procedure_term(text: str) -> ProcedureTerm:
    term = _Parser(text.strip()).parse()
    if not isinstance(term, ModuleSelect):
        raise ModuleTermParseError("procedure must have a module qualifier")
    return ProcedureTerm(module=term.base, procedure=term.field)


def parse_module_term(text: str) -> ModuleTerm:
    """Parse one module term for bounded lexical candidate planning."""

    return _Parser(text.strip()).parse()


def render_module_term(term: ModuleTerm) -> str:
    if isinstance(term, ModuleName):
        return term.name
    if isinstance(term, ModuleApply):
        arguments = ", ".join(render_module_term(item) for item in term.arguments)
        return f"{render_module_term(term.function)}({arguments})"
    if isinstance(term, ModuleSelect):
        return f"{render_module_term(term.base)}.{term.field}"
    raise TypeError(f"unsupported module term {type(term).__name__}")


def render_procedure_term(term: ProcedureTerm) -> str:
    return f"{render_module_term(term.module)}.{term.procedure}"


def lexical_procedure_views(value: str) -> tuple[str, ...]:
    """Return bounded source-spelling candidates for a native procedure xpath.

    EasyCrypt's canonical procedure identities use ``./proc`` and may qualify
    module paths with the current theory root.  Printed source declarations
    commonly omit that root.  These views are *only* lexical candidates for a
    subsequent native elaboration request: removing a root here never asserts
    namespace, module-signature, or restriction equivalence.

    A functor parameter can be the outermost module (for example
    ``A(Top.F(...))./guess``), so the canonical ``Top`` root need not be the
    first name in the tree.  We remove only EasyCrypt's explicit top-namespace
    marker, consistently throughout the tree.  Other qualified roots are
    preserved because they may be real library/module names.
    """

    canonical = value.count("./") == 1
    try:
        parsed = parse_native_procedure_identity(value)
    except ModuleTermParseError:
        return ()
    original = render_procedure_term(parsed)
    if canonical and _contains_module_root(
        parsed.module,
        _EASYCRYPT_TOP_ROOT,
    ):
        return (render_procedure_term(ProcedureTerm(
            module=_strip_module_root(parsed.module, _EASYCRYPT_TOP_ROOT),
            procedure=parsed.procedure,
        )),)
    return (original,)


def parse_native_procedure_identity(value: str) -> ProcedureTerm:
    """Parse either source ``M.p`` syntax or canonical ``M./p`` syntax."""

    if value.count("./") == 1:
        module, procedure = value.rsplit("./", 1)
        if not module or not procedure:
            raise ModuleTermParseError("incomplete native procedure identity")
        return ProcedureTerm(
            module=parse_module_term(module),
            procedure=procedure,
        )
    return parse_procedure_term(value)


def _contains_module_root(value: ModuleTerm, root: str) -> bool:
    if isinstance(value, ModuleApply):
        return _contains_module_root(value.function, root) or any(
            _contains_module_root(item, root) for item in value.arguments
        )
    if isinstance(value, ModuleSelect):
        return (
            isinstance(value.base, ModuleName)
            and value.base.name == root
        ) or _contains_module_root(value.base, root)
    if isinstance(value, ModuleName):
        return False
    return False


def _strip_module_root(value: ModuleTerm, root: str) -> ModuleTerm:
    if isinstance(value, ModuleApply):
        return ModuleApply(
            _strip_module_root(value.function, root),
            tuple(_strip_module_root(item, root) for item in value.arguments),
        )
    if isinstance(value, ModuleSelect):
        if isinstance(value.base, ModuleName) and value.base.name == root:
            return ModuleName(value.field)
        return ModuleSelect(
            _strip_module_root(value.base, root),
            value.field,
        )
    return value


def unify_module_term(
    pattern: ModuleTerm,
    actual: ModuleTerm,
    variables: frozenset[str],
    bindings: dict[str, ModuleTerm],
) -> bool:
    if isinstance(pattern, ModuleName) and pattern.name in variables:
        previous = bindings.get(pattern.name)
        if previous is None:
            bindings[pattern.name] = actual
            return True
        return previous == actual
    if type(pattern) is not type(actual):
        return False
    if isinstance(pattern, ModuleName):
        return pattern.name == actual.name
    if isinstance(pattern, ModuleApply):
        return (
            len(pattern.arguments) == len(actual.arguments)
            and unify_module_term(
                pattern.function,
                actual.function,
                variables,
                bindings,
            )
            and all(
                unify_module_term(left, right, variables, bindings)
                for left, right in zip(pattern.arguments, actual.arguments)
            )
        )
    if isinstance(pattern, ModuleSelect):
        return pattern.field == actual.field and unify_module_term(
            pattern.base, actual.base, variables, bindings
        )
    return False


def substitute_module_term(
    term: ModuleTerm,
    bindings: Mapping[str, ModuleTerm],
) -> ModuleTerm:
    if isinstance(term, ModuleName):
        return bindings.get(term.name, term)
    if isinstance(term, ModuleApply):
        return ModuleApply(
            substitute_module_term(term.function, bindings),
            tuple(substitute_module_term(item, bindings) for item in term.arguments),
        )
    if isinstance(term, ModuleSelect):
        return ModuleSelect(substitute_module_term(term.base, bindings), term.field)
    raise TypeError(f"unsupported module term {type(term).__name__}")
