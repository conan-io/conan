from collections import namedtuple
import re
from conans.errors import ConanException, InvalidNameException
from conans.model.version import Version


class ConanName(object):
    _max_chars = 50
    _min_chars = 2
    _validation_pattern = re.compile("^[a-zA-Z0-9_][a-zA-Z0-9_\+\.-]{%s,%s}$"
                                     % (_min_chars - 1, _max_chars))

    @staticmethod
    def invalid_name_message(name):
        if len(name) > ConanName._max_chars:
            message = ("'%s' is too long. Valid names must contain at most %s characters."
                       % (name, ConanName._max_chars))
        elif len(name) < ConanName._min_chars:
            message = ("'%s' is too short. Valid names must contain at least %s characters."
                       % (name, ConanName._min_chars))
        else:
            message = ("'%s' is an invalid name. Valid names MUST begin with a "
                       "letter or number, have between %s-%s chars, including "
                       "letters, numbers, underscore, dot and dash"
                       % (name, ConanName._min_chars, ConanName._max_chars))
        raise InvalidNameException(message)

    @staticmethod
    def validate_user(username):
        if ConanName._validation_pattern.match(username) is None:
            ConanName.invalid_name_message(username)

    @staticmethod
    def validate_name(name, version=False):
        """Check for name compliance with pattern rules"""
        if name == "*":
            return
        if ConanName._validation_pattern.match(name) is None:
            if version and name.startswith("[") and name.endswith("]"):
                return
            ConanName.invalid_name_message(name)


class ConanFileReference(namedtuple("ConanFileReference", "name version user channel")):
    """ Full reference of a package recipes, e.g.:
    opencv/2.4.10@lasote/testing
    """
    whitespace_pattern = re.compile(r"\s+")
    sep_pattern = re.compile("@|/|#")
    revision = None

    def __new__(cls, name, version, user, channel, revision=None):
        """Simple name creation.
        @param name:        string containing the desired name
        @param validate:    checks for valid complex name. default True
        """
        ConanName.validate_name(name)
        ConanName.validate_name(version, True)
        ConanName.validate_name(user)
        ConanName.validate_name(channel)
        version = Version(version)
        obj = super(cls, ConanFileReference).__new__(cls, name, version, user, channel)
        if revision:
            ConanName.validate_name(revision)
        obj.revision = revision
        return obj

    def __eq__(self, value):
        if not value:
            return False
        return super(ConanFileReference, self).__eq__(value) and self.revision == value.revision

    def __ne__(self, other):
        """Overrides the default implementation (unnecessary in Python 3)"""
        return not self.__eq__(other)

    def __hash__(self):
        return hash((self.name, self.version, self.user, self.channel, self.revision))

    @staticmethod
    def loads(text):
        """ Parses a text string to generate a ConanFileReference object
        """
        text = ConanFileReference.whitespace_pattern.sub("", text)
        tokens = ConanFileReference.sep_pattern.split(text)
        try:
            if len(tokens) not in (4, 5):
                raise ValueError
            name, version, user, channel = tokens[0:4]
            revision = tokens[4] if len(tokens) == 5 else None
        except ValueError:
            raise ConanException("Wrong package recipe reference %s\nWrite something like "
                                 "OpenCV/1.0.6@user/stable" % text)
        obj = ConanFileReference(name, version, user, channel)
        obj.revision = revision
        return obj

    def __repr__(self):
        return "%s/%s@%s/%s" % (self.name, self.version, self.user, self.channel)

    def full_repr(self):
        str_rev = "#%s" % self.revision if self.revision else ""
        return "%s%s" % (str(self), str_rev)

    def copy_with_revision(self, revision):
        tmp = ConanFileReference.loads(str(self))
        tmp.revision = revision
        return tmp

    def copy_without_revision(self):
        ret = ConanFileReference.loads(str(self))
        ret.revision = None
        return ret


class PackageReference(namedtuple("PackageReference", "conan package_id")):
    """ Full package reference, e.g.:
    opencv/2.4.10@lasote/testing, fe566a677f77734ae
    """
    revision = None

    def __new__(cls, conan, package_id):
        revision = None
        if "#" in package_id:
            package_id, revision = package_id.rsplit("#", 1)
            ConanName.validate_name(revision)
        obj = super(cls, PackageReference).__new__(cls, conan, package_id)
        obj.revision = revision
        return obj

    @staticmethod
    def loads(text):
        text = text.strip()
        tmp = text.split(":")
        try:
            conan = ConanFileReference.loads(tmp[0].strip())
            package_id = tmp[1].strip()
        except IndexError:
            raise ConanException("Wrong package reference  %s" % text)
        return PackageReference(conan, package_id)

    def __repr__(self):
        return "%s:%s" % (self.conan, self.package_id)

    def full_repr(self):
        str_rev = "#%s" % self.revision if self.revision else ""
        return "%s%s" % (str(self), str_rev)

    def copy_with_revisions(self, revision, p_revision):
        ret = PackageReference(self.conan.copy_with_revision(revision), self.package_id)
        ret.revision = p_revision
        return ret

    def copy_without_revision(self):
        ret = PackageReference.loads(str(self))
        ret.revision = None
        ret.conan.revision = None
        return ret
