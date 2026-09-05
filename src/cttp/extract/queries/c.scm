;; cttp definitions for C — the read side (spec §3, plan P6-T1).
;;
;; Each pattern captures one definition node as `@definition.<kind>` and, where the grammar has a
;; field for it, the node carrying its name as `@name`. A function's or a variable's name sits at
;; the bottom of a declarator chain (`*`, `[]`, `(…)` wrap it), so `treesitter.py` descends the
;; `declarator` field when no `@name` was captured. Kinds: function, constant, type, macro.
;;
;; Every pattern matches anywhere in the tree; `treesitter.py` keeps only file-scope definitions
;; (nothing inside a function body, a struct body, a parameter list or an enumerator list).

;; a function with a body
(function_definition) @definition.function

;; a variable defined with an initializer — a table, a constant
(declaration
  declarator: (init_declarator)) @definition.constant

;; a tagged type with a body: struct, union, enum — addressed as `struct.<tag>` etc.
(struct_specifier
  name: (type_identifier) @name
  body: (field_declaration_list)) @definition.type
(union_specifier
  name: (type_identifier) @name
  body: (field_declaration_list)) @definition.type
(enum_specifier
  name: (type_identifier) @name
  body: (enumerator_list)) @definition.type

;; a typedef
(type_definition
  declarator: (type_identifier) @name) @definition.type

;; a macro, with or without parameters
(preproc_def
  name: (identifier) @name) @definition.macro
(preproc_function_def
  name: (identifier) @name) @definition.macro
