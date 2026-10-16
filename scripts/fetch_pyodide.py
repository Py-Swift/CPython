#!/usr/bin/env python3
"""Fetch Pyodide's Python for WebAssembly builds (WASM_BUILD=1).

In the browser Python is Pyodide: the interpreter cibuildwheel's `pyodide`
platform builds wheels against (`cp313-pyodide_wasm32`), so wheels built
that way (Kivy's, …) load into it. Pyodide ships its Python as an
already-linked module, `pyodide.asm.wasm` (+ its loader `pyodide.asm.js`),
which imports its memory and function table and exports the whole C API —
there is no libpython archive to link. So for a wasm build this package
gives:

    PythonHeaders-pyodide/   Pyodide's Python headers (its pyconfig.h);
                             CPython.h includes them on wasm, the C API
                             calls stay imports, resolved from
                             pyodide.asm.wasm at load
    PythonHeaders-pyodide/python-functions.txt
                             Python's functions, which an app may leave
                             undefined: they become imports
    Sources/CPython/CPython+Pyodide.S
                             Python's data symbols, defined in the app at
                             the addresses they get there (write_link_inputs)
    Pyodide/                 the runtime: pyodide.asm.wasm, pyodide.asm.js,
                             pyodide.mjs / pyodide.js, pyodide-lock.json,
                             python_stdlib.zip, and VERSION (the Pyodide,
                             Python and Emscripten versions and the ABI
                             wheels must be built for)

Both come from Pyodide's cross-build environment (xbuildenv) — the same
archive cibuildwheel installs to build the wheels.

    python3 scripts/fetch_pyodide.py                    # Pyodide 0.29.5 (Python 3.13)
    python3 scripts/fetch_pyodide.py --pyodide 314.0.7  # another release

The default is cibuildwheel's default Pyodide for cp313 (cibuildwheel
4.3.1, build-platforms.toml), Python 3.13 like PythonHeaders/.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import sys
import tarfile
import urllib.request
from pathlib import Path

PACKAGE_DIR = Path(__file__).resolve().parent.parent
WORK_DIR = PACKAGE_DIR / "scripts" / ".work"
HEADERS_DIR = PACKAGE_DIR / "PythonHeaders-pyodide"
RUNTIME_DIR = PACKAGE_DIR / "Pyodide"

DEFAULT_PYODIDE = "0.29.5"
# sha256 of xbuildenv-<version>.tar.bz2 from Pyodide's GitHub release.
KNOWN_SHA256 = {
    "0.29.5": "5421beee636023f84e87a95d7d4c5fd15cb41939476731c8ed8387e72fb8cce1",
}
URL = "https://github.com/pyodide/pyodide/releases/download/{v}/xbuildenv-{v}.tar.bz2"

# What the page needs to start Pyodide (loadPyodide) and import the stdlib.
RUNTIME_FILES = (
    "pyodide.asm.wasm",
    "pyodide.asm.js",
    "pyodide.mjs",
    "pyodide.js",
    "pyodide-lock.json",
    "python_stdlib.zip",
)


def log(message: str) -> None:
    print(f"[fetch_pyodide] {message}", flush=True)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def download(version: str) -> Path:
    WORK_DIR.mkdir(parents=True, exist_ok=True)
    archive = WORK_DIR / f"xbuildenv-{version}.tar.bz2"
    if not archive.is_file():
        url = URL.format(v=version)
        log(f"downloading {url}")
        partial = archive.with_suffix(".part")
        urllib.request.urlretrieve(url, partial)
        partial.rename(archive)
    actual = sha256(archive)
    expected = KNOWN_SHA256.get(version)
    if expected is None:
        log(f"sha256 {actual} (no pinned checksum for {version})")
    elif actual != expected:
        archive.unlink()
        sys.exit(f"error: {archive.name}: sha256 {actual}, expected {expected}")
    return archive


def extract(archive: Path, version: str) -> Path:
    root = WORK_DIR / f"xbuildenv-{version}"
    if not (root / "xbuildenv" / "pyodide-root").is_dir():
        if root.exists():
            shutil.rmtree(root)
        root.mkdir(parents=True)
        log(f"extracting {archive.name}")
        with tarfile.open(archive) as tf:
            tf.extractall(root, filter="data")
    return root / "xbuildenv" / "pyodide-root"


def makefile_var(makefile: str, name: str) -> str:
    match = re.search(rf"^export {name} \?= (\S+)", makefile, re.MULTILINE)
    if not match:
        sys.exit(f"error: {name} not in Makefile.envs")
    return match.group(1)


def install(pyodide_root: Path, version: str) -> None:
    makefile = (pyodide_root / "Makefile.envs").read_text()
    python = makefile_var(makefile, "PYVERSION")
    emscripten = makefile_var(makefile, "PYODIDE_EMSCRIPTEN_VERSION")
    abi = makefile_var(makefile, "PYODIDE_ABI_VERSION")
    major_minor = ".".join(python.split(".")[:2])

    include = pyodide_root / "cpython" / "installs" / f"python-{python}" / "include" / f"python{major_minor}"
    if not (include / "Python.h").is_file():
        sys.exit(f"error: no Python.h in {include}")
    if HEADERS_DIR.exists():
        shutil.rmtree(HEADERS_DIR)
    shutil.copytree(include, HEADERS_DIR)
    # Headers in cpython/ include their siblings as "cpython/x.h", which
    # only resolves with the headers' root on the include path — CPython.h
    # includes them by relative path, for every target that imports it.
    # Later 3.13 releases (PythonHeaders/) include them as "x.h"; same here.
    for header in (HEADERS_DIR / "cpython").glob("*.h"):
        text = header.read_text()
        fixed = re.sub(r'(#\s*include\s+")cpython/', r"\1", text)
        if fixed != text:
            header.write_text(fixed)
    log(f"headers  -> {HEADERS_DIR.relative_to(PACKAGE_DIR)}/ (Python {python})")

    # Only the files fetched here are replaced: pyodide.wasm-host.mjs, next
    # to them, is this package's own.
    RUNTIME_DIR.mkdir(exist_ok=True)
    for name in RUNTIME_FILES:
        source = pyodide_root / "dist" / name
        if not source.is_file():
            sys.exit(f"error: {name} not in the xbuildenv's dist/")
        shutil.copy2(source, RUNTIME_DIR / name)
    loader = (pyodide_root / "dist" / "pyodide.asm.js").read_text()
    static_size = int(re.search(r"var ___stack_high=(\d+);", loader).group(1)) - int(base_address(loader))
    patch_loader(RUNTIME_DIR / "pyodide.asm.js")
    module = (RUNTIME_DIR / "pyodide.asm.wasm").read_bytes()
    # The memory pyodide.asm.wasm asks for at its own base, and the size of
    # its data and stack: the region an app keeps for them.
    pages = memory_import_minimum(module)
    (RUNTIME_DIR / "layout.json").write_text(json.dumps({"memoryPages": pages, "staticSize": static_size}) + "\n")
    functions, data = python_exports(module)
    write_link_inputs(version, functions, data, static_size)
    (RUNTIME_DIR / "VERSION").write_text(
        f"pyodide={version}\n"
        f"python={python}\n"
        f"emscripten={emscripten}\n"
        f"abi=pyodide_{abi}_wasm32\n"
    )
    log(f"runtime  -> {RUNTIME_DIR.relative_to(PACKAGE_DIR)}/ (Pyodide {version}, Emscripten {emscripten}, ABI pyodide_{abi}_wasm32)")

    apple = (PACKAGE_DIR / "PythonHeaders" / "patchlevel.h").read_text()
    apple_version = re.search(r'#define PY_VERSION\s+"(\d+\.\d+)', apple).group(1)
    if apple_version != major_minor:
        log(f"warning: Pyodide {version} is Python {major_minor}, PythonHeaders/ is {apple_version}")


def patch_loader(path: Path) -> None:
    """Let pyodide.asm.js place Python in a host module's memory and table.

    pyodide.asm.wasm is relocatable — it imports __memory_base, __table_base,
    __stack_pointer and its heap base — but its loader hardcodes where it
    goes: data at 1024, its stack and heap above, functions from table index
    1 of a table it creates. With `Module.hostLayout = { memoryBase, table, heapBase }`
    (and `Module.wasmMemory`, which the loader already takes) every one of
    those moves by the same offset, into the host's table; without it the
    loader is unchanged.
    """
    text = path.read_text()

    def patch(pattern: str, replacement) -> re.Match:
        matches = list(re.finditer(pattern, text))
        if len(matches) != 1:
            sys.exit(f"error: {path.name}: expected one match of {pattern!r}, found {len(matches)}")
        return matches[0]

    memory_base = patch(r'var ___memory_base=new WebAssembly\.Global\(\{value:"i32",mutable:false\},(\d+)\);', None)
    table_base = patch(r'var ___table_base=new WebAssembly\.Global\(\{value:"i32",mutable:false\},(\d+)\);', None)
    base, first_slot = memory_base.group(1), table_base.group(1)

    replacements = [
        # Read once, before anything below runs.
        (r"var Module=moduleArg;",
         lambda m: m.group(0)
         + 'var __hostLayout=Module["hostLayout"];'
         + f"var __hostDelta=__hostLayout?__hostLayout.memoryBase-{base}:0;"
         + "var __hostTable=__hostLayout?__hostLayout.table:null;"
         + "var __hostTableBase=__hostTable?__hostTable.length:0;"),
        (r"relocateExports\(wasmExports,(\d+)\)",
         lambda m: f"relocateExports(wasmExports,{m.group(1)}+__hostDelta)"),
        (r'var ___memory_base=new WebAssembly\.Global\(\{value:"i32",mutable:false\},(\d+)\);',
         lambda m: f'var ___memory_base=new WebAssembly.Global({{value:"i32",mutable:false}},{m.group(1)}+__hostDelta);'),
        (r"var ___global_base=(\d+);",
         lambda m: f"var ___global_base={m.group(1)}+__hostDelta;"),
        (r'var ___stack_high=(\d+);var ___stack_low=(\d+);var ___stack_pointer=new WebAssembly\.Global\(\{value:"i32",mutable:true\},(\d+)\);',
         lambda m: f"var ___stack_high={m.group(1)}+__hostDelta;var ___stack_low={m.group(2)}+__hostDelta;"
                   f'var ___stack_pointer=new WebAssembly.Global({{value:"i32",mutable:true}},{m.group(3)}+__hostDelta);'),
        # Its heap starts after the host's own data, which may follow its
        # region rather than precede it.
        (r"var ___heap_base=(\d+);",
         lambda m: f"var ___heap_base=__hostLayout&&__hostLayout.heapBase?__hostLayout.heapBase:{m.group(1)}+__hostDelta;"),
        # Its functions go after the host's: slots [length, length + size - first).
        (r'var ___table_base=new WebAssembly\.Global\(\{value:"i32",mutable:false\},(\d+)\);',
         lambda m: f'var ___table_base=new WebAssembly.Global({{value:"i32",mutable:false}},__hostTable?__hostTableBase:{m.group(1)});'),
        (r'var wasmTable=new WebAssembly\.Table\(\{initial:(\d+),element:"anyfunc"\}\);',
         lambda m: f"var wasmTable=__hostTable?(__hostTable.grow({m.group(1)}-{first_slot}),__hostTable)"
                   f':new WebAssembly.Table({{initial:{m.group(1)},element:"anyfunc"}});'),
    ]
    for pattern, replacement in replacements:
        match = patch(pattern, replacement)
        text = text[:match.start()] + replacement(match) + text[match.end():]

    # The addresses of its exported data are literals: `var _x=Module["_x"]=N;`.
    text, count = re.subn(r'(var (_[\w$]+)=Module\["\2"\]=)(\d+);', r"\1\3+__hostDelta;", text)
    if count == 0:
        sys.exit(f"error: {path.name}: no exported data addresses found")

    # EM_ASM snippets are keyed by their address in its data. Side modules
    # add theirs later at their own (absolute) addresses, so the main
    # module's keys are moved once, where they are defined.
    start = patch(r"var ASM_CONSTS=\{", None).end() - 1
    end = closing_brace(text, start)
    if not text.startswith(";", end + 1):
        sys.exit(f"error: {path.name}: unexpected end of ASM_CONSTS")
    text = (text[:end + 2]
            + "if(__hostDelta){ASM_CONSTS=Object.fromEntries(Object.entries(ASM_CONSTS).map(([k,v])=>[+k+__hostDelta,v]))}"
            + text[end + 2:])
    path.write_text(text)
    log(f"patched  {path.name}: Module.hostLayout places it in a host's memory and table")


def base_address(loader: str) -> str:
    """Where pyodide.asm.js places the module's data: its __memory_base."""
    return re.search(r'var ___memory_base=new WebAssembly\.Global\(\{value:"i32",mutable:false\},(\d+)\);', loader).group(1)


