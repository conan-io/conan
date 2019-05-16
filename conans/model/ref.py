import re
from collections import namedtuple

from six import string_types

from conans.errors import ConanException, InvalidNameException
from conans.model.version import Version


NONE_FOLDER_VALUE = "default"


def check_valid_ref(ref, allow_pattern):
    try:
        if not isinstance(ref, ConanFileReference):
            ref = ConanFileReference.loads(ref, validate=True)
        return "*" not in ref or allow_pattern
    except ConanException:
        pass
    return False


class ConanName(object):
    _max_chars = 51
    _min_chars = 2
    _validation_pattern = re.compile("^[a-zA-Z0-9_][a-zA-Z0-9_\+\.-]{%s,%s}$"
                                     % (_min_chars - 1, _max_chars - 1))

    _validation_revision_pattern = re.compile("^[a-zA-Z0-9]{1,%s}$" % _max_chars)

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

    @staticmethod
    def validate_revision(revision):
        if ConanName._validation_revision_pattern.match(revision) is None:
            raise InvalidNameException("The revision field, must contain only letters "
                                       "and numbers with a length between 1 and "
                                       "%s" % ConanName._max_chars)


class ConanFileReference(namedtuple("ConanFileReference", "name version user channel revision")):
    """ Full reference of a package recipes, e.g.:
    opencv/2.4.10@lasote/testing
    """
    sep_pattern = re.compile(r"([^/]+)/([^/]+)@([^/]+)/([^/#]+)#?(.+)?")

    def __new__(cls, name, version, user=None, channel=None, revision=None, validate=True):
        """Simple name creation.
        @param name:        string containing the desired name
        @param version:     string containing the desired version
        @param user:        string containing the user name
        @param channel:     string containing the user channel
        @param revision:    string containing the revision (optional)
        """
        version = Version(version) if version is not None else None
        obj = super(cls, ConanFileReference).__new__(cls, name, version, user, channel, revision)
        if validate:
            obj._validate()
        return obj

    def _validate(self):
        ConanName.validate_name(self.name, reference_token="package name")
        ConanName.validate_name(self.version, True, reference_token="package version")
        if self.user is not None:
            ConanName.validate_name(self.user, reference_token="user name")
        if self.channel is not None:
            ConanName.validate_name(self.channel, reference_token="channel")
        if self.revision:
            ConanName.validate_revision(self.revision)

    @staticmethod
    def loads(text, validate=True, user_channel_needed=False):
        """ Parses a text string to generate a ConanFileReference object
        """
        err_msg = 'Wrong package recipe reference %s\nWrite something like ' \
                  '"OpenCV/1.0.6@user/stable"' % text

        # FIXME: At Conan 2.0 we can force "lib/1.0@" to specify without user channel
        # FIXME: and "@user/channel" to not mess with patterns etc

        if "@" not in text and user_channel_needed:
            raise ConanException("Specify a complete reference like "
                                 "OpenCV/1.0.6@user/stable")

        if "@" not in text:
            try:
                # Split returns empty start and end groups
                name, version = text.split("/")
                user, channel, revision = None, None, None
            except ValueError:
                raise ConanException(err_msg)
        else:
            try:
                # Split returns empty start and end groups
                _, name, version, user, channel, revision, _ = ConanFileReference.sep_pattern.split(text)
            except ValueError:
                raise ConanException("Wrong package recipe reference %s\nWrite something like "
                                     "OpenCV/1.0.6@user/stable" % text)

        # FIXME: Hack in case someone is doing:
        # self.requires("Say/0.1@%s/%s" % (self.user, self.channel))
        # being self.user and self.channel None
        if user == "None":
            user = None
        if channel == "None":
            channel = None

        ref = ConanFileReference(name, version, user, channel, revision, validate=validate)
        return ref

    def __repr__(self):
        if self.user is None and self.channel is None:
            return "%s/%s" % (self.name, self.version)
        return "%s/%s@%s/%s" % (self.name, self.version, self.user, self.channel)

    def full_str(self):
        return "%s/%s@%s/%s" % (self.name, self.version, self.user, self.channel)

    def full_repr(self):
        tmp = str(self)
        str_rev = "#%s" % self.revision if self.revision else ""
        return "%s%s" % (tmp, str_rev)

    def dir_repr(self):
        channel = self.channel or NONE_FOLDER_VALUE
        user = self.user or NONE_FOLDER_VALUE
        return "/".join([self.name, self.version, user, channel])

    def copy_with_rev(self, revision):
        return ConanFileReference(self.name, self.version, self.user, self.channel, revision)

    def copy_clear_rev(self):
        return ConanFileReference(self.name, self.version, self.user, self.channel, None)


class PackageReference(namedtuple("PackageReference", "ref id revision")):
    """ Full package reference, e.g.:
    opencv/2.4.10@lasote/testing, fe566a677f77734ae
    """

    def __new__(cls, ref, package_id, revision=None, validate=True):
        if "#" in package_id:
            package_id, revision = package_id.rsplit("#", 1)
        obj = super(cls, PackageReference).__new__(cls, ref, package_id, revision)
        if validate:
            obj.validate()
        return obj

    def validate(self):
        if self.revision:
            ConanName.validate_revision(self.revision)

    @staticmethod
    def loads(text, validate=True):
        text = text.strip()
        tmp = text.split(":")
        try:
            ref = ConanFileReference.loads(tmp[0].strip(), validate=validate)
            package_id = tmp[1].strip()
        except IndexError:
            raise ConanException("Wrong package reference  %s" % text)
        return PackageReference(ref, package_id, validate=validate)

    def __repr__(self):
        return "%s:%s" % (self.ref, self.id)

    def full_repr(self):
        str_rev = "#%s" % self.revision if self.revision else ""
        tmp = "%s:%s%s" % (self.ref.full_repr(), self.id, str_rev)
        return tmp

    def copy_with_revs(self, revision, p_revision):
        return PackageReference(self.ref.copy_with_rev(revision), self.id, p_revision)

    def copy_clear_rev(self):
        ref = self.ref.copy_clear_rev()
        return PackageReference(ref, self.id, revision=None)

    def copy_clear_revs(self):
        return self.copy_with_revs(None, None)
