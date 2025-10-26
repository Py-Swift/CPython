//
//  shim.c
//  CPython
//
//  Created by CodeBuilder on 19/10/2025.
//
#include "CPython.h"
#include <stdbool.h>

PyObject *__Py_True__ = Py_True;
PyObject *__Py_False__ = Py_False;
PyObject* __Py_None__ = Py_None;

 PyListObject* PyListCast(PyObject* o) {
     return _PyList_CAST(o);
}


bool pydatetime_loaded = false;
void initPyDateTime(void) {
    if (pydatetime_loaded) {
        return;
    }
    PyDateTime_IMPORT;
    pydatetime_loaded = true;
}

PyObject* PyDate_Create(int year, int month, int day) {
    return PyDate_FromDate(year, month, day);
}

PyObject* PyDateTime_Create(int year, int month, int day, int hour, int min, int sec, int usec) {
    //PyDateTime_IMPORT;
    return PyDateTime_FromDateAndTime(year, month, day, hour, min, sec, usec);
}

void PyDateTime_Info(PyObject* o, int* year, int* month, int* day, int* hour, int* min, int* sec, int* usec) {
    PyDateTime_DateTime* dt = (PyDateTime_DateTime*)o;
    *year = PyDateTime_GET_YEAR(dt);
    *month = PyDateTime_GET_MONTH(dt);
    *day = PyDateTime_GET_DAY(dt);
    *hour = PyDateTime_DATE_GET_HOUR(dt);
    *min = PyDateTime_DATE_GET_MINUTE(dt);
    *sec = PyDateTime_DATE_GET_SECOND(dt);
    *usec = PyDateTime_DATE_GET_MICROSECOND(dt);
}