def python_exports(wasm: bytes) -> tuple[list[str], dict[str, int]]:
    """The C API pyodide.asm.wasm exports: its functions' names, and its
    data's offsets from the module's memory base (exported globals)."""
    reader = WasmReader(wasm)
    imported_globals, initial_values, exports = 0, [], []
    for section, end in reader.sections():
        if section == 2:  # imports
            for _ in range(reader.leb()):
                reader.name(), reader.name()
                kind = reader.byte()
                if kind == 0:
                    reader.leb()
                elif kind in (1, 2):
                    if kind == 1:
                        reader.byte()
                    flags = reader.leb(); reader.leb()
                    if flags & 1:
                        reader.leb()
                elif kind == 3:
                    reader.byte(), reader.byte()
                    imported_globals += 1
                elif kind == 4:
                    reader.byte(); reader.leb()
        elif section == 6:  # globals: type, mutability, i32.const value, end
            for _ in range(reader.leb()):
                reader.byte(), reader.byte()
                value = reader.sleb() if reader.byte() == 0x41 else None
                while reader.byte() != 0x0B:
                    pass
                initial_values.append(value)
        elif section == 7:  # exports
            for _ in range(reader.leb()):
                exports.append((reader.name(), reader.byte(), reader.leb()))
        reader.at = end
    python = re.compile(r"_?Py[A-Za-z_]")
    functions = sorted(name for name, kind, _ in exports if kind == 0 and python.match(name))
    data = {
        name: initial_values[index - imported_globals]
        for name, kind, index in exports
        if kind == 3 and index >= imported_globals and python.match(name)
        and initial_values[index - imported_globals] is not None
    }
    return functions, data


