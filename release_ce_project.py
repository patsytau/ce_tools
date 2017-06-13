#!python3
"""
This script combines the required engine and project files into a single directory.
It also creates .pak files from the asset directory and writes an appropriate system.cfg.
"""
import os
import sys
import json
import shutil
import fnmatch
import platform
import subprocess
import collections

# Name of the Game/Plugin DLL file.
dll_name = 'Game.dll'

# Path to the project file. (Appended to end of command line specified projects)
cryproject_file = ''

class EngineMetadata(object):
    """
        Simple container for required metadata for each project
    """
    name = ""
    version = ""
    path = ""
    id = ""

    # The class "constructor" - It's actually an initializer 
    def __init__(self, name, version, path, id):
        self.name = name
        self.version = version
        self.path = path
        self.id = id

def main():
    """
        Main entry handles the command line entries
    """
    global cryproject_file
    
    cryproject_list = []
    
    # Check platform support
    if not is_platform_valid():
        print ("[WARNING] Platform ", platform.system()," is not supported.")
        return
    
    # Check for project path arguments
    cryproject_list = get_launch_args()
    if len(cryproject_list) > 0:
        if not cryproject_file:
            cryproject_file = cryproject_list[0]
        elif cryproject_file not in cryproject_list:
            cryproject_list.append(cryproject_file)
            
    # Check we have a project file
    if not cryproject_file:
        print ("Please specify a .cryproject file or drag one onto this script, for legacy 5.0-5.1 you can drop your project.cfg instead.")
        return
    
    # Multi-Project deployment option
    for project_file in cryproject_list:
        # Check existence of project file
        if os.path.exists(project_file):
            do_project_deploy(project_file)
        else:
            print ("Specified project file could not be found. ", project_file)
        
    return
    
def do_project_deploy(cryproject_filepath):
    """
    Main packaging routine.
    Detached from main to allow multi-project processing with multiple command-line arguments.
    """
    
    with open(cryproject_filepath) as fd:
        if cryproject_filepath.endswith("project.cfg"): # Legacy support
            project_cfg = make_project_from_legacy(fd)
        elif cryproject_filepath.endswith(".cryproject"):
            project_cfg = json.load(fd)
    
    if not "info" in project_cfg:
        print("Error reading project data.")
        return
    project_path = os.path.dirname(cryproject_filepath)
    
    # Engine tag is the id of the registered engine this project uses
    engine_tag = project_cfg['require']['engine']
    
    # Engine Meta contains the name, id, version and path to the engine root.
    engine_meta = get_engine_metadata(engine_tag)
    if not engine_meta:
        print ("Could not find a compatible engine registered.")
        return
        
    engine_path = engine_meta.path
    version = engine_meta.version
    
    print('Using engine path "{}".'.format(engine_path))
    
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
    
    # Copy any version-specific data
    copy_version_specific_content(version, project_path, export_path)
    
    return

def copy_version_specific_content(version, project_path, export_path):
    """
    For specific copy procedures needed for specific engine iterations
    Example: cryplugin.csv is required for 5.2 and 5.3
    """
    
    v53_copy_cryplugin_csv = False
    v50_rename_game_dll = False
    
    if version == "5.3":
        v53_copy_cryplugin_csv = True
    elif version == "5.2":
        v53_copy_cryplugin_csv = True
#    elif version == "5.1":
#        
    elif version == "5.0":
        v50_rename_game_dll = True
        
    # Copy cryplugin.csv
    if v53_copy_cryplugin_csv:
        csv_name = "cryplugin.csv"
        src = os.path.normpath(os.path.join(project_path, csv_name))
        dest = os.path.normpath(os.path.join(export_path, csv_name))
        if os.path.exists(src):
            if not os.path.exists(os.path.dirname(dest)):
                os.makedirs(os.path.dirname(dest))
            shutil.copy(src, dest)
    
    # Rename Game.dll to CryGameZero.dll
    if v50_rename_game_dll:
        src = os.path.normpath(os.path.join(export_path, "bin", "win_x64", dll_name))
        dest = os.path.normpath(os.path.join(export_path, "bin", "win_x64", "CryGameZero.dll"))
        if os.path.exists(src):
            os.rename(src, dest)
    return
    
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
    
    haspak = False
    
    for pakfile in os.listdir(os.path.join(engine_path, 'engine')):
        if pakfile.endswith('.cryasset.pak'):
            continue
        if pakfile.endswith('.pak'):
            shutil.copyfile(os.path.join(engine_path, 'engine', pakfile),
                            os.path.join(export_path, 'engine', pakfile))
            haspak = True
    
    if not haspak:
        raise OSError("Could not find any engine .pak asset archives.\nCheck your root/engine directory for .pak files.")

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

