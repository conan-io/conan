import json
import os

from conans.client.profile_loader import _load_profile
from conans.model.options import OptionsValues
from conans.tools import save
from conans.util.files import load


GRAPH_INFO_FILE = "graph_info.json"


class GraphInfo(object):

    def __init__(self, profile=None, options=None):
        self.profile = profile
        # This field is a temporary hack, to store dependencies options for the local flow
        self.options = options

    @staticmethod
    def load(path):
        if not path:
            raise IOError("Invalid path")
        p = path if os.path.isfile(path) else os.path.join(path, GRAPH_INFO_FILE)
        return GraphInfo.loads(load(p))

    @staticmethod
    def loads(text):
        graph_json = json.loads(text)
        profile = graph_json["profile"]
        # FIXME: Reading private very ugly
        profile, _ = _load_profile(profile, None, None)
        try:
            options = graph_json["options"]
        except KeyError:
            options = None
        else:
            options = OptionsValues(options)
        return GraphInfo(profile=profile, options=options)

    def save(self, folder, filename=None):
        filename = filename or GRAPH_INFO_FILE
        p = os.path.join(folder, filename)
        serialized_graph_str = self.dumps()
        save(p, serialized_graph_str)

    def dumps(self):
        result = {"profile": self.profile.dumps()}
        if self.options is not None:
            result["options"] = self.options.as_list()
        return json.dumps(result, indent=True)
