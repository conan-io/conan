import os

from conans.client.build.cppstd_flags import cppstd_default
from conans.client.tools.win import MSVS_DEFAULT_TOOLSETS_INVERSE
from conans.errors import ConanException
from conans.model.env_info import EnvValues
from conans.model.options import OptionsValues
from conans.model.ref import PackageReference
from conans.model.values import Values
from conans.paths import CONANINFO
from conans.util.config_parser import ConfigParser
from conans.util.files import load
from conans.util.sha import sha1


class RequirementInfo(object):
    def __init__(self, pref, default_package_id_mode, indirect=False):
        self.package = pref
        self.full_name = pref.ref.name
        self.full_version = pref.ref.version
        self.full_user = pref.ref.user
        self.full_channel = pref.ref.channel
        self.full_package_id = pref.id
        self._indirect = indirect

        try:
            getattr(self, default_package_id_mode)()
        except AttributeError:
            raise ConanException("'%s' is not a known package_id_mode" % default_package_id_mode)

    def copy(self):
        # Useful for build_id()
        result = RequirementInfo(self.package, "unrelated_mode")
        for f in ("name", "version", "user", "channel", "package_id"):
            setattr(result, f, getattr(self, f))
            f = "full_%s" % f
            setattr(result, f, getattr(self, f))
        return result

    def dumps(self):
        if not self.name:
            return ""
        result = ["%s/%s" % (self.name, self.version)]
        if self.user or self.channel:
            result.append("@%s/%s" % (self.user, self.channel))
        if self.package_id:
            result.append(":%s" % self.package_id)
        return "".join(result)

    @property
    def sha(self):
        vals = [str(n) for n in (self.name, self.version, self.user, self.channel, self.package_id)]
        # This is done later to NOT affect existing package-IDs (before revisions)
        return "/".join(vals)

    def unrelated_mode(self):
        self.name = self.version = self.user = self.channel = self.package_id = None

    def semver_direct_mode(self):
        if self._indirect:
            self.unrelated_mode()
        else:
            self.semver_mode()

    def semver_mode(self):
        self.name = self.full_name
        self.version = self.full_version.stable()
        self.user = self.channel = self.package_id = None

    semver = semver_mode  # Remove Conan 2.0

    def full_version_mode(self):
        self.name = self.full_name
        self.version = self.full_version
        self.user = self.channel = self.package_id = None

    def patch_mode(self):
        self.name = self.full_name
        self.version = self.full_version.patch()
        self.user = self.channel = self.package_id = None

    def base_mode(self):
        self.name = self.full_name
        self.version = self.full_version.base
        self.user = self.channel = self.package_id = None

    def minor_mode(self):
        self.name = self.full_name
        self.version = self.full_version.minor()
        self.user = self.channel = self.package_id = None

    def major_mode(self):
        self.name = self.full_name
        self.version = self.full_version.major()
        self.user = self.channel = self.package_id = None

    def full_recipe_mode(self):
        self.name = self.full_name
        self.version = self.full_version
        self.user = self.full_user
        self.channel = self.full_channel
        self.package_id = None

    def full_package_mode(self):
        self.name = self.full_name
        self.version = self.full_version
        self.user = self.full_user
        self.channel = self.full_channel
        self.package_id = self.full_package_id


