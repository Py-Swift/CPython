// pyodide.wasm-host.mjs — Python for a WebAssembly app that links CPython
// (WASM_BUILD=1), served with the app's resources.
//
// Python is Pyodide's build (scripts/fetch_pyodide.py): the interpreter
// cibuildwheel's pyodide platform builds wheels for. It comes as an
// already-linked module, pyodide.asm.wasm, so it is not linked into the app;
// the app and Python share one memory and one function table instead, the
// way Python and the extension modules it loads share them:
//
//   - the app imports its memory and table (CPython's linker settings), which
//     are created here, before the app;
//   - Python's module is loaded into them: its data and stack into the region
//     the app keeps for them (`__cpython_pyodide`, CPython+Pyodide.S, where
//     the app's Python data symbols point), its heap above the app's own data
//     and stack, its functions after the app's (pyodide.asm.js's
//     Module.hostLayout) — with its runtime and file system up, and Python
//     itself not started: Pyodide's `main` does not run. The app starts
//     Python, as on any other platform (Py_InitializeFromConfig), when and
//     how it chooses;
//   - the app's imports of the C API are that module's own functions: direct
//     calls. The app's malloc is the module's (CPython+Wasm.c): one heap.
//
// Python's file system has the standard library at /lib/python313.zip (on
// the default module search path for home "/") and the app's resource files
// at the paths the app sees them.
//
// The page calls `prepare` before it instantiates the app and passes the
// imports it returns along with the app's other imports.

const base = new URL('./', import.meta.url);

/**
 * @param {object} context
 * @param {ArrayBuffer} context.bytes          the app's module
 * @param {WebAssembly.Module} context.module  the same, compiled
 * @param {{ files: Object<string, Uint8Array> }} [context.resources]  the app's resource
 *   files by absolute path, written to Python's file system at the same paths
 * @returns {Promise<{ imports: object, attach: (instance) => void, runtime: object }>}
 *   the imports; `attach`, for once the app is instantiated; and the
 *   Emscripten module Python runs in (its FS, …)
 */
export async function prepare({ bytes, module, resources }) {
  const limits = appLayout(new Uint8Array(bytes));
  if (!limits.memory || !limits.table || limits.region === undefined) {
    throw new Error('the app does not import its memory and table or keep a region for Python: is it linked against CPython for wasm?');
  }
  const fetchBytes = async (name) => {
    const response = await fetch(new URL(name, base));
    if (!response.ok) throw new Error(`cannot load ${name} (${response.status})`);
    return response.arrayBuffer();
  };
  const [layout, python, stdlib] = await Promise.all([
    fetchBytes('layout.json').then((data) => JSON.parse(new TextDecoder().decode(data))),
    fetchBytes('pyodide.asm.wasm'),
    fetchBytes('python_stdlib.zip'),
  ]);

  // Python's data and stack in the app's region; its heap after everything
  // the app's memory starts with.
  const memoryBase = limits.region;
  const heapBase = limits.memory.minimum * 65536;
  const memory = new WebAssembly.Memory({ initial: Math.max(limits.memory.minimum + 16, layout.memoryPages), maximum: 65536 });
  const table = new WebAssembly.Table({ initial: limits.table.minimum, element: 'anyfunc' });

  if (typeof globalThis._createPyodideModule !== 'function') await import(new URL('pyodide.asm.js', base));
  const runtime = await globalThis._createPyodideModule({
    noInitialRun: true,
    wasmMemory: memory,
    hostLayout: { memoryBase, table, heapBase },
    print: (text) => console.log(text),
    printErr: (text) => console.error(text),
    API: { config: {}, runtimeEnv: runtimeEnv() },
    // pyodide.mjs adds this pair to the module's imports: a marker value
    // and its test.
    instantiateWasm(wasmImports, done) {
      const marker = Symbol('error marker');
      wasmImports.sentinel = { create_sentinel: () => marker, is_sentinel: (value) => value === marker };
      WebAssembly.instantiate(python, wasmImports).then(({ instance, module }) => done(instance, module));
      return {};
    },
    preRun: [(runtime) => {
      runtime.FS.mkdirTree('/lib');
      runtime.FS.writeFile('/lib/python313.zip', new Uint8Array(stdlib));
      for (const [path, contents] of Object.entries(resources?.files ?? {})) {
        runtime.FS.mkdirTree(path.slice(0, path.lastIndexOf('/')) || '/');
        runtime.FS.writeFile(path, contents);
      }
    }],
  });

  // The app's memory is imported, so instantiating it zeroes its .bss —
  // the region included — before anything of it runs (wasm-ld's
  // memory.fill in its start function). Python's data and stack are put
  // back right after (`attach`).
  const pythonStatic = new Uint8Array(memory.buffer, memoryBase, layout.staticSize).slice();

  const symbols = runtime.LDSO.loadedLibsByName.__main__.exports;
  const imports = { env: { memory, __indirect_function_table: table } };
  for (const { module: from, name, kind } of WebAssembly.Module.imports(module)) {
    if (from === 'env' && kind === 'function' && typeof symbols[name] === 'function') imports.env[name] = symbols[name];
  }
  // The app's exported functions join Python's global symbols, as a native
  // executable's do for the libraries it loads: an extension module that
  // leaves one undefined (a C api the app provides) finds it there.
  const attach = (instance) => {
    new Uint8Array(memory.buffer, memoryBase, layout.staticSize).set(pythonStatic);
    for (const [name, value] of Object.entries(instance.exports)) {
      if (typeof value === 'function' && !(name in symbols)) symbols[name] = value;
    }
  };
  return { imports, attach, runtime };
}

