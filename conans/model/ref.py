from collections import namedtuple
import re
from conans.errors import ConanException, InvalidNameException
from conans.model.version import Version


def validate_conan_name(name):
    """Check for name compliance with pattern rules"""
    try:
        if name == '*' and ConanFileReference.wildcard_is_allowed:
            return name
        if ConanFileReference.validation_pattern.match(name) is None:
            if len(name) > ConanFileReference.max_chars:
                message = "'%s' is too long. Valid names must " \
                          "contain at most %s characters." % (name,
                                                              ConanFileReference.max_chars)
            elif len(name) < ConanFileReference.min_chars:
                message = "'%s' is too short. Valid names must contain"\
                          " at least %s characters." % (name, ConanFileReference.min_chars)
            else:
                message = "'%s' is an invalid name. Valid names MUST begin with a "\
                          "letter or number, have between %s-%s chars, including "\
                          "letters, numbers, underscore,"\
                          " dot and dash" % (name, ConanFileReference.min_chars,
                                             ConanFileReference.max_chars)
            raise InvalidNameException(message)
        return name
    except AttributeError:
        raise InvalidNameException('Empty name provided', None)


class ConanFileReference(namedtuple("ConanFileReference", "name version user channel")):
    """ Full reference of a conans, e.g.:
    opencv/2.4.10@lasote/testing
    """
    max_chars = 40
    min_chars = 2
    base_er = "[a-zA-Z0-9_]+[a-zA-Z0-9_\.-]{%s,%s}" % (min_chars - 1, max_chars)
    regular_expression = "^%s$" % base_er
    validation_pattern = re.compile(regular_expression)
    whitespace_pattern = re.compile(r"\s+")
    sep_pattern = re.compile("@|/")
    wildcard_is_allowed = True

    def __new__(cls, name, version, user, channel, validate=True):
        """Simple name creation.
        @param name:        string containing the desired name
        @param validate:    checks for valid complex name. default True
        """
        if validate:
            name = validate_conan_name(name)
            version = validate_conan_name(version)
            user = validate_conan_name(user)
            channel = validate_conan_name(channel)
        version = Version(version)
        return super(cls, ConanFileReference).__new__(cls, name, version, user, channel)

    @staticmethod
    def loads(text, validate=True):
        """ Parses a text string to generate a ConanFileReference object
        """
        text = ConanFileReference.whitespace_pattern.sub("", text)
        tokens = ConanFileReference.sep_pattern.split(text)
        try:
            name = tokens[0]
            version = tokens[1]
            user = tokens[2]
            channel = tokens[3]
        except IndexError:
            raise ConanException("Wrong package recipe reference %s\nWrite something like "
                                 "OpenCV/1.0.6@phil/stable" % text)
        return ConanFileReference(name, version, user, channel, validate)

    def __repr__(self):
        return "%s/%s@%s/%s" % (self.name, self.version, self.user, self.channel)

    def package_ref(self, conan_info):
        package_id = conan_info.package_id(self)
        return PackageReference(self, package_id)


class PackageReference(namedtuple("PackageReference", "conan package_id")):
    """ Full package reference, e.g.:
    opencv/2.4.10@lasote/testing, fe566a677f77734ae
    """

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