class RequirementsInfo(object):
    def __init__(self, prefs, default_package_id_mode):
        # {PackageReference: RequirementInfo}
        self._data = {pref: RequirementInfo(pref, default_package_id_mode=default_package_id_mode)
                      for pref in prefs}

    def copy(self):
        # For build_id() implementation
        result = RequirementsInfo([], None)
        result._data = {pref: req_info.copy() for pref, req_info in self._data.items()}
        return result

    def clear(self):
        self._data = {}

    def remove(self, *args):
        for name in args:
            del self._data[self._get_key(name)]

    def add(self, prefs_indirect, default_package_id_mode):
        """ necessary to propagate from upstream the real
        package requirements
        """
        for r in prefs_indirect:
            self._data[r] = RequirementInfo(r, indirect=True,
                                            default_package_id_mode=default_package_id_mode)

    def refs(self):
        """ used for updating downstream requirements with this
        """
        return list(self._data.keys())

    def _get_key(self, item):
        for reference in self._data:
            if reference.ref.name == item:
                return reference
        raise ConanException("No requirement matching for %s" % (item))

    def __getitem__(self, item):
        """get by package name
        Necessary to access from conaninfo
        self.requires["Boost"].version = "2.X"
        """
        return self._data[self._get_key(item)]

    @property
    def pkg_names(self):
        return [r.ref.name for r in self._data.keys()]

    @property
    def sha(self):
        result = []
        # Remove requirements without a name, i.e. indirect transitive requirements
        data = {k: v for k, v in self._data.items() if v.name}
        for key in sorted(data):
            s = data[key].sha
            result.append(s)
        return sha1('\n'.join(result).encode())

    def dumps(self):
        result = []
        for ref in sorted(self._data):
            dumped = self._data[ref].dumps()
            if dumped:
                result.append(dumped)
        return "\n".join(result)

    def unrelated_mode(self):
        self.clear()

    def semver_direct_mode(self):
        for r in self._data.values():
            r.semver_direct_mode()

    def semver_mode(self):
        for r in self._data.values():
            r.semver_mode()

    def patch_mode(self):
        for r in self._data.values():
            r.patch_mode()

    def minor_mode(self):
        for r in self._data.values():
            r.minor_mode()

    def major_mode(self):
        for r in self._data.values():
            r.major_mode()

    def base_mode(self):
        for r in self._data.values():
            r.base_mode()

    def full_version_mode(self):
        for r in self._data.values():
            r.full_version_mode()

    def full_recipe_mode(self):
        for r in self._data.values():
            r.full_recipe_mode()

    def full_package_mode(self):
        for r in self._data.values():
            r.full_package_mode()


class _PackageReferenceList(list):
    @staticmethod
    def loads(text):
        return _PackageReferenceList([PackageReference.loads(package_reference)
                                     for package_reference in text.splitlines()])

    def dumps(self):
        return "\n".join(self.serialize())

    def serialize(self):
        return [str(r) for r in sorted(self)]


