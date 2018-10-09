from collections import namedtuple
import re
from six import string_types
from conans.errors import ConanException, InvalidNameException
from conans.model.version import Version


class ConanName(object):
    _max_chars = 51
    _min_chars = 2
    _validation_pattern = re.compile("^[a-zA-Z0-9_][a-zA-Z0-9_\+\.-]{%s,%s}$"
                                     % (_min_chars - 1, _max_chars - 1))

    @staticmethod
    def invalid_name_message(value, reference_token=None):
        if len(value) > ConanName._max_chars:
            reason = "is too long. Valid names must contain at most %s characters."\
                     % ConanName._max_chars
        elif len(value) < ConanName._min_chars:
            reason = "is too short. Valid names must contain at least %s characters."\
                     % ConanName._min_chars
        else:
            reason = ("is an invalid name. Valid names MUST begin with a "
                      "letter, number or underscore, have between %s-%s chars, including "
                      "letters, numbers, underscore, dot and dash"
                      % (ConanName._min_chars, ConanName._max_chars))
        message = "Value provided{ref_token}, '{value}' (type {type}), {reason}".format(
            ref_token=" for {}".format(reference_token) if reference_token else "",
            value=value, type=type(value).__name__, reason=reason
        )
        raise InvalidNameException(message)

    @staticmethod
    def validate_string(value, reference_token=None):
        """Check for string"""
        if not isinstance(value, string_types):
            message = "Value provided{ref_token}, '{value}' (type {type}), {reason}".format(
                ref_token=" for {}".format(reference_token) if reference_token else "",
                value=value, type=type(value).__name__,
                reason="is not a string"
            )
            raise InvalidNameException(message)

    @staticmethod
    def validate_name(name, version=False, reference_token=None):
        """Check for name compliance with pattern rules"""
        ConanName.validate_string(name, reference_token=reference_token)
        if name == "*":
            return
        if ConanName._validation_pattern.match(name) is None:
            if version and name.startswith("[") and name.endswith("]"):
                return
            ConanName.invalid_name_message(name, reference_token=reference_token)


class ConanFileReference(namedtuple("ConanFileReference", "name version user channel")):
    """ Full reference of a package recipes, e.g.:
    opencv/2.4.10@lasote/testing
    """
    whitespace_pattern = re.compile(r"\s+")
    sep_pattern = re.compile("@|/|#")
    revision = None

    def __new__(cls, name, version, user, channel, revision=None, validate=True):
        """Simple name creation.
        @param name:        string containing the desired name
        @param version:     string containing the desired version
        @param user:        string containing the user name
        @param channel:     string containing the user channel
        @param revision:    string containing the revision (optional)
        """
        version = Version(version)
        obj = super(cls, ConanFileReference).__new__(cls, name, version, user, channel)
        obj.revision = revision
        if validate:
            obj.validate()
        return obj

    def validate(self):
        ConanName.validate_name(self.name, reference_token="package name")
        ConanName.validate_name(self.version, True, reference_token="package version")
        ConanName.validate_name(self.user, reference_token="user name")
        ConanName.validate_name(self.channel, reference_token="channel")
        if self.revision:
            ConanName.validate_name(self.revision, reference_token="revision")

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
    def loads(text, validate=True):
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
        obj = ConanFileReference(name, version, user, channel, revision, validate=validate)
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

    def __new__(cls, conan, package_id, validate=True):
        revision = None
        if "#" in package_id:
            package_id, revision = package_id.rsplit("#", 1)
        obj = super(cls, PackageReference).__new__(cls, conan, package_id)
        obj.revision = revision
        if validate:
            obj.validate()
        return obj

    def validate(self):
        if self.revision:
            ConanName.validate_name(self.revision, reference_token="revision")

    @staticmethod
    def loads(text, validate=True):
        text = text.strip()
        tmp = text.split(":")
        try:
            conan = ConanFileReference.loads(tmp[0].strip())
            package_id = tmp[1].strip()
        except IndexError:
            raise ConanException("Wrong package reference  %s" % text)
        return PackageReference(conan, package_id, validate=validate)

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
