import os

from conans.client.file_copier import FileCopier
from conans.errors import ConanException
from conans.model.build_info import CppInfo, CppInfoDefaultValues
from conans.util.log import logger


class _LayoutEntry(object):

    def __init__(self, default_cpp_info_values=None):
        self.cpp_info = CppInfo(None, None, default_values=default_cpp_info_values)

        self.include_patterns = []
        self.lib_patterns = []
        self.bin_patterns = []
        self.src_patterns = []
        self.build_patterns = []
        self.res_patterns = []
        self.framework_patterns = []
        self.folder = ""


class Layout(object):
    def __init__(self):

        self._base_install_folder = None
        self._base_source_folder = None
        self._base_build_folder = None
        self._base_package_folder = None
        self._base_generators_folder = None

        # By default, the cpp_info of the components are empty.
        # Otherwise it become very difficult and confusing to override the default layout, for
        # example, to clion, because every component created have the defaults again.
        source_defaults = CppInfoDefaultValues()
        self.source = _LayoutEntry(source_defaults)
        self.source.cpp_info.includedirs = ["include"]
        self.source.include_patterns = ["*.h", "*.hpp", "*.hxx"]

        build_defaults = CppInfoDefaultValues()
        self.build = _LayoutEntry(build_defaults)
        self.build.cpp_info.builddirs = ["."]
        self.build.lib_patterns = ["*.so", "*.so.*", "*.a", "*.lib", "*.dylib"]
        self.build.bin_patterns = ["*.exe", "*.dll"]

        self.package = _LayoutEntry()

        generators_defaults = CppInfoDefaultValues()
        self.generators = _LayoutEntry(generators_defaults)

    def __repr__(self):
        return str(self.__dict__)

    def package_files(self):
        # Map of origin paths and the patterns

        matching_vars = ["include", "lib", "bin", "framework", "src", "build", "res"]

        # Check that the components declared in source/build are in package
        def comp_names(el):
            return set(el.cpp_info.components.keys())
        component_names = comp_names(self.source).union(comp_names(self.build))
        if component_names.difference(comp_names(self.package)):
            # TODO: Raise? Warning? Ignore?
            raise ConanException("There are components declared in layout.source.cpp_info.components"
                                 " or in layout.build.cpp_info.components that are not declared in"
                                 " layout.package.cpp_info.components")

        for var in matching_vars:
            for origin in (self.source, self.build):
                if component_names:
                    for cname in component_names:
                        if cname in origin.cpp_info.components:
                            self._package_cppinfo(var, origin,
                                                  origin.cpp_info.components[cname],
                                                  self.package.cpp_info.components[cname])
                else:  # No components declared
                    self._package_cppinfo(var, origin, origin.cpp_info, self.package.cpp_info)

    def _package_cppinfo(self, name, origin, origin_cppinfo, package_cppinfo):
        """
        @param name: one from ["include", "lib", "bin", "framework", "src", "build", "res"]
        @param origin: one from [self.source, self.build] (_LayoutEntry)
        @param origin_cppinfo: cpp_info object of an origin (can be a component cppinfo too)
        @param package_cppinfo: cpp_info object of the package or a component from package
        """
        var_name = "{}_paths".format(name)
        origin_patterns_var = "{}_patterns".format(name)
        origin_paths = getattr(origin_cppinfo, var_name)
        patterns = getattr(origin, origin_patterns_var)
        destinations = getattr(package_cppinfo, var_name)
        if not destinations:  # For example: Not declared "includedirs" in package.cpp_info
            logger.debug("No '{}' in package, skipping copy".format(var_name))
            return
        if len(destinations) > 1:
            # Check if there is only one possible destination at package, otherwise the
            # copy would need to be done manually
            label = var_name.replace("_paths", "dirs")
            err_msg = "The package has more than 1 cpp_info.{}, cannot package automatically"
            raise ConanException(err_msg.format(label))

        for src in origin_paths:
            logger.debug("Copying '{}': "
                         "From '{}' patterns '{}'".format(var_name, src, patterns))
            copier = FileCopier([src], self._base_package_folder)
            for pattern in patterns:
                copier(pattern, dst=destinations[0])


    @property
    def source_folder(self):
        if self._base_source_folder is None:
            return None
        if not self.source.folder:
            return self._base_source_folder

        return os.path.join(self._base_source_folder, self.source.folder)

    @property
    def base_source_folder(self):
        return self._base_source_folder

    def set_base_source_folder(self, folder):
        self._base_source_folder = folder
        self.source.cpp_info.rootpath = self.source_folder

    @property
    def build_folder(self):
        if self._base_build_folder is None:
            return None
        if not self.build.folder:
            return self._base_build_folder
        return os.path.join(self._base_build_folder, self.build.folder)

    @property
    def base_build_folder(self):
        return self._base_build_folder

    def set_base_build_folder(self, folder):
        self._base_build_folder = folder
        self.build.cpp_info.rootpath = self.build_folder

    @property
    def base_install_folder(self):
        return self._base_install_folder

    def set_base_install_folder(self, folder):
        self._base_install_folder = folder

    @property
    def base_package_folder(self):
        return self._base_package_folder

    def set_base_package_folder(self, folder):
        self._base_package_folder = folder
        self.package.cpp_info.rootpath = folder

    @property
    def generators_folder(self):
        if not self.generators.folder:
            return self.base_install_folder
        return os.path.join(self._base_generators_folder, self.generators.folder)

    def set_base_generators_folder(self, folder):
        self._base_generators_folder = folder
