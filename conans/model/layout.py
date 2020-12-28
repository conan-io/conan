import os


class _LayoutEntry(object):

    def __init__(self):
        self.folder = ""
        self.includedirs = []
        self.includepatterns = []

        self.builddirs = []
        self.buildpatterns = []

        self.resdirs = []
        self.respatterns = []

        self.libdirs = []
        self.libpatterns = []

        self.bindirs = []
        self.binpatterns = []


class Layout(object):
    def __init__(self):

        self._base_source_folder = None
        self._base_build_folder = None
        self._base_install_folder = None
        self._base_package_folder = None

        self.install = _LayoutEntry()
        self.install.folder = ""

        self.source = _LayoutEntry()
        self.source.folder = ""
        self.source.includedirs = [""]
        self.source.includepatterns = ["*.h", "*.hpp", "*.hxx"]  # To be packaged

        self.build = _LayoutEntry()
        self.build.folder = ""  # Where the software is built (relative to _base_build_folder)
        self.build.libdirs = [""]
        self.build.libpatterns = ["*.so", "*.so.*", "*.a", "*.lib", "*.dylib"]  # To be packaged
        self.build.bindirs = [""]
        self.build.binpatterns = ["*.exe", "*.dll"]  # To be packaged

        self.package = _LayoutEntry()  # Where the artifacts are installed
        self.package.includedirs = ["include"]
        self.package.includepatterns = ["*"]  # To be deployed
        self.package.bindirs = ["bin"]
        self.package.binpatterns = ["*"]  # To be deployed
        self.package.libdirs = ["lib"]
        self.package.libpatterns = ["*"]  # To be deployed

    def __repr__(self):
        return str(self.__dict__)

    @property
    def source_folder(self):
        if self._base_source_folder is None:
            return None
        if not self.source.folder:
            return self._base_source_folder

        return os.path.join(self._base_source_folder, self.source.folder)

    def set_base_source_folder(self, folder):
        self._base_source_folder = folder

    @property
    def build_folder(self):
        if self._base_build_folder is None:
            return None
        if not self.build.folder:
            return self._base_build_folder
        return os.path.join(self._base_build_folder, self.build.folder)

    def set_base_build_folder(self, folder):
        self._base_build_folder = folder

    @property
    def install_folder(self):
        if self._base_install_folder is None:
            return self.build_folder  # If None, default to build_folder (review)
        if not self.install.folder:
            return self._base_install_folder

        return os.path.join(self._base_install_folder, self.install.folder)

    def set_base_install_folder(self, folder):
        self._base_install_folder = folder

    @property
    def package_folder(self):
        if self._base_package_folder is None:
            return None
        if not self.package.folder:
            return self._base_package_folder

        return os.path.join(self._base_package_folder, self.package.folder)

    def set_base_package_folder(self, folder):
        self._base_package_folder = folder
