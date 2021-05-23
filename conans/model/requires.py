from collections import OrderedDict

from conans.errors import ConanException
from conans.model.pkg_type import PackageType
from conans.model.ref import ConanFileReference


class Requirement:
    """ A user definition of a requires in a conanfile
    """
    def __init__(self, ref, include=True, link=True, build=False, run=None, public=True,
                 transitive_headers=None, test=False, package_id_mode=None, force=None):
        # By default this is a generic library requirement
        self.ref = ref
        self.include = include  # This dependent node has headers that must be -I<include-path>
        self.link = link
        self.build = build  # This dependent node is a build tool that is executed at build time only
        self.run = run  # node contains executables, shared libs or data necessary at host run time
        self.public = public  # Even if not linked or visible, the node is unique, can conflict
        self.transitive_headers = transitive_headers
        self.test = test
        self.package_id_mode = package_id_mode
        self.force = force

    def __repr__(self):
        return repr(self.__dict__)

    def copy(self):
        return Requirement(self.ref, self.include, self.link, self.build, self.run, self.public,
                           self.transitive_headers)

    @property
    def version_range(self):
        """ returns the version range expression, without brackets []
        or None if it is not an expression
        """
        version = self.ref.version
        if version.startswith("[") and version.endswith("]"):
            return version[1:-1]

    def compute_run(self, node):
        """ if the run=None, it means it can be deduced from the shared option of the dependency
        """
        if self.run is not None:
            return
        up_shared = str(node.conanfile.options.get_safe("shared"))
        if up_shared == "True":
            self.run = True
        elif up_shared == "False":
            self.run = False

    def __hash__(self):
        return hash((self.ref.name, self.build))

    def __eq__(self, other):
        return (self.ref.name == other.ref.name and self.build == other.build and
                ((self.include and other.include) or
                 (self.link and other.link) or
                 (self.run and other.run) or
                 (self.public and other.public) or
                 (self.ref == other.ref)))

    def __ne__(self, other):
        return not self.__eq__(other)

    def transform_downstream(self, pkg_type, require, dep_pkg_type):
        """
        consumer(not known type) -> requires(self) -> pkg_type -> require -> dep_pkg_type
        compute new Requirement to be applied to "consumer" translating the effect of the dependency
        to such "consumer".
        Result can be None if nothing is to be propagated
        """
        if require.build:  # Build-requires do not propagate anything
            return  # TODO: check this

        if require.public is False:
            # TODO: We could implement checks in case private is violated (e.g shared libs)
            return

        if self.build:  # Build-requires
            # If the above is shared or the requirement is explicit run=True
            if dep_pkg_type is PackageType.SHARED or dep_pkg_type is PackageType.RUN or require.run:
                downstream_require = Requirement(require.ref, include=False, link=False, build=True,
                                                 run=True, public=False,)
                return downstream_require
            return

        # Regular and test requires
        if dep_pkg_type is PackageType.SHARED or dep_pkg_type is PackageType.RUN:
            if pkg_type is PackageType.SHARED:
                downstream_require = Requirement(require.ref, include=False, link=False, run=True)
            elif pkg_type is PackageType.STATIC:
                downstream_require = Requirement(require.ref, include=False, link=True, run=True)
            elif pkg_type is PackageType.RUN:
                downstream_require = Requirement(require.ref, include=False, link=False, run=True)
            else:  # unknown
                assert pkg_type is PackageType.UNKNOWN
                # Consumers will need to find it at build time too
                downstream_require = Requirement(require.ref, include=True, link=True, run=True)
        elif dep_pkg_type is PackageType.STATIC:
            if pkg_type is PackageType.SHARED:
                downstream_require = Requirement(require.ref, include=False, link=False, run=False)
            elif pkg_type is PackageType.RUN:
                downstream_require = Requirement(require.ref, include=False, link=False, run=False)
            elif pkg_type is PackageType.STATIC:  # static
                downstream_require = Requirement(require.ref, include=False, link=True, run=False)
            else:  # unknown
                assert pkg_type is PackageType.UNKNOWN
                downstream_require = Requirement(require.ref, include=True, link=True, run=False)
        elif dep_pkg_type is PackageType.HEADER:
            downstream_require = Requirement(require.ref, include=False, link=False, run=False)
        else:
            # Unknown, default. This happens all the time while check_downstream as shared is unknown
            # FIXME
            downstream_require = require.copy()

        assert require.public, "at this point require should be public"

        if require.transitive_headers:
            downstream_require.include = True

        # If non-default, then the consumer requires has priority
        if self.public is False:
            downstream_require.public = False

        if self.include is False:
            downstream_require.include = False

        if self.link is False:
            downstream_require.link = False

        # TODO: Automatic assignment invalidates user possibility of overriding default
        # if required.run is not None:
        #    downstream_require.run = required.run

        if self.test:
            downstream_require.test = True

        return downstream_require


