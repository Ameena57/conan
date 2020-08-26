import json

from conans.cli.command import conan_command, conan_subcommand, OnceArgument


def output_remote_list_json(info, out):
    myjson = json.dumps(info, indent=4)
    out.writeln(myjson)


def output_remote_list_cli(info, out):
    for remote_info in info:
        output_str = "{}: {} [Verify SSL: {}, Enabled: {}]".format(remote_info["name"],
                                                                   remote_info["url"],
                                                                   remote_info["verify"],
                                                                   remote_info["enabled"])
        out.writeln(output_str)


@conan_subcommand(formatters={"cli": output_remote_list_cli, "json": output_remote_list_json})
def remote_list(*args, conan_api, parser, subparser):
    """
    List current remotes
    """
    args = parser.parse_args(*args)
    info = [{"name": "remote1", "url": "https://someurl1", "verify": True, "enabled": False},
            {"name": "remote2", "url": "https://someurl2", "verify": False, "enabled": True},
            {"name": "remote3", "url": "https://someurl3", "verify": True, "enabled": True},
            {"name": "remote4", "url": "https://someurl4", "verify": False, "enabled": False}]
    return info


@conan_subcommand()
def remote_add(*args, conan_api, parser, subparser):
    """
    Add a remote
    """
    subparser.add_argument("remote", help="Name of the remote to add")
    subparser.add_argument("url", help="Url for the rempote")
    subparser.add_argument("-v", "--verify_ssl", action=OnceArgument, default="True",
                           help="Verify SSL certificated")
    subparser.add_argument("-i", "--insert", action=OnceArgument,
                           help="Insert remote at specific index")
    subparser.add_argument("-f", "--force", action='store_true', default=False,
                           help="Force addition, will update if existing")
    args = parser.parse_args(*args)


@conan_subcommand()
def remote_remove(*args, conan_api, parser, subparser):
    """
    Remove conan remotes
    """
    subparser.add_argument("remote", help="Name of the remote to remove. "
                                          "Accepts 'fnmatch' style wildcards.")  # to discuss
    args = parser.parse_args(*args)


@conan_subcommand()
def remote_update(*args, conan_api, parser, subparser):
    """
    Update remote info
    """
    subparser.add_argument("remote", help="Name of the remote to update")
    subparser.add_argument("-n", "--name", action=OnceArgument,
                           help="New name for the remote")
    subparser.add_argument("-u", "--url", action=OnceArgument,
                           help="New url for the rempote")
    subparser.add_argument("-v", "--verify_ssl", action=OnceArgument,
                           help="Verify SSL certificated")
    subparser.add_argument("-i", "--insert", action=OnceArgument,
                           help="Insert remote at specific index")
    args = parser.parse_args(*args)
    if not (args.name or args.url or args.verify_ssl or args.insert):
        subparser.error("Please add at least one remote field to update: "
                        "name, url, verify_ssl, insert")


@conan_subcommand()
def remote_enable(*args, conan_api, parser, subparser):
    """
    Update remote info
    """
    subparser.add_argument("remote", help="Pattern of the remote/s to enable. "
                                          "The pattern uses 'fnmatch' style wildcards.")
    args = parser.parse_args(*args)


@conan_subcommand()
def remote_disable(*args, conan_api, parser, subparser):
    """
    Update remote info
    """
    subparser.add_argument("remote", help="Pattern of the remote/s to disable. "
                                          "The pattern uses 'fnmatch' style wildcards.")
    args = parser.parse_args(*args)


@conan_command(group="Misc commands")
def remote(*args, conan_api, parser, **kwargs):
    """
    Manages the remote list and the package recipes associated with a remote.
    """
