from conan.internal.rest.client_routes import ClientV2Router
from conan.internal.util.files import sha1sum


def add_urls(package_list, remote):
    router = ClientV2Router(remote.url.rstrip("/"))
    for ref, bundle in package_list.refs().items():
        for f, fp in bundle.get("files", {}).items():
            bundle.setdefault("upload-urls", {})[f] = {
                'url': router.recipe_file(ref, f), 'checksum': sha1sum(fp)
            }
        for pref, prev_bundle in package_list.prefs(ref, bundle).items():
            for f, fp in prev_bundle.get("files", {}).items():
                prev_bundle.setdefault("upload-urls", {})[f] = {
                    'url': router.package_file(pref, f), 'checksum': sha1sum(fp)
                }
