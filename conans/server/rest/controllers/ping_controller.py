from bottle import response

from conans.server.rest.controllers.controller import Controller


class PingController(Controller):

    def attach_to(self, app):

        @app.route("%s/ping" % self.route, method=["GET"])
        def ping():
            """
            Response OK. Useful to get server capabilities
            """
            response.headers['X-Conan-Server-Capabilities'] = ",".join(app.server_capabilities)
            return
