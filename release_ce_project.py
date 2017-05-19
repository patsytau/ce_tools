#!python3
"""
This script combines the required engine and project files into a single directory.
It also creates .pak files from the asset directory and writes an appropriate system.cfg.
"""
import os
import json
import shutil
import fnmatch
import platform
import subprocess

dll_name = 'Game.dll'


def main():
    # Path to the project file as created by the launcher - engine and project path are derivable from this.
    cryproject_file = ''

    with open(cryproject_file) as fd:
        project_cfg = json.load(fd)

    project_path = os.path.dirname(cryproject_file)
    engine_path = get_engine_path(project_cfg)

    # Path to which the game is to be exported.
    export_path = os.path.join(os.environ['HOMEDRIVE'],
                               os.environ['HOMEPATH'],
                               'Desktop',
                               project_cfg['info']['name'])

    # Ensure that only the current data are exported, making sure that errors are reported.
    if os.path.exists(export_path):
        shutil.rmtree(export_path)

    # Copy engine (common) files.
    copy_engine_assets(engine_path, export_path)
    copy_engine_binaries(engine_path, export_path, os.path.join('bin', 'win_x64'))

    if 'csharp' in project_cfg:
        copy_mono_files(engine_path, export_path)

    # Copy project-specific files.
    copy_game_dll(project_path, export_path)

    asset_dir = project_cfg['content']['assets'][0]
    package_assets(asset_dir, project_path, export_path)
    copy_levels(asset_dir, project_path, export_path)
    create_config(asset_dir, export_path)


def copy_engine_binaries(engine_path, export_path, rel_dir):
    """
    Copy a directory to its corresponding location in the export directory.
    :param engine_path: Current location of the files (project_path or engine_path).
    :param export_path: Path to which the binaries should be exported.
    :param rel_dir: Path of the directory to copy, relative to *source_dir*.
    """
    copypaths = []

    excludes = ['imageformats**',
                'ToolkitPro*',
                'platforms**',
                'Qt*',
                'mfc*',
                'CryGame*',
                'CryEngine.*.dll*',
                'Sandbox*',
                'ShaderCacheGen*',
                'smpeg2*',
                'icu*',
                'python27*',
                'LuaCompiler*',
                'Editor**',
                'PySide2*',
                'shiboken*',
                'crashrpt*',
                'CrashSender*'
                ]

    pwd = os.getcwd()
    os.chdir(engine_path)
    for root, _, filenames in os.walk(rel_dir):
        for filename in filenames:
            copypaths.append(os.path.normpath(os.path.join(root, filename)))
    os.chdir(pwd)

    for path in copypaths:
        excluded = False
        for pattern in excludes:
            excluded = excluded or fnmatch.fnmatch(path, os.path.join(rel_dir, pattern))
        if excluded:
            continue
        destpath = os.path.normpath(os.path.join(export_path, path))
        if not os.path.exists(os.path.dirname(destpath)):
            os.makedirs(os.path.dirname(destpath))
        shutil.copy(os.path.join(engine_path, path), destpath)


def copy_mono_files(engine_path, export_path):
    """
    Copy mono directory and CRYENGINE C# libraries to export path.
    """
    input_bindir = os.path.join(engine_path, 'bin')
    output_bindir = os.path.join(export_path, 'bin')

    shutil.copytree(os.path.join(input_bindir, 'common'), os.path.join(output_bindir, 'common'))

    for csharp_file in os.listdir(os.path.join(input_bindir, 'win_x64')):
        # We've already copied the non-C# libraries, so skip them here.
        if not fnmatch.fnmatch(csharp_file, 'CryEngine.*.dll'):
            continue
        shutil.copyfile(os.path.join(input_bindir, 'win_x64', csharp_file),
                        os.path.join(output_bindir, 'win_x64', csharp_file))


def copy_engine_assets(engine_path, export_path):
    """
    Copy the engine assets, making sure to avoid .cryasset.pak files.
    """
    os.makedirs(os.path.join(export_path, 'engine'))

    for pakfile in os.listdir(os.path.join(engine_path, 'engine')):
        if pakfile.endswith('.cryasset.pak'):
            continue
        shutil.copyfile(os.path.join(engine_path, 'engine', pakfile),
                        os.path.join(export_path, 'engine', pakfile))


