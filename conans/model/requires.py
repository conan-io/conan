from collections import OrderedDict

from conans.errors import ConanException
from conans.model.pkg_type import PackageType
from conans.model.ref import ConanFileReference


class Requirement:
    """ A user definition of a requires in a conanfile
    """
    def __init__(self, ref, *, headers=True, libs=True, build=False, run=None, visible=True,
                 transitive_headers=None, transitive_libs=None, test=False, package_id_mode=None,
                 force=False, override=False, direct=True):
        # * prevents the usage of more positional parameters, always ref + **kwargs
        # By default this is a generic library requirement
        self.ref = ref
        self.headers = headers  # This dependent node has headers that must be -I<headers-path>
        self.libs = libs
        self.build = build  # This dependent node is a build tool that is executed at build time only
        self.run = run  # node contains executables, shared libs or data necessary at host run time
        self.visible = visible  # Even if not libsed or visible, the node is unique, can conflict
        self.transitive_headers = transitive_headers
        self.transitive_libs = transitive_libs
        self.test = test
        self.package_id_mode = package_id_mode
        self.force = force
        self.override = override
        self.direct = direct

    def __repr__(self):
        return repr(self.__dict__)

    def copy_requirement(self):
        return Requirement(self.ref, headers=self.headers, libs=self.libs, build=self.build,
                           run=self.run, visible=self.visible,
                           transitive_headers=self.transitive_headers,
                           transitive_libs=self.transitive_libs)

    @property
    def version_range(self):
        """ returns the version range expression, without brackets []
        or None if it is not an expression
        """
        version = self.ref.version
        if version.startswith("[") and version.endswith("]"):
            return version[1:-1]

    @property
    def alias(self):
        version = self.ref.version
        if version.startswith("(") and version.endswith(")"):
            return ConanFileReference(self.ref.name, version[1:-1], self.ref.user, self.ref.channel,
                                      self.ref.revision, validate=False)

    def process_package_type(self, node):
        """ if the run=None, it means it can be deduced from the shared option of the dependency
        """
        if self.run is not None:
            return
        pkg_type = node.conanfile.package_type
        if pkg_type is PackageType.APP:
            # Change the default requires headers&libs to False for APPS
            self.headers = False
            self.libs = False
            self.run = True
        elif pkg_type is PackageType.SHARED:
            self.run = True
        elif pkg_type is PackageType.STATIC:
            self.run = False
        elif pkg_type is PackageType.HEADER:
            self.run = False
            self.libs = False
            self.headers = True

    def __hash__(self):
        return hash((self.ref.name, self.build))

    def __eq__(self, other):
        return (self.ref.name == other.ref.name and self.build == other.build and
                ((self.headers and other.headers) or
                 (self.libs and other.libs) or
                 (self.run and other.run) or
                 (self.visible and other.visible) or
                 (self.ref == other.ref)))

    def aggregate(self, other):
        """ when closing loop and finding the same dependency on a node, the information needs
        to be aggregated
        """
        assert self.build == other.build
        self.headers |= other.headers
        self.libs |= other.libs
        self.run = self.run or other.run
        self.visible |= other.visible
        # TODO: self.package_id_mode => Choose more restrictive?

    def transform_downstream(self, pkg_type, require, dep_pkg_type):
        """
        consumer(not known type) -> requires(self) -> pkg_type -> require -> dep_pkg_type
        compute new Requirement to be applied to "consumer" translating the effect of the dependency
        to such "consumer".
        Result can be None if nothing is to be propagated
        """
        if require.visible is False:
            # TODO: We could implement checks in case private is violated (e.g shared libs)
            return

        if require.build:  # public!
            # TODO: To discuss if this way of conflicting build_requires is actually useful or not
            downstream_require = Requirement(require.ref, headers=False, libs=False, build=True,
                                             run=False, visible=True, direct=False)
            return downstream_require

        if self.build:  # Build-requires
            # If the above is shared or the requirement is explicit run=True
            if dep_pkg_type is PackageType.SHARED or require.run:
                downstream_require = Requirement(require.ref, headers=False, libs=False, build=True,
                                                 run=True, visible=False, direct=False)
                return downstream_require
            return

        # Regular and test requires
        if dep_pkg_type is PackageType.SHARED:
            if pkg_type is PackageType.SHARED:
                downstream_require = Requirement(require.ref, headers=False, libs=False, run=True)
            elif pkg_type is PackageType.STATIC:
                downstream_require = Requirement(require.ref, headers=False, libs=True, run=True)
            elif pkg_type is PackageType.APP:
                downstream_require = Requirement(require.ref, headers=False, libs=False, run=True)
            else:
                assert pkg_type is PackageType.UNKNOWN
                # TODO: This is undertested, changing it did not break tests
                downstream_require = require.copy_requirement()
        elif dep_pkg_type is PackageType.STATIC:
            if pkg_type is PackageType.SHARED:
                downstream_require = Requirement(require.ref, headers=False, libs=False, run=False)
            elif pkg_type is PackageType.STATIC:
                downstream_require = Requirement(require.ref, headers=False, libs=True, run=False)
            elif pkg_type is PackageType.APP:
                downstream_require = Requirement(require.ref, headers=False, libs=False, run=False)
            else:
                assert pkg_type is PackageType.UNKNOWN
                # TODO: This is undertested, changing it did not break tests
                downstream_require = require.copy_requirement()
        elif dep_pkg_type is PackageType.HEADER:
            downstream_require = Requirement(require.ref, headers=False, libs=False, run=False)
        else:
            # Unknown, default. This happens all the time while check_downstream as shared is unknown
            # FIXME
            downstream_require = require.copy_requirement()

        assert require.visible, "at this point require should be visible"

        if require.transitive_headers is not None:
            downstream_require.headers = require.transitive_headers

        if require.transitive_libs is not None:
            downstream_require.libs = require.transitive_libs

        # If non-default, then the consumer requires has priority
        if self.visible is False:
            downstream_require.visible = False

        if self.headers is False:
            downstream_require.headers = False

        if self.libs is False:
            downstream_require.libs = False

        # TODO: Automatic assignment invalidates user possibility of overriding default
        # if required.run is not None:
        #    downstream_require.run = required.run

        if self.test:
            downstream_require.test = True

        downstream_require.direct = False
        return downstream_require


