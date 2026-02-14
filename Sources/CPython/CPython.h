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
#if defined(__ANDROID__)
#include "../../PythonHeaders-android/Python.h"
#include "../../PythonHeaders-android/datetime.h"
#else
// Apple platforms use xcframework headers via binary target
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
