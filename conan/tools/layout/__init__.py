import os

from conan.tools.microsoft.msbuild import msbuild_arch
from conans.client.file_copier import FileCopier
from conans.errors import ConanException


def cmake_layout(conanfile, generator=None):
    gen = conanfile.conf["tools.cmake.cmaketoolchain:generator"] or generator
    if gen:
        multi = "Visual" in gen or "Xcode" in gen or "Multi-Config" in gen
    elif conanfile.settings.compiler == "Visual Studio" or conanfile.settings.compiler == "msvc":
        multi = True
    else:
        multi = False

    conanfile.folders.source = "."
    if multi:
        conanfile.folders.build = "build"
        conanfile.folders.generators = "build/conan"
    else:
        build_type = str(conanfile.settings.build_type).lower()
        conanfile.folders.build = "cmake-build-{}".format(build_type)
        conanfile.folders.generators = os.path.join(conanfile.folders.build, "conan")

    conanfile.cpp.source.includedirs = ["src"]
    if multi:
        conanfile.cpp.build.libdirs = ["{}".format(conanfile.settings.build_type)]
        conanfile.cpp.build.bindirs = ["{}".format(conanfile.settings.build_type)]
    else:
        conanfile.cpp.build.libdirs = ["."]
        conanfile.cpp.build.bindirs = ["."]


def clion_layout(conanfile):
    if not conanfile.settings.get_safe("build_type"):
        raise ConanException("The 'clion_layout' requires the 'build_type' setting")
    base = "cmake-build-{}".format(str(conanfile.settings.build_type).lower())
    conanfile.folders.build = base
    conanfile.cpp.build.libdirs = ["."]
    conanfile.folders.generators = os.path.join(base, "generators")
    conanfile.folders.source = "."
    conanfile.cpp.source.includedirs = ["."]


def vs_layout(conanfile):
    if not conanfile.settings.get_safe("build_type"):
        raise ConanException("The 'vs_layout' requires the 'build_type' setting")
    if not conanfile.settings.get_safe("arch"):
        raise ConanException("The 'vs_layout' requires the 'arch' setting")

    if conanfile.settings.arch != "x86":
        arch = msbuild_arch(conanfile.settings.arch)
        if not arch:
            raise ConanException("The 'vs_layout' doesn't "
                                 "work with the arch '{}'".format(conanfile.settings.arch))
        base = "{}/{}".format(arch, str(conanfile.settings.build_type))
    else:
        base = str(conanfile.settings.build_type)

    conanfile.folders.build = base
    conanfile.cpp.build.libdirs = ["."]
    conanfile.folders.generators = os.path.join(base, "generators")
    conanfile.folders.source = "."
    conanfile.cpp.source.includedirs = ["."]


class LayoutPackager(object):

    def __init__(self, conanfile):
        self._conanfile = conanfile

    def package(self):
        cf = self._conanfile

        # Check that the components declared in source/build are in package
        cnames = set(cf.cpp.source.component_names)
        cnames = cnames.union(set(cf.cpp.build.component_names))
        if cnames.difference(set(cf.cpp.package.component_names)):
            # TODO: Raise? Warning? Ignore?
            raise ConanException("There are components declared in source_cpp_info.components"
                                 " or in build_cpp_info.components that are not declared in"
                                 " package_cpp_info.components")

        if cnames:
            for cname in cnames:
                if cname in cf.cpp.source.components:
                    self._package_cppinfo("source", cf.cpp.source.components[cname],
                                                    cf.cpp.package.components[cname])
                if cname in cf.cpp.build.components:
                    self._package_cppinfo("build",  cf.cpp.build.components[cname],
                                                    cf.cpp.package.components[cname])
        else:  # No components declared
            self._package_cppinfo("source", cf.cpp.source, cf.cpp.package)
            self._package_cppinfo("build", cf.cpp.build, cf.cpp.package)

    def _package_cppinfo(self, origin_name, origin_cppinfo, dest_cppinfo):
        """
        @param origin_name: one from ["source", "build"]
        @param origin_cppinfo: cpp_info object of an origin (can be a component cppinfo too)
        @param dest_cppinfo: cpp_info object of the package or a component from package
        """
        patterns_var = getattr(self._conanfile.patterns, origin_name)
        base_folder = getattr(self._conanfile, "{}_folder".format(origin_name))
        for var in ["include", "lib", "bin", "framework", "src", "build", "res"]:
            dirs_var_name = "{}dirs".format(var)
            origin_paths = getattr(origin_cppinfo, dirs_var_name)
            if not origin_paths:
                continue
            patterns = getattr(patterns_var, var)
            destinations = getattr(dest_cppinfo, dirs_var_name)
            if not destinations:  # For example: Not declared "includedirs" in package.cpp_info
                continue
            if len(destinations) > 1:
                # Check if there is only one possible destination at package, otherwise the
                # copy would need to be done manually
                err_msg = "The package has more than 1 cpp_info.{}, cannot package automatically"
                raise ConanException(err_msg.format(dirs_var_name))

            for d in origin_paths:
                copier = FileCopier([os.path.join(base_folder, d)],
                                    self._conanfile.folders.base_package)
                for pattern in patterns:
                    copier(pattern, dst=destinations[0])
