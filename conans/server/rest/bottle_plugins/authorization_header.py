import inspect
from abc import ABCMeta, abstractmethod

import six
from bottle import PluginError, request

from conans.util.log import logger


class AuthorizationHeader(object):
    """ Generic plugin to handle Authorization header. Must be extended and implement
    some abstract methods in subclasses """
    __metaclass__ = ABCMeta

    name = 'authorizationheader'
    api = 2

    def __init__(self, keyword):
        # Required
        self.keyword = keyword

    def setup(self, app):
        """ Make sure that other installed plugins don't affect the same
            keyword argument. """
        for other in app.plugins:
            if not isinstance(other, self.__class__):
                continue
            if other.keyword == self.keyword:
                raise PluginError("Found another AuthorizationHeaderBottlePlugin plugin with "
                                  "conflicting settings (non-unique keyword).")

    def apply(self, callback, context):
        """ Test if the original callback accepts a 'self.keyword' keyword. """
        args = inspect.getfullargspec(context.callback)[0] if six.PY3 \
            else inspect.getargspec(context.callback)[0]
        logger.debug("Call: %s" % str(callback))
        if self.keyword not in args:
            return callback

        def wrapper(*args, **kwargs):
            """ Check for user credentials in http header """
            # Get Authorization
            header_value = self.get_authorization_header_value()
            new_kwargs = self.parse_authorization_value(header_value)
            if not new_kwargs:
                raise self.get_invalid_header_response()
            kwargs.update(new_kwargs)
            return callback(*args, **kwargs)  # kwargs has :xxx variables from url

        # Replace the route callback with the wrapped one.
        return wrapper

    def get_authorization_header_value(self):
        """ Get from the request the header of http basic auth:
         http://en.wikipedia.org/wiki/Basic_access_authentication """
        auth_type = self.get_authorization_type()
        if request.headers.get("Authorization", None) is not None:
            auth_line = request.headers.get("Authorization", None)
            if not auth_line.startswith("%s " % auth_type):
                raise self.get_invalid_header_response()
            return auth_line[len(auth_type) + 1:]
        else:
            return None

    @abstractmethod
    def get_authorization_type(self):
        """Abstract. Example: Basic (for http basic auth) or Beagle for JWT"""
        raise NotImplementedError()

    @abstractmethod
    def parse_authorization_value(self, header_value):
        """Abstract. Parse header_value and return kwargs to apply bottle
        method parameters"""
        raise NotImplementedError()

    @abstractmethod
    def get_invalid_header_response(self):
        """A response from a malformed header"""
        raise NotImplementedError()
