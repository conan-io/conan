from conans.client.graph.graph import BINARY_INVALID
from conans.errors import ConanException
from conans.model.dependencies import UserRequirementsDict
from conans.model.options import Options
from conans.model.package_ref import PkgReference
from conans.model.recipe_ref import RecipeReference, Version
from conans.util.config_parser import ConfigParser
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

    def full_mode(self):
        for r in self._data.values():
            r.full_mode()

    recipe_revision_mode = full_mode  # to not break everything and help in upgrade


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

    def full_mode(self):
        self._name = self._ref.name
        self._version = self._ref.version
        self._user = self._ref.user
        self._channel = self._ref.channel
        self._revision = self._ref.revision

    recipe_revision_mode = full_mode

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

    def full_mode(self):
        for r in self._refs:
            r.full_mode()

    recipe_revision_mode = full_mode


class BinaryInfo:
    """ class to load a conaninfo.txt and be able to use it for the 'conan list packages'
    command (previos conan search <ref>). As the server will transmit the whole
    conaninfo.txt contents, it will be used in the client
    """
    def __init__(self, settings, options, requires, build_requires):
        self.settings = settings
        self.options = options
        self.requires = requires
        self.build_requires = build_requires

    @staticmethod
    def loads(text):
        # This is used for search functionality, search prints info from this file
        parser = ConfigParser(text, ["settings", "options", "requires"],
                              raise_unexpected_field=False)

        def _loads_settings(settings_text):
            settings_result = []
            for line in settings_text.splitlines():
                if not line.strip():
                    continue
                name, value = line.split("=", 1)
                settings_result.append((name.strip(), value.strip()))
            return settings_result

        settings = _loads_settings(parser.settings)
        options = Options.loads(parser.options)
        # Requires after load are not used for any purpose, CAN'T be used, they are not correct
        # FIXME: remove this uglyness
        requires = parser.requires.splitlines() if parser.requires else []
        requires = [r for r in requires if r]
        return BinaryInfo(settings, options, requires, None)

    def serialize_min(self):
        """
        This info will be shown in search results.
        """
        # self.settings is already a simple serialized list, it has been loaded from conaninfo.txt
        conan_info_json = {"settings": dict(self.settings),
                           "options": dict(self.options.serialize())["options"],
                           "requires": self.requires
                           }
        return conan_info_json


class ConanInfo:

    def __init__(self, settings=None, options=None, reqs_info=None, build_requires_info=None,
                 python_requires=None):
        self.invalid = None
        self.settings = settings
        self.options = options
        self.requires = reqs_info
        self.build_requires = build_requires_info
        self.python_requires = python_requires

    def clone(self):
        """ Useful for build_id implementation and for compatibility()
        """
        result = ConanInfo()
        result.invalid = self.invalid
        result.settings = self.settings.copy()
        result.options = self.options.copy_conaninfo_options()
        result.requires = self.requires.copy()
        result.build_requires = self.build_requires.copy()
        result.python_requires = self.python_requires.copy()
        return result

    def dumps(self):
        """
        Get all the information contained in settings, options, requires,
        python_requires, build_requires and conf.
        :return: `str` with the result of joining all the information, e.g.,
            `"[settings]\nos=Windows\n[options]\n[requires]\n"`
        """
        result = ["[settings]"]
        settings_dumps = self.settings.dumps()
        if settings_dumps:
            result.append(settings_dumps)
        result.append("[options]")
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
            result.append(self.conf.dumps())
        result.append("")  # Append endline so file ends with LF
        return '\n'.join(result)

    def package_id(self):
        """
        Get the `package_id` that is the result of applying the has function SHA-1 to the
        `self.dumps()` return.
        :return: `str` the `package_id`, e.g., `"040ce2bd0189e377b2d15eb7246a4274d1c63317"`
        """
        text = self.dumps()
        package_id = sha1(text.encode())
        return package_id

    def header_only(self):
        self.settings.clear()
        self.options.clear()
        self.requires.clear()

    def validate(self):
        # If the options are not fully defined, this is also an invalid case
        try:
            self.options.validate()
        except ConanException as e:
            self.invalid = BINARY_INVALID, str(e)

        try:
            self.settings.validate()
        except ConanException as e:
            self.invalid = BINARY_INVALID, str(e)
