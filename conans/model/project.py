from collections import OrderedDict
import re
from conans.errors import ConanException
import os


class LocalPackage(object):
    def __init__(self, base_folder):
        self._base_folder = base_folder
        self._conanfile_folder = None  # The folder with the conanfile
        self._source_folder = ""  # By default the conanfile_folder
        self._build_folder = "build_{settings.build_type}_{settings.arch}"
        # package_folder can be None, then it will directly use build_folder
        self._package_folder = "package_{settings.build_type}_{settings.arch}"
        self._includedirs = None  # To override include dirs, mainly for build_folder
        self._libdirs = None  # To override libdirs...

    @property
    def conanfile_path(self):
        return os.path.abspath(os.path.join(self._base_folder, self._conanfile_folder, "conanfile.py"))

    @property
    def package_path(self):
        return os.path.abspath(os.path.join(self._base_folder, self._conanfile_folder, "package"))

    @property
    def build_path(self):
        return os.path.abspath(os.path.join(self._base_folder, self._conanfile_folder, "build"))

    def load_lines(self, lines):
        for line in lines:
            key, value = line.split(":", 1)
            key = key.strip().lower()
            value = value.strip()
            if key == "folder":
                self._conanfile_folder = value
            elif key == "source":
                self._source_folder = value
            elif key == "build":
                self._build_folder = value
            elif key == "package":
                self._package_folder = value
            else:
                raise ConanException("Conan-project: Incorrect key: %s" % key)


class ConanProject(object):
    def __init__(self, base_folder):
        self._base_folder = base_folder
        self._local_packages = OrderedDict()

    def get_conanfile_path(self, reference):
        local = self._local_packages.get(reference.name)
        if not local:
            return None
        return local.conanfile_path

    def get_package_path(self, package_reference):
        local = self._local_packages.get(package_reference.conan.name)
        if not local:
            return None
        return local.package_path

    def get_build_path(self, conan_ref):
        local = self._local_packages.get(conan_ref.name)
        return local.build_path

    def loads(self, text):
        # Some duplication with _loads_cpp_info()
        pattern = re.compile(r"^\[([a-zA-Z0-9._:-]+)\]([^\[]+)", re.MULTILINE)

        try:
            for m in pattern.finditer(text):
                var_name = m.group(1)
                lines = []
                for line in m.group(2).splitlines():
                    line = line.strip()
                    if not line or line[0] == "#":
                        continue
                    lines.append(line)
                if not lines:
                    continue
                local_package = LocalPackage(self._base_folder)
                local_package.load_lines(lines)
                self._local_packages[var_name] = local_package
        except Exception as e:
            raise ConanException("There was an error parsing conan-project: %s" % str(e))