/** Where the page runs, as pyodide.mjs works it out for the module's JavaScript side. */
function runtimeEnv() {
  const IN_BUN = typeof globalThis.Bun !== 'undefined';
  const IN_DENO = typeof globalThis.Deno !== 'undefined';
  const IN_NODE = typeof process === 'object' && typeof process.versions?.node === 'string' && !process.browser;
  const IN_BROWSER = !IN_NODE && !IN_DENO && !IN_BUN;
  const userAgent = typeof navigator === 'object' ? String(navigator.userAgent) : '';
  return {
    IN_BUN, IN_DENO, IN_NODE, IN_BROWSER,
    IN_SAFARI: !userAgent.includes('Chrome') && userAgent.includes('Safari'),
    IN_SHELL: false,
    IN_NODE_COMMONJS: false,
    IN_NODE_ESM: IN_NODE,
    IN_BROWSER_MAIN_THREAD: IN_BROWSER && typeof window !== 'undefined' && typeof document !== 'undefined'
      && typeof globalThis.importScripts !== 'function',
    IN_BROWSER_WEB_WORKER: IN_BROWSER && typeof globalThis.WorkerGlobalScope !== 'undefined'
      && globalThis.self instanceof globalThis.WorkerGlobalScope,
  };
}

/**
 * The app's layout, from its sections: the minimums of its imported memory
 * and table, and the address of the region it keeps for Python's data
 * (its exported `__cpython_pyodide` global).
 */
function appLayout(wasm) {
  let at = 8;
  const leb = () => {
    let result = 0, shift = 0, byte;
    do { byte = wasm[at++]; result += (byte & 0x7f) * 2 ** shift; shift += 7; } while (byte & 0x80);
    return result;
  };
  const sleb = () => {
    let result = 0, shift = 0, byte;
    do { byte = wasm[at++]; result += (byte & 0x7f) * 2 ** shift; shift += 7; } while (byte & 0x80);
    return byte & 0x40 ? result - 2 ** shift : result;
  };
  const name = () => { const length = leb(); at += length; return new TextDecoder().decode(wasm.subarray(at - length, at)); };
  const limits = () => {
    const flags = leb();
    const minimum = leb();
    if (flags & 1) leb();
    return { minimum };
  };
  const found = {};
  let importedGlobals = 0;
  const globalValues = [];
  let regionGlobal;
  while (at < wasm.length) {
    const section = wasm[at++];
    const size = leb();
    const end = at + size;
    if (section === 2) {                                         // imports
      for (let count = leb(); count > 0; count--) {
        name(); name();
        const kind = wasm[at++];
        if (kind === 0) leb();                                   // function: type index
        else if (kind === 1) { at++; found.table = limits(); }  // table: element type, limits
        else if (kind === 2) found.memory = limits();            // memory
        else if (kind === 3) { at += 2; importedGlobals++; }     // global: type, mutability
        else if (kind === 4) { at++; leb(); }                    // tag
      }
    } else if (section === 6) {                                  // globals: type, mutability, init
      for (let count = leb(); count > 0; count--) {
        at += 2;
        const opcode = wasm[at++];
        globalValues.push(opcode === 0x41 ? sleb() : undefined);  // i32.const
        while (wasm[at++] !== 0x0b);
      }
    } else if (section === 7) {                                  // exports
      for (let count = leb(); count > 0; count--) {
        const exported = name();
        const kind = wasm[at++];
        const index = leb();
        if (kind === 3 && exported === '__cpython_pyodide') regionGlobal = index;
      }
    }
    at = end;
  }
  if (regionGlobal !== undefined) found.region = globalValues[regionGlobal - importedGlobals];
  return found;
}
