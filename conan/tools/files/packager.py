import os

from conans.client.file_copier import FileCopier
from conans.errors import ConanException


class _AutoPackagerPatternEntry(object):

    def __init__(self):
        self.include = ["*.h", "*.hpp", "*.hxx"]
        self.lib = ["*.so", "*.so.*", "*.a", "*.lib", "*.dylib"]
        self.bin = ["*.exe", "*.dll"]
        self.src = []
        self.build = []
        self.res = []
        self.framework = []


class AutoPackager(object):

    def __init__(self, conanfile):
        self._conanfile = conanfile
        self.patterns = _AutoPackagerPatternEntry()

    def run(self):
        cf = self._conanfile

        # Check that the components declared in  local are in package
        cnames = set(cf.cpp.local.component_names)
        if cnames.difference(set(cf.cpp.package.component_names)):
            # TODO: Raise? Warning? Ignore?
            raise ConanException("There are components declared in cpp.local.components"
                                 " that are not declared in cpp.package.components")

        if cnames:
            for cname in cnames:
                if cname in cf.cpp.local.components:
                    self._package_cppinfo(cf.cpp.local.components[cname],
                                          cf.cpp.package.components[cname])

        else:  # No components declared
            self._package_cppinfo(cf.cpp.local, cf.cpp.package)

    def _package_cppinfo(self, origin_cppinfo, dest_cppinfo):
        """
        @param origin_name: one from ["source", "build"]
        @param origin_cppinfo: cpp_info object of an origin (can be a component cppinfo too)
        @param dest_cppinfo: cpp_info object of the package or a component from package
        """
        for var in ["include", "lib", "bin", "framework", "src", "build", "res"]:
            dirs_var_name = "{}dirs".format(var)
            origin_paths = getattr(origin_cppinfo, dirs_var_name)
            if not origin_paths:
                continue
            patterns = getattr(self.patterns, var)
            destinations = getattr(dest_cppinfo, dirs_var_name)
            if not destinations:  # For example: Not declared "includedirs" in package.cpp_info
                continue
            if len(destinations) > 1:
                # Check if there is only one possible destination at package, otherwise the
                # copy would need to be done manually
                err_msg = "The package has more than 1 cpp_info.{}, cannot package automatically"
                raise ConanException(err_msg.format(dirs_var_name))

            # We cannot know if the declared folder lives in source or build... so we copy everything
            paths = [os.path.join(self._conanfile.folders.base_source, f) for f in origin_paths]
            if self._conanfile.folders.base_build != self._conanfile.folders.base_source:
                paths.extend([os.path.join(self._conanfile.folders.base_build, f)
                              for f in origin_paths])

            copier = FileCopier(paths, self._conanfile.folders.base_package)
            for pattern in patterns:
                copier(pattern, dst=destinations[0])
