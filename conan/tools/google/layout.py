import os


def bazel_layout(conanfile, src_folder="."):
    """Bazel layout is so limited. It does not allow to create its special symlinks in other
    folder. See more information in https://bazel.build/remote/output-directories"""
    subproject = conanfile.folders.subproject
    conanfile.folders.source = src_folder if not subproject else os.path.join(subproject, src_folder)
    conanfile.folders.build = "."  # Bazel always build the whole project in the root folder
    # FIXME: Keeping backward-compatibility. Defaulting to "conan" in Conan 2.x.
    conanfile.folders.generators = conanfile.conf.get("tools.google.bazel_layout:generators_folder",
                                                      default=".", check_type=str)
    # FIXME: used in test package for example, to know where the binaries are (editables not supported yet)?
    conanfile.cpp.build.bindirs = [os.path.join(conanfile.folders.build, "bazel-bin")]
    conanfile.cpp.build.libdirs = [os.path.join(conanfile.folders.build, "bazel-bin")]
