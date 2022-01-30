def meson_layout(conanfile):
    conanfile.folders.build = "build-{}".format(str(conanfile.settings.build_type).lower())
    conanfile.cpp.build.bindirs = ["."]
    conanfile.cpp.build.libdirs = ["."]
