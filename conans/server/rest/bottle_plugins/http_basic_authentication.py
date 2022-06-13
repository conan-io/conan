import base64
from collections import namedtuple

from bottle import HTTPResponse

from conans.server.rest.bottle_plugins.authorization_header import AuthorizationHeader


class UserPasswordPair(namedtuple('UserPasswordPair', ['user', 'password'])):
    """ Simple tuple for store user and pass """
    pass


class HttpBasicAuthentication(AuthorizationHeader):
    """ The HttpBasicAuthenticationBottlePlugin plugin requires Http Basic Authentication """

    name = 'basichttpauth'
    api = 2

    def __init__(self, keyword='http_basic_credentials'):
        self.keyword = keyword
        super(HttpBasicAuthentication, self).__init__(keyword)

    def get_authorization_type(self):
        """String in Authorization header for type"""
        return "Basic"

    def parse_authorization_value(self, header_value):
        """Parse header_value and return kwargs to apply bottle
        method parameters"""
        if header_value is None:
            return None
        # HTTP protocol is utf-8
        username, password = base64.b64decode(header_value).decode().split(":", 1)
        ret = UserPasswordPair(username, password)
        return {self.keyword: ret}

    def get_invalid_header_response(self):
        """A response from a malformed header. Includes WWW-Authenticate for
        ask browser to request user and password"""
        return HTTPResponse("'Http Authentication not implemented'",
                            "401 Unauthorized",
                            {"WWW-Authenticate": 'Basic realm="Login Required"'})
