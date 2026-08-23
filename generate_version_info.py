"""Writes _version.py and a PyInstaller --version-file resource from a
version string, so the built exe reports the right version both to the app
itself (--version, startup log, UI) and in Windows Explorer's file
Properties > Details tab. Run before PyInstaller, not shipped in the build.
"""
import re
import sys

version = sys.argv[1] if len(sys.argv) > 1 else 'dev'

with open('_version.py', 'w') as f:
    f.write(f'VERSION = "{version}"\n')

match = re.match(r'v?(\d+)\.(\d+)\.(\d+)', version)
numeric = tuple(int(g) for g in match.groups()) + (0,) if match else (0, 0, 0, 0)

version_info = f'''VSVersionInfo(
  ffi=FixedFileInfo(
    filevers={numeric},
    prodvers={numeric},
    mask=0x3f,
    flags=0x0,
    OS=0x40004,
    fileType=0x1,
    subtype=0x0,
    date=(0, 0)
  ),
  kids=[
    StringFileInfo(
      [
      StringTable(
        u'040904B0',
        [StringStruct(u'CompanyName', u'VMFinder'),
        StringStruct(u'FileDescription', u'VMFinder'),
        StringStruct(u'FileVersion', u'{version}'),
        StringStruct(u'InternalName', u'vmfinder'),
        StringStruct(u'OriginalFilename', u'vmfinder.exe'),
        StringStruct(u'ProductName', u'VMFinder'),
        StringStruct(u'ProductVersion', u'{version}')])
      ]),
    VarFileInfo([VarStruct(u'Translation', [1033, 1200])])
  ]
)
'''

with open('version_info.txt', 'w') as f:
    f.write(version_info)

print(f'Wrote _version.py and version_info.txt for version {version} {numeric}')
