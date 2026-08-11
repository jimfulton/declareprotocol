# Protocol Adapter Registry Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a typed adapter registry that registers, selects, and invokes single-, multi-, and zero-source adapters for declared Python protocols.

**Architecture:** Keep `declareprotocol.adapter` as one cohesive registry module containing validation, insertion-ordered registration storage, deterministic scoring, and query invocation. Reuse declaration metadata through the `declareprotocol.declarations` module; normalize each lookup position to an ordered declaration tuple so protocol inheritance and declaration order can be scored without `issubclass()`.

**Tech Stack:** Python 3.12+, `typing.Protocol`, dataclasses, pytest, Ruff, uv

## Global Constraints

- Add no runtime dependency on `zope.interface`.
- Support Python `>=3.12` and the repository's existing typing and formatting conventions.
- Preserve only the approved core API: `register`, `unregister`, `registered`, `lookup`, `lookup1`, `queryAdapter`, `queryMultiAdapter`, and `adapter_hook`.
- Do not add registry inheritance, lookup caching, generation tracking, persistence customization, subscriptions, utilities, notifications, C accelerators, or `zope.interface` object compatibility.
- Treat registration order as the final tie-breaker, and retain an entry's position when replacing its value.
- Let malformed declarations, non-callable selected values, and factory exceptions fail explicitly.

## File Structure

- Create `src/declareprotocol/adapter.py`: public `AdapterRegistry`, internal registration record, protocol validation, lookup normalization, deterministic matching, and adapter invocation.
- Create `src/declareprotocol/adapter_test.py`: focused behavioral tests grouped around storage, matching, and invocation.
- Modify `src/declareprotocol/__init__.py`: package-level `AdapterRegistry` export.
- Modify `README.md`: concise single-adapter usage example.

The registry is expected to remain near the module-size review threshold. Keep its private helpers narrowly focused; do not split them into a generic utility module because all matching helpers belong only to adapter selection.

## Testing Value Gate

The planned automated tests exercise public production behavior and can fail for meaningful regressions in registration identity, protocol inheritance, precedence, arity, invocation, defaults, and error propagation. These reusable API contracts justify ongoing test maintenance. The README text is not tested as static content; verify its example directly with Python and rely on Ruff plus the complete existing suite for code validation.

---

### Task 1: Exact Registration Storage and Validation

**Files:**
- Create: `src/declareprotocol/adapter.py`
- Create: `src/declareprotocol/adapter_test.py`

**Interfaces:**
- Consumes: `declareprotocol.declarations._is_protocol_class(value: object) -> bool`
- Produces: `AdapterRegistry.register(required, provided, name, value) -> None`, `AdapterRegistry.unregister(required, provided, name, value=None) -> bool`, and `AdapterRegistry.registered(required, provided, name="") -> object | None`
- Establishes: `_Registration.required`, `.provided`, `.name`, and `.value`, whose insertion order is used by later lookup scoring

- [ ] **Step 1: Write failing exact-storage tests**

Create `src/declareprotocol/adapter_test.py` with:

