import os


def bazel_layout(conanfile, src_folder=".", build_folder="."):
    """Bazel layout is so limited. It does not allow to create its special symlinks in other
    folder. See more information in https://bazel.build/remote/output-directories"""
    subproject = conanfile.folders.subproject
    conanfile.folders.source = src_folder if not subproject else os.path.join(subproject, src_folder)
    # Bazel always build the whole project in the root folder, but consumer can put another one
    conanfile.folders.build = build_folder
    conanfile.output.warning("In bazel_layout() call, generators folder changes its default value "
                             "from './' to './conan/' in Conan 2.x")
    conanfile.folders.generators = os.path.join(conanfile.folders.build, ".")
    conanfile.cpp.build.bindirs = [os.path.join(conanfile.folders.build, "bazel-bin")]
    conanfile.cpp.build.libdirs = [os.path.join(conanfile.folders.build, "bazel-bin")]
