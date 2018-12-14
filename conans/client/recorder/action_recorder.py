
# FIXME: The functions from the tracer.py module should be called here, I removed from there some
# of them because it has to be called in the remote manager, not in the proxy, where we have info
# about the downloaded files prior to unzip them

from collections import OrderedDict, defaultdict, namedtuple
from datetime import datetime

# Install actions
from conans.model.ref import ConanFileReference, PackageReference

INSTALL_CACHE = 0
INSTALL_DOWNLOADED = 1
INSTALL_BUILT = 2
INSTALL_EXPORTED = 3
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
        self.error = False
        self._inst_recipes_actions = OrderedDict()
        self._inst_packages_actions = OrderedDict()
        self._inst_recipes_develop = set()  # Recipes being created (to set dependency=False)
        self._inst_packages_info = defaultdict(dict)

    # ###### INSTALL METHODS ############
    def add_recipe_being_developed(self, reference):
        assert(isinstance(reference, ConanFileReference))
        self._inst_recipes_develop.add(reference)

    def _add_recipe_action(self, reference, action):
        assert(isinstance(reference, ConanFileReference))
        reference = reference.copy_clear_rev()
        if reference not in self._inst_recipes_actions:
            self._inst_recipes_actions[reference] = []
        self._inst_recipes_actions[reference].append(action)

    def _add_package_action(self, reference, action):
        reference = reference.copy_clear_rev()
        assert(isinstance(reference, PackageReference))
        if reference not in self._inst_packages_actions:
            self._inst_packages_actions[reference] = []
        self._inst_packages_actions[reference].append(action)

    # RECIPE METHODS
    def recipe_exported(self, reference):
        self._add_recipe_action(reference, Action(INSTALL_EXPORTED))

    def recipe_fetched_from_cache(self, reference):
        self._add_recipe_action(reference, Action(INSTALL_CACHE))

    def recipe_downloaded(self, reference, remote_name):
        self._add_recipe_action(reference, Action(INSTALL_DOWNLOADED, {"remote": remote_name}))

    def recipe_install_error(self, reference, error_type, description, remote_name):
        doc = {"type": error_type, "description": description, "remote": remote_name}
        self._add_recipe_action(reference, Action(INSTALL_ERROR, doc))

    # PACKAGE METHODS
    def package_exported(self, reference):
        self._add_package_action(reference, Action(INSTALL_EXPORTED))

    def package_built(self, reference):
        self._add_package_action(reference, Action(INSTALL_BUILT))

    def package_fetched_from_cache(self, reference):
        self._add_package_action(reference, Action(INSTALL_CACHE))

    def package_downloaded(self, reference, remote_name):
        self._add_package_action(reference, Action(INSTALL_DOWNLOADED, {"remote": remote_name}))

    def package_install_error(self, reference, error_type, description, remote_name=None):
        assert(isinstance(reference, PackageReference))
        reference = reference.copy_clear_rev()
        if reference not in self._inst_packages_actions:
            self._inst_packages_actions[reference] = []
        doc = {"type": error_type, "description": description, "remote": remote_name}
        self._inst_packages_actions[reference].append(Action(INSTALL_ERROR, doc))

    def package_cpp_info(self, reference, cpp_info):
        assert isinstance(reference, PackageReference)
        reference = reference.copy_clear_rev()
        # assert isinstance(cpp_info, CppInfo)
        doc = {}
        for it, value in vars(cpp_info).items():
            if it.startswith("_") or not value:
                continue
            doc[it] = value
        self._inst_packages_info[reference]['cpp_info'] = doc

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
        ret = {"error": self.install_errored or self.error,
               "installed": []}

        def get_doc_for_ref(the_ref, the_actions):
            errors = [action.doc for action in the_actions if action.type == INSTALL_ERROR]
            error = None if not errors else errors[0]
            remotes = [action.doc.get("remote") for action in the_actions
                       if action.doc.get("remote", None) is not None]
            remote = None if not remotes else remotes[0]
            action_types = [action.type for action in the_actions]
            time = the_actions[0].time

            doc = {"id": str(the_ref),
                   "downloaded": INSTALL_DOWNLOADED in action_types,
                   "exported": INSTALL_EXPORTED in action_types,
                   "error": error,
                   "remote": remote,
                   "time": time}
            if isinstance(the_ref, ConanFileReference):
                doc["dependency"] = not self.in_development_recipe(the_ref.copy_clear_rev())
                doc["name"] = the_ref.name
                doc["version"] = the_ref.version
                doc["user"] = the_ref.user
                doc["channel"] = the_ref.channel
                if the_ref.revision:
                    doc["revision"] = the_ref.revision
            else:
                doc["built"] = INSTALL_BUILT in action_types

            if doc["remote"] is None and error:
                doc["remote"] = error.get("remote", None)
            return doc

        for ref, actions in self._inst_recipes_actions.items():
            tmp = {"recipe": get_doc_for_ref(ref, actions),
                   "packages": []}

            packages = self._get_installed_packages(ref)
            for p_ref, p_action in packages:
                p_doc = get_doc_for_ref(p_ref.package_id, [p_action])
                package_data = self._inst_packages_info.get(p_ref, {})
                p_doc.update(package_data)
                tmp["packages"].append(p_doc)

            ret["installed"].append(tmp)

        return ret
