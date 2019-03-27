#pragma once

#ifdef WIN32
  #define BYE_EXPORT __declspec(dllexport)
#else
  #define BYE_EXPORT
#endif

BYE_EXPORT void bye();
