from conans.client.recorder.action_recorder import INSTALL_ERROR_MISSING
from conans.errors import ConanException
from conans.model.ref import PackageReference
from conans.util.files import rmdir, make_read_only
from conans.util.env_reader import get_env


def raise_package_not_found_error(conan_file, conan_ref, package_id, out, recorder, remote_url):
    settings_text = ", ".join(conan_file.info.full_settings.dumps().splitlines())
    options_text = ", ".join(conan_file.info.full_options.dumps().splitlines())

    msg = '''Can't find a '%s' package for the specified options and settings:
- Settings: %s
- Options: %s
- Package ID: %s
''' % (conan_ref, settings_text, options_text, package_id)
    out.warn(msg)
    recorder.package_install_error(PackageReference(conan_ref, package_id),
                                   INSTALL_ERROR_MISSING, msg, remote=remote_url)
    raise ConanException('''Missing prebuilt package for '%s'
Try to build it from sources with "--build %s"
Or read "http://docs.conan.io/en/latest/faq/troubleshooting.html#error-missing-prebuilt-package"
''' % (conan_ref, conan_ref.name))


def get_package(conanfile, package_ref, package_folder, output, recorder, remote_manager, remote):
    try:
        # remote will be defined, as package availability has been checked from installer
        remote_manager.get_package(conanfile, package_ref, package_folder, remote, output, recorder)
        if get_env("CONAN_READ_ONLY_CACHE", False):
            make_read_only(package_folder)
        recorder.package_downloaded(package_ref, remote.url)
        return True
    except BaseException as e:
        output.error("Exception while getting package: %s" % str(package_ref.package_id))
        output.error("Exception: %s %s" % (type(e), str(e)))
        _clean_package(package_folder, output)
        raise


def _clean_package(package_folder, output):
    try:
        output.warn("Trying to remove package folder: %s" % package_folder)
        rmdir(package_folder)
    except OSError as e:
        raise ConanException("%s\n\nCouldn't remove folder '%s', might be busy or open. Close any app "
                             "using it, and retry" % (str(e), package_folder))
