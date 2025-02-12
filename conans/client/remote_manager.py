import os
import shutil
from typing import List

from requests.exceptions import ConnectionError

from conan.api.model import LOCAL_RECIPES_INDEX
from conans.client.rest_client_local_recipe_index import RestApiClientLocalRecipesIndex
from conan.api.model import Remote
from conan.api.output import ConanOutput
from conan.internal.cache.conan_reference_layout import METADATA
from conans.client.pkg_sign import PkgSignaturesPlugin
from conan.internal.errors import ConanConnectionError, NotFoundException, PackageNotFoundException
from conan.errors import ConanException
from conan.internal.model.info import load_binary_info
from conan.api.model import PkgReference
from conan.api.model import RecipeReference
from conans.util.files import rmdir, human_size
from conan.internal.paths import EXPORT_SOURCES_TGZ_NAME, EXPORT_TGZ_NAME, PACKAGE_TGZ_NAME
from conans.util.files import mkdir, tar_extract


class RemoteManager:
    """ Will handle the remotes to get recipes, packages etc """
    def __init__(self, cache, auth_manager, home_folder):
        self._cache = cache
        self._auth_manager = auth_manager
        self._signer = PkgSignaturesPlugin(cache, home_folder)
        self._home_folder = home_folder

    def _local_folder_remote(self, remote):
        if remote.remote_type == LOCAL_RECIPES_INDEX:
            return RestApiClientLocalRecipesIndex(remote, self._home_folder)

    def check_credentials(self, remote, force_auth=False):
        self._call_remote(remote, "check_credentials", force_auth)

    def upload_recipe(self, ref, files_to_upload, remote):
        assert isinstance(ref, RecipeReference)
        assert ref.revision, "upload_recipe requires RREV"
        self._call_remote(remote, "upload_recipe", ref, files_to_upload)

    def upload_package(self, pref, files_to_upload, remote):
        assert pref.ref.revision, "upload_package requires RREV"
        assert pref.revision, "upload_package requires PREV"
        self._call_remote(remote, "upload_package", pref, files_to_upload)

    def get_recipe(self, ref, remote, metadata=None):
        assert ref.revision, "get_recipe without revision specified"
        assert ref.timestamp, "get_recipe without ref.timestamp specified"

        layout = self._cache.create_ref_layout(ref)

        export_folder = layout.export()
        local_folder_remote = self._local_folder_remote(remote)
        if local_folder_remote is not None:
            local_folder_remote.get_recipe(ref, export_folder)
            return layout

        download_export = layout.download_export()
        try:
            zipped_files = self._call_remote(remote, "get_recipe", ref, download_export, metadata,
                                             only_metadata=False)
            # The timestamp of the ``ref`` from the server has been already obtained by ConanProxy
            # or it will be obtained explicitly by the ``conan download``
            # filter metadata files
            # This could be also optimized in download, avoiding downloading them, for performance
            zipped_files = {k: v for k, v in zipped_files.items() if not k.startswith(METADATA)}
            # quick server package integrity check:
            if "conanfile.py" not in zipped_files:
                raise ConanException(f"Corrupted {ref} in '{remote.name}' remote: no conanfile.py")
            if "conanmanifest.txt" not in zipped_files:
                raise ConanException(f"Corrupted {ref} in '{remote.name}' remote: "
                                     f"no conanmanifest.txt")
            self._signer.verify(ref, download_export, files=zipped_files)
        except BaseException:  # So KeyboardInterrupt also cleans things
            ConanOutput(scope=str(ref)).error(f"Error downloading from remote '{remote.name}'", error_type="exception")
            self._cache.remove_recipe_layout(layout)
            raise
        export_folder = layout.export()
        tgz_file = zipped_files.pop(EXPORT_TGZ_NAME, None)

        if tgz_file:
            uncompress_file(tgz_file, export_folder, scope=str(ref))
        mkdir(export_folder)
        for file_name, file_path in zipped_files.items():  # copy CONANFILE
            shutil.move(file_path, os.path.join(export_folder, file_name))

        # Make sure that the source dir is deleted
        rmdir(layout.source())
        return layout

    def get_recipe_metadata(self, ref, remote, metadata):
        """
        Get only the metadata for a locally existing recipe in Cache
        """
        assert ref.revision, "get_recipe without revision specified"
        output = ConanOutput(scope=str(ref))
        output.info("Retrieving recipe metadata from remote '%s' " % remote.name)
        layout = self._cache.recipe_layout(ref)
        download_export = layout.download_export()
        try:
            self._call_remote(remote, "get_recipe", ref, download_export, metadata,
                              only_metadata=True)
        except BaseException:  # So KeyboardInterrupt also cleans things
            output.error(f"Error downloading metadata from remote '{remote.name}'", error_type="exception")
            raise

    def get_recipe_sources(self, ref, layout, remote):
        assert ref.revision, "get_recipe_sources requires RREV"

        download_folder = layout.download_export()
        export_sources_folder = layout.export_sources()
        local_folder_remote = self._local_folder_remote(remote)
        if local_folder_remote is not None:
            local_folder_remote.get_recipe_sources(ref, export_sources_folder)
            return

        zipped_files = self._call_remote(remote, "get_recipe_sources", ref, download_folder)
        if not zipped_files:
            mkdir(export_sources_folder)  # create the folder even if no source files
            return

        self._signer.verify(ref, download_folder, files=zipped_files)
        tgz_file = zipped_files[EXPORT_SOURCES_TGZ_NAME]
        uncompress_file(tgz_file, export_sources_folder, scope=str(ref))

    def get_package(self, pref, remote, metadata=None):
        output = ConanOutput(scope=str(pref.ref))
        output.info("Retrieving package %s from remote '%s' " % (pref.package_id, remote.name))

        assert pref.revision is not None

        pkg_layout = self._cache.create_pkg_layout(pref)
        with pkg_layout.set_dirty_context_manager():
            self._get_package(pkg_layout, pref, remote, output, metadata)

    def get_package_metadata(self, pref, remote, metadata):
        """
        only download the metadata, not the packge itself
        """
        output = ConanOutput(scope=str(pref.ref))
        output.info("Retrieving package metadata %s from remote '%s' "
                    % (pref.package_id, remote.name))

        assert pref.revision is not None
        pkg_layout = self._cache.pkg_layout(pref)
        try:
            download_pkg_folder = pkg_layout.download_package()
            self._call_remote(remote, "get_package", pref, download_pkg_folder,
                              metadata, only_metadata=True)
        except BaseException as e:  # So KeyboardInterrupt also cleans things
            output.error(f"Exception while getting package metadata: {str(pref.package_id)}", error_type="exception")
            output.error(f"Exception: {type(e)} {str(e)}", error_type="exception")
            raise

    def _get_package(self, layout, pref, remote, scoped_output, metadata):
        try:
            assert pref.revision is not None

            download_pkg_folder = layout.download_package()
            # Download files to the pkg_tgz folder, not to the final one
            zipped_files = self._call_remote(remote, "get_package", pref, download_pkg_folder,
                                             metadata, only_metadata=False)
            zipped_files = {k: v for k, v in zipped_files.items() if not k.startswith(METADATA)}
            # quick server package integrity check:
            for f in ("conaninfo.txt", "conanmanifest.txt", "conan_package.tgz"):
                if f not in zipped_files:
                    raise ConanException(f"Corrupted {pref} in '{remote.name}' remote: no {f}")
            self._signer.verify(pref, download_pkg_folder, zipped_files)

            tgz_file = zipped_files.pop(PACKAGE_TGZ_NAME, None)
            package_folder = layout.package()
            uncompress_file(tgz_file, package_folder, scope=str(pref.ref))
            mkdir(package_folder)  # Just in case it doesn't exist, because uncompress did nothing
            for file_name, file_path in zipped_files.items():  # copy CONANINFO and CONANMANIFEST
                shutil.move(file_path, os.path.join(package_folder, file_name))

            scoped_output.success('Package installed %s' % pref.package_id)
            scoped_output.info("Downloaded package revision %s" % pref.revision)
        except NotFoundException:
            raise PackageNotFoundException(pref)
        except BaseException as e:  # So KeyboardInterrupt also cleans things
            self._cache.remove_package_layout(layout)
            scoped_output.error(f"Exception while getting package: {str(pref.package_id)}", error_type="exception")
            scoped_output.error(f"Exception: {type(e)} {str(e)}", error_type="exception")
            raise

    def search_recipes(self, remote, pattern):
        cached_method = remote._caching.setdefault("search_recipes", {})
        try:
            return cached_method[pattern]
        except KeyError:
            result = self._call_remote(remote, "search", pattern)
            cached_method[pattern] = result
            return result

    def search_packages(self, remote, ref):
        packages = self._call_remote(remote, "search_packages", ref)
        # Avoid serializing conaninfo in server side
        packages = {PkgReference(ref, pid): load_binary_info(data["content"])
                    if "content" in data else data
                    for pid, data in packages.items() if not data.get("recipe_hash")}
        return packages

    def remove_recipe(self, ref, remote):
        return self._call_remote(remote, "remove_recipe", ref)

    def remove_packages(self, prefs, remote):
        return self._call_remote(remote, "remove_packages", prefs)

    def remove_all_packages(self, ref, remote):
        return self._call_remote(remote, "remove_all_packages", ref)

    def authenticate(self, remote, name, password):
        return self._call_remote(remote, 'authenticate', name, password, enforce_disabled=False)

    def get_recipe_revisions_references(self, ref, remote):
        assert ref.revision is None, "get_recipe_revisions_references of a reference with revision"
        return self._call_remote(remote, "get_recipe_revisions_references", ref)

    def get_package_revisions_references(self, pref, remote, headers=None) -> List[PkgReference]:
        assert pref.revision is None, "get_package_revisions_references of a reference with revision"
        return self._call_remote(remote, "get_package_revisions_references", pref, headers=headers)

    def get_latest_recipe_reference(self, ref, remote):
        assert ref.revision is None, "get_latest_recipe_reference of a reference with revision"
        return self._call_remote(remote, "get_latest_recipe_reference", ref)

    def get_latest_package_reference(self, pref, remote, info=None) -> PkgReference:
        assert pref.revision is None, "get_latest_package_reference of a reference with revision"
        # These headers are useful to know what configurations are being requested in the server
        headers = None
        if info:
            headers = {}
            settings = [f'{k}={v}' for k, v in info.settings.items()]
            if settings:
                headers['Conan-PkgID-Settings'] = ';'.join(settings)
            options = [f'{k}={v}' for k, v in info.options.serialize().items()
                       if k in ("shared", "fPIC", "header_only")]
            if options:
                headers['Conan-PkgID-Options'] = ';'.join(options)

        cached_method = remote._caching.setdefault("get_latest_package_reference", {})
        try:
            return cached_method[pref]
        except KeyError:
            result = self._call_remote(remote, "get_latest_package_reference", pref, headers=headers)
            cached_method[pref] = result
            return result

    def get_recipe_revision_reference(self, ref, remote) -> bool:
        assert ref.revision is not None, "recipe_exists needs a revision"
        return self._call_remote(remote, "get_recipe_revision_reference", ref)

    def get_package_revision_reference(self, pref, remote) -> bool:
        assert pref.revision is not None, "get_package_revision_reference needs a revision"
        return self._call_remote(remote, "get_package_revision_reference", pref)

    def _call_remote(self, remote, method, *args, **kwargs):
        assert (isinstance(remote, Remote))
        enforce_disabled = kwargs.pop("enforce_disabled", True)
        if remote.disabled and enforce_disabled:
            raise ConanException("Remote '%s' is disabled" % remote.name)
        local_folder_remote = self._local_folder_remote(remote)
        if local_folder_remote is not None:
            return local_folder_remote.call_method(method, *args, **kwargs)
        try:
            return self._auth_manager.call_rest_api_method(remote, method, *args, **kwargs)
        except ConnectionError as exc:
            raise ConanConnectionError(("%s\n\nUnable to connect to remote %s=%s\n"
                                        "1. Make sure the remote is reachable or,\n"
                                        "2. Disable it with 'conan remote disable <remote>' or,\n"
                                        "3. Use the '-nr/--no-remote' argument\n"
                                        "Then try again."
                                        ) % (str(exc), remote.name, remote.url))
        except ConanException as exc:
            exc.remote = remote
            raise
        except Exception as exc:
            raise ConanException(exc, remote=remote)


def uncompress_file(src_path, dest_folder, scope=None):
    try:
        filesize = os.path.getsize(src_path)
        big_file = filesize > 10000000  # 10 MB
        if big_file:
            hs = human_size(filesize)
            ConanOutput(scope=scope).info(f"Decompressing {hs} {os.path.basename(src_path)}")
        with open(src_path, mode='rb') as file_handler:
            tar_extract(file_handler, dest_folder)
    except Exception as e:
        error_msg = "Error while extracting downloaded file '%s' to %s\n%s\n"\
                    % (src_path, dest_folder, str(e))
        # try to remove the files
        try:
            if os.path.exists(dest_folder):
                shutil.rmtree(dest_folder)
                error_msg += "Folder removed"
        except Exception:
            error_msg += "Folder not removed, files/package might be damaged, remove manually"
        raise ConanException(error_msg)
