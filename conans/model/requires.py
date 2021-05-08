from collections import OrderedDict

from conans.model.ref import ConanFileReference


class Requirement:
    """ A user definition of a requires in a conanfile
    """
    def __init__(self, ref, include=True, link=True, build=False, run=None, public=True,
                 transitive_headers=None):
        # TODO: Decompose build_require in its traits
        self.ref = ref
        self.include = include  # This dependent node has headers that must be -I<include-path>
        self.link = link
        self.build = build  # This dependent node is a build tool that is executed at build time only
        self.run = run  # node contains executables, shared libs or data necessary at host run time
        self.public = public  # Even if not linked or visible, the node is unique, can conflict
        self.transitive_headers = transitive_headers

    def __repr__(self):
        return repr((self.ref, self.include, self.link, self.build, self.run, self.public,
                    self.transitive_headers))

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
        return self.ref.name == other.ref.name and self.build == other.build and \
               ((self.include and other.include) or
                (self.link and other.link) or
                (self.run and other.run) or
                (self.public and other.public))

    def __ne__(self, other):
        return not self.__eq__(other)


class BuildRequirements:
    # Just a wrapper around requires for backwards compatibility with self.build_requires() syntax
    def __init__(self, requires):
        self._requires = requires

    def __call__(self, ref):
        self._requires(ref, build_require=True)


class Requirements:
    """ User definitions of all requires in a conanfile
    """
    def __init__(self, declared=None, declared_build=None):
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
                # Todo: Deprecate Conan 1.X definition of tuples, force to use method
                self.__call__(item, build_require=True)

    def values(self):
        return self._requires.values()

    def __call__(self, str_ref, build_require=False, transitive_headers=None, public=None):
        assert isinstance(str_ref, str)
        ref = ConanFileReference.loads(str_ref)
        if build_require:
            req = Requirement(ref, include=False, link=False, build=True, run=True, public=False)
        else:
            if public is None:  # TODO: This pattern is a bit ugly
                req = Requirement(ref, transitive_headers=transitive_headers)
            else:
                req = Requirement(ref, transitive_headers=transitive_headers, public=public)
        self._requires[req] = req

    def __repr__(self):
        return repr(self._requires.values())