def write_link_inputs(version: str, functions: list[str], data: dict[str, int], static_size: int) -> None:
    """What an app links against Python with, in the browser.

    Python's functions are imports of the app (the host passes Pyodide's own),
    listed for the linker to allow undefined. Python's data is defined in the
    app: a zero-filled region the size of Pyodide's data and stack, where the
    host loads it, with every data symbol at its offset in it — so a pointer
    to Py_None or a type object is a link-time address, as everywhere else.
    """
    (HEADERS_DIR / "python-functions.txt").write_text("\n".join(functions) + "\n")
    lines = [
        f"// Generated by scripts/fetch_pyodide.py from Pyodide {version}'s pyodide.asm.wasm. Do not edit.",
        "//",
        "// WebAssembly: Python's data lives in the app — the region Pyodide/pyodide.wasm-host.mjs",
        "// loads pyodide.asm.wasm's data and stack into — and each of its data symbols is",
        "// the address of that symbol there.",
        "#if defined(__wasm__)",
        '  .section .bss.__cpython_pyodide,"",@',
        "  .globl __cpython_pyodide",
        "  .p2align 16",
        "__cpython_pyodide:",
        f"  .skip {static_size}",
        f"  .size __cpython_pyodide, {static_size}",
    ]
    for name, offset in sorted(data.items()):
        lines += [f"  .globl {name}", f"  .set {name}, __cpython_pyodide+{offset}"]
    lines.append("#endif")
    (PACKAGE_DIR / "Sources" / "CPython" / "CPython+Pyodide.S").write_text("\n".join(lines) + "\n")
    log(f"link     -> {len(functions)} Python functions imported, {len(data)} data symbols in a {static_size}-byte region")


