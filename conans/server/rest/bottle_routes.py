from conans.model.rest_routes import RestRoutes


class BottleRoutes(RestRoutes):

    def __getattribute__(self, item):
        tmp = super(BottleRoutes, self).__getattribute__(item)
        return tmp.replace("{path}", "<the_path:path>").replace("{", "<").replace("}", ">")