class ConanInfo(object):

    def copy(self):
        """ Useful for build_id implementation
        """
        result = ConanInfo()
        result.settings = self.settings.copy()
        result.options = self.options.copy()
        result.requires = self.requires.copy()
        return result

    @staticmethod
    def create(settings, options, prefs_direct, prefs_indirect, default_package_id_mode):
        result = ConanInfo()
        result.full_settings = settings
        result.settings = settings.copy()
        result.full_options = options
        result.options = options.copy()
        result.options.clear_indirect()
        result.full_requires = _PackageReferenceList(prefs_direct)
        result.requires = RequirementsInfo(prefs_direct, default_package_id_mode)
        result.requires.add(prefs_indirect, default_package_id_mode)
        result.full_requires.extend(prefs_indirect)
        result.recipe_hash = None
        result.env_values = EnvValues()
        result.vs_toolset_compatible()
        result.discard_build_settings()
        result.default_std_matching()

        return result

    @staticmethod
    def loads(text):
        # This is used for search functionality, search prints info from this file
        # Other use is from the BinariesAnalyzer, to get the recipe_hash and know
        # if package is outdated
        parser = ConfigParser(text, ["settings", "full_settings", "options", "full_options",
                                     "requires", "full_requires", "scope", "recipe_hash", "env"],
                              raise_unexpected_field=False)
        result = ConanInfo()
        result.settings = Values.loads(parser.settings)
        result.full_settings = Values.loads(parser.full_settings)
        result.options = OptionsValues.loads(parser.options)
        result.full_options = OptionsValues.loads(parser.full_options)
        result.full_requires = _PackageReferenceList.loads(parser.full_requires)
        # Requires after load are not used for any purpose, CAN'T be used, they are not correct
        result.requires = RequirementsInfo(result.full_requires, "semver_direct_mode")
        result.recipe_hash = parser.recipe_hash or None

        # TODO: Missing handling paring of requires, but not necessary now
        result.env_values = EnvValues.loads(parser.env)
        return result

    def dumps(self):
        def indent(text):
            if not text:
                return ""
            return '\n'.join("    " + line for line in text.splitlines())
        result = list()

        result.append("[settings]")
        result.append(indent(self.settings.dumps()))
        result.append("\n[requires]")
        result.append(indent(self.requires.dumps()))
        result.append("\n[options]")
        result.append(indent(self.options.dumps()))
        result.append("\n[full_settings]")
        result.append(indent(self.full_settings.dumps()))
        result.append("\n[full_requires]")
        result.append(indent(self.full_requires.dumps()))
        result.append("\n[full_options]")
        result.append(indent(self.full_options.dumps()))
        result.append("\n[recipe_hash]\n%s" % indent(self.recipe_hash))
        result.append("\n[env]")
        result.append(indent(self.env_values.dumps()))

        return '\n'.join(result) + "\n"

    def __eq__(self, other):
        """ currently just for testing purposes
        """
        return self.dumps() == other.dumps()

    def __ne__(self, other):
        return not self.__eq__(other)

    @staticmethod
    def load_file(conan_info_path):
        """ load from file
        """
        try:
            config_text = load(conan_info_path)
        except IOError:
            raise ConanException("Does not exist %s" % conan_info_path)
        else:
            return ConanInfo.loads(config_text)

    @staticmethod
    def load_from_package(package_folder):
        info_path = os.path.join(package_folder, CONANINFO)
        return ConanInfo.load_file(info_path)

    def package_id(self):
        """ The package_id of a conans is the sha1 of its specific requirements,
        options and settings
        """
        result = []
        result.append(self.settings.sha)
        # Only are valid requires for OPtions those Non-Dev who are still in requires
        self.options.filter_used(self.requires.pkg_names)
        result.append(self.options.sha)
        requires_sha = self.requires.sha
        result.append(requires_sha)

        package_id = sha1('\n'.join(result).encode())
        return package_id

    def serialize_min(self):
        """
        This info will be shown in search results.
        """
        conan_info_json = {"settings": dict(self.settings.serialize()),
                           "options": dict(self.options.serialize()["options"]),
                           "full_requires": self.full_requires.serialize(),
                           "recipe_hash": self.recipe_hash}
        return conan_info_json

    def header_only(self):
        self.settings.clear()
        self.options.clear()
        self.requires.clear()

    def vs_toolset_compatible(self):
        """Default behaviour, same package for toolset v140 with compiler=Visual Studio 15 than
        using Visual Studio 14"""
        if self.full_settings.compiler != "Visual Studio":
            return

        toolset = str(self.full_settings.compiler.toolset)
        version = MSVS_DEFAULT_TOOLSETS_INVERSE.get(toolset)
        if version is not None:
            self.settings.compiler.version = version
            del self.settings.compiler.toolset

    def vs_toolset_incompatible(self):
        """Will generate different packages for v140 and visual 15 than the visual 14"""
        if self.full_settings.compiler != "Visual Studio":
            return
        self.settings.compiler.version = self.full_settings.compiler.version
        self.settings.compiler.toolset = self.full_settings.compiler.toolset

    def discard_build_settings(self):
        # When os is defined, os_build is irrelevant for the consumer.
        # only when os_build is alone (installers, etc) it has to be present in the package_id
        if self.full_settings.os and self.full_settings.os_build:
            del self.settings.os_build
        if self.full_settings.arch and self.full_settings.arch_build:
            del self.settings.arch_build

    def include_build_settings(self):
        self.settings.os_build = self.full_settings.os_build
        self.settings.arch_build = self.full_settings.arch_build

    def default_std_matching(self):
        """
        If we are building with gcc 7, and we specify -s cppstd=gnu14, it's the default, so the
        same as specifying None, packages are the same
        """

        if self.full_settings.cppstd and \
                self.full_settings.compiler and \
                self.full_settings.compiler.version:
            default = cppstd_default(str(self.full_settings.compiler),
                                     str(self.full_settings.compiler.version))
            if default == str(self.full_settings.cppstd):
                self.settings.cppstd = None

    def default_std_non_matching(self):
        if self.full_settings.cppstd:
            self.settings.cppstd = self.full_settings.cppstd