```python
import typing

import pytest

from declareprotocol.adapter import AdapterRegistry


class Source(typing.Protocol):
    source: str


class OtherSource(typing.Protocol):
    other: str


class Target(typing.Protocol):
    target: str


class TargetBase(typing.Protocol):
    base: str


class DerivedTarget(TargetBase, typing.Protocol):
    derived: str


def first_factory(value: object) -> tuple[str, object]:
    return ("first", value)


def second_factory(value: object) -> tuple[str, object]:
    return ("second", value)


def test_empty_registry_and_exact_registration() -> None:
    registry = AdapterRegistry()

    assert registry.registered((Source,), Target) is None
    assert registry.lookup((Source,), Target, default="missing") == "missing"

    registry.register((Source,), Target, "", first_factory)

    assert registry.registered((Source,), Target) is first_factory


def test_register_replaces_and_none_unregisters() -> None:
    registry = AdapterRegistry()
    registry.register((Source,), Target, "", first_factory)
    registry.register((Source,), Target, "", second_factory)

    assert registry.registered((Source,), Target) is second_factory

    registry.register((Source,), Target, "", None)

    assert registry.registered((Source,), Target) is None


def test_unregister_honors_optional_value_identity() -> None:
    registry = AdapterRegistry()
    registry.register((Source,), Target, "named", first_factory)

    assert not registry.unregister(
        (Source,),
        Target,
        "named",
        second_factory,
    )
    assert registry.unregister(
        (Source,),
        Target,
        "named",
        first_factory,
    )
    assert not registry.unregister((Source,), Target, "named")


def test_registered_is_exact_for_required_provided_and_name() -> None:
    registry = AdapterRegistry()
    registry.register((Source,), DerivedTarget, "named", first_factory)

    assert registry.registered((OtherSource,), DerivedTarget, "named") is None
    assert registry.registered((Source,), TargetBase, "named") is None
    assert registry.registered((Source,), DerivedTarget, "") is None


@pytest.mark.parametrize(
    ("required", "provided"),
    [
        ((str,), Target),
        ((Source,), str),
        (((Source,),), Target),
    ],
)
def test_registration_rejects_invalid_protocols(
    required: tuple[object, ...],
    provided: object,
) -> None:
    registry = AdapterRegistry()

    with pytest.raises(TypeError):
        registry.register(required, provided, "", first_factory)  # type: ignore[arg-type]


@pytest.mark.parametrize("name", [None, 1, object()])
def test_registration_rejects_non_string_names(name: object) -> None:
    registry = AdapterRegistry()

    with pytest.raises(ValueError):
        registry.register((Source,), Target, name, first_factory)  # type: ignore[arg-type]
```

- [ ] **Step 2: Run the focused tests and confirm the missing module failure**

Run:

```bash
uv run python -m pytest src/declareprotocol/adapter_test.py -q
```

Expected: collection fails with `ModuleNotFoundError: No module named 'declareprotocol.adapter'`.

- [ ] **Step 3: Implement exact registration storage and validation**

Create `src/declareprotocol/adapter.py` with:

```python
import dataclasses
import typing

from . import declarations

__all__ = ["AdapterRegistry"]

Protocol = type[object]
Required = Protocol | None
Declaration = tuple[Protocol, ...]
LookupRequirement = Protocol | Declaration


@dataclasses.dataclass
class _Registration:
    required: tuple[Required, ...]
    provided: Protocol
    name: str
    value: object


class AdapterRegistry:
    def __init__(self) -> None:
        self._registrations: list[_Registration] = []

    @staticmethod
    def _validate_name(name: str) -> None:
        if not isinstance(name, str):
            raise ValueError("name is not a string")

    @staticmethod
    def _validate_protocol(protocol: object) -> None:
        if not declarations._is_protocol_class(protocol):
            raise TypeError(f"{protocol!r} is not a Protocol class")

    @classmethod
    def _normalize_registered_required(
        cls,
        required: typing.Iterable[Required],
    ) -> tuple[Required, ...]:
        normalized = tuple(required)
        for protocol in normalized:
            if protocol is not None:
                cls._validate_protocol(protocol)
        return normalized

    @classmethod
    def _registration_key(
        cls,
        required: typing.Iterable[Required],
        provided: Protocol,
        name: str,
    ) -> tuple[tuple[Required, ...], Protocol, str]:
        normalized = cls._normalize_registered_required(required)
        cls._validate_protocol(provided)
        cls._validate_name(name)
        return normalized, provided, name

    def register(
        self,
        required: typing.Iterable[Required],
        provided: Protocol,
        name: str,
        value: object,
    ) -> None:
        key = self._registration_key(required, provided, name)
        for index, registration in enumerate(self._registrations):
            if (
                registration.required,
                registration.provided,
                registration.name,
            ) != key:
                continue
            if value is None:
                del self._registrations[index]
            else:
                registration.value = value
            return

        if value is not None:
            self._registrations.append(_Registration(*key, value))

    def unregister(
        self,
        required: typing.Iterable[Required],
        provided: Protocol,
        name: str,
        value: object = None,
    ) -> bool:
        key = self._registration_key(required, provided, name)
        for index, registration in enumerate(self._registrations):
            if (
                registration.required,
                registration.provided,
                registration.name,
            ) != key:
                continue
            if value is not None and registration.value is not value:
                return False
            del self._registrations[index]
            return True
        return False

    def registered(
        self,
        required: typing.Iterable[Required],
        provided: Protocol,
        name: str = "",
    ) -> object | None:
        key = self._registration_key(required, provided, name)
        for registration in self._registrations:
            if (
                registration.required,
                registration.provided,
                registration.name,
            ) == key:
                return registration.value
        return None

    def lookup(
        self,
        required: typing.Iterable[LookupRequirement],
        provided: Protocol,
        name: str = "",
        default: object = None,
    ) -> object:
        self._validate_protocol(provided)
        self._validate_name(name)
        return default
```