class WasmReader:
    def __init__(self, wasm: bytes):
        self.wasm, self.at = wasm, 8

    def byte(self) -> int:
        self.at += 1
        return self.wasm[self.at - 1]

    def leb(self) -> int:
        result = shift = 0
        while True:
            byte = self.byte()
            result |= (byte & 0x7F) << shift
            shift += 7
            if not byte & 0x80:
                return result

    def sleb(self) -> int:
        result = shift = 0
        while True:
            byte = self.byte()
            result |= (byte & 0x7F) << shift
            shift += 7
            if not byte & 0x80:
                return result - (1 << shift) if byte & 0x40 else result

    def name(self) -> str:
        length = self.leb()
        self.at += length
        return self.wasm[self.at - length:self.at].decode()

    def sections(self):
        while self.at < len(self.wasm):
            section = self.byte()
            size = self.leb()
            yield section, self.at + size


def memory_import_minimum(wasm: bytes) -> int:
    """The minimum, in pages, of the module's imported memory."""
    at = 8

    def leb() -> int:
        nonlocal at
        result = shift = 0
        while True:
            byte = wasm[at]
            at += 1
            result |= (byte & 0x7F) << shift
            shift += 7
            if not byte & 0x80:
                return result

    def name() -> str:
        nonlocal at
        length = leb()
        at += length
        return wasm[at - length:at].decode()

    while at < len(wasm):
        section, size = wasm[at], None
        at += 1
        size = leb()
        if section != 2:
            at += size
            continue
        for _ in range(leb()):
            name(), name()
            kind = wasm[at]
            at += 1
            if kind == 0:      # function: type index
                leb()
            elif kind == 1:    # table: element type, limits
                at += 1
                flags = leb(); leb()
                if flags & 1:
                    leb()
            elif kind == 2:    # memory: limits
                flags = leb()
                return leb()
            elif kind == 3:    # global: value type, mutability
                at += 2
            elif kind == 4:    # tag: attribute, type index
                at += 1
                leb()
        break
    sys.exit("error: pyodide.asm.wasm imports no memory")


def closing_brace(text: str, start: int) -> int:
    """Index of the `}` closing the `{` at `start`, skipping string literals."""
    depth, i, quote = 0, start, None
    while i < len(text):
        c = text[i]
        if quote:
            if c == "\\":
                i += 1
            elif c == quote:
                quote = None
        elif c in "\"'`":
            quote = c
        elif c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return i
        i += 1
    sys.exit("error: unbalanced braces")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--pyodide", default=DEFAULT_PYODIDE, help=f"Pyodide release (default {DEFAULT_PYODIDE})")
    args = parser.parse_args()
    archive = download(args.pyodide)
    install(extract(archive, args.pyodide), args.pyodide)


if __name__ == "__main__":
    main()
