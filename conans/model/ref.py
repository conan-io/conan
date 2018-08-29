from collections import namedtuple
import re
from six import string_types
from conans.errors import ConanException, InvalidNameException
from conans.model.version import Version


class ConanName(object):
    _max_chars = 50
    _min_chars = 2
    _validation_pattern = re.compile("^[a-zA-Z0-9_][a-zA-Z0-9_\+\.-]{%s,%s}$"
                                     % (_min_chars - 1, _max_chars - 1))

    @staticmethod
    def invalid_name_message(value, message=None):
        message = message or "'{value}' {reason}"
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
        raise InvalidNameException(message.format(value=value, reason=reason,
                                                  type=type(value).__name__))

    @staticmethod
    def validate_string(value, message=None):
        """Check for string"""
        if not isinstance(value, string_types):
            message = message or "'{value}' (type {type}) {reason}"
            raise InvalidNameException(message.format(value=value, reason="is not a string",
                                                      type=type(value).__name__))

    @staticmethod
    def validate_user(username, message=None):
        ConanName.validate_string(username, message=message)
        if ConanName._validation_pattern.match(username) is None:
            ConanName.invalid_name_message(username, message=message)

    @staticmethod
    def validate_name(name, version=False, message=None):
        """Check for name compliance with pattern rules"""
        ConanName.validate_string(name, message=message)
        if name == "*":
            return
        if ConanName._validation_pattern.match(name) is None:
            if version and name.startswith("[") and name.endswith("]"):
                # TODO: Check value between brackets
                return
            ConanName.invalid_name_message(name, message=message)


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
        @param version:     string containing the desired version
        @param user:        string containing the user name
        @param channel:     string containing the user channel
        @param revision:    string containing the revision (optional)
        """
        message = "Value provided for {item}, '{{value}}' (type {{type}}), {{reason}}"
        ConanName.validate_name(name, message=message.format(item="package name"))
        ConanName.validate_name(version, True, message=message.format(item="package version"))
        ConanName.validate_name(user, message=message.format(item="package user name"))
        ConanName.validate_name(channel, message=message.format(item="package user"))
        version = Version(version)
        obj = super(cls, ConanFileReference).__new__(cls, name, version, user, channel)
        if revision:
            ConanName.validate_name(revision, message=message.format(item="package revision"))
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
            message = "Value provided for package revision, '{value}' (type {type}) {reason}"
            ConanName.validate_name(revision, message=message)
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
