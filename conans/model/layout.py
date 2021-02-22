import os


class _LayoutEntry(object):

    def __init__(self):
        self.folder = None


class Layout(object):
    def __init__(self):

        self._base_install_folder = None
        self._base_source_folder = None
        self._base_build_folder = None
        self._base_package_folder = None

        self.source = _LayoutEntry()
        self.build = _LayoutEntry()

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
    def base_source_folder(self):
        return self._base_source_folder

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
    def base_build_folder(self):
        return self._base_build_folder

    @property
    def base_install_folder(self):
        return self._base_install_folder

    def set_base_install_folder(self, folder):
        self._base_install_folder = folder

    def set_base_package_folder(self, folder):
        self._base_package_folder = folder

    @property
    def base_package_folder(self):
        return self._base_package_folder
