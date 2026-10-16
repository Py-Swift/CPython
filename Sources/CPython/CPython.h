//
//  shim.h
//  CPython
//

#ifndef CPython_h
#define CPython_h

// Swift targets with C++ interop import this as a C++ clang module. Python's own
// headers include system headers inside `extern "C" {}`, which clang rejects for
// modular headers by default (-Wmodule-import-in-extern-c). Those headers carry
// their own linkage, so the diagnostic is safe to silence here.
#ifdef __cplusplus
#pragma clang diagnostic push
#pragma clang diagnostic ignored "-Wmodule-import-in-extern-c"
#endif

// Platform-specific Python header inclusion.
// PIP_MODE is set as a cSetting define by CPython's Package.swift in all pip/cibuildwheel
// build modes (macOS PIP_MODE, Android new-style PIP_MODE). It is NOT set in Xcode / xcframework mode.
#if defined(__wasm__)
// WebAssembly: Pyodide's headers (scripts/fetch_pyodide.py); the C API
// itself is exported by Pyodide/pyodide.asm.wasm.
#include "../../PythonHeaders-pyodide/Python.h"
#include "../../PythonHeaders-pyodide/datetime.h"
#elif defined(__ANDROID__) && !defined(PIP_MODE)
// Old Android: bundled PythonHeaders-android
#include "../../PythonHeaders-android/Python.h"
#include "../../PythonHeaders-android/datetime.h"
#elif defined(PIP_MODE)
// PIP_MODE (macOS cibuildwheel or Android new-style): Python.h from CPATH env var.
// On Android, bionic's pthread_types.h uses uint32_t/int32_t before stdint.h has
// been pulled in by the Python.h include chain — include it explicitly first.
#if defined(__ANDROID__)
#include <stdint.h>
#endif
#include "Python.h"
#include "datetime.h"
#else
// Normal Apple (Xcode, no PIP_MODE): use bundled PythonHeaders/ from the CPython package.
// Avoids <Python/Python.h> (framework-style) which requires the xcframework to be staged
// to PackageFrameworks first — something Xcode's clang dependency scanner doesn't wait for.
// The xcframework is still listed as a dependency for linking.
#include "../../PythonHeaders/Python.h"
#include "../../PythonHeaders/datetime.h"
#endif

#ifdef __cplusplus
#pragma clang diagnostic pop
extern "C" {
#endif

extern PyObject* __Py_True__;
extern PyObject* __Py_False__;
extern PyObject* __Py_None__;

void initPyDateTime(void);
PyObject* PyDate_Create(int year, int month, int day);
PyObject* PyDateTime_Create(int year, int month, int day, int hour, int min, int sec, int usec);
void PyDateTime_Info(PyObject* o, int* year, int* month, int* day, int* hour, int* min, int* sec, int* usec);



#ifdef __cplusplus
}
#endif

#endif /* CPython_h */
