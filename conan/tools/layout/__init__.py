import os


def basic_layout(conanfile, src_folder="."):
    subproject = conanfile.folders.subproject

    conanfile.folders.source = src_folder if not subproject else os.path.join(subproject, src_folder)
    conanfile.folders.build = "build" if not subproject else os.path.join(subproject, "build")
    if conanfile.settings.get_safe("build_type"):
        conanfile.folders.build += "-{}".format(str(conanfile.settings.build_type).lower())
    conanfile.folders.generators = os.path.join(conanfile.folders.build, "conan")
    conanfile.cpp.build.bindirs = ["."]
    conanfile.cpp.build.libdirs = ["."]
