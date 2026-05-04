//
//  shim.h
//  CPython
//

#ifdef __cplusplus
extern "C" {
#endif

#ifndef CPython_h
#define CPython_h

// Platform-specific Python header inclusion
// Note: Android PIP_MODE defines PIP_MODE via cSettings, so it falls through to
// the CPATH branch below (same as macOS PIP_MODE).
#if defined(__ANDROID__) && !defined(PIP_MODE)
#include "../../PythonHeaders-android/Python.h"
#include "../../PythonHeaders-android/datetime.h"
#elif __has_include(<Python/Python.h>)
// Normal Apple: xcframework headers available via binary target
#include <Python/Python.h>
#include <Python/datetime.h>
#else
// PIP_MODE: Python.h located via CPATH env var (-Xcc -I in setup.py / cibuildwheel)
// On Android, bionic's pthread_types.h uses uint32_t/int32_t before stdint.h has
// been pulled in by the Python.h include chain — include it explicitly first.
#if defined(__ANDROID__)
#include <stdint.h>
#endif
#include "Python.h"
#include "datetime.h"
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
