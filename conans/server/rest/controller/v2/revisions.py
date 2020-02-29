from conans.model.ref import ConanFileReference
from conans.server.rest.bottle_routes import BottleRoutes
from conans.server.rest.controller.v2 import get_package_ref
from conans.server.service.v2.service_v2 import ConanServiceV2


class RevisionsController(object):
    """
        Serve requests related with Conan
    """
    @staticmethod
    def attach_to(app):

        r = BottleRoutes()

        @app.route(r.recipe_revisions, method="GET")
        def get_recipe_revisions(name, version, username, channel, auth_user):
            """ Gets a JSON with the revisions for the specified recipe
            """
            conan_reference = ConanFileReference(name, version, username, channel)
            conan_service = ConanServiceV2(app.authorizer, app.server_store)
            revs = conan_service.get_recipe_revisions(conan_reference, auth_user)
            return _format_revs_return(revs)

        @app.route(r.recipe_latest, method="GET")
        def get_latest_recipe_revision(name, version, username, channel, auth_user):
            """ Gets a JSON with the revisions for the specified recipe
            """
            conan_reference = ConanFileReference(name, version, username, channel)
            conan_service = ConanServiceV2(app.authorizer, app.server_store)
            rev = conan_service.get_latest_revision(conan_reference, auth_user)
            return _format_rev_return(rev)

        @app.route(r.package_revisions, method="GET")
        def get_package_revisions(name, version, username, channel, package_id, auth_user,
                                  revision):
            """ Get a JSON with the revisions for a specified RREV """
            package_reference = get_package_ref(name, version, username, channel, package_id,
                                                revision, p_revision=None)
            conan_service = ConanServiceV2(app.authorizer, app.server_store)
            revs = conan_service.get_package_revisions(package_reference, auth_user)
            return _format_revs_return(revs)

        @app.route(r.package_revision_latest, method="GET")
        def get_latest_package_revision(name, version, username, channel, package_id, auth_user,
                                        revision):
            """ Gets a JSON with the revisions for the specified recipe
            """
            package_reference = get_package_ref(name, version, username, channel, package_id,
                                                revision, p_revision=None)
            conan_service = ConanServiceV2(app.authorizer, app.server_store)
            rev = conan_service.get_latest_package_revision(package_reference, auth_user)
            return _format_rev_return(rev)


def _format_rev_return(rev):
    return {"revision": rev[0],
            "time": rev[1]}


def _format_revs_return(revs):
    return {"revisions": [_format_rev_return(rev)for rev in revs]}
