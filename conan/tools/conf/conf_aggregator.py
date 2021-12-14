import os
import json
from collections import OrderedDict

from conans.util.files import save


class ConfAggregator:
    """Generator that accumulate the configs from the build-require dependencies"""
    filename = "conf_aggregator.json"

    def __init__(self, conanfile):
        self._conanfile = conanfile
        self.data = OrderedDict()
        # Same behavior than _receive_conf, direct build requires only
        for dep in self._conanfile.dependencies.direct_build.values():
            if dep.conf_info:
                for key, value in dep.conf_info.items():
                    if key in self.data:
                        self.data[key].append(value)
                    else:
                        self.data[key] = [value, ]

    @property
    def content(self):
        return json.dumps(self.data)

    def generate(self):
        path = os.path.join(self._conanfile.generators_folder, self.filename)
        save(path, self.content)
