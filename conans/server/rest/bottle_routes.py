from conans.model.rest_routes import RestRoutes


class BottleRoutes(RestRoutes):

    def __init__(self, matrix_params):
        super(BottleRoutes, self).__init__(matrix_params=matrix_params)

    def __getattribute__(self, item):
        tmp = super(BottleRoutes, self).__getattribute__(item)
        tmp = tmp.replace("{path}", "<the_path:path>").replace("{", "<").replace("}", ">")
        if not tmp.startswith("/"):
            return "/{}".format(tmp)
        return tmp
