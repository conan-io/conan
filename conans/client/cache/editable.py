import json
import os
from contextlib import contextmanager
from os.path import join, normpath

from conans.model.ref import ConanFileReference
from conans.util.files import load, save


EDITABLE_PACKAGES_FILE = 'editable_packages.json'


class EditablePackages(object):
    def __init__(self, cache_folder):
        self._cache_folder = cache_folder
        self._edited_file = normpath(join(cache_folder, EDITABLE_PACKAGES_FILE))
        if os.path.exists(self._edited_file):
            edited = load(self._edited_file)
            edited_js = json.loads(edited)
            self._edited_refs = {ConanFileReference.loads(r, validate=False): d
                                 for r, d in edited_js.items()}
        else:
            self._edited_refs = {}  # {ref: {"path": path, "layout": layout}}

    @property
    def edited_refs(self):
        return self._edited_refs

    def save(self):
        d = {str(ref): d for ref, d in self._edited_refs.items()}
        save(self._edited_file, json.dumps(d))

    def get(self, ref):
        ref = ref.copy_clear_rev()
        return self._edited_refs.get(ref)

    def add(self, ref, path, layout, output_folder=None):
        assert isinstance(ref, ConanFileReference)
        ref = ref.copy_clear_rev()
        self._edited_refs[ref] = {"path": path, "layout": layout, "output_folder": output_folder}
        self.save()

    def remove(self, ref):
        assert isinstance(ref, ConanFileReference)
        ref = ref.copy_clear_rev()
        if self._edited_refs.pop(ref, None):
            self.save()
            return True
        return False

    def override(self, workspace_edited):
        self._edited_refs = workspace_edited

    @contextmanager
    def disable_editables(self):
        """
        Temporary disable editables, if we want to make operations on the cache, as updating
        remotes in packages metadata.
        """
        edited_refs = self._edited_refs
        self._edited_refs = {}
        yield
        self._edited_refs = edited_refs
