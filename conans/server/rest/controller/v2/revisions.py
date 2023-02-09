from conans.model.recipe_ref import RecipeReference
from conans.server.rest.bottle_routes import BottleRoutes
from conans.server.rest.controller.v2 import get_package_ref
from conans.server.service.v2.service_v2 import ConanServiceV2
from conans.util.dates import from_timestamp_to_iso8601


class RevisionsController(object):
    """
        Serve requests related with Conan
    """
    @staticmethod
    def attach_to(app):

        r = BottleRoutes()

        @app.route(r.recipe_revisions, method="GET")
        def get_recipe_revisions_references(name, version, username, channel, auth_user):
            """ Gets a JSON with the revisions for the specified recipe
            """
            conan_reference = RecipeReference(name, version, username, channel)
            conan_service = ConanServiceV2(app.authorizer, app.server_store)
            revs = conan_service.get_recipe_revisions_references(conan_reference, auth_user)
            return _format_revs_return(revs)

        @app.route(r.recipe_latest, method="GET")
        def get_latest_recipe_reference(name, version, username, channel, auth_user):
            """ Gets a JSON with the revisions for the specified recipe
            """
            conan_reference = RecipeReference(name, version, username, channel)
            conan_service = ConanServiceV2(app.authorizer, app.server_store)
            rev = conan_service.get_latest_revision(conan_reference, auth_user)
            return _format_rev_return(rev)

        @app.route(r.package_revisions, method="GET")
        def get_package_revisions_references(name, version, username, channel, package_id, auth_user,
                                             revision):
            """ Get a JSON with the revisions for a specified RREV """
            package_reference = get_package_ref(name, version, username, channel, package_id,
                                                revision, p_revision=None)
            conan_service = ConanServiceV2(app.authorizer, app.server_store)
            prefs = conan_service.get_package_revisions_references(package_reference, auth_user)
            return _format_prefs_return(prefs)

        @app.route(r.package_revision_latest, method="GET")
        def get_latest_package_reference(name, version, username, channel, package_id, auth_user,
                                         revision):
            """ Gets a JSON with the revisions for the specified recipe
            """
            package_reference = get_package_ref(name, version, username, channel, package_id,
                                                revision, p_revision=None)
            conan_service = ConanServiceV2(app.authorizer, app.server_store)
            pref = conan_service.get_latest_package_reference(package_reference, auth_user)
            return _format_pref_return(pref)


def _format_rev_return(rev):
    # FIXME: fix this when RecipeReference
    return {"revision": rev[0], "time": from_timestamp_to_iso8601(rev[1])}


def _format_revs_return(revs):
    return {"revisions": [_format_rev_return(rev) for rev in revs]}


def _format_pref_return(pref):
    return {"revision": pref.revision, "time": from_timestamp_to_iso8601(pref.timestamp)}


def _format_prefs_return(revs):
    return {"revisions": [_format_pref_return(rev) for rev in revs]}
