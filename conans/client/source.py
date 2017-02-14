from conans.paths import DIRTY_FILE, EXPORT_SOURCES_DIR, EXPORT_TGZ_NAME, EXPORT_SOURCES_TGZ_NAME,\
    CONANFILE
import os
from conans.util.files import rmdir, save
import six
from conans.errors import ConanException, format_conanfile_exception
import shutil
from conans import tools


def config_source(export_folder, src_folder, conan_file, output, force=False):
    """ creates src folder and retrieve, calling source() from conanfile
    the necessary source code
    """
    dirty = os.path.join(src_folder, DIRTY_FILE)

    def remove_source(raise_error=True):
        output.warn("This can take a while for big packages")
        try:
            rmdir(src_folder)
        except BaseException as e_rm:
            save(dirty, "")  # Creation of DIRTY flag
            msg = str(e_rm)
            if six.PY2:
                msg = str(e_rm).decode("latin1")  # Windows prints some chars in latin1
            output.error("Unable to remove source folder %s\n%s" % (src_folder, msg))
            output.warn("**** Please delete it manually ****")
            if raise_error or isinstance(e_rm, KeyboardInterrupt):
                raise ConanException("Unable to remove source folder")

    if force:
        output.warn("Forced removal of source folder")
        remove_source()
    elif os.path.exists(dirty):
        output.warn("Trying to remove dirty source folder")
        remove_source()
    elif conan_file.build_policy_always:
        output.warn("Detected build_policy 'always', trying to remove source folder")
        remove_source()

    if not os.path.exists(src_folder):
        output.info('Configuring sources in %s' % src_folder)
        shutil.copytree(export_folder, src_folder, symlinks=True)
        # Now move the export-sources to the right location
        source_sources_folder = os.path.join(src_folder, EXPORT_SOURCES_DIR)
        if os.path.exists(source_sources_folder):
            for filename in os.listdir(source_sources_folder):
                shutil.move(os.path.join(source_sources_folder, filename),
                            os.path.join(src_folder, filename))
            # finally remove copied folder
            os.rmdir(source_sources_folder)
        for f in (EXPORT_TGZ_NAME, EXPORT_SOURCES_TGZ_NAME, CONANFILE+"c", CONANFILE+"o"):
            try:
                os.remove(os.path.join(src_folder, f))
            except OSError:
                pass
        try:
            shutil.rmtree(os.path.join(src_folder, "__pycache__"))
        except OSError:
            pass

        save(dirty, "")  # Creation of DIRTY flag
        os.chdir(src_folder)
        try:
            with tools.environment_append(*conan_file.env_values_dicts):
                conan_file.source()
            os.remove(dirty)  # Everything went well, remove DIRTY flag
        except Exception as e:
            os.chdir(export_folder)
            # in case source() fails (user error, typically), remove the src_folder
            # and raise to interrupt any other processes (build, package)
            output.warn("Trying to remove dirty source folder")
            remove_source(raise_error=False)
            msg = format_conanfile_exception(output.scope, "source", e)
            raise ConanException(msg)


def config_source_local(export_folder, current_path, conan_file, output):
    output.info('Configuring sources in %s' % current_path)
    dirty = os.path.join(current_path, DIRTY_FILE)
    if os.path.exists(dirty):
        output.warn("Your previous source command failed")

    if current_path != export_folder:
        for item in os.listdir(export_folder):
            origin = os.path.join(export_folder, item)
            if os.path.isdir(origin):
                shutil.copytree(origin, os.path.join(current_path, item))
            else:
                shutil.copy2(origin, os.path.join(current_path, item))

    save(dirty, "")  # Creation of DIRTY flag
    try:
        with tools.environment_append(*conan_file.env_values_dicts):
            conan_file.source()
        os.remove(dirty)  # Everything went well, remove DIRTY flag
    except Exception as e:
        msg = format_conanfile_exception(output.scope, "source", e)
        raise ConanException(msg)