class BuildRequirements:
    # Just a wrapper around requires for backwards compatibility with self.build_requires() syntax
    def __init__(self, requires):
        self._requires = requires

    def __call__(self, ref, package_id_mode=None, visible=False):
        # TODO: Check which arguments could be user-defined
        self._requires.build_require(ref, package_id_mode=package_id_mode, visible=visible)


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

    def build_require(self, ref, raise_if_duplicated=True, package_id_mode=None, visible=False):
        # FIXME: This raise_if_duplicated is ugly, possibly remove
        ref = ConanFileReference.loads(ref)
        req = Requirement(ref, headers=False, libs=False, build=True, run=True, visible=visible,
                          package_id_mode=package_id_mode)
        if raise_if_duplicated and self._requires.get(req):
            raise ConanException("Duplicated requirement: {}".format(ref))
        self._requires[req] = req

    def override(self, ref):
        name = ref.name
        req = Requirement(ref)
        old_requirement = self._requires.get(req)
        if old_requirement is not None:
            req.force = True
            self._requires[req] = req
        else:
            req.override = True
            self._requires[req] = req

    def test_require(self, ref):
        ref = ConanFileReference.loads(ref)
        req = Requirement(ref, headers=True, libs=True, build=False, run=None, visible=False,
                          test=True, package_id_mode=None)
        if self._requires.get(req):
            raise ConanException("Duplicated requirement: {}".format(ref))
        self._requires[req] = req

    def __repr__(self):
        return repr(self._requires.values())
