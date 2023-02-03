import copy
import json
import os
from os.path import join, normpath

from conans.model.recipe_ref import RecipeReference
from conans.util.files import load, save


EDITABLE_PACKAGES_FILE = 'editable_packages.json'


class EditablePackages:
    def __init__(self, cache_folder):
        self._edited_file = normpath(join(cache_folder, EDITABLE_PACKAGES_FILE))
        if os.path.exists(self._edited_file):
            edited = load(self._edited_file)
            edited_js = json.loads(edited)
            self._edited_refs = {RecipeReference.loads(r): d
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
        _tmp = copy.copy(ref)
        _tmp.revision = None
        return self._edited_refs.get(_tmp)

    def get_path(self, ref):
        editable = self.get(ref)
        if editable is not None:
            return editable["path"]

    def add(self, ref, path, output_folder=None):
        assert isinstance(ref, RecipeReference)
        _tmp = copy.copy(ref)
        _tmp.revision = None
        self._edited_refs[ref] = {"path": path, "output_folder": output_folder}
        self.save()

    def remove(self, ref):
        assert isinstance(ref, RecipeReference)
        _tmp = copy.copy(ref)
        _tmp.revision = None
        if self._edited_refs.pop(_tmp, None):
            self.save()
            return True
        return False
