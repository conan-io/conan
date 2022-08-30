import os

from conans.model.new_build_info import NewCppInfo


class Infos(object):

    def __init__(self):
        self.source = NewCppInfo()
        self.build = NewCppInfo()
        self.package = NewCppInfo(with_defaults=True)


class Folders(object):

    def __init__(self):
        self._base_install = None
        self._base_source = None
        self._base_build = None
        self._base_package = None
        self._base_generators = None
        self._base_imports = None
        self._base_export = None
        self._base_export_sources = None

        self.source = ""
        self.build = ""
        self.package = ""
        self.generators = ""
        self.imports = ""
        # Relative location of the project root, if the conanfile is not in that project root, but
        # in a subfolder: e.g: If the conanfile is in a subfolder then self.root = ".."
        self.root = None
        # The relative location with respect to the project root of the subproject containing the
        # conanfile.py, that makes most of the output folders defined in layouts (cmake_layout, etc)
        # start from the subproject again
        self.subproject = None

    def __repr__(self):
        return str(self.__dict__)

    def set_base_folders(self, conanfile_folder, output_folder):
        """ this methods can be used for defining all the base folders in the
        local flow (conan install, source, build), where only the current conanfile location
        and the potential --output-folder user argument are the folders to take into account
        If the "layout()" method defines a self.folders.root = "xxx" it will be used to compute
        the base folder

        @param conanfile_folder: the location where the current consumer conanfile is
        @param output_folder: Can potentially be None (for export-pkg: TODO), in that case
        the conanfile location is used
        """
        # This must be called only after ``layout()`` has been called
        base_folder = conanfile_folder if self.root is None else \
            os.path.normpath(os.path.join(conanfile_folder, self.root))

        self._base_source = base_folder

        self._base_install = output_folder or base_folder
        self._base_build = output_folder or base_folder
        self._base_generators = output_folder or base_folder
        self._base_imports = output_folder or base_folder

        self._base_export_sources = output_folder or base_folder

    @property
    def source_folder(self):
        if self._base_source is None:
            return None
        if not self.source:
            return self._base_source

        return os.path.join(self._base_source, self.source)

    @property
    def base_source(self):
        return self._base_source

    def set_base_source(self, folder):
        self._base_source = folder

    @property
    def build_folder(self):
        if self._base_build is None:
            return None
        if not self.build:
            return self._base_build
        return os.path.join(self._base_build, self.build)

    @property
    def base_build(self):
        return self._base_build

    def set_base_build(self, folder):
        self._base_build = folder

    @property
    def base_install(self):
        return self._base_install

    def set_base_install(self, folder):
        self._base_install = folder

    @property
    def base_package(self):
        return self._base_package

    def set_base_package(self, folder):
        self._base_package = folder

    @property
    def package_folder(self):
        """For the cache, the package folder is only the base"""
        return self._base_package

    @property
    def generators_folder(self):
        if self._base_generators is None:
            return None
        if not self.generators:
            return self._base_generators
        return os.path.join(self._base_generators, self.generators)

    def set_base_generators(self, folder):
        self._base_generators = folder

    @property
    def imports_folder(self):
        if self._base_imports is None:
            return None
        if not self.imports:
            return self._base_imports

        return os.path.join(self._base_imports, self.imports)

    @property
    def base_imports(self):
        return self._base_imports

    def set_base_imports(self, folder):
        self._base_imports = folder

    @property
    def base_export(self):
        return self._base_export

    def set_base_export(self, folder):
        self._base_export = folder

    @property
    def base_export_sources(self):
        return self._base_export_sources

    def set_base_export_sources(self, folder):
        self._base_export_sources = folder
