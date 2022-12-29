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

PREV_UNKNOWN = "PREV unknown"
PACKAGE_ID_UNKNOWN = "Package_ID_unknown"
PACKAGE_ID_INVALID = "INVALID"


class RequirementInfo(object):

    def __init__(self, pref, default_package_id_mode, indirect=False):
        self.package = pref
        self.full_name = pref.ref.name
        self.full_version = pref.ref.version
        self.full_user = pref.ref.user
        self.full_channel = pref.ref.channel
        self.full_recipe_revision = pref.ref.revision
        self.full_package_id = pref.id
        self.full_package_revision = pref.revision
        self._indirect = indirect

        try:
            func_package_id_mode = getattr(self, default_package_id_mode)
        except AttributeError:
            raise ConanException("'%s' is not a known package_id_mode" % default_package_id_mode)
        else:
            func_package_id_mode()

    def copy(self):
        # Useful for build_id()
        result = RequirementInfo(self.package, "unrelated_mode")
        for f in ("name", "version", "user", "channel", "recipe_revision", "package_id",
                  "package_revision"):

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
        if self.recipe_revision:
            result.append("#%s" % self.recipe_revision)
        if self.package_id:
            result.append(":%s" % self.package_id)
        if self.package_revision:
            result.append("#%s" % self.package_revision)
        return "".join(result)

    @property
    def sha(self):
        if self.package_id == PACKAGE_ID_UNKNOWN or self.package_revision == PREV_UNKNOWN:
            return None
        if self.package_id == PACKAGE_ID_INVALID:
            return PACKAGE_ID_INVALID
        vals = [str(n) for n in (self.name, self.version, self.user, self.channel, self.package_id)]
        # This is done later to NOT affect existing package-IDs (before revisions)
        if self.recipe_revision:
            vals.append(self.recipe_revision)
        if self.package_revision:
            # A package revision is required = True, but didn't get a real value
            vals.append(self.package_revision)
        return "/".join(vals)

    def unrelated_mode(self):
        self.name = self.version = self.user = self.channel = self.package_id = None
        self.recipe_revision = self.package_revision = None

    def semver_direct_mode(self):
        if self._indirect:
            self.unrelated_mode()
        else:
            self.semver_mode()

    def semver_mode(self):
        self.name = self.full_name
        self.version = self.full_version.stable()
        self.user = self.channel = self.package_id = None
        self.recipe_revision = self.package_revision = None

    semver = semver_mode  # Remove Conan 2.0

    def full_version_mode(self):
        self.name = self.full_name
        self.version = self.full_version
        self.user = self.channel = self.package_id = None
        self.recipe_revision = self.package_revision = None

    def patch_mode(self):
        self.name = self.full_name
        self.version = self.full_version.patch()
        self.user = self.channel = self.package_id = None
        self.recipe_revision = self.package_revision = None

    def base_mode(self):
        self.name = self.full_name
        self.version = self.full_version.base
        self.user = self.channel = self.package_id = None
        self.recipe_revision = self.package_revision = None

    def minor_mode(self):
        self.name = self.full_name
        self.version = self.full_version.minor()
        self.user = self.channel = self.package_id = None
        self.recipe_revision = self.package_revision = None

    def major_mode(self):
        self.name = self.full_name
        self.version = self.full_version.major()
        self.user = self.channel = self.package_id = None
        self.recipe_revision = self.package_revision = None

    def full_recipe_mode(self):
        self.name = self.full_name
        self.version = self.full_version
        self.user = self.full_user
        self.channel = self.full_channel
        self.package_id = None
        self.recipe_revision = self.package_revision = None

    def full_package_mode(self):
        self.name = self.full_name
        self.version = self.full_version
        self.user = self.full_user
        self.channel = self.full_channel
        self.package_id = self.full_package_id
        self.recipe_revision = self.package_revision = None

    def recipe_revision_mode(self):
        self.name = self.full_name
        self.version = self.full_version
        self.user = self.full_user
        self.channel = self.full_channel
        self.package_id = self.full_package_id
        self.recipe_revision = self.full_recipe_revision
        self.package_revision = None

    def package_revision_mode(self):
        self.name = self.full_name
        self.version = self.full_version
        self.user = self.full_user
        self.channel = self.full_channel
        self.package_id = self.full_package_id
        self.recipe_revision = self.full_recipe_revision
        # It is requested to use, but not defined (binary not build yet)
        self.package_revision = self.full_package_revision or PREV_UNKNOWN


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
        # FIXME: This is a very bad name, it return prefs, not refs
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
            if s is None:
                return None
            if s == PACKAGE_ID_INVALID:
                return PACKAGE_ID_INVALID
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

    def recipe_revision_mode(self):
        for r in self._data.values():
            r.recipe_revision_mode()

    def package_revision_mode(self):
        for r in self._data.values():
            r.package_revision_mode()


