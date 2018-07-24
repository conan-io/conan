import os
import fasteners

from collections import OrderedDict, namedtuple

from conans.errors import ConanException, NoRemoteAvailable
from conans.model.ref import ConanFileReference
from conans.util.files import load, save
from conans.util.config_parser import get_bool_from_text_value
from conans.util.log import logger


default_remotes = "conan-center https://conan.bintray.com True"

Remote = namedtuple("Remote", "name url verify_ssl")


class RemoteRegistry(object):
    """ conan_ref: remote
    remote is (name, url)
    """
    def __init__(self, filename, output):
        self._filename = filename
        self._output = output
        self._remotes = None

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
            chunks = line.split()
            if not end_remotes:
                if len(chunks) == 2:  # Retro compatibility
                    ref, remote_name = chunks
                    verify_ssl = "True"
                elif len(chunks) == 3:
                    ref, remote_name, verify_ssl = chunks
                else:
                    raise ConanException("Bad file format, wrong item numbers in line '%s'" % line)

                verify_ssl = get_bool_from_text_value(verify_ssl)
                remotes[ref] = (remote_name, verify_ssl)
            else:
                ref, remote_name = chunks
                refs[ref] = remote_name

        return remotes, refs

    def _to_string(self, remotes, refs):
        lines = ["%s %s %s" % (ref, remote_name, verify_ssl) for ref, (remote_name, verify_ssl) in remotes.items()]
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
        except IndexError:
            raise NoRemoteAvailable("No default remote defined in %s" % self._filename)

    @property
    def remotes(self):
        return list(self._remote_dict.values())

    def remote(self, remote_name):
        try:
            return self._remote_dict[remote_name]
        except KeyError:
            raise NoRemoteAvailable("No remote '%s' defined in remotes in file %s"
                                    % (remote_name, self._filename))

    @property
    def _remote_dict(self):
        if self._remotes is None:
            with fasteners.InterProcessLock(self._filename + ".lock", logger=logger):
                remotes, _ = self._load()
                self._remotes = OrderedDict([(ref, Remote(ref, remote_name, verify_ssl))
                                             for ref, (remote_name, verify_ssl) in remotes.items()])
        return self._remotes

    @property
    def refs(self):
        with fasteners.InterProcessLock(self._filename + ".lock", logger=logger):
            _, refs = self._load()
            return refs

    def get_recipe_remote(self, conan_reference):
        assert(isinstance(conan_reference, ConanFileReference))
        with fasteners.InterProcessLock(self._filename + ".lock", logger=logger):
            remotes, refs = self._load()
            remote_name = refs.get(str(conan_reference))
            try:
                return Remote(remote_name, remotes[remote_name][0], remotes[remote_name][1])
            except:
                return None

    def remove_ref(self, conan_reference, quiet=False):
        assert(isinstance(conan_reference, ConanFileReference))
        with fasteners.InterProcessLock(self._filename + ".lock", logger=logger):
            remotes, refs = self._load()
            try:
                del refs[str(conan_reference)]
                self._save(remotes, refs)
            except:
                if not quiet:
                    self._output.warn("Couldn't delete '%s' from remote registry"
                                      % str(conan_reference))

    def set_ref(self, conan_reference, remote_name, check_exists=False):
        assert(isinstance(conan_reference, ConanFileReference))
        with fasteners.InterProcessLock(self._filename + ".lock", logger=logger):
            remotes, refs = self._load()
            if check_exists:
                if conan_reference in refs:
                    raise ConanException("%s already exists. Use update" % conan_reference)
                if remote_name not in remotes:
                    raise ConanException("%s not in remotes" % remote_name)
            refs[str(conan_reference)] = remote_name
            self._save(remotes, refs)

    def update_ref(self, conan_reference, remote_name):
        assert(isinstance(conan_reference, ConanFileReference))
        with fasteners.InterProcessLock(self._filename + ".lock", logger=logger):
            remotes, refs = self._load()
            if str(conan_reference) not in refs:
                raise ConanException("%s does not exist. Use add" % str(conan_reference))
            if remote_name not in remotes:
                raise ConanException("%s not in remotes" % remote_name)
            refs[str(conan_reference)] = remote_name
            self._save(remotes, refs)

    def _upsert(self, remote_name, url, verify_ssl, insert):
        self._remotes = None  # invalidate cached remotes
        with fasteners.InterProcessLock(self._filename + ".lock", logger=logger):
            remotes, refs = self._load()
            # Remove duplicates
            remotes.pop(remote_name, None)
            remotes_list = []
            renamed = None
            for name, r in remotes.items():
                if r[0] != url:
                    remotes_list.append((name, r))
                else:
                    renamed = name

            if insert is not None:
                try:
                    insert_index = int(insert)
                except ValueError:
                    raise ConanException("insert argument must be an integer")
                remotes_list.insert(insert_index, (remote_name, (url, verify_ssl)))
                remotes = OrderedDict(remotes_list)
            else:
                remotes = OrderedDict(remotes_list)
                remotes[remote_name] = (url, verify_ssl)

            if renamed:
                for k, v in refs.items():
                    if v == renamed:
                        refs[k] = remote_name
            self._save(remotes, refs)

    def add(self, remote_name, url, verify_ssl=True, insert=None, force=None):
        if force:
            return self._upsert(remote_name, url, verify_ssl, insert)

        def exists_function(remotes):
            if remote_name in remotes:
                raise ConanException("Remote '%s' already exists in remotes (use update to modify)"
                                     % remote_name)
        self._add_update(remote_name, url, verify_ssl, exists_function, insert)

    def remove(self, remote_name):
        self._remotes = None  # invalidate cached remotes
        with fasteners.InterProcessLock(self._filename + ".lock", logger=logger):
            remotes, refs = self._load()
            if remote_name not in remotes:
                raise ConanException("Remote '%s' not found in remotes" % remote_name)
            del remotes[remote_name]
            refs = {k: v for k, v in refs.items() if v != remote_name}
            self._save(remotes, refs)

    def update(self, remote_name, url, verify_ssl=True, insert=None):
        def exists_function(remotes):
            if remote_name not in remotes:
                raise ConanException("Remote '%s' not found in remotes" % remote_name)
        self._add_update(remote_name, url, verify_ssl, exists_function, insert)

    def rename(self, remote_name, new_remote_name):
        self._remotes = None  # invalidate cached remotes
        with fasteners.InterProcessLock(self._filename + ".lock", logger=logger):
            remotes, refs = self._load()
            if remote_name not in remotes:
                raise ConanException("Remote '%s' not found in remotes" % remote_name)
            new_remotes = OrderedDict()
            for name, info in remotes.items():
                name = name if name != remote_name else new_remote_name
                new_remotes[name] = info
            remotes = new_remotes
            for k, v in refs.items():
                if v == remote_name:
                    refs[k] = new_remote_name
            self._save(remotes, refs)

    def define_remotes(self, remotes):
        self._remotes = None  # invalidate cached remotes
        with fasteners.InterProcessLock(self._filename + ".lock", logger=logger):
            _, refs = self._load()
            new_remotes = OrderedDict()
            for remote in remotes:
                new_remotes[remote.name] = (remote.url, remote.verify_ssl)
            refs = {k: v for k, v in refs.items() if v in new_remotes}
            self._save(new_remotes, refs)

    def _add_update(self, remote_name, url, verify_ssl, exists_function, insert=None):
        self._remotes = None  # invalidate cached remotes
        with fasteners.InterProcessLock(self._filename + ".lock", logger=logger):
            remotes, refs = self._load()
            exists_function(remotes)
            urls = {r[0]: name for name, r in remotes.items() if name != remote_name}
            if url in urls:
                raise ConanException("Remote '%s' already exists with same URL" % urls[url])
            if insert is not None:
                try:
                    insert_index = int(insert)
                except ValueError:
                    raise ConanException("insert argument must be an integer")
                remotes.pop(remote_name, None)  # Remove if exists (update)
                remotes_list = list(remotes.items())
                remotes_list.insert(insert_index, (remote_name, (url, verify_ssl)))
                remotes = OrderedDict(remotes_list)
            else:
                remotes[remote_name] = (url, verify_ssl)
            self._save(remotes, refs)
