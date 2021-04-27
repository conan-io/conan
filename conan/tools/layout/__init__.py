import os

from conans.client.file_copier import FileCopier
from conans.errors import ConanException


# FIXME: Not documented, just a POC, missing a way to do something similar without modifying
#        the recipe

def clion_layout(conanfile):
    if not conanfile.settings.get_safe("build_type"):
        raise ConanException("The 'clion_layout' requires the 'build_type' setting")
    base = "cmake-build-{}".format(str(conanfile.settings.build_type).lower())
    conanfile.folders.build = base
    conanfile.infos.build.libdirs = ["."]

    conanfile.folders.generators = os.path.join(base, "generators")

    conanfile.folders.source = "."
    conanfile.infos.source.includedirs = ["include"]


# FIXME: Not sure about the location, interface, name etc.
#        Do we want a public explicit FileCopier maybe? Review and suggest!
class LayoutPackager(object):

    def __init__(self, conanfile):
        self._conanfile = conanfile

    def package(self):
        cf = self._conanfile

        # Check that the components declared in source/build are in package
        cnames = set(cf.infos.source.component_names)
        cnames = cnames.union(set(cf.infos.build.component_names))
        if cnames.difference(set(cf.infos.package.component_names)):
            # TODO: Raise? Warning? Ignore?
            raise ConanException("There are components declared in source_cpp_info.components"
                                 " or in build_cpp_info.components that are not declared in"
                                 " package_cpp_info.components")


        if cnames:
            for cname in cnames:
                if cname in cf.infos.source.components:
                    self._package_cppinfo("source", cf.infos.source.components[cname],
                                                    cf.infos.package.components[cname])
                if cname in cf.infos.build.components:
                    self._package_cppinfo("build",  cf.infos.build.components[cname],
                                                    cf.infos.package.components[cname])
        else:  # No components declared
            self._package_cppinfo("source", cf.infos.source, cf.infos.package)
            self._package_cppinfo("build", cf.infos.build, cf.infos.package)

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
