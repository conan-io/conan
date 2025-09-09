from conan.internal.rest.client_routes import ClientV2Router
from conan.internal.util.files import sha1sum


def add_urls(package_list, remote):
    router = ClientV2Router(remote.url.rstrip("/"))
    for ref, ref_info, packages in package_list.walk():
        for f, fp in ref_info.get("files", {}).items():
            ref_info.setdefault("upload-urls", {})[f] = {
                'url': router.recipe_file(ref, f), 'checksum': sha1sum(fp)
            }
        for pref, pref_info in packages.items():
            for f, fp in pref_info.get("files", {}).items():
                pref_info.setdefault("upload-urls", {})[f] = {
                    'url': router.package_file(pref, f), 'checksum': sha1sum(fp)
                }
