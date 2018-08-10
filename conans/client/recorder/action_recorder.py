
# FIXME: The functions from the tracer.py module should be called here, I removed from there some
# of them because it has to be called in the remote manager, not in the proxy, where we have info
# about the downloaded files prior to unzip them

from datetime import datetime
from collections import namedtuple, OrderedDict

# Install actions
from conans.model.ref import ConanFileReference, PackageReference

INSTALL_CACHE = 0
INSTALL_DOWNLOADED = 1
INSTALL_BUILT = 2
INSTALL_ERROR = -1

# Actions errors
INSTALL_ERROR_MISSING = "missing"
INSTALL_ERROR_NETWORK = "network"
INSTALL_ERROR_MISSING_BUILD_FOLDER = "missing_build_folder"
INSTALL_ERROR_BUILDING = "building"


class Action(namedtuple("Action", "type, doc, time")):

    def __new__(cls, the_type, doc=None):
        doc = doc or {}
        the_time = datetime.utcnow()
        return super(cls, Action).__new__(cls, the_type, doc, the_time)


class ActionRecorder(object):

    def __init__(self):
        self._inst_recipes_actions = OrderedDict()
        self._inst_packages_actions = OrderedDict()
        self._inst_recipes_develop = set()  # Recipes being created (to set dependency=False)

    # ###### INSTALL METHODS ############
    def add_recipe_being_developed(self, reference):
        self._inst_recipes_develop.add(reference)

    def _add_recipe_action(self, reference, action):
        assert(isinstance(reference, ConanFileReference))
        if reference not in self._inst_recipes_actions:
            self._inst_recipes_actions[reference] = []
        self._inst_recipes_actions[reference].append(action)

    def _add_package_action(self, reference, action):
        assert(isinstance(reference, PackageReference))
        if reference not in self._inst_packages_actions:
            self._inst_packages_actions[reference] = []
        self._inst_packages_actions[reference].append(action)

    # RECIPE METHODS
    def recipe_fetched_from_cache(self, reference):
        self._add_recipe_action(reference, Action(INSTALL_CACHE))

    def recipe_downloaded(self, reference, remote_name):
        self._add_recipe_action(reference, Action(INSTALL_DOWNLOADED, {"remote": remote_name}))

    def recipe_install_error(self, reference, error_type, description, remote_name):
        doc = {"type": error_type, "description": description, "remote": remote_name}
        self._add_recipe_action(reference, Action(INSTALL_ERROR, doc))

    # PACKAGE METHODS
    def package_built(self, reference):
        self._add_package_action(reference, Action(INSTALL_BUILT))

    def package_fetched_from_cache(self, reference):
        self._add_package_action(reference, Action(INSTALL_CACHE))

    def package_downloaded(self, reference, remote_name):
        self._add_package_action(reference, Action(INSTALL_DOWNLOADED, {"remote": remote_name}))

    def package_install_error(self, reference, error_type, description, remote_name=None):
        assert(isinstance(reference, PackageReference))
        if reference not in self._inst_packages_actions:
            self._inst_packages_actions[reference] = []
        doc = {"type": error_type, "description": description, "remote": remote_name}
        self._inst_packages_actions[reference].append(Action(INSTALL_ERROR, doc))

    @property
    def install_errored(self):
        all_values = list(self._inst_recipes_actions.values()) + list(self._inst_packages_actions.values())
        for acts in all_values:
            for act in acts:
                if act.type == INSTALL_ERROR:
                    return True
        return False

    def _get_installed_packages(self, reference):
        assert(isinstance(reference, ConanFileReference))
        ret = []
        for _package_ref, _package_actions in self._inst_packages_actions.items():
            # Could be a download and then an access to cache, we want the first one
            _package_action = _package_actions[0]
            if _package_ref.conan == reference:
                ret.append((_package_ref, _package_action))
        return ret

    def in_development_recipe(self, reference):
        return reference in self._inst_recipes_develop

    def get_info(self):
        return self.get_install_info()

    def get_install_info(self):
        ret = {"error": self.install_errored,
               "installed": []}

        def get_doc_for_ref(the_ref, the_action):
            error = None if the_action.type != INSTALL_ERROR else the_action.doc
            doc = {"id": str(the_ref),
                   "downloaded": the_action.type == INSTALL_DOWNLOADED,
                   "cache": the_action.type == INSTALL_CACHE,
                   "error": error,
                   "remote": the_action.doc.get("remote", None),
                   "time": the_action.time}
            if isinstance(the_ref, ConanFileReference):
                doc["dependency"] = not self.in_development_recipe(the_ref)
            else:
                doc["built"] = the_action.type == INSTALL_BUILT

            if doc["remote"] is None and error:
                doc["remote"] = error.get("remote", None)
            return doc

        for ref, actions in self._inst_recipes_actions.items():
            # Could be a download and then an access to cache, we want the first one
            action = actions[0]
            recipe_doc = get_doc_for_ref(ref, action)
            packages = self._get_installed_packages(ref)
            tmp = {"recipe": recipe_doc,
                   "packages": []}

            for p_ref, p_action in packages:
                p_doc = get_doc_for_ref(p_ref.package_id, p_action)
                tmp["packages"].append(p_doc)

            ret["installed"].append(tmp)

        return ret
