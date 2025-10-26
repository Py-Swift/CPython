//
//  shim.h
//  CPython
//

#ifdef __cplusplus
extern "C" {
#endif

#ifndef CPython_h
#define CPython_h



#include <Python/Python.h>
#include <Python/datetime.h>

PyObject* __Py_True__;
PyObject* __Py_False__;
PyObject* __Py_None__;

void initPyDateTime(void);
PyObject* PyDate_Create(int year, int month, int day);
PyObject* PyDateTime_Create(int year, int month, int day, int hour, int min, int sec, int usec);
void PyDateTime_Info(PyObject* o, int* year, int* month, int* day, int* hour, int* min, int* sec, int* usec);



#endif /* CPython_h */

#ifdef __cplusplus
}
#endif
