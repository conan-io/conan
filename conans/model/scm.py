import json
from conans.util.files import load, save
import re
import os
from conans.client.tools.git import git_origin, git_uncommitted, git_branch,\
    git_commit


def capture_export_scm_data(scm_origin_folder, conanfile, output):
    scm = SCM.get_scm(conanfile)
    if not scm:
        return

    user_folder = os.path.dirname(scm_origin_folder).replace("\\", "/")

    if scm.url == "auto":  # get origin
        origin = git_origin(user_folder)
        if origin:
            output.success("Repo origin deduced by 'auto': %s" % origin)
            scm.type = "git"
            scm.url = origin
        else:
            output.warn("Repo origin cannot be deduced by 'auto', using source folder")
            scm.url = user_folder
            scm.checkout = SCM.SOURCE

    if scm.is_source_folder():
        scm.url = user_folder
    elif scm.checkout in [SCM.BRANCH, SCM.COMMIT]:
        modified = git_uncommitted(user_folder)
        if modified:
            output.warn("Repo is modified, using source folder")
            scm.checkout = SCM.SOURCE
            scm.url = user_folder
        else:
            if scm.checkout == "branch":
                scm.checkout = git_branch(user_folder)
            elif scm.checkout == "commit":
                scm.checkout = git_commit(user_folder)

    return scm


class SCM(object):
    SOURCE = "source"
    BRANCH = "branch"
    COMMIT = "commit"

    def __init__(self, data):
        self.url = data.get("url")
        self.checkout = data.get("checkout")
        self.type = data.get("type")

    @staticmethod
    def get_scm(conanfile):
        data = getattr(conanfile, "scm", None)
        if data is not None:
            return SCM(data)

    def is_source_folder(self):
        return self.checkout == SCM.SOURCE

    def __repr__(self):
        d = {"url": self.url, "checkout": self.checkout, "type": self.type}
        d = {k: v for k, v in d.items() if v}
        return json.dumps(d)

    def is_git(self):
        if not self.url:
            return False
        return self.url.startswith("git") or self.url.endswith(".git") or self.type == "git"

    def replace_in_file(self, path):
        content = load(path)
        dumps = self.__repr__()
        dumps = ",\n          ".join(dumps.split(","))
        content = re.sub(
           r"scm\s*=\s*{[^}]*}", "scm = %s" % dumps,
           content)
        save(path, content)
