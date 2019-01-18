import os

from conans.errors import NotFoundException
from conans.util.dates import from_timestamp_to_datetime


def get_local_recipe_revision(ref, cache):
    if not os.path.exists(cache.export(ref)):
        raise NotFoundException("Recipe not found: '%s'" % ref.full_repr())
    metadata = cache.load_metadata(ref)
    the_time = from_timestamp_to_datetime(metadata.recipe.time) \
        if metadata.recipe.time else None
    return metadata.recipe.revision, the_time


def get_local_package_revision(pref, cache):
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

    return metadata.packages[pref.id].revision, tm
