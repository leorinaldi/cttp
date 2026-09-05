# crepo

A small C repository. It exists so that cttp's tree-sitter extractor has every kind of
definition it must handle: macros with and without parameters, an enum, a struct, a typedef, a
constant table, functions (one returning a pointer, one with a kernel-doc comment), a construct
the grammar does not know (`MODULE_DEVICE_TABLE`), link lines in both C comment syntaxes — and the
same decoder written three times: verbatim in `src/sensor.c` and `src/twin.c` (one identity), with
other names and literals in `src/other.c` (one shape). Served in tests as
`github.com/leorinaldi/crepo`.
