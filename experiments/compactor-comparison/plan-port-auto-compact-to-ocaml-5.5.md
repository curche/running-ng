# Port: Automatic Compaction to Stock OCaml 5.5

**Repo**: `/home/curche/git/ocaml-compiler/ocaml-git`
**Branch**: `auto-compact-5.5` (based on tag `5.5.0`)
**Source patch**: `automatic-compactor-oxcaml.patch` (originally from OxCaml PR #3500)
**Reference port**: `new_compactor` branch in `socaml-git` (for comparison)

## Context

The patch was written against OxCaml, which already has the chunk-based pool
compactor (`pool_freelist.active_pools`, batch pool growth). Stock OCaml 5.5
uses a simpler allocator: `pool_acquire()` maps exactly one pool (`POOL_WSIZE`
words) at a time; there is no `active_pools` counter. Every file therefore
needs explicit review rather than a mechanical apply-and-skip.

Key structural differences from the socaml-git port:
- `shared_heap.c`: no `active_pools` — `caml_shared_heap_grow_bsize()` must
  return `Bsize_wsize(POOL_WSIZE)` (one pool) instead of the chunk-based formula
- `gc_ctrl.c`: stock 5.5 has no `extern caml_percent_max` to replace, and
  `caml_gc_get` does not set field 4 at all (it is implicitly 0); field 4 must
  be added, not replaced
- `gc_ctrl.c`: `caml_percent_free` and friends use `atomic_store_relaxed` /
  `atomic_load_relaxed` in stock 5.5 — preserve these when adding `caml_max_percent_free`

---

## Step 1 — Create branch

```bash
cd /home/curche/git/ocaml-compiler/ocaml-git
git checkout -b auto-compact-5.5 5.5.0
```

---

## Step 2 — `runtime/caml/config.h`

Add `Max_percent_free_def` after `Percent_free_def`:

```c
/* Default setting for the compacter: 500%
   (i.e. trigger the compacter when 5/6 of the heap is free or garbage).
 */
#define Max_percent_free_def 500
```

---

## Step 3 — `runtime/caml/major_gc.h`

Replace `caml_finish_major_cycle(int force_compaction)` with the enum + new signature:

```c
enum {
  Compaction_none,
  Compaction_forced,
  Compaction_auto,
};

void caml_finish_major_cycle(int compaction_mode);
```

---

## Step 4 — `runtime/caml/startup_aux.h`

Add `init_max_percent_free` to `caml_params` after `init_percent_free`.

---

## Step 5 — `runtime/caml/shared_heap.h`

Add the declaration:
```c
uintnat caml_shared_heap_grow_bsize(void);
```

---

## Step 6 — `runtime/shared_heap.c` *(adapted)*

The patch refactors `alloc_pool()` using `pool_freelist.active_pools` — absent
in stock 5.5. Instead, add only:

```c
uintnat caml_shared_heap_grow_bsize(void)
{
  return Bsize_wsize(POOL_WSIZE);
}
```

Leave `pool_acquire()` untouched.

---

## Step 7 — `runtime/major_gc.c`

1. Add `uintnat caml_max_percent_free = Max_percent_free_def;`
2. `caml_orphan_finalisers`: `caml_finish_major_cycle(0)` → `Compaction_none`
3. Add `should_compact_from_stw_single()` before `stw_cycle_all_domains`
4. In `stw_cycle_all_domains`: rename `force_compaction` → `compaction_mode`, add `static bool compacting` driven by `should_compact_from_stw_single`
5. `caml_opportunistic_major_collection_slice` → `Compaction_none`
6. `caml_major_collection_slice` both paths → `Compaction_auto`
7. `caml_finish_major_cycle` parameter rename throughout

---

## Step 8 — `runtime/gc_ctrl.c` *(adapted)*

- Add extern for `caml_max_percent_free`
- `caml_gc_get`: add `Store_field(res, 4, Val_long(caml_max_percent_free))`
- Add `norm_pmax()` after `norm_pfree()`
- `caml_gc_set`: read field 4, update `caml_max_percent_free` with message
- `gc_major_res`: pass `Compaction_auto`
- `gc_full_major_res`: `i == 2 ? Compaction_auto : Compaction_none`
- `caml_gc_compaction`: `i == 2 ? Compaction_forced : Compaction_none`
- `caml_init_gc`: init `caml_max_percent_free` from params
- `caml_runtime_parameters`: add `O=%...` to format string

---

## Step 9 — `runtime/startup_aux.c`

1. `init_startup_params`: add `params.init_max_percent_free = Max_percent_free_def;`
2. `parse_ocamlrunparam`: add `case 'O': scanmult(opt, &params.init_max_percent_free); break;`

---

## Step 10 — `stdlib/gc.mli`

Remove "This metric is currently not available in OCaml 5" note from `max_overhead`.
Replace with `Default: 500.`

---

## Step 11 — `manual/src/cmds/runtime.etex`

Add after the `o` entry:
```latex
  \item[O] ("max_overhead")  The compaction control setting.
        See the Gc module documentation for details.
```

---

## Step 12 — Version string

1. `build-aux/ocaml_version.m4`: set `OCAML__VERSION_EXTRA` to `ocaml-auto-compact`
2. Update `VERSION` to `5.5.0+ocaml-auto-compact`
3. Run `./tools/autogen`
4. `ocaml-variants.opam`: version `5.5.0+ocaml-auto-compact`, updated synopsis

---

## Step 13 — Build and verify

```bash
# Local build
./configure --enable-ocamltest && make coldstart && make -j$(nproc) && make tests

# Opam switch
SWITCH=ocaml-auto-compact-$(date +%Y%m%d-%H%M%S)
opam switch create "$SWITCH" --empty --yes
opam pin add ocaml-variants . --working-dir --yes --switch "$SWITCH"
opam install dune ocamlfind --switch "$SWITCH" --yes
opam exec --switch "$SWITCH" -- ocamlopt --version
# Expected: 5.5.0+ocaml-auto-compact
```
