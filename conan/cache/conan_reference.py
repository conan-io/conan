from conans.errors import ConanException
from conans.model.package_ref import PkgReference
from conans.model.recipe_ref import RecipeReference
from conans.model.ref import ConanFileReference


class ConanReference:
    def __init__(self, *args):
        if isinstance(args[0], ConanFileReference):
            ref = args[0]
            self._name = ref.name
            self._version = ref.version
            self._user = ref.user
            self._channel = ref.channel
            self._rrev = ref.revision
            self._pkgid = None
            self._prev = None
        elif isinstance(args[0], PkgReference):
            ref = args[0]
            self._name = ref.ref.name
            self._version = ref.ref.version
            self._user = ref.ref.user
            self._channel = ref.ref.channel
            self._rrev = ref.ref.revision
            self._pkgid = ref.package_id
            self._prev = ref.revision
        elif isinstance(args[0], RecipeReference):
            ref = args[0]
            self._name = ref.name
            self._version = ref.version
            self._user = ref.user
            self._channel = ref.channel
            self._rrev = ref.revision
            self._pkgid = None
            self._prev = None
        elif len(args) == 7 and all(isinstance(arg, str) or arg is None for arg in args):
            self._name = args[0]
            self._version = args[1]
            self._user = args[2]
            self._channel = args[3]
            self._rrev = args[4]
            self._pkgid = args[5]
            self._prev = args[6]
        else:
            raise ConanException("Invalid arguments for ConanReference")

    @property
    def name(self):
        return self._name

    @property
    def version(self):
        return self._version

    @property
    def user(self):
        return self._user

    @property
    def channel(self):
        return self._channel

    @property
    def rrev(self):
        return self._rrev

    @property
    def pkgid(self):
        return self._pkgid

    @property
    def prev(self):
        return self._prev

    def as_package_reference(self):
        return PkgReference.loads(self.full_reference)

    def as_conanfile_reference(self):
        return ConanFileReference.loads(self.full_reference, validate=False)

    @property
    def reference(self):
        if self.user is None and self.channel is None:
            return f'{self.name}/{self.version}'
        return f'{self.name}/{self.version}@{self.user}/{self.channel}'

    @property
    def full_reference(self):
        result = f'{self.reference}#{self.rrev}'
        if self.pkgid:
            result += f":{self.pkgid}"
            if self.prev:
                result += f'#{self.prev}'
        return result

    @property
    def recipe_reference(self):
        return f'{self.reference}#{self.rrev}'
