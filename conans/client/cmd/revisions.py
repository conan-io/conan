import os

from conans.errors import NotFoundException
from conans.util.time import from_timestamp_to_datetime


def get_local_recipe_revisions(ref, cache):
    if not os.path.exists(cache.export(ref)):
        raise NotFoundException("Recipe not found: '%s'" % ref.full_repr())
    ret = {"reference": ref.full_repr(), "revisions": []}
    metadata = cache.load_metadata(ref)
    the_time = from_timestamp_to_datetime(metadata.recipe.time) \
        if metadata.recipe.time else None
    ret["revisions"].append({"revision": metadata.recipe.revision,
                             "time": the_time})
    return ret


def get_local_package_revisions(pref, cache):
    ret = {"reference": pref.full_repr(), "revisions": []}
    if not os.path.exists(cache.export(pref.ref)) or \
            (pref.ref.revision and
             cache.load_metadata(pref.ref).recipe.revision != pref.ref.revision):
        raise NotFoundException("Recipe not found: '%s'" % pref.ref.full_repr())
    if not os.path.exists(cache.package(pref)):
        raise NotFoundException("Package not found: '%s'" % pref.full_repr())
    metadata = cache.load_metadata(pref.ref)
    if metadata.packages[pref.id].time:
        tm = from_timestamp_to_datetime(metadata.packages[pref.id].time)
    else:
        tm = None
    ret["revisions"].append({"revision": metadata.packages[pref.id].revision,
                             "time": tm})
    return ret