class RequirementDict:
    def __init__(self):
        self._requires = OrderedDict()  # {require: XXX}

    def __repr__(self):
        return repr(self._requires)

    def get(self, require):
        return self._requires.get(require)

    def set(self, require, value):
        # TODO: Might need to move to an update() for performance
        self._requires.pop(require, None)
        self._requires[require] = value

    def items(self):
        return self._requires.items()

    def values(self):
        return self._requires.values()


class UserRequirementsDict:
    """ user facing dict to allow access of dependencies by name
    """
    def __init__(self, data):
        self._data = data  # dict-like

    @staticmethod
    def _get_require(ref, **kwargs):
        assert isinstance(ref, str)
        if "/" in ref:
            ref = ConanFileReference.loads(ref)
        else:
            ref = ConanFileReference(ref, "unknown", "unknown", "unknown", validate=False)
        r = Requirement(ref, **kwargs)
        return r

    def get(self, ref, **kwargs):
        r = self._get_require(ref, **kwargs)
        return self._data.get(r)

    def __getitem__(self, name):
        r = self._get_require(name)
        return self._data[r]

    def __delitem__(self, name):
        r = self._get_require(name)
        del self._data[r]

    def items(self):
        return self._data.items()

    def __iter__(self):
        return iter(self._data.values())

    def __next__(self):
        return next(self._data.values())


class BuildRequirements:
    # Just a wrapper around requires for backwards compatibility with self.build_requires() syntax
    def __init__(self, requires):
        self._requires = requires

    def __call__(self, ref):
        self._requires.build_require(ref)


class TestRequirements:
    # Just a wrapper around requires for backwards compatibility with self.build_requires() syntax
    def __init__(self, requires):
        self._requires = requires

    def __call__(self, ref):
        self._requires.test_require(ref)


class Requirements:
    """ User definitions of all requires in a conanfile
    """
    def __init__(self, declared=None, declared_build=None, declared_test=None):
        self._requires = OrderedDict()
        # Construct from the class definitions
        if declared is not None:
            if isinstance(declared, str):
                declared = [declared, ]
            for item in declared:
                # Todo: Deprecate Conan 1.X definition of tuples, force to use method
                self.__call__(item)
        if declared_build is not None:
            if isinstance(declared_build, str):
                declared_build = [declared_build, ]
            for item in declared_build:
                self.build_require(item)
        if declared_test is not None:
            if isinstance(declared_test, str):
                declared_test = [declared_test, ]
            for item in declared_test:
                self.test_require(item)

    def values(self):
        return self._requires.values()

    # TODO: Plan the interface for smooth transition from 1.X
    def __call__(self, str_ref, **kwargs):
        assert isinstance(str_ref, str)
        ref = ConanFileReference.loads(str_ref)
        req = Requirement(ref, **kwargs)
        if self._requires.get(req):
            raise ConanException("Duplicated requirement: {}".format(ref))
        self._requires[req] = req

    def build_require(self, ref, raise_if_duplicated=True):
        # FIXME: This raise_if_duplicated is ugly, possibly remove
        ref = ConanFileReference.loads(ref)
        req = Requirement(ref, include=False, link=False, build=True, run=True, public=False,
                          package_id_mode=None)
        if raise_if_duplicated and self._requires.get(req):
            raise ConanException("Duplicated requirement: {}".format(ref))
        self._requires[req] = req

    def test_require(self, ref):
        ref = ConanFileReference.loads(ref)
        req = Requirement(ref, include=True, link=True, build=False, run=None, public=False,
                          test=True, package_id_mode=None)
        if self._requires.get(req):
            raise ConanException("Duplicated requirement: {}".format(ref))
        self._requires[req] = req

    def __repr__(self):
        return repr(self._requires.values())
