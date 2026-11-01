# Worklog

## Root cause: ppxlib's `ast_506.ml` missing two "hole" constructors

`../trunk-auto-compact-comparison/`'s run had 12/29 benchmarks fail
identically on both `ocaml-trunk` and `ocaml-auto-compact-trunk` with
`Parsetree.<X>_desc` structural-equality errors. Root-caused by writing a
tiny standalone test (`type nonrec t = M.t = A | B` against a real `M.t =
A | B | C`) to pin down which side of the compiler's "extra/missing
constructor" wording refers to the *real* type vs. the local mirror --
confirmed "the original definition" = the right-hand-side real type being
matched against, so "extra constructor provided in the original
definition" means **the real compiler's `Parsetree` has it and the mirror
doesn't** (opposite of what the wording suggests at first read).

Checked `parsing/parsetree.mli` in the `auto-compact-trunk` compiler
directly: trunk added exactly two nullary "hole" constructors since 5.5.0
-- `Pexp_hole` (`expression_desc`) and `Pmod_hole` (`module_expr_desc`), a
recent language feature (`_` recognized as a placeholder expression/module
expression, rejected by the type-checker, meant to be eliminated by a ppx
before type-checking). The vendored ppxlib's `astlib/ast_506.ml` (its
mirror of the 5.6 `Parsetree` shape) predates this and has neither.

**First attempt was wrong**: initially added both constructors to
`ppxlib/ast/ast.ml` too (ppxlib's own internal "current AST" + 7 visitor
classes per type, mirroring the compiler-side fix pattern from
`auto-compact-tuning` Phase 10's socaml/`Ptyp_functor` fix). This broke
things further -- `ast.ml`'s own `(*IF_CURRENT*)`-style equality check
turned out to be against `Ppxlib_ast__.Import.Parsetree`, which traces
(via `import.ml`'s `Select_ast(Ocaml)` functor doing `include Js` where
`Js = Versions.OCaml_502`, never overridden) to `astlib/ast_502.ml` -- a
**fixed pivot AST ppxlib normalizes everything to/from**, not the real
compiler's actual Parsetree. Confirmed by checking `ast_502.ml` directly:
it has `Pexp_letop`/`Pexp_unreachable` (adopted post-5.0.2 features) but
no `Pexp_hole`/`Pmod_hole` -- so `ast.ml` is *correctly* missing them, and
my edit there was the bug, not the fix. Reverted all 15 added lines in
`ast.ml`.

**Real fix, confined to `astlib/`** (the layer that *does* check against
the true compiler-libs `Parsetree`, per-version):
- `duniverse/ppxlib/astlib/ast_506.ml`: added `Pexp_hole` to
  `expression_desc` and `Pmod_hole` to `module_expr_desc`, in the same
  position as the real `parsing/parsetree.mli` (both inert -- ppxlib's own
  grammar never constructs them, only the check needs to pass).
- `duniverse/ppxlib/astlib/migrate_506_505.ml` (the 506->505 downgrade
  migration -- the only other place that pattern-matches `Ast_506`'s
  `expression_desc`/`module_expr_desc` exhaustively): added
  `assert false` arms for both, since 505's pivot has no equivalent and
  our benchmarks never actually construct a hole node in practice
  (holes are a rare, deliberately-placed ppx-target feature, not something
  that shows up from parsing ordinary source).

Verified building `alt_ergo_fill` manually on both `ocaml-trunk` and
`ocaml-auto-compact-trunk` before re-running the full suite -- clean build
+ clean run on both.

## Remaining gap: `infer_default` on `ocaml-auto-compact-trunk` only

Its `scripts/vendor-javalib-sawja.sh` step builds two OCaml libraries via a
raw `make` (not `dune build`), which shells out to `ocamlfind ocamlopt`.
`ocamlfind`'s compiler binding is fixed to whichever opam switch is
active, not to `PATH` -- and since `ocaml-auto-compact-trunk` has no opam
switch of its own (`executable:` mode, built locally, the tooling env
comes from activating `running-ng-ocaml-trunk`'s switch for
`dune`/`ocamlfind` and prepending the real binary's `bin/` to `PATH`),
`ocamlfind` silently compiles javalib against `ocaml-trunk`'s real
compiler instead of `ocaml-auto-compact-trunk`'s, producing a genuine
(not spurious) "inconsistent assumptions over implementation Unix" link
error against the two different builds' `unix.cmxa`. Reproduced twice,
including after a full `rm -rf` of the vendored prefix and clean rebuild.
Not fixed here -- narrow, affects one cell out of 145 (5 runtimes x 29
benchmarks), and the general fix (making every vendor script's compiler
discovery PATH-consistent rather than opam-switch-tied) is out of scope
for a build-gap fix task. `ocaml-trunk` itself (which does have a matching
real opam switch) builds and runs `infer_default` fine.

## Re-run

Same 5 runtimes and full suite as `../trunk-auto-compact-comparison/`.
Result: 29/29 on every runtime except `ocaml-auto-compact-trunk` (28/29,
`infer_default` excluded per above) -- up from 17/29 on both trunk
runtimes in the original run. See `results.md` for the full writeup.
