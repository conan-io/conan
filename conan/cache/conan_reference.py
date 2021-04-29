import re
from collections import namedtuple

from conans.errors import ConanException
from conans.model.ref import ConanFileReference, PackageReference


class ConanReference(namedtuple("ConanFileReference", "name version user channel rrev pkgid prev")):
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
            raise ConanException("Invalid type")
        return obj

    @property
    # TODO: use coherent names for different parts of name/version@user/channel#rrev:pkgid#prev
    def reference(self):
        if self.user is None and self.channel is None:
            return f'{self.name}/{self.version}'
        return f'{self.name}/{self.version}@{self.user}/{self.channel}'

    def full_reference(self):
        if self.prev:
            return f'{self.reference}#{self.rrev}:{self.pkgid}#{self.prev}'
        else:
            return f'{self.reference}#{self.rrev}'

    @staticmethod
    def loads(text):
        def get_field(reference, start, index):
            try:
                found = re.findall(f'{start}(.*?)(:|@|#|/|$)', reference)
                try:
                    ret = found[index][0]
                except IndexError:
                    return None
            except AttributeError:
                return None
            return ret

        name = get_field(text, "", 0)
        version = get_field(text, "/", 0)
        if "@" in text:
            user = get_field(text, "@", 0)
            channel = get_field(text, "/", 1)
        else:
            user = None
            channel = None
        rrev = get_field(text, "#", 0)
        pkgid = get_field(text, ":", 0)
        prev = get_field(text, "#", 1)
        ref = ConanReference(name, version, user, channel, rrev, pkgid, prev)
        return ref
