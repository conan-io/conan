@echo off
if defined C_INCLUDE_PATH (SET "C_INCLUDE_PATH=%C_INCLUDE_PATH%;path/to/includes/lib1;path/to/includes/lib2") else (SET "C_INCLUDE_PATH=path/to/includes/lib1;path/to/includes/lib2")
if defined CPLUS_INCLUDE_PATH (SET "CPLUS_INCLUDE_PATH=%CPLUS_INCLUDE_PATH%;path/to/includes/lib1;path/to/includes/lib2") else (SET "CPLUS_INCLUDE_PATH=path/to/includes/lib1;path/to/includes/lib2")
SET "LIBRARY_PATH=path/to/lib1;path/to/lib2"
if defined LIBRARY_PATH (SET "LIBRARY_PATH=%LIBRARY_PATH%;path/to/lib1;path/to/lib2") else (SET "LIBRARY_PATH=path/to/lib1;path/to/lib2")