class PythonRequireInfo(object):

    def __init__(self, ref, default_package_id_mode):
        self._ref = ref
        self._name = None
        self._version = None
        self._user = None
        self._channel = None
        self._revision = None

        try:
            func_package_id_mode = getattr(self, default_package_id_mode)
        except AttributeError:
            raise ConanException("'%s' is not a known package_id_mode" % default_package_id_mode)
        else:
            func_package_id_mode()

    @property
    def sha(self):
        vals = [n for n in (self._name, self._version, self._user, self._channel, self._revision)
                if n]
        return "/".join(vals)

    def semver_mode(self):
        self._name = self._ref.name
        self._version = self._ref.version.stable()
        self._user = self._channel = None
        self._revision = None

    def full_version_mode(self):
        self._name = self._ref.name
        self._version = self._ref.version
        self._user = self._channel = None
        self._revision = None

    def patch_mode(self):
        self._name = self._ref.name
        self._version = self._ref.version.patch()
        self._user = self._channel = None
        self._revision = None

    def minor_mode(self):
        self._name = self._ref.name
        self._version = self._ref.version.minor()
        self._user = self._channel = None
        self._revision = None

    def major_mode(self):
        self._name = self._ref.name
        self._version = self._ref.version.major()
        self._user = self._channel = None
        self._revision = None

    def full_recipe_mode(self):
        self._name = self._ref.name
        self._version = self._ref.version
        self._user = self._ref.user
        self._channel = self._ref.channel
        self._revision = None

    def recipe_revision_mode(self):
        self._name = self._ref.name
        self._version = self._ref.version
        self._user = self._ref.user
        self._channel = self._ref.channel
        self._revision = self._ref.revision

    def unrelated_mode(self):
        self._name = self._version = self._user = self._channel = self._revision = None


