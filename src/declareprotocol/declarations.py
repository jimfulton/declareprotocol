import inspect
import typing

__all__ = [
    'alsoProvides',
    'directlyProvidedBy',
    'directlyProvides',
    'implementedBy',
    'implementer',
    'noLongerProvides',
    'providedBy',
    ]


def _is_protocol_class(value: object) -> bool:
    if not isinstance(value, type):
        return False

    is_protocol = getattr(typing, 'is_protocol', None)
    if is_protocol is not None:
        return bool(is_protocol(value))

    return bool(getattr(value, '_is_protocol', False))


def _iter_protocol_members(protocol: type[object]) -> typing.Iterator[str]:
    get_members = getattr(typing, 'get_protocol_members', None)
    if get_members is not None:
        members = get_members(protocol)
    else:
        members: set[str] = set()
        for base in protocol.__mro__:
            if not getattr(base, '_is_protocol', False):
                continue

            members.update(base.__dict__.get('__annotations__', {}))
            members.update(
                name
                for name, value in base.__dict__.items()
                if value is ... or callable(value)
                )

    for name in members:
        if name.startswith('_abc_'):
            continue
        if name.startswith('__') and name.endswith('__'):
            continue
        yield name


def _class_annotations(cls: type[object]) -> set[str]:
    names: set[str] = set()
    for base in cls.__mro__:
        annotations = getattr(base, '__annotations__', {})
        names.update(annotations.keys())
    return names


def _validate_protocols(protocols: tuple[type[object], ...]) -> None:
    for protocol in protocols:
        if not _is_protocol_class(protocol):
            raise TypeError(f'{protocol!r} is not a Protocol class')


def _normalize_protocols(*groups: tuple[type[object], ...]) -> tuple[type[object], ...]:
    result: list[type[object]] = []
    seen: set[type[object]] = set()
    for group in groups:
        for protocol in group:
            if protocol in seen:
                continue
            seen.add(protocol)
            result.append(protocol)
    return tuple(result)


def _validate_class_conformance(
    cls: type[object],
    protocols: tuple[type[object], ...],
    ) -> None:
    annotations = _class_annotations(cls)
    missing: list[str] = []
    for protocol in protocols:
        for name in _iter_protocol_members(protocol):
            if name in annotations:
                continue
            try:
                inspect.getattr_static(cls, name)
            except AttributeError:
                missing.append(f'{protocol.__name__}.{name}')

    if missing:
        joined = ', '.join(sorted(set(missing)))
        raise TypeError(f'{cls.__name__} is missing protocol members: {joined}')


def implementer(*protocols: type[object]):
    declared = tuple(protocols)
    _validate_protocols(declared)

    def decorate(cls: type[object]) -> type[object]:
        _validate_class_conformance(cls, declared)
        current = tuple(cls.__dict__.get('__implemented__', ()))
        cls.__implemented__ = _normalize_protocols(current, declared)
        return cls

    return decorate


def implementedBy(cls: type[object]) -> tuple[type[object], ...]:
    declared: list[tuple[type[object], ...]] = []
    for base in cls.__mro__:
        implemented = tuple(base.__dict__.get('__implemented__', ()))
        _validate_protocols(implemented)
        declared.append(implemented)
    return _normalize_protocols(*declared)


def directlyProvides(obj: object, *protocols: type[object]) -> None:
    declared = tuple(protocols)
    _validate_protocols(declared)
    obj.__provides__ = _normalize_protocols(declared)


def directlyProvidedBy(obj: object) -> tuple[type[object], ...]:
    provided = getattr(obj, '__provides__', ())
    if provided is None:
        return ()
    declared = tuple(provided)
    _validate_protocols(declared)
    return _normalize_protocols(declared)


def alsoProvides(obj: object, *protocols: type[object]) -> None:
    declared = tuple(protocols)
    _validate_protocols(declared)
    current = directlyProvidedBy(obj)
    directlyProvides(obj, *current, *declared)


def noLongerProvides(obj: object, protocol: type[object]) -> None:
    _validate_protocols((protocol,))
    current = directlyProvidedBy(obj)
    if protocol not in current:
        raise ValueError('Can only remove directly provided protocols.')
    remaining = tuple(item for item in current if item is not protocol)
    directlyProvides(obj, *remaining)


def providedBy(obj: object) -> tuple[type[object], ...]:
    cls = obj.__class__
    return _normalize_protocols(
        directlyProvidedBy(obj),
        implementedBy(cls),
        )