- [ ] **Step 4: Run storage tests and Ruff**

Run:

```bash
uv run python -m pytest src/declareprotocol/adapter_test.py -q
uv run ruff check src/declareprotocol/adapter.py src/declareprotocol/adapter_test.py
uv run ruff format --check src/declareprotocol/adapter.py src/declareprotocol/adapter_test.py
```

Expected: all adapter tests pass; both Ruff commands exit 0.

- [ ] **Step 5: Commit exact storage**

```bash
git add src/declareprotocol/adapter.py src/declareprotocol/adapter_test.py
git commit -m "feat: add exact adapter registrations"
```

---

### Task 2: Deterministic Protocol Lookup

**Files:**
- Modify: `src/declareprotocol/adapter.py`
- Modify: `src/declareprotocol/adapter_test.py`

**Interfaces:**
- Consumes: insertion-ordered `_Registration` records from Task 1 and declaration tuples returned by `implementedBy()` or `providedBy()`
- Produces: `lookup(required, provided, name="", default=None) -> object` and `lookup1(required, provided, name="", default=None) -> object`
- Matching contract: name and arity exact; provided exact before nearest derived; required exact before inherited before wildcard, position by position; declaration order and then registration order break remaining ties

- [ ] **Step 1: Add failing exact, named, and declaration-tuple lookup tests**

Append to `src/declareprotocol/adapter_test.py`:

```python
class DerivedSource(Source, typing.Protocol):
    derived_source: str


class AlternateSource(typing.Protocol):
    alternate: str


def test_lookup_and_lookup1_match_exact_and_named_registrations() -> None:
    registry = AdapterRegistry()
    registry.register((Source,), Target, "", first_factory)
    registry.register((Source,), Target, "named", second_factory)

    assert registry.lookup((Source,), Target) is first_factory
    assert registry.lookup1(Source, Target) is first_factory
    assert registry.lookup1(Source, Target, "named") is second_factory
    assert registry.lookup1(Source, Target, "absent", "missing") == "missing"


def test_lookup_treats_declaration_tuple_as_one_source_position() -> None:
    registry = AdapterRegistry()
    registry.register((AlternateSource,), Target, "", first_factory)

    assert (
        registry.lookup(((Source, AlternateSource),), Target)
        is first_factory
    )


def test_lookup_rejects_malformed_declaration_tuple() -> None:
    registry = AdapterRegistry()

    with pytest.raises(TypeError):
        registry.lookup(((Source, str),), Target)

    with pytest.raises(TypeError):
        registry.lookup(([Source],), Target)  # type: ignore[list-item]
```

- [ ] **Step 2: Run the new lookup tests and confirm failure**

Run:

```bash
uv run python -m pytest \
  src/declareprotocol/adapter_test.py::test_lookup_and_lookup1_match_exact_and_named_registrations \
  src/declareprotocol/adapter_test.py::test_lookup_treats_declaration_tuple_as_one_source_position \
  src/declareprotocol/adapter_test.py::test_lookup_rejects_malformed_declaration_tuple -q
```

Expected: the first two tests fail because `lookup()` returns the default, and the malformed declaration test fails because no `TypeError` is raised.

- [ ] **Step 3: Add lookup normalization and exact matching**

Add these methods to `AdapterRegistry` immediately before `lookup`, then replace `lookup` and add `lookup1`:

```python
    @classmethod
    def _normalize_lookup_required(
        cls,
        required: typing.Iterable[LookupRequirement],
    ) -> tuple[Declaration, ...]:
        normalized: list[Declaration] = []
        for requirement in required:
            if isinstance(requirement, tuple):
                declaration = requirement
            else:
                cls._validate_protocol(requirement)
                declaration = (requirement,)
            for protocol in declaration:
                cls._validate_protocol(protocol)
            normalized.append(declaration)
        return tuple(normalized)

    @staticmethod
    def _provided_score(
        registered: Protocol,
        requested: Protocol,
    ) -> tuple[int, int] | None:
        try:
            distance = registered.__mro__.index(requested)
        except ValueError:
            return None
        return (0 if distance == 0 else 1, distance)

    @staticmethod
    def _required_score(
        registered: Required,
        declaration: Declaration,
    ) -> tuple[int, int, int] | None:
        if registered is None:
            return (2, 0, 0)

        matches: list[tuple[int, int, int]] = []
        for declaration_index, protocol in enumerate(declaration):
            try:
                distance = protocol.__mro__.index(registered)
            except ValueError:
                continue
            matches.append(
                (
                    0 if distance == 0 else 1,
                    distance,
                    declaration_index,
                )
            )
        return min(matches, default=None)

    @classmethod
    def _score(
        cls,
        registration: _Registration,
        required: tuple[Declaration, ...],
        provided: Protocol,
        name: str,
    ) -> tuple[tuple[int, int], tuple[tuple[int, int, int], ...]] | None:
        if registration.name != name or len(registration.required) != len(required):
            return None

        provided_score = cls._provided_score(registration.provided, provided)
        if provided_score is None:
            return None

        required_scores: list[tuple[int, int, int]] = []
        for registered, declaration in zip(registration.required, required):
            score = cls._required_score(registered, declaration)
            if score is None:
                return None
            required_scores.append(score)
        return provided_score, tuple(required_scores)

    def lookup(
        self,
        required: typing.Iterable[LookupRequirement],
        provided: Protocol,
        name: str = "",
        default: object = None,
    ) -> object:
        normalized = self._normalize_lookup_required(required)
        self._validate_protocol(provided)
        self._validate_name(name)
        matches = (
            (score, registration.value)
            for registration in self._registrations
            if (
                score := self._score(
                    registration,
                    normalized,
                    provided,
                    name,
                )
            )
            is not None
        )
        return min(matches, default=((), default), key=lambda match: match[0])[1]

    def lookup1(
        self,
        required: LookupRequirement,
        provided: Protocol,
        name: str = "",
        default: object = None,
    ) -> object:
        return self.lookup((required,), provided, name, default)
```

- [ ] **Step 4: Run the focused lookup tests**

Run:

```bash
uv run python -m pytest \
  src/declareprotocol/adapter_test.py::test_lookup_and_lookup1_match_exact_and_named_registrations \
  src/declareprotocol/adapter_test.py::test_lookup_treats_declaration_tuple_as_one_source_position \
  src/declareprotocol/adapter_test.py::test_lookup_rejects_malformed_declaration_tuple -q
```

Expected: 3 tests pass.

- [ ] **Step 5: Add failing inheritance, wildcard, covariance, arity, and tie-break tests**

Append to `src/declareprotocol/adapter_test.py`:

```python
def test_required_precedence_is_lexicographic_by_source_position() -> None:
    registry = AdapterRegistry()
    first_position_exact = object()
    second_position_exact = object()
    registry.register(
        (Source, None),
        Target,
        "",
        first_position_exact,
    )
    registry.register(
        (None, DerivedSource),
        Target,
        "",
        second_position_exact,
    )

    assert (
        registry.lookup(
            (DerivedSource, DerivedSource),
            Target,
        )
        is first_position_exact
    )


def test_exact_required_beats_inherited_and_wildcard() -> None:
    registry = AdapterRegistry()
    inherited = object()
    wildcard = object()
    exact = object()
    registry.register((Source,), Target, "", inherited)
    registry.register((None,), Target, "", wildcard)
    registry.register((DerivedSource,), Target, "", exact)

    assert registry.lookup1(DerivedSource, Target) is exact

    registry.unregister((DerivedSource,), Target, "")
    assert registry.lookup1(DerivedSource, Target) is inherited


def test_declaration_order_breaks_equal_required_matches() -> None:
    registry = AdapterRegistry()
    source_value = object()
    alternate_value = object()
    registry.register((AlternateSource,), Target, "", alternate_value)
    registry.register((Source,), Target, "", source_value)

    assert (
        registry.lookup(((Source, AlternateSource),), Target)
        is source_value
    )


def test_provided_exact_beats_nearest_derived_protocol() -> None:
    registry = AdapterRegistry()
    derived_value = object()
    exact_value = object()
    registry.register((Source,), DerivedTarget, "", derived_value)
    registry.register((Source,), TargetBase, "", exact_value)

    assert registry.lookup1(Source, TargetBase) is exact_value

    registry.unregister((Source,), TargetBase, "")
    assert registry.lookup1(Source, TargetBase) is derived_value


def test_lookup_matches_adapter_arity_exactly() -> None:
    registry = AdapterRegistry()
    single = object()
    multi = object()
    registry.register((Source,), Target, "", single)
    registry.register((Source, OtherSource), Target, "", multi)

    assert registry.lookup((Source,), Target) is single
    assert registry.lookup((Source, OtherSource), Target) is multi
    assert registry.lookup((), Target, "", "missing") == "missing"


def test_lookup_validates_provided_protocol_and_name() -> None:
    registry = AdapterRegistry()

    with pytest.raises(TypeError):
        registry.lookup((Source,), str)  # type: ignore[arg-type]

    with pytest.raises(ValueError):
        registry.lookup((Source,), Target, None)  # type: ignore[arg-type]
```

- [ ] **Step 6: Run all lookup tests**

Run:

```bash
uv run python -m pytest src/declareprotocol/adapter_test.py -q
```

Expected: all adapter tests pass.

- [ ] **Step 7: Run Ruff and commit lookup behavior**

Run:

```bash
uv run ruff check src/declareprotocol/adapter.py src/declareprotocol/adapter_test.py
uv run ruff format --check src/declareprotocol/adapter.py src/declareprotocol/adapter_test.py
```

Expected: both commands exit 0. If formatting check reports changes, run `uv run ruff format` on the two files, inspect the diff, and rerun both commands.

Commit:

```bash
git add src/declareprotocol/adapter.py src/declareprotocol/adapter_test.py
git commit -m "feat: select adapters by protocol specificity"
```

---

### Task 3: Adapter Factory Invocation

**Files:**
- Modify: `src/declareprotocol/adapter.py`
- Modify: `src/declareprotocol/adapter_test.py`

**Interfaces:**
- Consumes: `declarations.providedBy(obj) -> tuple[type[object], ...]`, plus `lookup()` and `lookup1()` from Task 2
- Produces: `queryAdapter(obj, provided, name="", default=None) -> object`, `queryMultiAdapter(objects, provided, name="", default=None) -> object`, and `adapter_hook(provided, obj, name="", default=None) -> object`
- Invocation contract: call the selected factory once with original object order; return the query default if no factory exists or its result is `None`; propagate `TypeError` and factory exceptions

- [ ] **Step 1: Add declared source fixtures and failing query tests**

Add `import declareprotocol` beside the existing imports in `src/declareprotocol/adapter_test.py`, then append:

```python
@declareprotocol.implementer(Source)
class SourceObject:
    source = "source"


@declareprotocol.implementer(OtherSource)
class OtherSourceObject:
    other = "other"


def test_query_adapter_uses_provided_declarations_and_name() -> None:
    registry = AdapterRegistry()
    source = SourceObject()
    calls: list[object] = []

    def factory(value: object) -> tuple[str, object]:
        calls.append(value)
        return ("adapted", value)

    registry.register((Source,), Target, "named", factory)

    assert registry.queryAdapter(source, Target, "named") == (
        "adapted",
        source,
    )
    assert calls == [source]
    assert registry.adapter_hook(Target, source, "named") == (
        "adapted",
        source,
    )


def test_query_multi_adapter_preserves_argument_order() -> None:
    registry = AdapterRegistry()
    first = SourceObject()
    second = OtherSourceObject()

    def factory(*objects: object) -> tuple[object, ...]:
        return objects

    registry.register((Source, OtherSource), Target, "", factory)

    assert registry.queryMultiAdapter((first, second), Target) == (
        first,
        second,
    )


def test_query_uses_inherited_and_direct_object_declarations() -> None:
    registry = AdapterRegistry()
    inherited = object()
    direct = object()

    class InheritedSourceObject(SourceObject):
        pass

    class DirectSourceObject:
        alternate = "alternate"

    directly_declared = DirectSourceObject()
    declareprotocol.directlyProvides(directly_declared, AlternateSource)
    registry.register((Source,), Target, "inherited", lambda value: inherited)
    registry.register((AlternateSource,), Target, "direct", lambda value: direct)

    assert (
        registry.queryAdapter(
            InheritedSourceObject(),
            Target,
            "inherited",
        )
        is inherited
    )
    assert registry.queryAdapter(directly_declared, Target, "direct") is direct


def test_zero_source_lookup_and_query_invoke_zero_argument_factory() -> None:
    registry = AdapterRegistry()
    sentinel = object()
    registry.register((), Target, "", lambda: sentinel)

    assert registry.lookup((), Target) is not None
    assert registry.queryMultiAdapter((), Target) is sentinel


def test_query_defaults_for_missing_or_none_factory_result() -> None:
    registry = AdapterRegistry()
    source = SourceObject()

    assert registry.queryAdapter(source, Target, default="missing") == "missing"

    registry.register((Source,), Target, "", lambda value: None)

    assert registry.queryAdapter(source, Target, default="missing") == "missing"


def test_query_propagates_non_callable_and_factory_errors() -> None:
    registry = AdapterRegistry()
    source = SourceObject()
    registry.register((Source,), Target, "", object())

    with pytest.raises(TypeError):
        registry.queryAdapter(source, Target)

    def broken(value: object) -> object:
        raise RuntimeError("factory failed")

    registry.register((Source,), Target, "", broken)

    with pytest.raises(RuntimeError, match="factory failed"):
        registry.queryAdapter(source, Target)
```

- [ ] **Step 2: Run query tests and confirm missing methods**

Run:

```bash
uv run python -m pytest src/declareprotocol/adapter_test.py -q
```

Expected: the six new tests fail with `AttributeError` for `queryAdapter` or `queryMultiAdapter`.

- [ ] **Step 3: Implement single-, multi-, hook-, and zero-source invocation**

Add these methods to `AdapterRegistry` after `lookup1`:

```python
    def queryAdapter(
        self,
        obj: object,
        provided: Protocol,
        name: str = "",
        default: object = None,
    ) -> object:
        return self.queryMultiAdapter((obj,), provided, name, default)

    def queryMultiAdapter(
        self,
        objects: typing.Iterable[object],
        provided: Protocol,
        name: str = "",
        default: object = None,
    ) -> object:
        sources = tuple(objects)
        required = tuple(declarations.providedBy(obj) for obj in sources)
        factory = self.lookup(required, provided, name)
        if factory is None:
            return default
        result = factory(*sources)  # type: ignore[operator]
        return default if result is None else result

    def adapter_hook(
        self,
        provided: Protocol,
        obj: object,
        name: str = "",
        default: object = None,
    ) -> object:
        return self.queryAdapter(obj, provided, name, default)
```

- [ ] **Step 4: Run adapter tests, full tests, and Ruff**

Run:

```bash
uv run python -m pytest src/declareprotocol/adapter_test.py -q
uv run python -m pytest
uv run ruff check src
uv run ruff format --check src
```

Expected: all tests pass with coverage at or above 50%; both Ruff commands exit 0.

- [ ] **Step 5: Commit query behavior**

```bash
git add src/declareprotocol/adapter.py src/declareprotocol/adapter_test.py
git commit -m "feat: invoke registered adapter factories"
```

