import os

from conans.client.build.cppstd_flags import cppstd_default
from conans.client.graph.graph import BINARY_INVALID_BUILD, BINARY_INVALID, BINARY_UNKNOWN
from conan.tools.microsoft.visual import msvc_version_to_vs_ide_version
from conans.client.graph.graph import BINARY_INVALID
from conans.client.tools.win import MSVS_DEFAULT_TOOLSETS_INVERSE
from conans.errors import ConanException
from conans.model.dependencies import UserRequirementsDict
from conans.model.options import Options
from conans.model.package_ref import PkgReference
from conans.model.recipe_ref import RecipeReference, Version
from conans.model.settings import undefined_value
from conans.model.values import Values
from conans.paths import CONANINFO
from conans.util.config_parser import ConfigParser
from conans.util.files import load
from conans.util.sha import sha1

PREV_UNKNOWN = "PREV_UNKNOWN"
RREV_UNKNOWN = "RREV_UNKNOWN"
PACKAGE_ID_UNKNOWN = "UNKNOWN"


class _VersionRepr:
    """Class to return strings like 1.Y.Z from a Version object"""

    def __init__(self, version: Version):
        self._version = version

    def stable(self):
        if self._version.major == 0:
            return str(self._version)
        else:
            return self.major()

    def major(self):
        if not isinstance(self._version.major.value, int):
            return str(self._version.major)
        return ".".join([str(self._version.major), 'Y', 'Z'])

    def minor(self, fill=True):
        if not isinstance(self._version.major.value, int):
            return str(self._version.major)

        v0 = str(self._version.major)
        v1 = str(self._version.minor) if self._version.minor is not None else "0"
        if fill:
            return ".".join([v0, v1, 'Z'])
        return ".".join([v0, v1])

    def patch(self):
        if not isinstance(self._version.major.value, int):
            return str(self._version.major)

        v0 = str(self._version.major)
        v1 = str(self._version.minor) if self._version.minor is not None else "0"
        v2 = str(self._version.patch) if self._version.patch is not None else "0"
        return ".".join([v0, v1, v2])

    def pre(self):
        if not isinstance(self._version.major.value, int):
            return str(self._version.major)

        v0 = str(self._version.major)
        v1 = str(self._version.minor) if self._version.minor is not None else "0"
        v2 = str(self._version.patch) if self._version.patch is not None else "0"
        v = ".".join([v0, v1, v2])
        if self._version.pre is not None:
            v += "-%s" % self._version.pre
        return v

    @property
    def build(self):
        return self._version.build if self._version.build is not None else ""


class RequirementInfo(object):

    def __init__(self, pref, default_package_id_mode, binary, indirect=False):
        self.package = pref
        self.full_name = pref.ref.name
        self.full_version = pref.ref.version
        self.full_user = pref.ref.user
        self.full_channel = pref.ref.channel
        self.full_recipe_revision = pref.ref.revision
        self.full_package_id = pref.package_id
        self.full_package_revision = pref.revision
        self._indirect = indirect
        self._binary = binary

        try:
            func_package_id_mode = getattr(self, default_package_id_mode)
        except AttributeError:
            raise ConanException("'%s' is not a known package_id_mode" % default_package_id_mode)
        else:
            func_package_id_mode()

    def req_binary_error(self):
        if (self.package_id or self.package_revision) and self._binary in (BINARY_INVALID_BUILD,
                                                                           BINARY_INVALID):
            return BINARY_INVALID
        if self.package_revision == PREV_UNKNOWN:
            return BINARY_UNKNOWN

    def copy(self):
        # Useful for build_id()
        result = RequirementInfo(self.package, "unrelated_mode", self._binary)
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

        ref = RecipeReference(self.name, self.version, self.user, self.channel,
                                 self.recipe_revision)
        pref = repr(ref)
        if self.package_id:
            pref += ":{}".format(self.package_id)
            if self.package_revision:
                pref += "#{}".format(self.package_revision)

        return pref

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
        self.version = _VersionRepr(self.full_version).stable()
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
        self.version = _VersionRepr(self.full_version).patch()
        self.user = self.channel = self.package_id = None
        self.recipe_revision = self.package_revision = None

    def base_mode(self):
        self.name = self.full_name
        self.version = _VersionRepr(self.full_version).base
        self.user = self.channel = self.package_id = None
        self.recipe_revision = self.package_revision = None

    def minor_mode(self):
        self.name = self.full_name
        self.version = _VersionRepr(self.full_version).minor()
        self.user = self.channel = self.package_id = None
        self.recipe_revision = self.package_revision = None

    def major_mode(self):
        self.name = self.full_name
        self.version = _VersionRepr(self.full_version).major()
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


