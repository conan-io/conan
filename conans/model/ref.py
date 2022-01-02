import re
from collections import namedtuple

from six import string_types

from conans.errors import ConanException, InvalidNameException
from conans.model.version import Version


def _split_pair(pair, split_char):
    if not pair or pair == split_char:
        return None, None
    if split_char not in pair:
        return None

    words = pair.split(split_char)
    if len(words) != 2:
        raise ConanException("The reference has too many '{}'".format(split_char))
    else:
        return words


def _noneize(text):
    if not text or text == "_":
        return None
    return text


def get_reference_fields(arg_reference, user_channel_input=False):
    # FIXME: The partial references meaning user/channel should be disambiguated at 2.0
    """
    :param arg_reference: String with a complete reference, or
        only user/channel (if user_channel_input)
        only name/version (if not pattern_is_user_channel)
    :param user_channel_input: Two items means user/channel or not.
    :return: name, version, user and channel, in a tuple
    """

    if not arg_reference:
        return None, None, None, None, None

    revision = None

    if "#" in arg_reference:
        tmp = arg_reference.split("#", 1)
        revision = tmp[1]
        arg_reference = tmp[0]

    if "@" in arg_reference:
        name_version, user_channel = _split_pair(arg_reference, "@")
        # FIXME: Conan 2.0
        #  In conan now "xxx@conan/stable" means that xxx is the version, I would say it should
        #  be the name
        name, version = _split_pair(name_version, "/") or (None, name_version)
        user, channel = _split_pair(user_channel, "/") or (user_channel, None)

        return _noneize(name), _noneize(version), _noneize(user), _noneize(channel), \
               _noneize(revision)
    else:
        if user_channel_input:
            # x/y is user and channel
            el1, el2 = _split_pair(arg_reference, "/") or (arg_reference, None)
            return None, None, _noneize(el1), _noneize(el2), _noneize(revision)
        else:
            # x/y is name and version
            el1, el2 = _split_pair(arg_reference, "/") or (arg_reference, None)
            return _noneize(el1), _noneize(el2), None, None, _noneize(revision)


def check_valid_ref(reference, strict_mode=True):
    """
    :param reference: string to be analyzed if it is a reference or not
    :param strict_mode: Only if the reference contains the "@" is valid, used to disambiguate"""
    try:
        if not reference:
            return False
        if strict_mode:
            if "@" not in reference:
                return False
            if "*" in reference:
                ref = ConanFileReference.loads(reference, validate=True)
                if "*" in ref.name or "*" in ref.user or "*" in ref.channel:
                    return False
                if str(ref.version).startswith("["):  # It is a version range
                    return True
                return False
        ConanFileReference.loads(reference, validate=True)
        return True
    except ConanException:
        return False


