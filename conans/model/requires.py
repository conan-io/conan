from collections import OrderedDict

import six

from conans.errors import ConanException
from conans.model.ref import ConanFileReference
from conans.util.env_reader import get_env


class Requirement(object):
    """ A reference to a package plus some attributes of how to
    depend on that package
    """
    def __init__(self, ref, private=False, override=False):
        """
        param override: True means that this is not an actual requirement, but something to
                        be passed upstream and override possible existing values
        """
        self.ref = ref
        self.range_ref = ref
        self.override = override
        self.private = private
        self.build_require = False
        self.build_require_context = None
        self.force_host_context = False
        self._locked_id = None

    def lock(self, locked_ref, locked_id):
        assert locked_ref is not None
        # When a requirement is locked it doesn't has ranges
        self.ref = self.range_ref = locked_ref
        self._locked_id = locked_id  # And knows the ID of the locked node that is pointing to

    @property
    def locked_id(self):
        return self._locked_id

    @property
    def version_range(self):
        """ returns the version range expression, without brackets []
        or None if it is not an expression
        """
        version = self.range_ref.version
        if version.startswith("[") and version.endswith("]"):
            return version[1:-1]

    @property
    def alias(self):
        version = self.ref.version
        if version.startswith("(") and version.endswith(")"):
            return ConanFileReference(self.ref.name, version[1:-1], self.ref.user, self.ref.channel,
                                      self.ref.revision, validate=False)

    @property
    def is_resolved(self):
        """ returns True if the version_range reference has been already resolved to a
        concrete reference
        """
        return self.ref != self.range_ref

    def __repr__(self):
        return ("%s" % str(self.ref) + (" P" if self.private else ""))

    def __eq__(self, other):
        return (self.override == other.override and
                self.ref == other.ref and
                self.private == other.private)

    def __ne__(self, other):
        return not self.__eq__(other)


class Requirements(OrderedDict):
    """ {name: Requirement} in order, e.g. {"Hello": Requirement for Hello}
    """

    def __init__(self, *args):
        super(Requirements, self).__init__()
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
                self.add(ref, private=private, override=override)
            else:
                self.add(v)

    def copy(self):
        """ We need a custom copy as the normal one requires __init__ to be
        properly defined. This is not a deep-copy, in fact, requirements in the dict
        are changed by RangeResolver, and are propagated upstream
        """
        result = Requirements()
        for name, req in self.items():
            result[name] = req
        return result

    def iteritems(self):  # FIXME: Just a trick to not change default testing conanfile for py3
        return self.items()

    def add(self, reference, private=False, override=False):
        """ to define requirements by the user in text, prior to any propagation
        """
        if reference is None:
            return
        assert isinstance(reference, six.string_types)
        ref = ConanFileReference.loads(reference)
        self.add_ref(ref, private, override)

    def add_ref(self, ref, private=False, override=False):
        name = ref.name

        new_requirement = Requirement(ref, private, override)
        old_requirement = self.get(name)
        if old_requirement and old_requirement != new_requirement:
            if old_requirement.override:
                # If this is a consumer package with requirements() method,
                # conan install . didn't add the requires yet, so they couldnt be overriden at
                # the override() method, override now
                self[name] = Requirement(old_requirement.ref, private, override)
            else:
                raise ConanException("Duplicated requirement %s != %s"
                                     % (old_requirement, new_requirement))
        else:
            self[name] = new_requirement

    def override(self, ref):
        name = ref.name
        old_requirement = self.get(ref.name)
        if old_requirement is not None:
            self[name] = Requirement(ref, private=False, override=False)
        else:
            self[name] = Requirement(ref, private=False, override=True)

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

        error_on_override = get_env("CONAN_ERROR_ON_OVERRIDE", False)

        new_reqs = down_reqs.copy()
        if own_ref:
            new_reqs.pop(own_ref.name, None)
        for name, req in self.items():
            if req.private:
                continue
            if name in down_reqs and not req.locked_id:
                other_req = down_reqs[name]
                # update dependency
                other_ref = other_req.ref
                if other_ref and other_ref != req.ref:
                    down_reference_str = str(down_ref) if down_ref else ""
                    msg = "%s: requirement %s overridden by %s to %s " \
                          % (own_ref, req.ref, down_reference_str or "your conanfile", other_ref)

                    if error_on_override and not other_req.override:
                        raise ConanException(msg)

                    output.warn(msg)
                    req.ref = other_ref
                    # FIXME: We should compute the intersection of version_ranges
                    if req.version_range and not other_req.version_range:
                        req.range_ref = other_req.range_ref  # Override

            new_reqs[name] = req
        return new_reqs

    def __call__(self, reference, private=False, override=False, **kwargs):
        self.add(reference, private, override)

    def __repr__(self):
        result = []
        for req in self.values():
            result.append(str(req))
        return '\n'.join(result)
