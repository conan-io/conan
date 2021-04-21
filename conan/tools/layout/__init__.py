import os

from conans.client.file_copier import FileCopier
from conans.errors import ConanException


# FIXME: Not documented, just a POC, missing a way to do something similar without modifying
#        the recipe

def clion_layout(conanfile):
    if not conanfile.settings.get_safe("build_type"):
        raise ConanException("The 'clion_layout' requires the 'build_type' setting")
    base = "cmake-build-{}".format(str(conanfile.settings.build_type).lower())
    conanfile.folders.build.folder = base
    conanfile.build_cpp_info.libdirs = ["."]

    conanfile.folders.generators.folder = os.path.join(base, "generators")

    conanfile.folders.source.folder = "."
    conanfile.source_cpp_info.includedirs = ["include"]


# FIXME: Not sure about the location, interface, name etc.
#        Do we want a public explicit FileCopier maybe? Review and suggest!
class LayoutPackager(object):

    def __init__(self, conanfile):
        self._conanfile = conanfile

    def package(self):
        cf = self._conanfile
        # FIXME: To be replaced with something like a LayoutPackager to be called explicitly

        # Check that the components declared in source/build are in package
        cnames = set(cf.source_cpp_info.component_names)
        cnames = cnames.union(set(cf.build_cpp_info.component_names))
        if cnames.difference(set(cf.package_cpp_info.component_names)):
            # TODO: Raise? Warning? Ignore?
            raise ConanException("There are components declared in source_cpp_info.components"
                                 " or in build_cpp_info.components that are not declared in"
                                 " package_cpp_info.components")

        for root, folder, cpp_info in ((cf.source_folder, cf.folders.source, cf.source_cpp_info),
                                       (cf.build_folder, cf.folders.build, cf.build_cpp_info)):
            if cnames:
                for cname in cnames:
                    if cname in cpp_info.components:
                        self._package_cppinfo(root, folder, cpp_info.components[cname],
                                              cf.package_cpp_info.components[cname])
            else:  # No components declared
                self._package_cppinfo(root, folder, cpp_info, cf.package_cpp_info)

    def _package_cppinfo(self, origin_root_folder,
                         origin, origin_cppinfo, dest_cppinfo):
        """
        @param origin: one from [self.source, self.build] (_LayoutEntry)
        @param origin_cppinfo: cpp_info object of an origin (can be a component cppinfo too)
        @param dest_cppinfo: cpp_info object of the package or a component from package
        """
        for var in ["include", "lib", "bin", "framework", "src", "build", "res"]:
            var_name = "{}dirs".format(var)
            origin_patterns_var = "{}_patterns".format(var)
            origin_paths = getattr(origin_cppinfo, var_name)
            patterns = getattr(origin, origin_patterns_var)
            destinations = getattr(dest_cppinfo, var_name)
            if not destinations:  # For example: Not declared "includedirs" in package.cpp_info
                continue
            if len(destinations) > 1:
                # Check if there is only one possible destination at package, otherwise the
                # copy would need to be done manually
                label = var_name.replace("_paths", "dirs")
                err_msg = "The package has more than 1 cpp_info.{}, cannot package automatically"
                raise ConanException(err_msg.format(label))

            for src in origin_paths:
                src_path = os.path.join(origin_root_folder, src)
                copier = FileCopier([src_path], self._conanfile.folders.base_package)
                for pattern in patterns:
                    copier(pattern, dst=destinations[0])
