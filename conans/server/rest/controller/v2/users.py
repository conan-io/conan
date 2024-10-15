from bottle import response

from conan.internal.errors import AuthenticationException

from conans.server.rest.bottle_routes import BottleRoutes
from conans.server.service.user_service import UserService


class UsersController(object):
    """
        Serve requests related with users
    """
    def attach_to(self, app):

        r = BottleRoutes()

        @app.route(r.common_authenticate, method=["GET"])
        def authenticate(http_basic_credentials):
            if not http_basic_credentials:
                raise AuthenticationException("Wrong user or password")

            user_service = UserService(app.authenticator,
                                       app.credentials_manager)

            token = user_service.authenticate(http_basic_credentials.user,
                                              http_basic_credentials.password)

            response.content_type = 'text/plain'
            return token

        @app.route(r.common_check_credentials, method=["GET"])
        def check_credentials(auth_user):
            """Just check if valid token. It not exception
            is raised from Bottle plugin"""
            if not auth_user:
                raise AuthenticationException("Logged user needed!")
            response.content_type = 'text/plain'
            return auth_user
