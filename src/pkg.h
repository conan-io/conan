#pragma once

#ifdef WIN32
  #define pkg_EXPORT __declspec(dllexport)
#else
  #define pkg_EXPORT
#endif

pkg_EXPORT void pkg();
