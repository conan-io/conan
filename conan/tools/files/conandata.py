import os

import yaml

from conans.errors import ConanException
from conans.util.files import load, save


def update_conandata(conanfile, data):
    """
    this only works for updating the conandata on the export() method, it seems it would
    be plain wrong to try to change it anywhere else
    """
    if not hasattr(conanfile, "export_folder") or conanfile.export_folder is None:
        raise ConanException("The 'update_conandata()' can only be used in the 'export()' method")
    path = os.path.join(conanfile.export_folder, "conandata.yml")
    if os.path.exists(path):
        conandata = load(path)
        conandata = yaml.safe_load(conandata)
    else:  # File doesn't exist, create it
        conandata = {}

    def recursive_dict_update(d, u):
        for k, v in u.items():
            if isinstance(v, dict):
                d[k] = recursive_dict_update(d.get(k, {}), v)
            else:
                d[k] = v
        return d

    recursive_dict_update(conandata, data)
    new_content = yaml.safe_dump(conandata)
    save(path, new_content)
