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
