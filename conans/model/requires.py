from collections import OrderedDict
from conans.errors import ConanException
from conans.model.ref import ConanFileReference
import six


class Requirement(object):
    """ A reference to a package plus some attributes of how to
    depend on that package
    """
    def __init__(self, conan_reference, private=False, override=False, dev=False):
        """
        param override: True means that this is not an actual requirement, but something to
                        be passed upstream and override possible existing values
        param private: True means that this requirement will be somewhat embedded (like
                       a static lib linked into a shared lib), so it is not required to link
        param dev: True means that this requirement is only needed at dev time, e.g. only
                    needed for building or testing, but not affects the package hash at all
        """
        self.conan_reference = conan_reference
        self.range_reference = conan_reference
        self.private = private
        self.override = override
        self.dev = dev

    @property
    def version_range(self):
        """ returns the version range expression, without brackets []
        or None if it is not an expression
        """
        version = self.range_reference.version
        if version.startswith("[") and version.endswith("]"):
            return version[1:-1]

    @property
    def is_resolved(self):
        """ returns True if the version_range reference has been already resolved to a
        concrete reference
        """
        return self.conan_reference != self.range_reference

    def __repr__(self):
        return ("%s" % str(self.conan_reference) + (" P" if self.private else ""))

    def __eq__(self, other):
        return (self.override == other.override and
                self.conan_reference == other.conan_reference and
                self.private == other.private and
                self.dev == other.dev)

    def __ne__(self, other):
        return not self.__eq__(other)


class Requirements(OrderedDict):
    """ {name: Requirement} in order, e.g. {"Hello": Requirement for Hello}
    """

    def __init__(self, *args):
        super(Requirements, self).__init__()
        self.allow_dev = False
        for v in args:
            if isinstance(v, tuple):
                override = private = dev = False
                ref = v[0]
                for elem in v[1:]:
                    if elem == "override":
                        override = True
                    elif elem == "private":
                        private = True
                    else:
                        raise ConanException("Unknown requirement config %s" % elem)
                self.add(ref, private=private, override=override, dev=dev)
            else:
                self.add(v)

    def add_dev(self, *args):
        for v in args:
            if isinstance(v, tuple):
                override = private = False
                ref = v[0]
                for elem in v[1:]:
                    if elem == "override":
                        override = True
                    elif elem == "private":
                        private = True
                    else:
                        raise ConanException("Unknown requirement config %s" % elem)
                self.add(ref, private=private, override=override, dev=True)
            else:
                self.add(v, dev=True)

    def copy(self):
        """ We need a custom copy as the normal one requires __init__ to be
        properly defined. This is not a deep-copy, in fact, requirements in the dict
        are changed by RequireResolver, and are propagated upstream
        """
        result = Requirements()
        for name, req in self.items():
            result[name] = req
        return result

    def iteritems(self):  # FIXME: Just a trick to not change default testing conanfile for py3
        return self.items()

    def add(self, reference, private=False, override=False, dev=False):
        """ to define requirements by the user in text, prior to any propagation
        """
        assert isinstance(reference, six.string_types)
        if dev and not self.allow_dev:
            return

        conan_reference = ConanFileReference.loads(reference)
        name = conan_reference.name

        new_requirement = Requirement(conan_reference, private, override, dev)
        old_requirement = self.get(name)
        if old_requirement and old_requirement != new_requirement:
            raise ConanException("Duplicated requirement %s != %s"
                                 % (old_requirement, new_requirement))
        else:
            self[name] = new_requirement

    def update(self, down_reqs, output, own_ref, down_ref):
        """ Compute actual requirement values when downstream values are defined
        param down_reqs: the current requirements as coming from downstream to override
                         current requirements
        param own_ref: ConanFileReference of the current conanfile
        param down_ref: ConanFileReference of the downstream that is overriding values or None
        return: new Requirements() value to be passed upstream
        """

        assert isinstance(down_reqs, Requirements)
        assert isinstance(own_ref, ConanFileReference) if own_ref else True
        assert isinstance(down_ref, ConanFileReference) if down_ref else True

        new_reqs = down_reqs.copy()
        if own_ref:
            new_reqs.pop(own_ref.name, None)
        for name, req in self.items():
            if req.private or req.dev:
                continue
            if name in down_reqs:
                other_req = down_reqs[name]
                # update dependency
                other_ref = other_req.conan_reference
                if other_ref and other_ref != req.conan_reference:
                    output.info("%s requirement %s overriden by %s to %s "
                                % (own_ref, req.conan_reference, down_ref or "your conanfile",
                                   other_ref))
                    req.conan_reference = other_ref

            new_reqs[name] = req
        return new_reqs

    def __call__(self, conan_reference, private=False, override=False, dev=False):
        self.add(conan_reference, private, override, dev)

    def __repr__(self):
        result = []
        for req in self.values():
            result.append(str(req))
        return '\n'.join(result)
