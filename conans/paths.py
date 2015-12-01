import os
from conans.model.ref import ConanFileReference, PackageReference
from conans.util.files import load, relative_dirs, path_exists
from os.path import isfile
from os.path import join, normpath
from conans.model.manifest import FileTreeManifest


EXPORT_FOLDER = "export"
SRC_FOLDER = "source"
BUILD_FOLDER = "build"
PACKAGES_FOLDER = "package"
SYSTEM_REQS_FOLDER = "system_reqs"

CONANFILE = 'conanfile.py'
CONANFILE_TXT = "conanfile.txt"
CONAN_MANIFEST = "conanmanifest.txt"
BUILD_INFO = 'conanbuildinfo.txt'
BUILD_INFO_GCC = 'conanbuildinfo.gcc'
BUILD_INFO_CMAKE = 'conanbuildinfo.cmake'
BUILD_INFO_VISUAL_STUDIO = 'conanbuildinfo.props'
BUILD_INFO_XCODE = 'conanbuildinfo.xcconfig'
CONANINFO = "conaninfo.txt"
SYSTEM_REQS = "system_reqs.txt"

PACKAGE_TGZ_NAME = "conan_package.tgz"


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

    def conan(self, conan_reference):
        """ the base conans folder, for each ConanFileReference
        """
        assert isinstance(conan_reference, ConanFileReference)
        return normpath(join(self._store_folder, "/".join(conan_reference)))

    def export(self, conan_reference):
        assert isinstance(conan_reference, ConanFileReference)
        return normpath(join(self.conan(conan_reference), EXPORT_FOLDER))

    def source(self, conan_reference):
        assert isinstance(conan_reference, ConanFileReference)
        return normpath(join(self.conan(conan_reference), SRC_FOLDER))

    def conanfile(self, conan_reference):
        assert isinstance(conan_reference, ConanFileReference)
        return normpath(join(self.conan(conan_reference), EXPORT_FOLDER, CONANFILE))

    def digestfile_conanfile(self, conan_reference):
        assert isinstance(conan_reference, ConanFileReference)
        return normpath(join(self.conan(conan_reference), EXPORT_FOLDER, CONAN_MANIFEST))

    def digestfile_package(self, package_reference):
        assert isinstance(package_reference, PackageReference)
        return normpath(join(self.package(package_reference), CONAN_MANIFEST))

    def builds(self, conan_reference):
        assert isinstance(conan_reference, ConanFileReference)
        return normpath(join(self.conan(conan_reference), BUILD_FOLDER))

    def build(self, package_reference):
        assert isinstance(package_reference, PackageReference)
        return normpath(join(self.conan(package_reference.conan), BUILD_FOLDER,
                             package_reference.package_id))

    def system_reqs(self, conan_reference):
        assert isinstance(conan_reference, ConanFileReference)
        return normpath(join(self.conan(conan_reference), SYSTEM_REQS_FOLDER, SYSTEM_REQS))

    def system_reqs_package(self, package_reference):
        assert isinstance(package_reference, PackageReference)
        return normpath(join(self.conan(package_reference.conan), SYSTEM_REQS_FOLDER,
                             package_reference.package_id, SYSTEM_REQS))

    def packages(self, conan_reference):
        assert isinstance(conan_reference, ConanFileReference)
        return normpath(join(self.conan(conan_reference), PACKAGES_FOLDER))

    def package(self, package_reference):
        assert isinstance(package_reference, PackageReference)
        return normpath(join(self.conan(package_reference.conan), PACKAGES_FOLDER,
                             package_reference.package_id))


# FIXME: Move to client, Should not be necessary in server anymore. Replaced with disk_adapter
class StorePaths(SimplePaths):
    """ Disk storage of conans and binary packages. Useful both in client and
    in server. Accesses to real disk and reads/write things.
    """

    def __init__(self, store_folder):
        super(StorePaths, self).__init__(store_folder)

    def export_paths(self, conan_reference):
        ''' Returns all file paths for a conans (relative to conans directory)'''
        return relative_dirs(self.export(conan_reference))

    def package_paths(self, package_reference):
        ''' Returns all file paths for a package (relative to conans directory)'''
        return relative_dirs(self.package(package_reference))

    def conan_packages(self, conan_reference):
        """ Returns a list of package_id from a conans """
        assert isinstance(conan_reference, ConanFileReference)
        packages_dir = self.packages(conan_reference)
        try:
            packages = [dirname for dirname in os.listdir(packages_dir)
                        if not isfile(os.path.join(packages_dir, dirname))]
        except:  # if there isn't any package folder
            packages = []
        return packages

    def conan_builds(self, conan_reference):
        """ Returns a list of build_id from a conans """
        assert isinstance(conan_reference, ConanFileReference)
        builds_dir = self.builds(conan_reference)
        try:
            builds = [dirname for dirname in os.listdir(builds_dir)
                      if not isfile(os.path.join(builds_dir, dirname))]
        except:  # if there isn't any build folder
            builds = []
        return builds

    def load_digest(self, conan_reference):
        '''conan_id = sha(zip file)'''
        filename = os.path.join(self.export(conan_reference), CONAN_MANIFEST)
        return FileTreeManifest.loads(load(filename))

    def valid_conan_digest(self, conan_reference):
        digest_path = self.digestfile_conanfile(conan_reference)
        if not path_exists(digest_path, self.store):
            return False
        return self.valid_digest(digest_path)

    def valid_package_digest(self, package_reference):
        digest_path = self.digestfile_package(package_reference)
        return self.valid_digest(digest_path)

    def valid_digest(self, digest_path):
        if not os.path.exists(digest_path):
            return False
        expected_digest = FileTreeManifest.create(os.path.dirname(digest_path))
        del expected_digest.file_sums[CONAN_MANIFEST]  # Exclude the MANIFEST itself
        expected_digest.file_sums.pop(CONANFILE + "c", None)  # Exclude the CONANFILE.pyc
        expected_digest.file_sums.pop(".DS_Store", None)  # Exclude tmp in mac
        readed_digest = FileTreeManifest.loads(load(digest_path))
        return readed_digest.file_sums == expected_digest.file_sums
