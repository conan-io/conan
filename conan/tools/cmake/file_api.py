import json
import fnmatch
import os

from conan.tools.files import CppPackage
from conans.util.files import save, load


class CMakeFileAPI(object):
    """
    implements https://cmake.org/cmake/help/latest/manual/cmake-file-api.7.html
    """
    CODEMODELV2 = "codemodel-v2"
    SKIP_TARGETS = ["ZERO_CHECK", "ALL_BUILD"]
    # https://cmake.org/cmake/help/v3.21/prop_tgt/TYPE.html
    SUPPORTED_TARGET_TYPES = ['STATIC_LIBRARY', 'SHARED_LIBRARY', 'MODULE_LIBRARY']

    def __init__(self, conanfile):
        self._conanfile = conanfile

    @property
    def api_dir(self):
        """
        :return: api directory <build>/.cmake/api/v1/
        """
        return os.path.join(self._conanfile.build_folder, ".cmake", "api", "v1")

    @property
    def query_dir(self):
        """
        :return: api query sub-directory <build>/.cmake/api/v1/query
        """
        return os.path.join(self.api_dir, "query")

    @property
    def reply_dir(self):
        """
        :return: api reply sub-directory <build>/.cmake/api/v1/reply
        """
        return os.path.join(self.api_dir, "reply")

    def query(self, query):
        """
        prepare the CMake File API query (the actual query will be done during the configure step)
        :param query: type of the CMake File API query (e.g. CODEMODELV2)
        :return: new query object
        """
        if query == self.CODEMODELV2:
            # implements codemodel-v2 query
            # https://cmake.org/cmake/help/latest/manual/cmake-file-api.7.html#codemodel-version-2
            os.makedirs(self.query_dir)
            save(os.path.join(self.query_dir, "codemodel-v2"), "")
            return
        raise NotImplementedError()

    def reply(self, reply):
        """
        obtain the CMake File API reply (which should have been made during the configure step)
        :param reply: type of the CMake File API reply (e.g. CODEMODELV2)
        :return: new reply object
        """
        if reply == self.CODEMODELV2:
            return self.CodeModelReplyV2(self)
        raise NotImplementedError()

    @property
    def build_type(self):
        """
        :return: active build type (configuration)
        """
        return self._conanfile.settings.get_safe("build_type")

    class CodeModelReplyV2(object):
        """
        implements codemodel-v2 reply
        https://cmake.org/cmake/help/latest/manual/cmake-file-api.7.html#codemodel-version-2
        """
        def __init__(self, api):

            def loadjs(filename):
                return json.loads(load(filename))

            codemodels = os.listdir(api.reply_dir)
            codemodels = [c for c in codemodels if fnmatch.fnmatch(c, "codemodel-v2-*.json")]
            assert len(codemodels) == 1
            self._codemodel = loadjs(os.path.join(api.reply_dir, codemodels[0]))

            self._configurations = dict()
            for configuration in self._codemodel['configurations']:
                if configuration["name"] != api.build_type:
                    continue

                self._components = dict()
                for target in configuration["targets"]:
                    if target['name'] in CMakeFileAPI.SKIP_TARGETS:
                        continue
                    self._components[target["name"]] = \
                        loadjs(os.path.join(api.reply_dir, target['jsonFile']))

        @classmethod
        def _name_on_disk2lib(cls, name_on_disk):
            """
            convert raw library file name into conan-friendly one
            :param name_on_disk: raw library file name read from target.json
            :return: conan-friendly library name, without suffix and prefix
            """
            if name_on_disk.endswith('.lib'):
                return name_on_disk[:-4]
            elif name_on_disk.endswith('.dll'):
                return name_on_disk[:-4]
            elif name_on_disk.startswith('lib') and name_on_disk.endswith('.a'):
                return name_on_disk[3:-2]
            else:
                # FIXME: This fails to parse executables
                raise Exception("don't know how to convert %s" % name_on_disk)

        @classmethod
        def _parse_dep_name(cls, name):
            """
            :param name: extract dependency name from the id like 'decoder::@5310dfab9e417c587352'
            :return: dependency name (part before ::@ token)
            """
            return name.split("::@")[0]

        def to_conan_package(self):
            """
            converts codemodel-v2 into conan_package.json object
            :return: ConanPackage instance
            """

            conan_package = CppPackage()

            for name, target in self._components.items():
                if target['type'] not in CMakeFileAPI.SUPPORTED_TARGET_TYPES:
                    continue
                component = conan_package.add_component(name)
                # TODO: CMakeDeps has nothing to do here
                component.names["CMakeDeps"] = name
                component.libs = [self._name_on_disk2lib(target['nameOnDisk'])]
                deps = target["dependencies"] if 'dependencies' in target else []
                deps = [self._parse_dep_name(d['id']) for d in deps]
                component.requires = [d for d in deps if d not in CMakeFileAPI.SKIP_TARGETS]

            return conan_package
