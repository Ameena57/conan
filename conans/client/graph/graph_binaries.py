from conans.client.graph.build_mode import BuildMode
from conans.client.graph.compute_pid import compute_package_id
from conans.client.graph.graph import (BINARY_BUILD, BINARY_CACHE, BINARY_DOWNLOAD, BINARY_MISSING,
                                       BINARY_UPDATE, RECIPE_EDITABLE, BINARY_EDITABLE,
                                       RECIPE_CONSUMER, RECIPE_VIRTUAL, BINARY_SKIP, BINARY_UNKNOWN,
                                       BINARY_INVALID, BINARY_ERROR)
from conans.errors import NoRemoteAvailable, NotFoundException, ConanException
from conans.model.info import PACKAGE_ID_UNKNOWN, PACKAGE_ID_INVALID
from conans.model.ref import PackageReference


class GraphBinariesAnalyzer(object):

    def __init__(self, cache, output, remote_manager):
        self._cache = cache
        self._output = output
        self._remote_manager = remote_manager
        # These are the nodes with pref (not including PREV) that have been evaluated
        self._evaluated = {}  # {pref: [nodes]}

    @staticmethod
    def _evaluate_build(node, build_mode):
        ref, conanfile = node.ref, node.conanfile
        with_deps_to_build = False
        # For cascade mode, we need to check also the "modified" status of the lockfile if exists
        # modified nodes have already been built, so they shouldn't be built again
        if build_mode.cascade and not (node.graph_lock_node and node.graph_lock_node.modified):
            for dep in node.dependencies:
                dep_node = dep.dst
                if (dep_node.binary == BINARY_BUILD or
                    (dep_node.graph_lock_node and dep_node.graph_lock_node.modified)):
                    with_deps_to_build = True
                    break
        if build_mode.forced(conanfile, ref, with_deps_to_build):
            conanfile.output.info('Forced build from source')
            node.binary = BINARY_BUILD
            node.prev = None
            return True

    def _evaluate_clean_pkg_folder_dirty(self, node, package_layout, pref):
        # Check if dirty, to remove it
        with package_layout.package_lock():
            assert node.recipe != RECIPE_EDITABLE, "Editable package shouldn't reach this code"
            if package_layout.package_is_dirty():
                node.conanfile.output.warn("Package binary is corrupted, removing: %s" % pref.id)
                package_layout.package_remove()
                return

    def _evaluate_cache_pkg(self, node, pref, remote, remotes, update):
        if update:
            output = node.conanfile.output
            if remote:
                try:
                    # if there's a later package revision in the remote we will take that one
                    pkg_id = PackageReference(pref.ref, pref.id)
                    remote_prevs = self._remote_manager.get_package_revisions(pkg_id, remote)
                    remote_latest_prev = PackageReference(pref.ref, pref.id,
                                                          revision=remote_prevs[0].get("revision"))
                    remote_latest_prev_time = remote_prevs[0].get("time")
                    cache_time = self._cache.get_timestamp(pref)
                except NotFoundException:
                    output.warn("Can't update, no package in remote")
                except NoRemoteAvailable:
                    output.warn("Can't update, no remote defined")
                else:
                    if cache_time < remote_latest_prev_time and remote_latest_prev != pref:
                        node.binary = BINARY_UPDATE
                        node.prev = remote_latest_prev.revision
                        output.info("Current package revision is older than the remote one")
                    else:
                        output.warn("Current package revision is newer than the remote one")
            elif remotes:
                pass  # Current behavior: no remote explicit or in metadata, do not update
            else:
                output.warn("Can't update, no remote defined")

        if not node.binary:
            node.binary = BINARY_CACHE
            assert node.prev, "PREV for %s is None" % str(pref)

    def _get_package_info(self, node, pref, remote):
        return self._remote_manager.get_package_info(pref, remote, info=node.conanfile.info)

    def _evaluate_remote_pkg(self, node, pref, remote, remotes, remote_selected, update):
        remote_info = None
        # If the remote is pinned (remote_selected) we won't iterate the remotes.
        # The "remote" can come from -r or from the registry (associated ref)
        if remote_selected or remote:
            try:
                remote_info, pref = self._get_package_info(node, pref, remote)
            except NotFoundException:
                pass
            except Exception:
                node.conanfile.output.error("Error downloading binary package: '{}'".format(pref))
                raise

        # If we didn't pin a remote with -r and:
        #   - The remote is None (not registry entry)
        #        or
        #   - We didn't find a package but having revisions enabled
        # We iterate the other remotes to find a binary. If we added --update we will
        # return the latest package among all remotes, otherwise return the first match
        if not remote_selected and (not remote or not remote_info):
            all_remotes_results = []
            for r in remotes.values():
                if r == remote:
                    continue
                try:
                    remote_info, pref = self._get_package_info(node, pref, r)
                except NotFoundException:
                    pass
                else:
                    if remote_info:
                        if update:
                            # TODO: refactor _get_package_info and so to get time there
                            #  here we should get always just one item corresponding with full pref
                            revisions = self._remote_manager.get_package_revisions(pref, r)[0]
                            all_remotes_results.append({'pref': pref, 'time': revisions.get('time'),
                                                        'remote': r, 'remote_info': remote_info})
                        else:
                            remote = r
                            break

        if update and len(all_remotes_results) > 0:
            remotes_results = sorted(all_remotes_results, key=lambda k: k['time'], reverse=True)
            result = remotes_results[0]
            remote = result.get('remote')
            remote_info = result.get('remote_info')
            pref = result.get('pref')

        if remote_info:
            node.binary = BINARY_DOWNLOAD
            node.prev = pref.revision
        else:
            node.prev = None
            node.binary = BINARY_MISSING

        return remote

    def _evaluate_is_cached(self, node, pref):
        previous_nodes = self._evaluated.get(pref)
        if previous_nodes:
            previous_nodes.append(node)
            previous_node = previous_nodes[0]
            # The previous node might have been skipped, but current one not necessarily
            # keep the original node.binary value (before being skipped), and if it will be
            # defined as SKIP again by self._handle_private(node) if it is really private
            if previous_node.binary == BINARY_SKIP:
                node.binary = previous_node.binary_non_skip
            else:
                node.binary = previous_node.binary
            node.binary_remote = previous_node.binary_remote
            node.prev = previous_node.prev
            return True
        self._evaluated[pref] = [node]

    def _evaluate_node(self, node, build_mode, update, remotes):
        assert node.binary is None, "Node.binary should be None"
        assert node.package_id is not None, "Node.package_id shouldn't be None"
        assert node.package_id != PACKAGE_ID_UNKNOWN, "Node.package_id shouldn't be Unknown"
        assert node.prev is None, "Node.prev should be None"

        # If it has lock
        locked = node.graph_lock_node
        if locked and locked.package_id and locked.package_id != PACKAGE_ID_UNKNOWN:
            pref = PackageReference(locked.ref, locked.package_id, locked.prev)  # Keep locked PREV
            self._process_node(node, pref, build_mode, update, remotes)
            if node.binary == BINARY_MISSING and build_mode.allowed(node.conanfile):
                node.binary = BINARY_BUILD
            if node.binary == BINARY_BUILD:
                locked.unlock_prev()

            if node.package_id != locked.package_id:  # It was a compatible package
                # https://github.com/conan-io/conan/issues/9002
                # We need to iterate to search the compatible combination
                for compatible_package in node.conanfile.compatible_packages:
                    comp_package_id = compatible_package.package_id()
                    if comp_package_id == locked.package_id:
                        node._package_id = locked.package_id  # FIXME: Ugly definition of private
                        node.conanfile.settings.values = compatible_package.settings
                        node.conanfile.options.values = compatible_package.options
                        break
                else:
                    raise ConanException("'%s' package-id '%s' doesn't match the locked one '%s'"
                                         % (repr(locked.ref), node.package_id, locked.package_id))
        else:
            assert node.prev is None, "Non locked node shouldn't have PREV in evaluate_node"
            assert node.binary is None, "Node.binary should be None if not locked"
            pref = PackageReference(node.ref, node.package_id)
            self._process_node(node, pref, build_mode, update, remotes)
            if node.binary in (BINARY_MISSING, BINARY_INVALID):
                if node.conanfile.compatible_packages:
                    compatible_build_mode = BuildMode(None, self._output)
                    for compatible_package in node.conanfile.compatible_packages:
                        package_id = compatible_package.package_id()
                        if package_id == node.package_id:
                            node.conanfile.output.info("Compatible package ID %s equal to the "
                                                       "default package ID" % package_id)
                            continue
                        pref = PackageReference(node.ref, package_id)
                        node.binary = None  # Invalidate it
                        # NO Build mode
                        self._process_node(node, pref, compatible_build_mode, update, remotes)
                        assert node.binary is not None
                        if node.binary not in (BINARY_MISSING, ):
                            node.conanfile.output.info("Main binary package '%s' missing. Using "
                                                       "compatible package '%s'"
                                                       % (node.package_id, package_id))

                            # Modifying package id under the hood, FIXME
                            node._package_id = package_id
                            # So they are available in package_info() method
                            node.conanfile.settings.values = compatible_package.settings
                            node.conanfile.options.values = compatible_package.options
                            break
                    if node.binary == BINARY_MISSING and node.package_id == PACKAGE_ID_INVALID:
                        node.binary = BINARY_INVALID
                if node.binary == BINARY_MISSING and build_mode.allowed(node.conanfile):
                    node.binary = BINARY_BUILD

            if locked:
                # package_id was not locked, this means a base lockfile that is being completed
                locked.complete_base_node(node.package_id, node.prev)

        if (node.binary in (BINARY_BUILD, BINARY_MISSING) and node.conanfile.info.invalid and
                node.conanfile.info.invalid[0] == BINARY_INVALID):
            node._package_id = PACKAGE_ID_INVALID  # Fixme: Hack
            node.binary = BINARY_INVALID

    def _process_node(self, node, pref, build_mode, update, remotes):
        # Check that this same reference hasn't already been checked
        if self._evaluate_is_cached(node, pref):
            return

        if node.conanfile.info.invalid and node.conanfile.info.invalid[0] == BINARY_ERROR:
            node.binary = BINARY_ERROR
            return

        if node.recipe == RECIPE_EDITABLE:
            node.binary = BINARY_EDITABLE  # TODO: PREV?
            return

        if pref.id == PACKAGE_ID_INVALID:
            # annotate pattern, so unused patterns in --build are not displayed as errors
            build_mode.forced(node.conanfile, node.ref)
            node.binary = BINARY_INVALID
            return

        if self._evaluate_build(node, build_mode):
            return

        latest_prev_for_pkg_id = self._cache.get_latest_prev(pref)

        if latest_prev_for_pkg_id:
            package_layout = self._cache.pkg_layout(latest_prev_for_pkg_id)
            self._evaluate_clean_pkg_folder_dirty(node, package_layout, pref)

        remote = remotes.selected
        remote_selected = remote is not None

        if latest_prev_for_pkg_id:  # Binary already exists in local, check if we want to update
            node.prev = latest_prev_for_pkg_id.revision
            self._evaluate_cache_pkg(node, latest_prev_for_pkg_id, remote, remotes, update)
        else:  # Binary does NOT exist locally
            # Returned remote might be different than the passed one if iterating remotes
            remote = self._evaluate_remote_pkg(node, pref, remote, remotes, remote_selected, update)

        node.binary_remote = remote

    def _evaluate_package_id(self, node):
        compute_package_id(node, self._cache.new_config)  # TODO: revise compute_package_id()

    def evaluate_graph(self, deps_graph, build_mode, update, remotes, nodes_subset=None, root=None):
        build_mode = BuildMode(build_mode, self._output)
        assert isinstance(build_mode, BuildMode)

        default_package_id_mode = self._cache.config.default_package_id_mode
        default_python_requires_id_mode = self._cache.config.default_python_requires_id_mode
        for node in deps_graph.ordered_iterate(nodes_subset=nodes_subset):
            self._evaluate_package_id(node)
            if node.recipe in (RECIPE_CONSUMER, RECIPE_VIRTUAL):
                continue
            if node.package_id == PACKAGE_ID_UNKNOWN:
                assert node.binary is None, "Node.binary should be None"
                node.binary = BINARY_UNKNOWN
                # annotate pattern, so unused patterns in --build are not displayed as errors
                build_mode.forced(node.conanfile, node.ref)
                continue
            self._evaluate_node(node, build_mode, update, remotes)

        self._skip_binaries(deps_graph)

    @staticmethod
    def _skip_binaries(graph):
        required_nodes = set()
        required_nodes.add(graph.root)
        for node in graph.nodes:
            if node.binary != BINARY_BUILD and node is not graph.root:
                continue
            for req, dep in node.transitive_deps.items():
                dep_node = dep.node
                require = dep.require
                if require.headers or require.libs or require.run or require.build:
                    required_nodes.add(dep_node)

        for node in graph.nodes:
            if node not in required_nodes:
                node.binary = BINARY_SKIP

    def reevaluate_node(self, node, remotes, build_mode, update):
        """ reevaluate the node is necessary when there is some PACKAGE_ID_UNKNOWN due to
        package_revision_mode
        """
        assert node.binary == BINARY_UNKNOWN
        output = node.conanfile.output
        node._package_id = None  # Invalidate it, so it can be re-computed
        output.info("Unknown binary for %s, computing updated ID" % str(node.ref))
        self._evaluate_package_id(node)
        output.info("Updated ID: %s" % node.package_id)
        if node.recipe in (RECIPE_CONSUMER, RECIPE_VIRTUAL):
            return
        assert node.package_id != PACKAGE_ID_UNKNOWN
        node.binary = None  # Necessary to invalidate so it is properly evaluated
        self._evaluate_node(node, build_mode, update, remotes)
        output.info("Binary for updated ID from: %s" % node.binary)
        if node.binary == BINARY_BUILD:
            output.info("Binary for the updated ID has to be built")
