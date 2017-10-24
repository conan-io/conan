import hashlib
import os


from conans.errors import ConanException
from conans.model.ref import ConanFileReference
from conans.util.files import rmdir


class PackageTester(object):

    def __init__(self, manager, user_io):
        self._manager = manager
        self._user_io = user_io

    def _call_requirements(self, conanfile_path, profile):

        loader = self._manager.get_loader(profile)
        test_conanfile = loader.load_conan(conanfile_path, self._user_io.out, consumer=True)
        try:
            if hasattr(test_conanfile, "requirements"):
                test_conanfile.requirements()
        except Exception as e:
            raise ConanException("Error in test_package/conanfile.py requirements(). %s" % str(e))

        return test_conanfile

    def install_build_and_test(self, conanfile_abs_path, profile, name, version, user, channel,
                               remote, update, build_modes=None):
        """
        Installs the reference (specified by the parameters or extracted from the test conanfile)
        and builds the test_package/conanfile.py running the test() method.
        """
        base_folder = os.path.dirname(conanfile_abs_path)
        build_folder = self._build_folder(profile, base_folder)
        rmdir(build_folder)
        test_conanfile = self._call_requirements(conanfile_abs_path, profile)
        ref = self._get_reference_to_test(test_conanfile.requires, name, version, user, channel)
        if build_modes is None:
            build_modes = ["never"]
        self._manager.install(inject_require=ref,
                              reference=base_folder,
                              install_folder=build_folder,
                              remote=remote,
                              profile=profile,
                              update=update,
                              build_modes=build_modes)
        self._manager.build(conanfile_abs_path, base_folder, build_folder, package_folder=None,
                            install_folder=build_folder, test=str(ref))

    @staticmethod
    def _build_folder(profile, test_folder):
        sha = hashlib.sha1("".join(profile.dumps()).encode()).hexdigest()
        build_folder = os.path.join(test_folder, "build", sha)
        return build_folder

    @staticmethod
    def _get_reference_to_test(requires, name, version, user, channel):
        """Given the requirements of a test_package/conanfile.py and a user specified values,
        check if there are any conflict in the specified version and return the package to be
        tested"""

        # User do not specify anything, and there is a require
        if name is None and len(requires.items()) == 1:
            _, req = list(requires.items())[0]
            pname, pversion, puser, pchannel = req.conan_reference
        # The specified name is already in the test_package/conanfile requires, check conflicts
        elif name is not None and name in requires:
            a_ref = requires[name].conan_reference
            if version and (version != a_ref.version):
                raise ConanException("The specified version doesn't match with the "
                                     "requirement of the test_package/conanfile.py")
            pname, pversion, puser, pchannel = a_ref
            if user and channel:  # Override from the command line
                puser, pchannel = user, channel
        # Different from the requirements in test_package
        elif name is not None:
            if not version or not channel or not user:
                reqs = ", ".join(requires.keys())
                raise ConanException("The package name '%s' doesn't match with any requirement "
                                     "in the testing conanfile.py: %s" % (name, reqs))
            else:
                pname, pversion, puser, pchannel = name, version, user, channel
        else:
            raise ConanException("Cannot deduce the reference to be tested, specify a reference in "
                                 "the 'conan test' command or a single requirement in the "
                                 "test_package/conanfile.py file.")

        return ConanFileReference(pname, pversion, puser, pchannel)
