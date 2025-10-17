bl_info = {
    "name": "Dynamix Three Space",
    "author": "Dummiesman",
    "version": (0, 0, 2),
    "blender": (3, 6, 0),
    "location": "File > Import-Export",
    "description": "Import Dynamix Three Space (DTS) models from Torque3D",
    "warning": "",
    "doc_url": "https://github.com/Dummiesman/DynamixThreeSpaceBlenderAddon/",
    "tracker_url": "https://github.com/Dummiesman/DynamixThreeSpaceBlenderAddon/",
    "support": 'COMMUNITY',
    "category": "Import-Export"}

import bpy

from bpy.props import (
        BoolProperty,
        EnumProperty,
        FloatProperty,
        StringProperty,
        CollectionProperty,
        PointerProperty,
        )
from bpy_extras.io_utils import (
        ImportHelper,
        ExportHelper,
        )

class ImportDTS(bpy.types.Operator, ImportHelper):
    """Import from Dynamix Three Space (.DTS)"""
    bl_idname = "import_scene.dtst3d"
    bl_label = 'Import Dynamix Three Space'
    bl_options = {'UNDO'}

    filename_ext = ".dts"
    filter_glob: StringProperty(default="*.dts", options={'HIDDEN'})

    def execute(self, context):
        from . import import_dts
        keywords = self.as_keywords(ignore=("axis_forward",
                                            "axis_up",
                                            "filter_glob",
                                            "check_existing",
                                            ))

        return import_dts.load(self, context, **keywords)
    
def menu_func_import(self, context):
    self.layout.separator()
    self.layout.operator(ImportDTS.bl_idname, text="Dynamix Three Space (*.dts)")
    self.layout.separator()

# Register factories
def register():
    bpy.utils.register_class(ImportDTS)
    bpy.types.TOPBAR_MT_file_import.append(menu_func_import)

def unregister():
    bpy.types.TOPBAR_MT_file_import.remove(menu_func_import)
    bpy.utils.unregister_class(ImportDTS)

if __name__ == "__main__":
    register()