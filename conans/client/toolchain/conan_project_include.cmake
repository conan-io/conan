
# When using a Conan toolchain, this file is included as the last step of all `project()` calls.
# TODO: Add link to CMake docs

message(">>>> CONAN_PROJECT_INCLUDE-CMAKE")
include("${CMAKE_CURRENT_LIST_DIR}/conan_adjustments.cmake")

conan_set_vs_runtime()
