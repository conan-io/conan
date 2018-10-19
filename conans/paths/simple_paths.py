from conans.client.package_layouts import get_package_layout


class SimplePaths(object):
    """
    Generate Conan paths. Handles the conan domain path logic. NO DISK ACCESS, just
    path logic responsability
    """
    def __init__(self, store_folder):
        self._store_folder = store_folder

    @property
    def store(self):
        return self._store_folder

    def package_layout(self, conan_reference, short_paths=False):
        package_layout = get_package_layout(self.store, conan_reference, short_paths=short_paths)
        return package_layout

    def conan(self, conan_reference):
        """ the base folder for this package reference, for each ConanFileReference
        """
        return self.package_layout(conan_reference).conan()

    def export(self, conan_reference):
        return self.package_layout(conan_reference).export()

    def export_sources(self, conan_reference, short_paths=False):
        return self.package_layout(conan_reference, short_paths).export_sources()

    def source(self, conan_reference, short_paths=False):
        return self.package_layout(conan_reference, short_paths).source()

    def conanfile(self, conan_reference):
        return self.package_layout(conan_reference).conanfile()

    def builds(self, conan_reference):
        return self.package_layout(conan_reference).builds()

    def build(self, package_reference, short_paths=False):
        return self.package_layout(package_reference.conan, short_paths).build(package_reference)

    def system_reqs(self, conan_reference):
        return self.package_layout(conan_reference).system_reqs()

    def system_reqs_package(self, package_reference):
        return self.package_layout(package_reference.conan).system_reqs_package(package_reference)

    def packages(self, conan_reference):
        return self.package_layout(conan_reference).packages()

    def package(self, package_reference, short_paths=False):
        return self.package_layout(package_reference.conan, short_paths).package(package_reference)

    def scm_folder(self, conan_reference):
        return self.package_layout(conan_reference).scm_folder()