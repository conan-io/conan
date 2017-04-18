from conans.errors import InvalidNameException
import re


class Username(str):

    max_len = 30
    min_len = 2
    base_er = "[a-zA-Z][a-zA-Z0-9_-]{%s,%s}" % (min_len-1, max_len-1)
    pattern = re.compile("^%s$" % base_er)

    def __new__(cls, name):
        """Simple name creation.

        @param name:        string containing the desired name
        @param validate:    checks for valid simple name. default True
        """
        Username.validate(name)
        return str.__new__(cls, name)

    @staticmethod
    def validate(name, pattern=False):
        """Check for name compliance with pattern rules. User names can be
           with upper/lower case
        """
        if Username.pattern.match(name) is None:
            if pattern and name == "*":
                return
            if len(name) > Username.max_len:
                message = "'%s' is too long. Valid names must contain at most %s characters." \
                          "" % (name, Username.max_len)
            elif len(name) < Username.min_len:
                message = "'%s' is too short. Valid names must contain at least %s characters." \
                          "" % (name, Username.min_len)
            else:
                message = "'%s' is an invalid name. "\
                          "Valid names should begin with alphanumerical characters, '_' and '-'." % name
            raise InvalidNameException(message)
