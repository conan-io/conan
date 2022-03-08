import fnmatch

from conans.cli.api.subapi import api_method
from conans.cli.conan_app import ConanApp
from conans.errors import ConanException
from conans.model.recipe_ref import RecipeReference
from conans.search.search import search_recipes


class SearchAPI:

    def __init__(self, conan_api):
        self.conan_api = conan_api

    @api_method
    def recipes(self, query: str, remote=None):
        app = ConanApp(self.conan_api.cache_folder)
        if remote:
            return app.remote_manager.search_recipes(remote, query)
        else:
            references = search_recipes(app.cache, query)
            # For consistency with the remote search, we return references without revisions
            # user could use further the API to look for the revisions
            ret = []
            for r in references:
                r.revision = None
                r.timestamp = None
                if r not in ret:
                    ret.append(r)
            return ret

    @api_method
    def recipe_revisions(self, expression, remote=None, none_revision_allowed=True):
        """
        :param expression: A RecipeReference that can contain "*" at any field
        :param remote: Remote in case we want to check the references in a remote
        :return: a list of complete RecipeReference
        """
        if "/" not in expression:
            if "*" not in expression:
                raise ConanException("Invalid expression, specify a version "
                                     "or a wildcard. e.g: {}*".format(expression))
            if "#" in expression or ":" in expression:
                raise ConanException("Invalid expression, specify version")
            refs = self.conan_api.search.recipes(expression, remote)
            ref = RecipeReference(expression)
        else:
            ref = RecipeReference.loads(expression)
            if not ref.revision and "#" in expression:
                # Something like "foo/var#" without specifying revision
                raise ConanException("Specify a recipe revision")
            if not ref.user and "@" in expression:
                # Something like "foo/var@" without specifying user/channel
                raise ConanException("Specify a user/channel or remove the '@'")
            # First resolve any * in the regular reference, doing a search
            if any(["*" in field for field in (ref.name, str(ref.version),
                                               ref.user or "", ref.channel or "")]):
                refs = self.recipes(str(ref), remote)  # Do not return revisions
            else:
                refs = [ref]

        # Second, for the got references, check revisions matching.
        ret = []
        for _r in refs:
            if ref.revision is not None:
                _tmp = RecipeReference.loads(repr(_r))
                _tmp.revision = None
                if ref.revision == "latest":
                    ret.append(self.conan_api.list.latest_recipe_revision(_tmp, remote))
                else:
                    for _rrev in self.conan_api.list.recipe_revisions(_tmp, remote):
                        if fnmatch.fnmatch(_rrev.revision, ref.revision):
                            ret.append(_rrev)
            else:
                if not none_revision_allowed:  # package reference without recipe revision
                    raise ConanException("Specify a recipe revision or a wildcard. "
                                         "e.g: {}#*".format(expression))
                ret.extend(self.conan_api.list.recipe_revisions(_r, remote))

        return ret

    @api_method
    def package_revisions(self, expression, query=None, remote=None):
        """
        Resolve an expression like lib*/1*#*:9283*, filtering by query and obtaining all the package
        revisions
        :param expression: lib*/1*#*:9283*
        :param query: package configuration query like "os=Windows AND (arch=x86 OR compiler=gcc)"
        :param remote: Remote object
        :return: a List of PkgReference
        """
        if ":" in expression:
            recipe_expr, package_expr = expression.split(":", 1)
            if not package_expr:
                raise ConanException("Specify a package ID value after ':'")
        else:
            recipe_expr = expression
            package_expr = "*#*"

        if "#" in package_expr:
            package_id_expr, package_revision_expr = package_expr.split("#", 1)
            if not package_revision_expr:
                raise ConanException("Specify a package revision")
        else:
            package_id_expr = package_expr
            package_revision_expr = "*"

        # If we are specifing a pref, we need a recipe ref in the expression (at least a wildcard)
        refs = self.recipe_revisions(recipe_expr, remote, none_revision_allowed=False)
        ret = []
        for ref in refs:
            configurations = self.conan_api.list.packages_configurations(ref, remote)
            filtered_configurations = {}
            for _pref, configuration in configurations.items():
                if fnmatch.fnmatch(_pref.package_id, package_id_expr):
                    filtered_configurations[_pref] = configuration
            prefs = self.conan_api.list.filter_packages_configurations(filtered_configurations,
                                                                       query).keys()
            for pref in prefs:
                if package_revision_expr == "latest":
                    latest = self.conan_api.list.latest_package_revision(pref, remote)
                    if latest:
                        ret.append(latest)
                else:
                    prevs = self.conan_api.list.package_revisions(pref, remote)
                    for prev in prevs:
                        if fnmatch.fnmatch(prev.revision, package_revision_expr):
                            ret.append(prev)

        return ret
