import json
import os
import textwrap

from conans.test.assets.genconanfile import GenConanfile
from conans.test.utils.tools import TestClient


def test_upload_bundle():
    """ Test how a custom command can create an upload bundle and print it
    """
    c = TestClient(default_server_user=True)
    mycommand = textwrap.dedent("""
        import json
        import os

        from conan.cli.command import conan_command, OnceArgument
        from conan.api.output import cli_out_write

        @conan_command(group="custom commands")
        def upload_bundle(conan_api, parser, *args, **kwargs):
            \"""
            create an upload bundle
            \"""
            parser.add_argument('reference',
                                help="Recipe reference or package reference, can contain * as "
                                      "wildcard at any reference field. A placeholder 'latest'"
                                      "can be used in the revision fields: e.g: 'lib/*#latest'.")
            # using required, we may want to pass this as a positional argument?
            parser.add_argument("-r", "--remote", action=OnceArgument, required=True,
                                help='Upload to this specific remote')
            args = parser.parse_args(*args)

            remote = conan_api.remotes.get(args.remote)

            upload_bundle = conan_api.upload.get_bundle(args.reference)
            if not upload_bundle.recipes:
                raise ConanException("No recipes found matching pattern '{}'".format(args.reference))

            # Check if the recipes/packages are in the remote
            conan_api.upload.check_upstream(upload_bundle, remote)

            if not upload_bundle.any_upload:
                return

            conan_api.upload.prepare(upload_bundle)
            cli_out_write(json.dumps(upload_bundle.serialize(), indent=4))
        """)

    command_file_path = os.path.join(c.cache_folder, 'extensions',
                                     'commands', 'cmd_upload_bundle.py')
    c.save({command_file_path: mycommand})
    c.save({"conanfile.py": GenConanfile("pkg", "0.1")})
    c.run("create .")
    c.run('upload-bundle "*" -r=default', redirect_stdout="mybundle.json")
    bundle = c.load("mybundle.json")
    # print(bundle)
    bundle = json.loads(bundle)
    assert bundle[0]["ref"] == "pkg/0.1#485dad6cb11e2fa99d9afbe44a57a164"
