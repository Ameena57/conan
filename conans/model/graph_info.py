import json
import os

from conans.client.profile_loader import _load_profile
from conans.errors import ConanException
from conans.model.options import OptionsValues
from conans.model.ref import ConanFileReference
from conans.tools import save
from conans.util.files import load


GRAPH_INFO_FILE = "graph_info.json"


class GraphInfo(object):

    def __init__(self, profile_build, profile_host, options=None, root_ref=None):
        self.profile_build = profile_build
        self.profile_host = profile_host
        # This field is a temporary hack, to store dependencies options for the local flow
        self.options = options
        self.root = root_ref

    @staticmethod
    def load(path):
        if not path:
            raise IOError("Invalid path")
        p = path if os.path.isfile(path) else os.path.join(path, GRAPH_INFO_FILE)
        content = load(p)
        try:
            return GraphInfo.loads(content)
        except Exception as e:
            raise ConanException("Error parsing GraphInfo from file '{}': {}".format(p, e))

    @staticmethod
    def loads(text):
        graph_json = json.loads(text)
        profile_build = graph_json.get("profile_build", "profile")
        profile_host = graph_json.get("profile_host", "profile")
        # FIXME: Reading private very ugly
        profile_build, _ = _load_profile(profile_build, None, None)
        profile_host, _ = _load_profile(profile_host, None, None)
        try:
            options = graph_json["options"]
        except KeyError:
            options = None
        else:
            options = OptionsValues(options)
        root = graph_json.get("root", {"name": None, "version": None, "user": None, "channel": None})
        root_ref = ConanFileReference(root["name"], root["version"], root["user"], root["channel"],
                                      validate=False)
        return GraphInfo(profile_build=profile_build, profile_host=profile_host,
                         options=options, root_ref=root_ref)

    def save(self, folder, filename=None):
        filename = filename or GRAPH_INFO_FILE
        p = os.path.join(folder, filename)
        serialized_graph_str = self.dumps()
        save(p, serialized_graph_str)

    def dumps(self):
        result = {"profile_build": self.profile_build.dumps(),
                  "profile_host": self.profile_host.dumps()}
        if self.options is not None:
            result["options"] = self.options.as_list()
        result["root"] = {"name": self.root.name,
                          "version": self.root.version,
                          "user": self.root.user,
                          "channel": self.root.channel}
        return json.dumps(result, indent=True)
