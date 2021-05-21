import re
from collections import namedtuple

from conans.errors import ConanException
from conans.model.ref import ConanFileReference, PackageReference


class ConanReference(namedtuple("ConanReference", "name version user channel rrev pkgid prev")):
    def __new__(cls, *args):
        if isinstance(args[0], ConanFileReference):
            ref = args[0]
            obj = super(cls, ConanReference).__new__(cls, ref.name, ref.version, ref.user,
                                                     ref.channel, ref.revision, None, None)
        elif isinstance(args[0], PackageReference):
            ref = args[0]
            obj = super(cls, ConanReference).__new__(cls, ref.ref.name, ref.ref.version,
                                                     ref.ref.user, ref.ref.channel, ref.ref.revision,
                                                     ref.id, ref.revision)
        elif len(args) == 7 and all(isinstance(arg, str) or arg is None for arg in args):
            obj = super(cls, ConanReference).__new__(cls, *args)
        else:
            raise ConanException("Invalid arguments for ConanReference")
        return obj

    def as_package_reference(self):
        return PackageReference.loads(self.full_reference, validate=False)

    def as_conanfile_reference(self):
        return ConanFileReference.loads(self.full_reference, validate=False)

    @property
    def reference(self):
        if self.user is None and self.channel is None:
            return f'{self.name}/{self.version}'
        return f'{self.name}/{self.version}@{self.user}/{self.channel}'

    @property
    def full_reference(self):
        if self.prev:
            return f'{self.reference}#{self.rrev}:{self.pkgid}#{self.prev}'
        else:
            return f'{self.reference}#{self.rrev}'
