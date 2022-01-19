import json

from conans.cli.api.conan_api import ConanAPIV2
from conans.cli.api.model import UploadBundle
from conans.cli.command import conan_command, COMMAND_GROUPS, OnceArgument
from conans.client.userio import UserInput
from conans.errors import ConanException


@conan_command(group=COMMAND_GROUPS['creator'])
def upload(conan_api: ConanAPIV2, parser, *args):
    """
    Uploads a recipe and binary packages to a remote.
    By default, only the latest revisions matching the reference are uploaded, unles
    is specified.
    By default, if a recipe reference is specified, it will upload the latest revision of all the
    binary packages, unles --only-recipe is specified.
    """
    _not_specified_ = object()

    parser.add_argument('reference', help="Recipe reference or package reference, can contain * as "
                                          "wildcard at any reference field. e.g: 'lib/*'.")
    parser.add_argument('-p', '--package-query', default=None, action=OnceArgument,
                        help="Only upload packages matching a specific query. e.g: os=Windows AND "
                             "(arch=x86 OR compiler=gcc)")
    # using required, we may want to pass this as a positional argument?
    parser.add_argument("-r", "--remote", action=OnceArgument, required=True,
                        help='Upload to this specific remote')
    parser.add_argument("--only-recipe", action='store_true', default=False,
                        help='Upload only the recipe')
    parser.add_argument("--force", action='store_true', default=False,
                        help='Ignore the missing fields in the scm attribute and override '
                             'remote recipe and packages with local regardless of recipe date')
    parser.add_argument("--check", action='store_true', default=False,
                        help='Perform an integrity check, using the manifests, before upload')
    parser.add_argument('-c', '--confirm', default=False, action='store_true',
                        help='Upload all matching recipes without confirmation')
    parser.add_argument('--retry', default=None, type=int, action=OnceArgument,
                        help="In case of fail retries to upload again the specified times.")
    parser.add_argument('--retry-wait', default=None, type=int, action=OnceArgument,
                        help='Waits specified seconds before retry again')

    args = parser.parse_args(*args)
    remote = conan_api.remotes.get(args.remote) if args.remote else None

    upload_bundle = conan_api.upload.get_bundle(args.reference, args.package_query, args.only_recipe)

    if not upload_bundle.recipes:
        raise ConanException("No recipes found matching pattern '{}'".format(args.reference))

    if args.check:
        conan_api.upload.check_integrity(upload_bundle)

    # If only if search with "*" we ask for confirmation
    if not args.confirm and "*" in args.reference:
        _ask_confirm_upload(conan_api, upload_bundle)

    if not upload_bundle.any_upload:
        return
    conan_api.upload.upload_bundle(upload_bundle, remote, retry=args.retry, retry_wait=args.retry_wait,
                                   force=args.force)

    # print(json.dumps(upload_bundle.serialize()))


def _ask_confirm_upload(conan_api, upload_data):
    ui = UserInput(conan_api.config.get("core:non_interactive"))
    for recipe in upload_data.recipes:
        msg = "Are you sure you want to upload recipe '%s'?" % recipe.ref.repr_notime()
        if not ui.request_boolean(msg):
            recipe.upload = False
            for package in recipe.packages:
                package.upload = False
        else:
            for package in recipe.packages:
                msg = "Are you sure you want to upload package '%s'?" % package.pref.repr_notime()
                if not ui.request_boolean(msg):
                    package.upload = False
