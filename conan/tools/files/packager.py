import os

from conans.client.file_copier import FileCopier
from conans.errors import ConanException


class _PatternEntry(object):

    def __init__(self):
        self.include = []
        self.lib = []
        self.bin = []
        self.src = []
        self.build = []
        self.res = []
        self.framework = []


class _Patterns(object):

    def __init__(self):
        self.source = _PatternEntry()
        self.build = _PatternEntry()


class AutoPackager(object):

    def __init__(self, conanfile):
        self._conanfile = conanfile
        self.patterns = _Patterns()

        self.patterns.source.include = ["*.h", "*.hpp", "*.hxx"]
        self.patterns.source.lib = []
        self.patterns.source.bin = []

        self.patterns.build.include = ["*.h", "*.hpp", "*.hxx"]
        self.patterns.build.lib = ["*.so", "*.so.*", "*.a", "*.lib", "*.dylib"]
        self.patterns.build.bin = ["*.exe", "*.dll"]

    def run(self):
        cf = self._conanfile
        # Check that the components declared in source/build are in package
        cnames = set(cf.cpp.source.component_names)
        cnames = cnames.union(set(cf.cpp.build.component_names))
        if cnames.difference(set(cf.cpp.package.component_names)):
            # TODO: Raise? Warning? Ignore?
            raise ConanException("There are components declared in cpp.source.components"
                                 " or in cpp.build.components that are not declared in"
                                 " cpp.package.components")
        if cnames:
            for cname in cnames:
                if cname in cf.cpp.source.components:
                    self._package_cppinfo("source", cf.cpp.source.components[cname],
                                          cf.cpp.package.components[cname])
                if cname in cf.cpp.build.components:
                    self._package_cppinfo("build", cf.cpp.build.components[cname],
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

        patterns_var = getattr(self.patterns, origin_name)
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

