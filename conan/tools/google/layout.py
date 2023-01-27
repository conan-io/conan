

def bazel_layout(conanfile, generator=None, src_folder="."):
    """The layout for bazel is very limited, it builds in the root folder even specifying
       "bazel --output_base=xxx" in the other hand I don't know how to inject a custom path so
       the build can load the dependencies.bzl from the BazelDeps"""
    conanfile.folders.build = ""
    conanfile.folders.generators = ""
    # used in test package for example, to know where the binaries are (editables not supported yet)
    conanfile.cpp.build.bindirs = ["bazel-bin"]
    conanfile.cpp.build.libdirs = ["bazel-bin"]
