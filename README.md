# ce_tools
Small scripts to simplify and automate working with CRYENGINE, it is hoped that these scripts can be pushed upstream.
Only Python 3.5 has been used in development, earlier versions of Python 3 are likely, but not guaranteed, to work.

## release_ce_project.py
This script combines the required engine and project files into a single directory. 
It also creates .pak files from the asset directory and writes an appropriate system.cfg.
If available, (64-bit) 7-zip is used for this since it is usually faster when working with large amounts of data.
Otherwise Python's build-in archiving support is used.

It is necessary to set the following variables in the main() function at the top of the script:
* cryproject_file - the full path to the project file as created by the launcher.
* export_path - location to which the project should be exported (defaults to a folder 'ce_game' on the desktop).

The engine version is found from the .cryproject file, and the path found by querying the registry.
Consequently this script is primarily useful on Windows, however it could easily be adapted in future.

## testbuild.py

This is a simple script that clones/pulls a CRYENGINE repository from Git to the current directory and builds it.
It is intended as a quick script to ensure that the code in a repository is building correctly.

It assumes that in the same folder, there is a directory called 'SDKs' containing all required SDKs for that version.
This is so that if multiple repositorie based on similar CRYENGINE versions are built, they can share the SDKs.