class ConanName(object):
    _max_chars = 51
    _min_chars = 2
    _validation_pattern = re.compile("^[a-zA-Z0-9_][a-zA-Z0-9_\+\.-]{%s,%s}$"
                                     % (_min_chars - 1, _max_chars - 1))

    _validation_revision_pattern = re.compile("^[a-zA-Z0-9]{1,%s}$" % _max_chars)

    @staticmethod
    def raise_invalid_name_error(value, reference_token=None):
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
    def raise_invalid_version_error(name, version):
        message = ("Package {} has an invalid version number: '{}'. Valid names "
                   "MUST begin with a letter, number or underscore, have "
                   "between {}-{} chars, including letters, numbers, "
                   "underscore, dot and dash").format(
            name,
            version,
            ConanName._min_chars,
            ConanName._max_chars
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
    def validate_name(name, reference_token=None):
        """Check for name compliance with pattern rules"""
        ConanName.validate_string(name, reference_token=reference_token)
        if name == "*":
            return
        if ConanName._validation_pattern.match(name) is None:
            ConanName.raise_invalid_name_error(name, reference_token=reference_token)

    @staticmethod
    def validate_version(version, pkg_name):
        ConanName.validate_string(version)
        if version == "*":
            return
        if ConanName._validation_pattern.match(version) is None:
            if (
                (version.startswith("[") and version.endswith("]"))
                or (version.startswith("(") and version.endswith(")"))
            ):
                return
            ConanName.raise_invalid_version_error(pkg_name, version)

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

    def __new__(cls, name, version, user, channel, revision=None, validate=True):
        """Simple name creation.
        @param name:        string containing the desired name
        @param version:     string containing the desired version
        @param user:        string containing the user name
        @param channel:     string containing the user channel
        @param revision:    string containing the revision (optional)
        """
        if (user and not channel) or (channel and not user):
            raise InvalidNameException("Specify the 'user' and the 'channel' or neither of them")

        version = Version(version) if version is not None else None
        user = _noneize(user)
        channel = _noneize(channel)

        obj = super(cls, ConanFileReference).__new__(cls, name, version, user, channel, revision)
        if validate:
            obj._validate()
        return obj

    def _validate(self):
        if self.name is not None:
            ConanName.validate_name(self.name, reference_token="package name")
        if self.version is not None:
            ConanName.validate_version(self.version, self.name)
        if self.user is not None:
            ConanName.validate_name(self.user, reference_token="user name")
        if self.channel is not None:
            ConanName.validate_name(self.channel, reference_token="channel")
        if self.revision is not None:
            ConanName.validate_revision(self.revision)

        if not self.name or not self.version:
            raise InvalidNameException("Specify the 'name' and the 'version'")

        if (self.user and not self.channel) or (self.channel and not self.user):
            raise InvalidNameException("Specify the 'user' and the 'channel' or neither of them")

    @staticmethod
    def loads(text, validate=True):
        """ Parses a text string to generate a ConanFileReference object
        """
        name, version, user, channel, revision = get_reference_fields(text)
        ref = ConanFileReference(name, version, user, channel, revision, validate=validate)
        return ref

    @staticmethod
    def load_dir_repr(dir_repr):
        name, version, user, channel = dir_repr.split("/")
        if user == "_":
            user = None
        if channel == "_":
            channel = None
        return ConanFileReference(name, version, user, channel)

    def __str__(self):
        if self.name is None and self.version is None:
            return ""
        if self.user is None and self.channel is None:
            return "%s/%s" % (self.name, self.version)
        return "%s/%s@%s/%s" % (self.name, self.version, self.user, self.channel)

    def __repr__(self):
        str_rev = "#%s" % self.revision if self.revision else ""
        user_channel = "@%s/%s" % (self.user, self.channel) if self.user or self.channel else ""
        return "%s/%s%s%s" % (self.name, self.version, user_channel, str_rev)

    def full_str(self):
        str_rev = "#%s" % self.revision if self.revision else ""
        return "%s%s" % (str(self), str_rev)

    def dir_repr(self):
        return "/".join([self.name, self.version, self.user or "_", self.channel or "_"])

    def copy_with_rev(self, revision):
        return ConanFileReference(self.name, self.version, self.user, self.channel, revision,
                                  validate=False)

    def copy_clear_rev(self):
        return ConanFileReference(self.name, self.version, self.user, self.channel, None,
                                  validate=False)

    def __lt__(self, other):
        def de_noneize(ref):
            return ref.name, ref.version, ref.user or "", ref.channel or "", ref.revision or ""

        return de_noneize(self) < de_noneize(other)

    def is_compatible_with(self, new_ref):
        """Returns true if the new_ref is completing the RREV field of this object but
         having the rest equal """
        if repr(self) == repr(new_ref):
            return True
        if self.copy_clear_rev() != new_ref.copy_clear_rev():
            return False

        return self.revision is None


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
            raise ConanException("Wrong package reference %s" % text)
        return PackageReference(ref, package_id, validate=validate)

    def __repr__(self):
        str_rev = "#%s" % self.revision if self.revision else ""
        tmp = "%s:%s%s" % (repr(self.ref), self.id, str_rev)
        return tmp

    def __str__(self):
        return "%s:%s" % (self.ref, self.id)

    def __lt__(self, other):
        # We need this operator to sort prefs to compute the package_id
        # package_id() -> ConanInfo.package_id() -> RequirementsInfo.sha() -> sorted(prefs) -> lt
        me = self.ref, self.id, self.revision or ""
        other = other.ref, other.id, other.revision or ""
        return me < other

    def full_str(self):
        str_rev = "#%s" % self.revision if self.revision else ""
        tmp = "%s:%s%s" % (self.ref.full_str(), self.id, str_rev)
        return tmp

    def copy_with_revs(self, revision, p_revision):
        return PackageReference(self.ref.copy_with_rev(revision), self.id, p_revision)

    def copy_clear_prev(self):
        return self.copy_with_revs(self.ref.revision, None)

    def copy_clear_revs(self):
        return self.copy_with_revs(None, None)

    def is_compatible_with(self, new_ref):
        """Returns true if the new_ref is completing the PREV field of this object but
         having the rest equal """
        if repr(self) == repr(new_ref):
            return True
        if not self.ref.is_compatible_with(new_ref.ref) or self.id != new_ref.id:
            return False

        return self.revision is None  # Only the revision is different and we don't have one