class RequirementsInfo(UserRequirementsDict):

    def req_binary_error(self):
        for d in self._data.values():
            error = d.req_binary_error()
            if error:
                return error

    def copy(self):
        # For build_id() implementation
        data = {pref: req_info.copy() for pref, req_info in self._data.items()}
        return RequirementsInfo(data)

    def serialize(self):
        return [str(r) for r in sorted(self._data.values())]

    def __bool__(self):
        return bool(self._data)

    def clear(self):
        self._data = {}

    def remove(self, *args):
        for name in args:
            del self[name]

    @property
    def pkg_names(self):
        return [r.ref.name for r in self._data.keys()]

    def dumps(self):
        result = []
        for req_info in self._data.values():
            dumped = req_info.dumps()
            if dumped:
                result.append(dumped)

        if result:
            result = sorted(result)
            result.append("")
            return "\n".join(result)
        return ""

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

<<<<<<< HEAD
    def dumps(self):
        ref = ConanFileReference(self._name, self._version, self._user, self._channel,
                                 self._revision, validate=False)
=======
    @property
    def sha(self):
        ref = RecipeReference(self._name, self._version, self._user, self._channel,
                              self._revision)
>>>>>>> develop2
        return repr(ref)

    def semver_mode(self):
        self._name = self._ref.name
        self._version = _VersionRepr(self._ref.version).stable()
        self._user = self._channel = None
        self._revision = None

    def full_version_mode(self):
        self._name = self._ref.name
        self._version = self._ref.version
        self._user = self._channel = None
        self._revision = None

    def patch_mode(self):
        self._name = self._ref.name
        self._version = _VersionRepr(self._ref.version).patch()
        self._user = self._channel = None
        self._revision = None

    def minor_mode(self):
        self._name = self._ref.name
        self._version = _VersionRepr(self._ref.version).minor()
        self._user = self._channel = None
        self._revision = None

    def major_mode(self):
        self._name = self._ref.name
        self._version = _VersionRepr(self._ref.version).major()
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

    def clear(self):
        self._refs = None

    def dumps(self):
        result = []
        for req_info in self._refs or []:
            dumped = req_info.dumps()
            if dumped:
                result.append(dumped)
        if result:
            result.insert(0, "[python_requires]")
            result.append("")
        return "\n".join(sorted(result))

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
<<<<<<< HEAD
        return _PackageReferenceList([package_reference.strip()
                                     for package_reference in text.splitlines()
                                      if package_reference.strip()])
=======
        return _PackageReferenceList([PkgReference.loads(package_reference)
                                     for package_reference in text.splitlines()])
>>>>>>> develop2


class ConanInfo(object):
    def __init__(self):
        # WIP: to make it defined
        self.conf = None

    def copy(self):
        """ Useful for build_id implementation
        """
        result = ConanInfo()
        result.settings = self.settings.copy()
        result.options = self.options.copy_conaninfo_options()
        result.requires = self.requires.copy()
        result.build_requires = self.build_requires.copy()
        result.python_requires = self.python_requires.copy()
        return result

    def clone(self):
        return self.copy()

    @staticmethod
    def create(conanfile, settings, options, reqs_info, build_requires_info,
               python_requires, default_python_requires_id_mode):
        result = ConanInfo()
        result.conanfile = conanfile
        result.settings = settings.copy()
<<<<<<< HEAD

        result.options = options.copy()
        result.options.clear_indirect()
=======
        result.options = options.copy_conaninfo_options()
>>>>>>> develop2
        result.requires = reqs_info
        result.build_requires = build_requires_info

        result.vs_toolset_compatible()
        result.python_requires = PythonRequiresInfo(python_requires, default_python_requires_id_mode)
        return result

    @staticmethod
    def loads(text):
        # This is used for search functionality, search prints info from this file
