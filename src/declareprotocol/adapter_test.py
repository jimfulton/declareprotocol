import typing

import pytest

import declareprotocol
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

    assert registry.lookup(((Source, AlternateSource),), Target) is first_factory


def test_lookup_rejects_malformed_declaration_tuple() -> None:
    registry = AdapterRegistry()

    with pytest.raises(TypeError):
        registry.lookup(((Source, str),), Target)

    with pytest.raises(TypeError):
        registry.lookup(([Source],), Target)  # type: ignore[list-item]


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

    assert registry.lookup(((Source, AlternateSource),), Target) is source_value


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