def copy_levels(asset_dir, project_path, export_path):
    """
    Copy required level files to the export directory.
    """
    pwd = os.getcwd()
    os.chdir(os.path.join(project_path, asset_dir))

    # Other files are only required by the editor.
    level_files = ['filelist.xml', 'terraintexture.pak', 'level.pak']

    for root, _, filenames in os.walk('levels'):
        for filename in filenames:
            if filename not in level_files:
                continue

            path = os.path.normpath(os.path.join(root, filename))
            destpath = os.path.normpath(os.path.join(export_path, asset_dir, path))
            if not os.path.exists(os.path.dirname(destpath)):
                os.makedirs(os.path.dirname(destpath))
            shutil.copy(os.path.join(project_path, asset_dir, path), destpath)

    os.chdir(pwd)
    return


def package_assets(asset_dir, project_path, export_path):
    """
    Create .pak files from the loose assets, which are placed in the exported directory.
    """
    input_assetpath = os.path.join(project_path, asset_dir)
    output_assetpath = os.path.join(export_path, asset_dir)

    if not os.path.exists(output_assetpath):
        os.makedirs(output_assetpath)

    # Use 7-zip if it exists, because it's generally faster.
    use_7zip = os.path.exists(r"C:\Program Files\7-Zip")
    if use_7zip:
        os.environ['PATH'] = os.environ['PATH'] + os.pathsep + r"C:\Program Files\7-Zip"

    for itemname in os.listdir(input_assetpath):
        itempath = os.path.join(input_assetpath, itemname)

        # Levels are handled elsewhere.
        if 'levels' in itempath.lower():
            continue

        # .cryasset.pak files are editor-only, and so do not belong in exported projects.
        if itempath.endswith('.cryasset.pak'):
            continue

        if os.path.isfile(itempath):
            if not os.path.exists(os.path.join(export_path, 'Assets')):
                os.makedirs(os.path.join(export_path, 'Assets'))
            shutil.copyfile(itempath, os.path.join(output_assetpath, itemname))
        else:
            if use_7zip:
                zip_cmd = ['7z',
                           'a',
                           '-r',
                           '-tzip',
                           '-mx0',
                           os.path.join(output_assetpath, '{}.pak'.format(itemname)),
                           os.path.join(input_assetpath, itempath)]
                subprocess.check_call(zip_cmd)
            else:
                pakname = shutil.make_archive(base_name=os.path.join(output_assetpath, itemname),
                                              format='zip',
                                              root_dir=input_assetpath,
                                              base_dir=itemname)
                shutil.move(pakname, pakname.replace('.zip', '.pak'))
            print('Created {}.pak'.format(itemname))
    return


def create_config(asset_dir, export_path):
    with open(os.path.join(export_path, 'system.cfg'), 'w') as fd:
        fd.write('sys_game_folder={}\n'.format(asset_dir))
        fd.write('sys_dll_game={}\n'.format(dll_name))
        fd.write('sys_PakLogInvalidFileAccess=0')


def copy_game_dll(project_path, export_path):
    """
    Search the project's bin/win_x64 directory for a game DLL.
    When one is found, set this globally (so that it can be added to the system.cfg).
    """
    global dll_name

    binpath = os.path.join(project_path, 'bin', 'win_x64')
    for filename in os.listdir(binpath):
        # Ignore any .pdb, .ilk, .manifest, or any other files that aren't DLLs.
        if not fnmatch.fnmatch(os.path.join(binpath, filename), '*.dll'):
            continue

        dll_name = filename
        shutil.copyfile(os.path.join(binpath, filename),
                        os.path.join(export_path, 'bin', 'win_x64', filename))


def get_engine_path(project_data):
    """
    Find the path to the project's engine by querying the registry on Windows.
    At the moment there is no way to register engine locations on Linux, so it is left as
    an exercise to the user to specify paths/determine a lookup scheme there.
    :param project_data: Data loaded from the .cryproject file.
    :return: Absolute path to the engine used by this project.
    """

    engine_tag = project_data['require']['engine']
    version = engine_tag.split('-')[1]              # 'engine-5.3' -> '5.3'

    engine_paths = {}

    if platform.system() == 'Windows':
        import winreg
        reg = winreg.ConnectRegistry(None, winreg.HKEY_CURRENT_USER)
        ce_key = winreg.OpenKey(reg, r'SOFTWARE\Crytek\CryEngine')

        # The first value of the key is a null entry, so check for this.
        try:
            i = 0
            while True:
                ver, path, _ = winreg.EnumValue(ce_key, i)
                if ver:
                    engine_paths[ver] = path
                i += 1
        except OSError:
            pass
    else:
        print('Engine path lookups are currently only possible on Windows.')

    print('Found the following engines = {}'.format(json.dumps(engine_paths, indent=4)))
    if version not in engine_paths:
        raise OSError('Engine version {} not found.'.format(version))

    print('Using engine path "{}".'.format(engine_paths[version]))
    return engine_paths[version]


if __name__ == '__main__':
    main()