<<<<<<< HEAD
        parser = ConfigParser(text, ["settings", "options", "requires"],
=======
        parser = ConfigParser(text, ["settings", "full_settings", "options",
                                     "requires", "full_requires", "env"],
>>>>>>> develop2
                              raise_unexpected_field=False)
        result = ConanInfo()
        result.settings = Values.loads(parser.settings)
<<<<<<< HEAD
        result.options = OptionsValues.loads(parser.options)
        result.requires = _PackageReferenceList.loads(parser.requires)
        return result

    def dumps(self):
        result = []
        settings = self.settings.dumps()
        if settings:
            result.append("[settings]")
            result.append(settings)
        options = self.options.dumps()
        if options:
            result.append("[options]")
            result.append(options)
        requires = self.requires.dumps()
        if requires:
            result.append("[requires]")
            result.append(requires)
        python_requires = self.python_requires.dumps()
        if python_requires:
            result.append(python_requires)
        build_requires = self.build_requires.dumps()
        if build_requires:
            result.append(build_requires)
        if self.conf is not None:
            conf = self.conf.dumps()
            if conf:
                result.append(conf)
        return '\n'.join(result)
=======
        result.full_settings = Values.loads(parser.full_settings)
        result.options = Options.loads(parser.options)
        # Requires after load are not used for any purpose, CAN'T be used, they are not correct
        # FIXME: remove this uglyness
        result.requires = RequirementsInfo({})
        result.build_requires = RequirementsInfo({})

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
        return '\n'.join(result) + "\n"

    def clone(self):
        q = self.copy()
        q.full_settings = self.full_settings.copy()
        return q
>>>>>>> develop2

    def __eq__(self, other):
        """ currently just for testing purposes
        """
        return self.dumps() == other.dumps()

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

    def req_binary_error(self):
        return self.requires.req_binary_error()

    def package_id(self):
        """ The package_id of a conans is the sha1 of its specific requirements,
        options and settings
        """
<<<<<<< HEAD
        text = self.dumps()
        print("HASHING--------")
        print(text)
        print("------------------------")
=======
        result = [self.settings.sha,
                  self.options.sha]
        requires_sha = self.requires.sha
        if requires_sha is None:
            return PACKAGE_ID_UNKNOWN
        if requires_sha == PACKAGE_ID_INVALID:
            self.invalid = BINARY_INVALID, "Invalid transitive dependencies"
            return PACKAGE_ID_INVALID
        result.append(requires_sha)
        if self.python_requires:
            result.append(self.python_requires.sha)
        if self.build_requires:
            result.append(self.build_requires.sha.replace("[requires]", "[build_requires]"))
        if hasattr(self, "conf"):
            result.append(self.conf.sha)
        result.append("")  # Append endline so file ends with LF
        text = '\n'.join(result)
        # print("HASING ", text)
>>>>>>> develop2
        package_id = sha1(text.encode())
        return package_id

    def serialize_min(self):
        """
        This info will be shown in search results.
        """
        # Lets keep returning the legacy "full_requires" just in case some client uses it
        conan_info_json = {"settings": dict(self.settings.serialize()),
<<<<<<< HEAD
                           "options": dict(self.options.serialize()["options"]),
                           "requires": self.requires.serialize()
=======
                           "options": dict(self.options.serialize())["options"],
<<<<<<< HEAD
                           "full_requires": self.full_requires.serialize()
>>>>>>> develop2
=======
                           "requires": self.requires.serialize()
>>>>>>> develop2
                           }
        return conan_info_json

    def header_only(self):
        self.settings.clear()
        self.options.clear()
        self.requires.clear()

    def msvc_compatible(self):
        if self.settings.compiler != "msvc":
            return

        compatible = self.clone()
        version = compatible.settings.compiler.version
        runtime = compatible.settings.compiler.runtime
        runtime_type = compatible.settings.compiler.runtime_type

        if version is None:
            raise undefined_value('settings.compiler.version')
        if runtime is None:
            raise undefined_value('settings.compiler.runtime')

        compatible.settings.compiler = "Visual Studio"
        visual_version = msvc_version_to_vs_ide_version(version)
        compatible.settings.compiler.version = visual_version
        runtime = "MT" if runtime == "static" else "MD"
        if  runtime_type == "Debug":
            runtime = "{}d".format(runtime)
        compatible.settings.compiler.runtime = runtime
        return compatible

    def vs_toolset_compatible(self):
        """Default behaviour, same package for toolset v140 with compiler=Visual Studio 15 than
        using Visual Studio 14"""
        if self.conanfile.settings.get_safe("compiler") != "Visual Studio":
            return

        toolset = str(self.conanfile.settings.compiler.toolset)
        version = MSVS_DEFAULT_TOOLSETS_INVERSE.get(toolset)
        if version is not None:
            self.settings.compiler.version = version
            del self.settings.compiler.toolset

    def vs_toolset_incompatible(self):
        """Will generate different packages for v140 and visual 15 than the visual 14"""
<<<<<<< HEAD
        if self.conanfile.settings.get_safe("compiler") != "Visual Studio":
            return
        self.settings.compiler.version = self.conanfile.settings.compiler.version
        self.settings.compiler.toolset = self.conanfile.settings.compiler.toolset
=======
        if self.full_settings.compiler != "Visual Studio":
            return
        self.settings.compiler.version = self.full_settings.compiler.version
        self.settings.compiler.toolset = self.full_settings.compiler.toolset
>>>>>>> develop2

    def parent_compatible(self, *_, **kwargs):
        """If a built package for Intel has to be compatible for a Visual/GCC compiler
        (consumer). Transform the visual/gcc conanfile.settings into an intel one"""

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
        self.settings.compiler.base = self.conanfile.settings.compiler
        for field in self.conanfile.settings.compiler.fields:
            value = getattr(self.conanfile.settings.compiler, field)
            setattr(self.settings.compiler.base, field, value)

    def base_compatible(self):
        """If a built package for Visual/GCC has to be compatible for an Intel compiler
          (consumer). Transform the Intel profile into an visual/gcc one"""
        if not self.conanfile.settings.compiler.base:
            raise ConanException("The compiler '{}' has "
                                 "no 'base' sub-setting".format(self.conanfile.settings.compiler))

        self.settings.compiler = self.conanfile.settings.compiler.base
        for field in self.conanfile.settings.compiler.base.fields:
            value = getattr(self.conanfile.settings.compiler.base, field)
            setattr(self.settings.compiler, field, value)