class PythonRequiresInfo(object):

    def __init__(self, refs, default_package_id_mode):
        self._default_package_id_mode = default_package_id_mode
        if refs:
            self._refs = [PythonRequireInfo(r, default_package_id_mode=default_package_id_mode)
                          for r in sorted(refs)]
        else:
            self._refs = None

    def copy(self):
        # For build_id() implementation
        refs = [r._ref for r in self._refs] if self._refs else None
        return PythonRequiresInfo(refs, self._default_package_id_mode)

    def __bool__(self):
        return bool(self._refs)

    def __nonzero__(self):
        return self.__bool__()

    def clear(self):
        self._refs = None

    @property
    def sha(self):
        result = [r.sha for r in self._refs]
        return sha1('\n'.join(result).encode())

    def unrelated_mode(self):
        self._refs = None

    def semver_mode(self):
        for r in self._refs:
            r.semver_mode()

    def patch_mode(self):
        for r in self._refs:
            r.patch_mode()

    def minor_mode(self):
        for r in self._refs:
            r.minor_mode()

    def major_mode(self):
        for r in self._refs:
            r.major_mode()

    def full_version_mode(self):
        for r in self._refs:
            r.full_version_mode()

    def full_recipe_mode(self):
        for r in self._refs:
            r.full_recipe_mode()

    def recipe_revision_mode(self):
        for r in self._refs:
            r.recipe_revision_mode()


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
        result.invalid = self.invalid
        result.settings = self.settings.copy()
        result.options = self.options.copy()
        result.requires = self.requires.copy()
        result.python_requires = self.python_requires.copy()
        return result

    @staticmethod
    def create(settings, options, prefs_direct, prefs_indirect, default_package_id_mode,
               python_requires, default_python_requires_id_mode):
        result = ConanInfo()
        result.invalid = None
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
        result.python_requires = PythonRequiresInfo(python_requires, default_python_requires_id_mode)
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
        result.invalid = None
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

    def clone(self):
        q = self.copy()
        q.full_settings = self.full_settings.copy()
        q.full_options = self.full_options.copy()
        q.full_requires = _PackageReferenceList.loads(self.full_requires.dumps())
        return q

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
        if self.invalid:
            return PACKAGE_ID_INVALID
        result = [self.settings.sha]
        # Only are valid requires for OPtions those Non-Dev who are still in requires
        self.options.filter_used(self.requires.pkg_names)
        result.append(self.options.sha)
        requires_sha = self.requires.sha
        if requires_sha is None:
            return PACKAGE_ID_UNKNOWN
        if requires_sha == PACKAGE_ID_INVALID:
            self.invalid = "Invalid transitive dependencies"
            return PACKAGE_ID_INVALID
        result.append(requires_sha)
        if self.python_requires:
            result.append(self.python_requires.sha)
        if hasattr(self, "conf"):
            result.append(self.conf.sha)
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

    # FIXME: Rename this to "clear" in 2.0
    def header_only(self):
        self.settings.clear()
        self.options.clear()
        self.requires.clear()

    clear = header_only

    def msvc_compatible(self):
        if self.settings.compiler != "msvc":
            return

        compatible = self.clone()
        version = compatible.settings.compiler.version
        runtime = compatible.settings.compiler.runtime
        runtime_type = compatible.settings.compiler.runtime_type

        compatible.settings.compiler = "Visual Studio"
        from conan.tools.microsoft.visual import msvc_version_to_vs_ide_version
        visual_version = msvc_version_to_vs_ide_version(version)
        compatible.settings.compiler.version = visual_version
        runtime = "MT" if runtime == "static" else "MD"
        if runtime_type == "Debug":
            runtime = "{}d".format(runtime)
        compatible.settings.compiler.runtime = runtime
        return compatible

    def apple_clang_compatible(self):
        # https://github.com/conan-io/conan/pull/10797
        # apple-clang compiler version 13 will be compatible with 13.0
        if not self.settings.compiler or \
           (self.settings.compiler != "apple-clang" or self.settings.compiler.version != "13"):
            return

        compatible = self.clone()
        compatible.settings.compiler.version = "13.0"
        return compatible

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
        if self.full_settings.compiler == "msvc":
            # This post-processing of package_id was a hack to introduce this in a non-breaking way
            # This whole function will be removed in Conan 2.0, and the responsibility will be
            # of the input profile
            return
        if (self.full_settings.compiler and
                self.full_settings.compiler.version):
            default = cppstd_default(self.full_settings)

            if str(self.full_settings.cppstd) == default:
                self.settings.cppstd = None

            if str(self.full_settings.compiler.cppstd) == default:
                self.settings.compiler.cppstd = None

    def default_std_non_matching(self):
        if self.full_settings.cppstd:
            self.settings.cppstd = self.full_settings.cppstd

        if self.full_settings.compiler.cppstd:
            self.settings.compiler.cppstd = self.full_settings.compiler.cppstd

    def shared_library_package_id(self):
        if "shared" in self.full_options and self.full_options.shared:
            for dep_name in self.requires.pkg_names:
                dep_options = self.full_options[dep_name]
                if "shared" not in dep_options or not dep_options.shared:
                    self.requires[dep_name].package_revision_mode()

    def parent_compatible(self, *_, **kwargs):
        """If a built package for Intel has to be compatible for a Visual/GCC compiler
        (consumer). Transform the visual/gcc full_settings into an intel one"""

        if "compiler" not in kwargs:
            raise ConanException("Specify 'compiler' as a keywork argument. e.g: "
                                 "'parent_compiler(compiler=\"intel\")' ")

        self.settings.compiler = kwargs["compiler"]
        # You have to use here a specific version or create more than one version of
        # compatible packages
        kwargs.pop("compiler")
        for setting_name in kwargs:
            # Won't fail even if the setting is not valid, there is no validation at info
            setattr(self.settings.compiler, setting_name, kwargs[setting_name])
        self.settings.compiler.base = self.full_settings.compiler
        for field in self.full_settings.compiler.fields:
            value = getattr(self.full_settings.compiler, field)
            setattr(self.settings.compiler.base, field, value)

    def base_compatible(self):
        """If a built package for Visual/GCC has to be compatible for an Intel compiler
          (consumer). Transform the Intel profile into an visual/gcc one"""
        if not self.full_settings.compiler.base:
            raise ConanException("The compiler '{}' has "
                                 "no 'base' sub-setting".format(self.full_settings.compiler))

        self.settings.compiler = self.full_settings.compiler.base
        for field in self.full_settings.compiler.base.fields:
            value = getattr(self.full_settings.compiler.base, field)
            setattr(self.settings.compiler, field, value)
