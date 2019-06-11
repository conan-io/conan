
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


def _cpp_info_to_dict(cpp_info):
    doc = {}
    for it, value in vars(cpp_info).items():
        if it.startswith("_") or not value:
            continue

        if it == "configs":
            configs_data = {}
            for cfg_name, cfg_cpp_info in value.items():
                configs_data[cfg_name] = _cpp_info_to_dict(cfg_cpp_info)
            doc["configs"] = configs_data
            continue

        doc[it] = value
    return doc


class Action(namedtuple("Action", "type, full_ref, doc, time")):

    def __new__(cls, the_type, full_ref, doc=None):
        doc = doc or {}
        the_time = datetime.utcnow()
        return super(cls, Action).__new__(cls, the_type, full_ref, doc, the_time)


class ActionRecorder(object):

    def __init__(self):
        self.error = False
        self._inst_recipes_actions = OrderedDict()
        self._inst_packages_actions = OrderedDict()
        self._inst_recipes_develop = set()  # Recipes being created (to set dependency=False)
        self._inst_packages_info = defaultdict(dict)

    # ###### INSTALL METHODS ############
    def add_recipe_being_developed(self, ref):
        assert(isinstance(ref, ConanFileReference))
        self._inst_recipes_develop.add(ref.copy_clear_rev())

    def _add_recipe_action(self, ref, action):
        assert(isinstance(ref, ConanFileReference))
        ref = ref.copy_clear_rev()
        if ref not in self._inst_recipes_actions:
            self._inst_recipes_actions[ref] = []
        self._inst_recipes_actions[ref].append(action)

    def _add_package_action(self, pref, action):
        assert(isinstance(pref, PackageReference))
        pref = pref.copy_clear_revs()
        if pref not in self._inst_packages_actions:
            self._inst_packages_actions[pref] = []
        self._inst_packages_actions[pref].append(action)

    # RECIPE METHODS
    def recipe_exported(self, ref):
        self._add_recipe_action(ref, Action(INSTALL_EXPORTED, ref))

    def recipe_fetched_from_cache(self, ref):
        self._add_recipe_action(ref, Action(INSTALL_CACHE, ref))

    def recipe_downloaded(self, ref, remote_name):
        self._add_recipe_action(ref, Action(INSTALL_DOWNLOADED, ref, {"remote": remote_name}))

    def recipe_install_error(self, ref, error_type, description, remote_name):
        doc = {"type": error_type, "description": description, "remote": remote_name}
        self._add_recipe_action(ref, Action(INSTALL_ERROR, ref, doc))

    # PACKAGE METHODS
    def package_exported(self, pref):
        self._add_package_action(pref, Action(INSTALL_EXPORTED, pref))

    def package_built(self, pref):
        self._add_package_action(pref, Action(INSTALL_BUILT, pref))

    def package_fetched_from_cache(self, pref):
        self._add_package_action(pref, Action(INSTALL_CACHE, pref))

    def package_downloaded(self, pref, remote_name):
        self._add_package_action(pref, Action(INSTALL_DOWNLOADED, pref, {"remote": remote_name}))

    def package_install_error(self, pref, error_type, description, remote_name=None):
        assert(isinstance(pref, PackageReference))
        if pref not in self._inst_packages_actions:
            self._inst_packages_actions[pref.copy_clear_revs()] = []
        doc = {"type": error_type, "description": description, "remote": remote_name}
        self._inst_packages_actions[pref.copy_clear_revs()].append(Action(INSTALL_ERROR, pref, doc))

    def package_cpp_info(self, pref, cpp_info):
        assert isinstance(pref, PackageReference)
        # assert isinstance(cpp_info, CppInfo)
        self._inst_packages_info[pref.copy_clear_revs()]['cpp_info'] = _cpp_info_to_dict(cpp_info)

    @property
    def install_errored(self):
        all_values = list(self._inst_recipes_actions.values()) + list(self._inst_packages_actions.values())
        for acts in all_values:
            for act in acts:
                if act.type == INSTALL_ERROR:
                    return True
        return False

    def _get_installed_packages(self, ref):
        assert(isinstance(ref, ConanFileReference))
        ret = []
        for _pref, _package_actions in self._inst_packages_actions.items():
            # Could be a download and then an access to cache, we want the first one
            _package_action = _package_actions[0]
            if _pref.ref == ref:
                ret.append((_pref, _package_action))
        return ret

    def in_development_recipe(self, ref):
        return ref in self._inst_recipes_develop

    def get_info(self, revisions_enabled):
        return self.get_install_info(revisions_enabled)

    def get_install_info(self, revisions_enabled):
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
            if revisions_enabled and isinstance(the_ref, ConanFileReference):
                the_id = the_actions[0].full_ref.full_repr()
            else:
                the_id = str(the_ref)

            doc = {"id": the_id,
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
            for pref, p_action in packages:
                p_doc = get_doc_for_ref(pref.id, [p_action])
                package_data = self._inst_packages_info.get(pref, {})
                p_doc.update(package_data)
                tmp["packages"].append(p_doc)

            ret["installed"].append(tmp)

        return ret
