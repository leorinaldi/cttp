# pyrepo

The closure fixture (plan P3-T1): `lib.py` has a function that calls two siblings, one of which
calls a third; a function importing `requests`; a function calling a name that does not exist.
`many.py` is a chain of 51 tiny definitions, over the closure budget. Nothing here is meant to run
as a package; the tests serve it as `github.com/leorinaldi/pyrepo`.
