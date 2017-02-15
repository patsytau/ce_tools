# ce_tools
Small scripts to simplify and automate working with CRYENGINE, it is hoped that these scripts can be pushed upstream.
Only Python 3.5 has been used in development, earlier versions of Python 3 are likely, but not guaranteed, to work.

## release_ce_project.py
This script combines the required engine and project files into a single directory. 
It also creates .pak files from the asset directory and writes an appropriate system.cfg. 

It is necessary to set the following variables in the main() function at the bottom of the script:
* engine_version - version of the engine, e.g. "5.3".
* engine_path - path to the engine, can be from the launcher or a self-compiled version.
* project_path - path of the project you wish to export.
* export_path - location to which the project should be exported.
