import os

from conans.client.graph.graph import BINARY_INVALID
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


class RequirementInfo:

    def __init__(self, pref, default_package_id_mode):
        self._pref = pref
        self.name = self.version = self.user = self.channel = self.package_id = None
        self.recipe_revision = None

        try:
            func_package_id_mode = getattr(self, default_package_id_mode)
        except AttributeError:
            raise ConanException("'%s' is not a known package_id_mode" % default_package_id_mode)
        else:
            func_package_id_mode()

    def copy(self):
        # Useful for build_id()
        result = RequirementInfo(self._pref, "unrelated_mode")
        for f in ("name", "version", "user", "channel", "recipe_revision", "package_id"):
            setattr(result, f, getattr(self, f))
        return result

    def pref(self):
        ref = RecipeReference(self.name, self.version, self.user, self.channel, self.recipe_revision)
        return PkgReference(ref, self.package_id)

    def dumps(self):
        return repr(self.pref())

    def unrelated_mode(self):
        self.name = self.version = self.user = self.channel = self.package_id = None
        self.recipe_revision = None

    def semver_mode(self):
        self.name = self._pref.ref.name
        self.version = _VersionRepr(self._pref.ref.version).stable()
        self.user = self.channel = self.package_id = None
        self.recipe_revision = None

    def full_version_mode(self):
        self.name = self._pref.ref.name
        self.version = self._pref.ref.version
        self.user = self.channel = self.package_id = None
        self.recipe_revision = None

    def patch_mode(self):
        self.name = self._pref.ref.name
        self.version = _VersionRepr(self._pref.ref.version).patch()
        self.user = self.channel = self.package_id = None
        self.recipe_revision = None

    def minor_mode(self):
        self.name = self._pref.ref.name
        self.version = _VersionRepr(self._pref.ref.version).minor()
        self.user = self.channel = self.package_id = None
        self.recipe_revision = None

    def major_mode(self):
        self.name = self._pref.ref.name
        self.version = _VersionRepr(self._pref.ref.version).major()
        self.user = self.channel = self.package_id = None
        self.recipe_revision = None

    def full_recipe_mode(self):
        self.name = self._pref.ref.name
        self.version = self._pref.ref.version
        self.user = self._pref.ref.user
        self.channel = self._pref.ref.channel
        self.package_id = None
        self.recipe_revision = None

    def full_package_mode(self):
        self.name = self._pref.ref.name
        self.version = self._pref.ref.version
        self.user = self._pref.ref.user
        self.channel = self._pref.ref.channel
        self.package_id = self._pref.package_id
        self.recipe_revision = None

    def full_mode(self):
        self.name = self._pref.ref.name
        self.version = self._pref.ref.version
        self.user = self._pref.ref.user
        self.channel = self._pref.ref.channel
        self.package_id = self._pref.package_id
        self.recipe_revision = self._pref.ref.revision

    recipe_revision_mode = full_mode  # to not break everything and help in upgrade


class RequirementsInfo(UserRequirementsDict):

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
        return "\n".join(sorted(result))

    def unrelated_mode(self):
        self.clear()

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

    def dumps(self):
        ref = RecipeReference(self._name, self._version, self._user, self._channel, self._revision)
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
        return '\n'.join(r.dumps() for r in self._refs)

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


class ConanInfo(object):

    def copy(self):
        """ Useful for build_id implementation
        """
        result = ConanInfo()
        result.invalid = self.invalid
        result.settings = self.settings.copy()
        result.options = self.options.copy_conaninfo_options()
        result.requires = self.requires.copy()
        result.build_requires = self.build_requires.copy()
        result.python_requires = self.python_requires.copy()
        return result

    @staticmethod
    def create(settings, options, reqs_info, build_requires_info,
               python_requires, default_python_requires_id_mode):
        result = ConanInfo()
        result.invalid = None
        result.full_settings = settings
        result.settings = settings.copy()
        result.options = options.copy_conaninfo_options()
        result.requires = reqs_info
        result.build_requires = build_requires_info
        result.python_requires = PythonRequiresInfo(python_requires, default_python_requires_id_mode)
        return result

    @staticmethod
    def loads(text):
        # This is used for search functionality, search prints info from this file
        parser = ConfigParser(text, ["settings", "options", "requires"],
                              raise_unexpected_field=False)
        result = ConanInfo()
        result.invalid = None
        result.settings = Values.loads(parser.settings)
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

    def package_id(self):
        """ The package_id of a conans is the sha1 of its specific requirements,
        options and settings
        """
        result = [self.settings.sha,
                  "[options]"]
        options_dumps = self.options.dumps()
        if options_dumps:
            result.append(options_dumps)
        result.append("[requires]")
        requires_dumps = self.requires.dumps()
        if requires_dumps:
            result.append(requires_dumps)
        if self.python_requires:
            result.append("[python_requires]")
            result.append(self.python_requires.dumps())
        if self.build_requires:
            result.append("[build_requires]")
            result.append(self.build_requires.dumps())
        if hasattr(self, "conf"):
            result.append(self.conf.sha)
        result.append("")  # Append endline so file ends with LF
        text = '\n'.join(result)
        package_id = sha1(text.encode())
        try:
            self.options.validate()
        except ConanException as e:
            self.invalid = BINARY_INVALID, str(e)
        return package_id

    def serialize_min(self):
        """
        This info will be shown in search results.
        """
        conan_info_json = {"settings": dict(self.settings.serialize()),
                           "options": dict(self.options.serialize())["options"],
                           "requires": self.requires.serialize()
                           }
        return conan_info_json

    def header_only(self):
        self.settings.clear()
        self.options.clear()
        self.requires.clear()

    def apple_clang_compatible(self):
        # https://github.com/conan-io/conan/pull/10797
        # apple-clang compiler version 13 will be compatible with 13.0
        if not self.settings.compiler or \
           (self.settings.compiler != "apple-clang" and self.settings.compiler.version != "13"):
            return

        compatible = self.clone()
        compatible.settings.compiler.version = "13.0"
        return compatible
