from conans.cli.api.conan_api import ConanAPIV2
from conans.cli.command import conan_command, COMMAND_GROUPS, Extender


@conan_command(group=COMMAND_GROUPS['creator'])
def remove(conan_api: ConanAPIV2, parser, *args, **kwargs):
    """
    Removes recipes and packages locally or in a remote server
    """
    #  WIP
