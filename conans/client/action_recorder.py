
# FIXME: The functions from the tracer.py module should be called here, I removed from there some
# of them because it has to be called in the remote manager, not in the proxy, where we have info
# about the downloaded files prior to unzip them

import time
from collections import namedtuple, defaultdict

# Install actions
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
        the_time = time.time()
        return super(cls, Action).__new__(cls, the_type, doc, the_time)


class ActionRecorder(object):

    def __init__(self):
        self._inst_recipes_actions = defaultdict(list)
        self._inst_packages_actions = defaultdict(list)

    # ###### INSTALL METHODS ############

    # RECIPE METHODS
    def recipe_fetched_from_cache(self, reference):
        if reference in self._inst_recipes_actions:
            if self._inst_recipes_actions[reference].type == INSTALL_DOWNLOADED:
                return
            assert self._inst_recipes_actions[reference].type == INSTALL_CACHE
        else:
            self._inst_recipes_actions[reference] = Action(INSTALL_CACHE)

    def recipe_downloaded(self, reference, remote):
        assert reference not in self._inst_recipes_actions
        self._inst_recipes_actions[reference] = Action(INSTALL_DOWNLOADED, {"remote": remote})

    def recipe_install_error(self, reference, error_type, description, remote):
        assert reference not in self._inst_recipes_actions
        self._inst_recipes_actions[reference] = Action(INSTALL_ERROR,
                                                       {"type": error_type,
                                                        "description": description,
                                                        "remote": remote})

    # PACKAGE METHODS
    def package_built(self, reference):
        assert reference not in self._inst_packages_actions
        self._inst_packages_actions[reference] = Action(INSTALL_BUILT)

    def package_fetched_from_cache(self, reference):
        if reference in self._inst_packages_actions:
            if self._inst_packages_actions[reference].type == INSTALL_BUILT:
                return
            assert self._inst_packages_actions[reference].type == INSTALL_CACHE
        else:
            self._inst_packages_actions[reference] = Action(INSTALL_CACHE)

    def package_downloaded(self, reference, remote):
        assert reference not in self._inst_packages_actions
        self._inst_packages_actions[reference] = Action(INSTALL_DOWNLOADED, {"remote": remote})

    def package_install_error(self, reference, error_type, description, remote=None):
        assert reference not in self._inst_packages_actions
        self._inst_packages_actions[reference] = Action(INSTALL_ERROR, {"type": error_type,
                                                                        "description": description,
                                                                        "remote": remote})
    @property
    def install_errored(self):
        for _, act in self._inst_recipes_actions.items():
            if act.type == INSTALL_ERROR:
                return True
        for _, act in self._inst_packages_actions.items():
            if act.type == INSTALL_ERROR:
                return True
        return False

    def _get_installed_package(self, reference):
        p_ref = p_action = None
        for _package_ref, _package_action in self._inst_packages_actions.items():
            if _package_ref.conan == reference:
                p_ref = _package_ref
                p_action = _package_action
                break
        return p_ref, p_action

    def get_install_info(self):
        ret = {"error": self.install_errored,
               "packages": []}

        def get_doc_for_ref(the_ref, the_action):
            error = None if the_action.type != INSTALL_ERROR else the_action.doc
            doc = {"id": str(the_ref),
                   "downloaded": the_action.type == INSTALL_DOWNLOADED,
                   "built": the_action.type == INSTALL_BUILT,
                   "cache": the_action.type == INSTALL_CACHE,
                   "error": error,
                   "remote": the_action.doc.get("remote", None),
                   "time": the_action.time}
            if doc["remote"] is None and error:
                doc["remote"] = error.get("remote", None)
            return doc

        for ref, action in self._inst_recipes_actions.items():
            recipe_doc = get_doc_for_ref(ref, action)
            del recipe_doc["built"]  # Avoid confusions
            p_ref, p_action = self._get_installed_package(ref)
            tmp = {"recipe": recipe_doc,
                   "package": get_doc_for_ref(p_ref.package_id, p_action) if p_ref else None}
            ret["packages"].append(tmp)

        return ret
