# Port the zope.interface Adapter Framework Design

## Goal

Add a small, typed adapter registry for declared protocols. The registry will
preserve the core `zope.interface.adapter.AdapterRegistry` API needed to
register, find, and invoke single- and multi-adapters without porting its
legacy persistence, subscription, or cache machinery.

## Chosen approach

Implement a purpose-built registry over an insertion-ordered collection of
registrations. This is preferable to copying the reference implementation,
whose data structures depend on `zope.interface` specification objects and
support features outside this issue. It is also preferable to maintaining a
nested cache initially: a direct matcher is smaller, makes protocol precedence
explicit, and can be optimized later without changing the public API.

## Public API

`declareprotocol.adapter` will define `AdapterRegistry`, also exported from
`declareprotocol`.

The registry will provide these core operations:

- `register(required, provided, name, value)` registers or replaces a value.
  `required` is an ordered sequence containing one required protocol per
  adapted object; `None` is a wildcard. `provided` is the target protocol,
  `name` is a string qualifier, and `value` is normally an adapter factory.
  Registering `None` removes the matching registration.
- `unregister(required, provided, name, value=None)` removes an exact
  registration and reports whether one was removed. When `value` is supplied,
  removal occurs only when it is the registered object.
- `registered(required, provided, name="")` returns only an exact registration.
- `lookup(required, provided, name="", default=None)` returns the best matching
  registered value without invoking it. Each lookup requirement may be a
  protocol or a declaration tuple returned by `implementedBy()` or
  `providedBy()`.
- `lookup1(required, provided, name="", default=None)` is the single-requirement
  convenience form.
- `queryAdapter(obj, provided, name="", default=None)` and
  `queryMultiAdapter(objects, provided, name="", default=None)` derive source
  declarations with `providedBy()`, find a factory, invoke it with the source
  object or objects, and return the result.
- `adapter_hook(provided, obj, name="", default=None)` delegates to
  `queryAdapter()` with the conventional argument order.

Names match exactly; the empty string is the unnamed registration. Registration
values may be arbitrary for `lookup()`, but query operations require the
selected value to be callable and let Python raise `TypeError` otherwise.

## Matching and precedence

A required protocol matches itself and protocols derived from it. Protocol
inheritance will be read from protocol MROs rather than with `issubclass()`,
which rejects protocols that are not runtime-checkable. A `None` requirement
matches any declaration. A declaration tuple is treated as the ordered set of
protocols declared for one source object, not as multiple adapted objects.

A registration for a provided protocol also satisfies a lookup for one of that
protocol's bases. Exact provided-protocol matches take precedence over derived
provided protocols.

Among matching registrations, selection is deterministic:

1. Match the requested name and adapter arity exactly.
2. Prefer an exact provided protocol, then its nearest derived protocol.
3. Prefer exact required protocols over inherited matches, and inherited
   matches over `None` wildcards, comparing adapted positions in order.
4. Preserve declaration order from `providedBy()`/`implementedBy()` when an
   object has multiple declarations.
5. Preserve registration insertion order for any remaining tie.

Replacing an exact registration retains its position. Zero-source registrations
are supported by `register((), ...)` and `lookup((), ...)`; querying an empty
object tuple invokes the selected zero-argument factory.

A selected factory is called once with the original objects. If it returns
`None`, query operations return their supplied default. Factory exceptions are
not caught.

## Validation and errors

Registration and lookup validate required and provided values as Protocol
classes, except for the documented `None` wildcard and declaration tuples.
Invalid protocols or malformed declaration tuples raise `TypeError`. A
non-string name raises `ValueError`, matching the reference API. Missing
registrations return the caller's default. The implementation will not silently
ignore malformed declarations or factory failures.

## Affected components

- Create `src/declareprotocol/adapter.py` for registration storage, matching,
  and factory invocation.
- Create `src/declareprotocol/adapter_test.py` for focused registry tests.
- Update `src/declareprotocol/__init__.py` to export `AdapterRegistry`.
- Update `README.md` with one concise single-adapter example so the new public
  behavior is discoverable.

No runtime dependency on `zope.interface` will be added. The implementation
must support the project's Python floor of 3.12 and follow its existing typing
and formatting conventions.

## Verification strategy

Tests will cover:

- empty registry behavior, exact registration, replacement, exact inspection,
  removal, names, defaults, and invalid arguments;
- single-adapter lookup through exact, inherited, multiple, class-inherited,
  and directly provided declarations;
- required specificity, wildcard fallback, provided-protocol covariance, and
  deterministic precedence;
- multi-adapter arity, per-position inheritance, wildcard matching, argument
  order, and no-match behavior;
- `queryAdapter()`, `queryMultiAdapter()`, `adapter_hook()`, zero-source
  factories, factory-returned `None`, and propagated factory errors;
- package-level import of `AdapterRegistry`.

Run the complete project checks used by CI:

```bash
uv run ruff check src
uv run ruff format --check src
uv run python -m pytest
```

## Non-goals

This first port will not implement registry inheritance, lookup caching,
generation tracking, persistence customization, subscriptions/subscribers,
utilities, change notifications, C accelerators, or compatibility with
`zope.interface` interface/specification objects. These features can be added
later behind the same core API if concrete use cases require them.
