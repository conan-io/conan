from bottle import response

from conans.server.rest.bottle_routes import BottleRoutes


class PingController(object):

    @staticmethod
    def attach_to(app):
        r = BottleRoutes()

        @app.route(r.ping, method=["GET"])
        def ping():
            """
            Response OK. Useful to get server capabilities
            """
            response.headers['X-Conan-Server-Capabilities'] = ",".join(app.server_capabilities)
            return
