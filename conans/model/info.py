from conans.errors import ConanException
from conans.model.env_info import EnvValues
from conans.model.options import OptionsValues
from conans.model.ref import PackageReference
from conans.model.scope import Scopes
from conans.model.values import Values
from conans.util.config_parser import ConfigParser
from conans.util.files import load
from conans.util.sha import sha1


class RequirementInfo(object):
    def __init__(self, value_str, indirect=False):
        """ parse the input into fields name, version...
        """
        ref = PackageReference.loads(value_str)
        self.package = ref
        self.full_name = ref.conan.name
        self.full_version = ref.conan.version
        self.full_user = ref.conan.user
        self.full_channel = ref.conan.channel
        self.full_package_id = ref.package_id

        # sha values
        if indirect:
            self.unrelated_mode()
        else:
            self.semver()

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
        return "/".join([str(n) for n in [self.name, self.version, self.user, self.channel,
                                          self.package_id]])

    def serialize(self):
        return str(self.package)

    @staticmethod
    def deserialize(data):
        ret = RequirementInfo(data)
        return ret

    def unrelated_mode(self):
        self.name = self.version = self.user = self.channel = self.package_id = None

    def semver_mode(self):
        self.name = self.full_name
        self.version = self.full_version.stable()
        self.user = self.channel = self.package_id = None

    semver = semver_mode

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
    def __init__(self, requires, non_devs_requirements):
        # {PackageReference: RequirementInfo}
        self._non_devs_requirements = non_devs_requirements
        self._data = {r: RequirementInfo(str(r)) for r in requires}

    def copy(self):
        return RequirementsInfo(self._data.keys(), self._non_devs_requirements.copy()
                                if self._non_devs_requirements else None)

    def clear(self):
        self._data = {}

    def remove(self, *args):
        for name in args:
            del self._data[self._get_key(name)]

    def add(self, indirect_reqs):
        """ necessary to propagate from upstream the real
        package requirements
        """
        for r in indirect_reqs:
            self._data[r] = RequirementInfo(str(r), indirect=True)

    def refs(self):
        """ used for updating downstream requirements with this
        """
        return list(self._data.keys())

    def _get_key(self, item):
        for reference in self._data:
            if reference.conan.name == item:
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
        return [r.conan.name for r in self._data.keys()]

    @property
    def sha(self):
        result = []
        # Remove requirements without a name, i.e. indirect transitive requirements
        data = {k: v for k, v in self._data.items() if v.name}
        if self._non_devs_requirements is None:
            for key in sorted(data):
                result.append(data[key].sha)
        else:
            for key in sorted(data):
                non_dev = key.conan.name in self._non_devs_requirements
                if non_dev:
                    result.append(data[key].sha)
        return sha1('\n'.join(result).encode())

    def dumps(self):
        result = []
        for ref in sorted(self._data):
            dumped = self._data[ref].dumps()
            if dumped:
                dev = (self._non_devs_requirements is not None and
                       ref.conan.name not in self._non_devs_requirements)
                if dev:
                    dumped += " DEV"
                result.append(dumped)
        return "\n".join(result)

    def serialize(self):
        return {str(ref): requinfo.serialize() for ref, requinfo in self._data.items()}

    @staticmethod
    def deserialize(data):
        ret = RequirementsInfo({}, None)
        for ref, requinfo in data.items():
            ref = PackageReference.loads(ref)
            ret._data[ref] = RequirementInfo.deserialize(requinfo)
        return ret

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


class RequirementsList(list):
    @staticmethod
    def loads(text):
        return RequirementsList.deserialize(text.splitlines())

    def dumps(self):
        return "\n".join(self.serialize())

    def serialize(self):
        return [str(r) for r in sorted(self)]

    @staticmethod
    def deserialize(data):
        return RequirementsList([PackageReference.loads(line) for line in data])


class ConanInfo(object):

    def copy(self):
        """ Useful for build_id implementation
        """
        result = ConanInfo()
        result.settings = self.settings.copy()
        result.options = self.options.copy()
        result.requires = self.requires.copy()
        result._non_devs_requirements = self._non_devs_requirements
        return result

    @staticmethod
    def create(settings, options, requires, indirect_requires, non_devs_requirements):
        result = ConanInfo()
        result.full_settings = settings
        result.settings = settings.copy()
        result.full_options = options
        result.options = options.copy()
        result.options.clear_indirect()
        result.full_requires = RequirementsList(requires)
        result.requires = RequirementsInfo(requires, non_devs_requirements)
        result.scope = None
        result.requires.add(indirect_requires)
        result.full_requires.extend(indirect_requires)
        result.recipe_hash = None
        result._non_devs_requirements = non_devs_requirements  # Can be None
        result.env_values = EnvValues()
        return result

    @staticmethod
    def loads(text):
        parser = ConfigParser(text, ["settings", "full_settings", "options", "full_options",
                                     "requires", "full_requires", "scope", "recipe_hash",
                                     "env"], raise_unexpected_field=False)
        result = ConanInfo()
        result.settings = Values.loads(parser.settings)
        result.full_settings = Values.loads(parser.full_settings)
        result.options = OptionsValues.loads(parser.options)
        result.full_options = OptionsValues.loads(parser.full_options)
        result.full_requires = RequirementsList.loads(parser.full_requires)
        result.requires = RequirementsInfo(result.full_requires, None)
        result.recipe_hash = parser.recipe_hash or None

        # TODO: Missing handling paring of requires, but not necessary now
        result.scope = Scopes.loads(parser.scope)
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
        result.append("\n[scope]")
        if self.scope:
            result.append(indent(self.scope.dumps()))
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

    def package_id(self):
        """ The package_id of a conans is the sha1 of its specific requirements,
        options and settings
        """
        computed_id = getattr(self, "_package_id", None)
        if computed_id:
            return computed_id
        result = []
        result.append(self.settings.sha)
        # Only are valid requires for OPtions those Non-Dev who are still in requires

        self.options.filter_used(self.requires.pkg_names)
        result.append(self.options.sha(self._non_devs_requirements))
        result.append(self.requires.sha)
        self._package_id = sha1('\n'.join(result).encode())
        return self._package_id

    def serialize(self):
        conan_info_json = {"settings": self.settings.serialize(),
                           "full_settings": self.full_settings.serialize(),
                           "options": self.options.serialize(),
                           "full_options": self.full_options.serialize(),
                           "requires": self.requires.serialize(),
                           "full_requires": self.full_requires.serialize(),
                           "recipe_hash": self.recipe_hash}
        return conan_info_json

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
        self.requires.unrelated_mode()
