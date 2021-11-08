import re

from conans.errors import ConanException, InvalidNameException
from conans.model.recipe_ref import RecipeReference


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
    # FIXME: Check if this is still/how necessary when the new commands
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
                ref = RecipeReference.loads(reference)
                validate_recipe_reference(ref)
                if "*" in ref.name or "*" in ref.user or "*" in ref.channel:
                    return False
                if str(ref.version).startswith("["):  # It is a version range
                    return True
                return False
        ref = RecipeReference.loads(reference)
        validate_recipe_reference(ref)
        return True
    except ConanException:
        return False


class ConanName(object):
    _max_chars = 51
    _min_chars = 2
    _validation_pattern = re.compile(r"^[a-zA-Z0-9_][a-zA-Z0-9_+.-]{%s,%s}$"
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
        if not isinstance(value, str):
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


def validate_recipe_reference(ref):
    if ref.name is not None:
        ConanName.validate_name(ref.name, reference_token="package name")
    if ref.version is not None:
        ConanName.validate_version(str(ref.version), ref.name)
    if ref.user is not None:
        ConanName.validate_name(ref.user, reference_token="user name")
    if ref.channel is not None:
        ConanName.validate_name(ref.channel, reference_token="channel")
    if ref.revision is not None:
        ConanName.validate_revision(ref.revision)

    if not ref.name or not ref.version:
        raise InvalidNameException("Specify the 'name' and the 'version'")

    if (ref.user and not ref.channel) or (ref.channel and not ref.user):
        raise InvalidNameException("Specify the 'user' and the 'channel' or neither of them")
