import os
from conans.errors import ConanException
from conans.util.files import load, save
from collections import OrderedDict, namedtuple
import fasteners



default_remotes = """conan.io https://server.conan.io
local http://localhost:9300
"""

Remote = namedtuple("Remote", "name url")


class RemoteRegistry(object):
    """ conan_ref: remote
    remote is (name, url)
    """
    def __init__(self, filename, output):
        self._filename = filename
        self._output = output

    def _parse(self, contents):
        remotes = OrderedDict()
        refs = {}
        end_remotes = False
        # Parse the file
        for line in contents.splitlines():
            line = line.strip()

            if not line:
                if end_remotes:
                    raise ConanException("Bad file format, blank line %s" % self._filename)
                end_remotes = True
                continue
            ref, remote = line.split()
            if not end_remotes:
                remotes[ref] = remote
            else:
                refs[ref] = remote
        return remotes, refs

    def _to_string(self, remotes, refs):
        lines = ["%s %s" % (ref, remote) for ref, remote in remotes.items()]
        lines.append("")
        lines.extend(["%s %s" % (ref, remote) for ref, remote in sorted(refs.items())])
        text = os.linesep.join(lines)
        return text

    def _load(self):
        try:
            contents = load(self._filename)
        except:
            self._output.warn("Remotes registry file missing, creating default one in %s"
                              % self._filename)
            contents = default_remotes
            save(self._filename, contents)
        return self._parse(contents)

    def _save(self, remotes, refs):
        save(self._filename, self._to_string(remotes, refs))

    @property
    def default_remote(self):
        try:
            return self.remotes[0]
        except:
            raise ConanException("No default remote defined in %s" % self._filename)

    @property
    def remotes(self):
        with fasteners.InterProcessLock(self._filename + ".lock"):
            remotes, _ = self._load()
            return [Remote(ref, remote) for ref, remote in remotes.items()]

    @property
    def refs(self):
        with fasteners.InterProcessLock(self._filename + ".lock"):
            _, refs = self._load()
            return refs

    def remote(self, name):
        with fasteners.InterProcessLock(self._filename + ".lock"):
            remotes, _ = self._load()
            try:
                return Remote(name, remotes[name])
            except KeyError:
                raise ConanException("No remote '%s' defined in remotes in file %s"
                                     % (name, self._filename))

    def get_ref(self, conan_reference):
        with fasteners.InterProcessLock(self._filename + ".lock"):
            remotes, refs = self._load()
            remote_name = refs.get(str(conan_reference))
            try:
                return Remote(remote_name, remotes[remote_name])
            except:
                return None

    def remove_ref(self, conan_reference, quiet=False):
        with fasteners.InterProcessLock(self._filename + ".lock"):
            conan_reference = str(conan_reference)
            remotes, refs = self._load()
            try:
                del refs[conan_reference]
                self._save(remotes, refs)
            except:
                if not quiet:
                    self._output.warn("Couldn't delete '%s' from remote registry"
                                      % conan_reference)

    def set_ref(self, conan_reference, remote):
        with fasteners.InterProcessLock(self._filename + ".lock"):
            conan_reference = str(conan_reference)
            remotes, refs = self._load()
            refs[conan_reference] = remote.name
            self._save(remotes, refs)

    def add_ref(self, conan_reference, remote):
        with fasteners.InterProcessLock(self._filename + ".lock"):
            conan_reference = str(conan_reference)
            remotes, refs = self._load()
            if conan_reference in refs:
                raise ConanException("%s already exists. Use update" % conan_reference)
            if remote not in remotes:
                raise ConanException("%s not in remotes" % remote)
            refs[conan_reference] = remote
            self._save(remotes, refs)

    def update_ref(self, conan_reference, remote):
        with fasteners.InterProcessLock(self._filename + ".lock"):
            conan_reference = str(conan_reference)
            remotes, refs = self._load()
            if conan_reference not in refs:
                raise ConanException("%s does not exist. Use add" % conan_reference)
            if remote not in remotes:
                raise ConanException("%s not in remotes" % remote)
            refs[conan_reference] = remote
            self._save(remotes, refs)

    def add(self, remote_name, remote):
        with fasteners.InterProcessLock(self._filename + ".lock"):
            remotes, refs = self._load()
            if remote_name in remotes:
                raise ConanException("Remote %s already exist in remotes (use update to modify)"
                                     % remote_name)
            remotes[remote_name] = remote
            self._save(remotes, refs)

    def remove(self, remote_name):
        with fasteners.InterProcessLock(self._filename + ".lock"):
            remotes, refs = self._load()
            if remote_name not in remotes:
                raise ConanException("%s not found in remotes" % remote_name)
            del remotes[remote_name]
            refs = {k: v for k, v in refs.items() if v!=remote_name}
            self._save(remotes, refs)

    def update(self, remote_name, remote):
        with fasteners.InterProcessLock(self._filename + ".lock"):
            remotes, refs = self._load()
            if remote_name not in remotes:
                raise ConanException("%s not found in remotes" % remote_name)
            remotes[remote_name] = remote
            self._save(remotes, refs)
