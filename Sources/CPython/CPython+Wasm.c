//
//  CPython+Wasm.c
//  CPython
//
//  WebAssembly: Python is Pyodide, in the app's own memory
//  (Pyodide/pyodide.wasm-host.mjs). Two allocators in one memory would hand
//  out the same pages — WASI libc's takes new pages with memory.grow, while
//  Emscripten's treats everything above its break as its own — so the app
//  allocates with Python's: these replace WASI libc's malloc (all of its
//  dlmalloc.o, so that is never linked) and call Pyodide's exports directly.
//
#if defined(__wasm__)

#include <stddef.h>

#define PYODIDE(name) __attribute__((import_module("env"), import_name(#name)))

PYODIDE(malloc) void *pyodide_malloc(size_t size);
PYODIDE(free) void pyodide_free(void *pointer);
PYODIDE(calloc) void *pyodide_calloc(size_t count, size_t size);
PYODIDE(realloc) void *pyodide_realloc(void *pointer, size_t size);
PYODIDE(posix_memalign) int pyodide_posix_memalign(void **result, size_t alignment, size_t size);
PYODIDE(aligned_alloc) void *pyodide_aligned_alloc(size_t alignment, size_t size);
PYODIDE(malloc_usable_size) size_t pyodide_malloc_usable_size(void *pointer);

void *malloc(size_t size) { return pyodide_malloc(size); }
void free(void *pointer) { pyodide_free(pointer); }
void *calloc(size_t count, size_t size) { return pyodide_calloc(count, size); }
void *realloc(void *pointer, size_t size) { return pyodide_realloc(pointer, size); }
int posix_memalign(void **result, size_t alignment, size_t size) { return pyodide_posix_memalign(result, alignment, size); }
void *aligned_alloc(size_t alignment, size_t size) { return pyodide_aligned_alloc(alignment, size); }
size_t malloc_usable_size(void *pointer) { return pyodide_malloc_usable_size(pointer); }

// WASI libc's own callers (locales, atexit) use these names.
void *__libc_malloc(size_t size) { return pyodide_malloc(size); }
void __libc_free(void *pointer) { pyodide_free(pointer); }
void *__libc_calloc(size_t count, size_t size) { return pyodide_calloc(count, size); }

#endif
