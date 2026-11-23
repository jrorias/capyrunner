"""Writes the Windows file properties of CapyRunner.exe (Details tab: product, version, "Devjr").
Used by the build: python packaging/version_info.py > packaging/version_info.txt"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from capyrunner import __version__  # noqa: E402

v = tuple((int(x) for x in __version__.split(".")[:3])) + (0,)
print(f"""VSVersionInfo(
  ffi=FixedFileInfo(filevers={v}, prodvers={v}, mask=0x3f, flags=0x0, OS=0x40004, fileType=0x1, subtype=0x0,
                    date=(0, 0)),
  kids=[
    StringFileInfo([StringTable('040904B0', [
      StringStruct('CompanyName', 'Devjr'),
      StringStruct('FileDescription', 'CapyRunner - Primo, the desktop mascot'),
      StringStruct('FileVersion', '{__version__}'),
      StringStruct('InternalName', 'CapyRunner'),
      StringStruct('LegalCopyright', 'Developed by Devjr'),
      StringStruct('OriginalFilename', 'CapyRunner.exe'),
      StringStruct('ProductName', 'CapyRunner'),
      StringStruct('ProductVersion', '{__version__}')])]),
    VarFileInfo([VarStruct('Translation', [1033, 1200])])
  ]
)""")
