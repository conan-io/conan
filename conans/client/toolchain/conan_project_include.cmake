
# When using a Conan toolchain, this file is included as the last step of all `project()` calls.
#  https://cmake.org/cmake/help/latest/variable/CMAKE_PROJECT_INCLUDE.html

include("${CMAKE_CURRENT_LIST_DIR}/conan_adjustments.cmake")

conan_set_vs_runtime()
