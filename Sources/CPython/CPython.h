//
//  shim.h
//  CPython
//

#ifdef __cplusplus
extern "C" {
#endif

#ifndef CPython_h
#define CPython_h

// Platform-specific Python header inclusion.
// PIP_MODE is set as a cSetting define by CPython's Package.swift in all pip/cibuildwheel
// build modes (macOS PIP_MODE, Android new-style PIP_MODE). It is NOT set in Xcode / xcframework mode.
#if defined(__ANDROID__) && !defined(PIP_MODE)
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
// Normal Apple (Xcode, no PIP_MODE): use embedded Python.xcframework.
// SPM binary target adds -F path/to/Frameworks so <Python/Python.h> resolves.
#include <Python/Python.h>
#include <Python/datetime.h>
#endif

extern PyObject* __Py_True__;
extern PyObject* __Py_False__;
extern PyObject* __Py_None__;

void initPyDateTime(void);
PyObject* PyDate_Create(int year, int month, int day);
PyObject* PyDateTime_Create(int year, int month, int day, int hour, int min, int sec, int usec);
void PyDateTime_Info(PyObject* o, int* year, int* month, int* day, int* hour, int* min, int* sec, int* usec);



#endif /* CPython_h */

#ifdef __cplusplus
}
#endif