def get_engine_metadata(engine_tag):
    """
        Wraps meta scanning for compatibility
        
        Will first search for Launcher JSON config files 
        for registered engines matching the specific 
        engine_tag.
        
        If no specific engine tag is found, and the 
        engine_tag matches the default format, the 
        registry is searched in legacy fashion. Will also 
        attempt to fallback to the current installed engine 
        if it can find a version match in the path name.
    """
    meta = {}
    
    # Attempt to find engine from launcher json data
    data_json = get_engine_json_data(engine_tag)
    if data_json:
        info = data_json['info']
        path = data_json['uri']
        
        # Remove *.cryengine if it's in the path
        path_splitt = os.path.splitext(os.path.basename(path))
        if len(path_splitt) > 1:
            if path_splitt[1].lower() == ".cryengine":
                path = os.path.split(path)[0]
        
        meta = EngineMetadata(info['name'], info['version'][:3], path, engine_tag)
        
    # legacy fallback
    elif is_default_tag(engine_tag):
        version = engine_tag[-3:]
        path = get_engine_path_registry(version)
        if path:
            meta = EngineMetadata("CRYENGINE "+version, version, path, engine_tag)
    
    if not meta:
        raise OSError('Compatible engine version {} not found.'.format(engine_tag))
        return
    
    return meta
    
def get_engine_path_registry(version_key):
    """
    Find the path to the project's engine by querying the registry on Windows.
    At the moment there is no way to register engine locations on Linux, so it is left as
    an exercise to the user to specify paths/determine a lookup scheme there.
    :param version: Engine version target.
    :return: Absolute path to the engine used by this project.
    """
    
    data = {}
    
    # Get the default registered engine from registry by Version
    data = get_windows_reg_value(r'SOFTWARE\Crytek\CryEngine', version_key)
    
    if version_key in data:
        return data[version_key]
    
    # Fallback - Get the current installed engine
    root_key = 'ENG_RootPath'
    data = get_windows_reg_value(r'SOFTWARE\Crytek\Settings', root_key)
    
    if root_key in data:
        # Check version (By default, engine path ends with the version '...\CRYENGINE_5.3')
        if version_key == data[root_key][:3]:
            print("Warning: Using default engine at \"", data[root_key], "\"")
            return data[root_key]
    
    return data
    
def get_engine_json_data(engine_id):
    """
    Attempts to read the specified engine registration info 
    from launcher json config files.
    """
    # Since crytek launcher uses both these locations and combines them, so must we.
    os_paths = [os.getenv('LOCALAPPDATA'), os.getenv('ALLUSERSPROFILE')]
    sub_path = os.path.join("Crytek", "CRYENGINE", "cryengine.json")
    
    # Just a quick combine sub path and check existence
    json_files = []
    for i in range(len(os_paths)):
        os_paths[i] = os.path.join(os_paths[i], sub_path)
        if os.path.exists(os_paths[i]):
            json_files.append(os_paths[i])
    
    # Open and parse each json file
    if len(json_files):
        for i in range(len(json_files)):
            with open(json_files[i]) as jf:
                data = json.load(jf)
                for engine in data:
                    if(engine == engine_id):
                        return data[engine]
    return False
    
def get_supported_platforms():
    """
    For future compatibility
    """
    return ["Windows"]

def get_launch_args():
    """
    Looks better
    """
    return sys.argv[1:]

def get_windows_reg_value(Key, Name = ""):
    """
    WINDOWS ONLY
    Non-Recursive.
    Gets registry key(s) from windows hive
    IF Name is specified, return will contain max 1 item
    IF Name is left unspecified, return will be ALL name/value pairs in this Key.
    """
    values = {}
    
    if platform.system() != 'Windows':
        raise OSError("Can only use get_windows_reg_value() on windows platform!")
        return values
    
    import winreg
    reg = winreg.ConnectRegistry(None, winreg.HKEY_CURRENT_USER)
    ce_key = winreg.OpenKey(reg, Key)

    # The first value of the key is a null entry, so check for this.
    try:
        i = 0
        while True:
            kn, kv, kt = winreg.EnumValue(ce_key, i)
            
            if Name == kn:
                values = {kn: kv}
                break
            elif not Name:
                values[kn] = kv
            
            i += 1
    except OSError:
        pass
    
    return values

def is_platform_valid():
    for platform_name in get_supported_platforms():
        if platform.system().lower() == platform_name.lower():
            return True
    return False

def is_default_tag(engine_tag):
    """
        Default project tags
        5.0-5.1 are generated in legacy code above.
    """
    if engine_tag == "engine-5.0":
        return True
    if engine_tag == "engine-5.1":
        return True
    if engine_tag == "engine-5.2":
        return True
    if engine_tag == "engine-5.3":
        return True
        
    return False
    
def make_project_from_legacy(project_cfg):
    """
    Creates a default project structure.
    Scans project.cfg for engine version.
    For legacy projects 5.0/5.1 that don't have a cryproject file.
    """
    
    lines = [line.rstrip('\n\r') for line in project_cfg]
    for line in lines:
        if len(line) == 20:
            if line.startswith("engine_version="):
                return {
                    "content": {
                        "assets": ["Assets"],
                        "code": ["Code"]
                    },
                    "info": {
                        "name": "My CryEngine Project"
                    },
                    "require": {
                        "engine": "engine-"+line[15:18]
                    }
                }
    return {}

if __name__ == '__main__':
    main()
