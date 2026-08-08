# zope.interface observations

## Revision inspected

- Repository: https://github.com/zopefoundation/zope.interface
- Local checkout: `/tmp/zope.interface`
- Revision: `b0ddabd`

## Notes relevant to issue #1

- Declaration/query APIs are concentrated in `declarations.py`.
- Adapter registry code in `adapter.py` depends on declaration queries,
  especially `providedBy`, more than declaration storage internals.
- `__implemented__` and `__provides__` are natural storage names for class
  and object declarations and match existing ecosystem expectations.
- For this first pass, a minimal declaration/query implementation can be built
  without reproducing all of the `Specification` machinery, while keeping the
  API shape adapter-friendly for later work.