---

### Task 4: Public Export, Documentation, and Complete Verification

**Files:**
- Modify: `src/declareprotocol/__init__.py`
- Modify: `src/declareprotocol/adapter_test.py`
- Modify: `README.md`

**Interfaces:**
- Consumes: `declareprotocol.adapter.AdapterRegistry` from Tasks 1-3
- Produces: `declareprotocol.AdapterRegistry` and a runnable public single-adapter example

- [ ] **Step 1: Add a failing package-export test**

Append to `src/declareprotocol/adapter_test.py`:

```python
def test_adapter_registry_is_exported_from_package() -> None:
    assert declareprotocol.AdapterRegistry is AdapterRegistry
```

- [ ] **Step 2: Run the export test and confirm failure**

Run:

```bash
uv run python -m pytest \
  src/declareprotocol/adapter_test.py::test_adapter_registry_is_exported_from_package -q
```

Expected: fail with `AttributeError: module 'declareprotocol' has no attribute 'AdapterRegistry'`.

- [ ] **Step 3: Export `AdapterRegistry` from the package**

Add this import before the declarations import in `src/declareprotocol/__init__.py`:

```python
from .adapter import AdapterRegistry
```

Add `"AdapterRegistry"` as the first entry in `__all__`:

```python
__all__ = [
    "AdapterRegistry",
    "alsoProvides",
    "directlyProvidedBy",
    "directlyProvides",
    "implementedBy",
    "implementer",
    "noLongerProvides",
    "providedBy",
]
```

- [ ] **Step 4: Run the export test**

Run:

```bash
uv run python -m pytest \
  src/declareprotocol/adapter_test.py::test_adapter_registry_is_exported_from_package -q
```

Expected: 1 test passes.

- [ ] **Step 5: Add the concise single-adapter README example**

Append this section after the existing dispatch example in `README.md`:

````markdown
## Adapters

An adapter registry can select and invoke factories using declared protocols:

```python
class Summary(typing.Protocol):
    text: str

registry = declareprotocol.AdapterRegistry()
registry.register(
    (HasRun,),
    Summary,
    "",
    lambda value: f"summary: {value.run()}",
)

assert registry.queryAdapter(runner, Summary) == "summary: run"
```
````

- [ ] **Step 6: Verify the README example directly**

Run:

```bash
uv run python - <<'PY'
import typing

import declareprotocol


class HasRun(typing.Protocol):
    def run(self) -> str: ...


class Summary(typing.Protocol):
    text: str


@declareprotocol.implementer(HasRun)
class Runner:
    def run(self) -> str:
        return "run"


runner = Runner()
registry = declareprotocol.AdapterRegistry()
registry.register(
    (HasRun,),
    Summary,
    "",
    lambda value: f"summary: {value.run()}",
)
assert registry.queryAdapter(runner, Summary) == "summary: run"
PY
```

Expected: exit 0 with no output.

- [ ] **Step 7: Run the exact CI validation commands**

`AGENTS.md` is absent from this repository, so use the commands defined in `.github/workflows/ci.yml` and repeated by the approved spec:

```bash
uv run ruff check src
uv run ruff format --check src
uv run python -m pytest
```

Expected: both Ruff commands exit 0; all tests pass and reported coverage is at least 50%.

- [ ] **Step 8: Review scope and module size**

Run:

```bash
git diff --check
git diff --stat
wc -l src/declareprotocol/adapter.py src/declareprotocol/adapter_test.py
git status --short
```

Expected: no whitespace errors; only `README.md`, `src/declareprotocol/__init__.py`, `src/declareprotocol/adapter.py`, and `src/declareprotocol/adapter_test.py` are changed since the plan commits; `adapter.py` remains a cohesive registry module. If it exceeds 400 meaningful lines, reduce duplication in registry-local helpers rather than creating a generic utility module.

- [ ] **Step 9: Commit the public API and documentation**

```bash
git add README.md src/declareprotocol/__init__.py src/declareprotocol/adapter_test.py
git commit -m "docs: document protocol adapter registry"
```
