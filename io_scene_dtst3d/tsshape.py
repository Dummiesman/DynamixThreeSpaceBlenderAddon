import struct
from typing import List, BinaryIO

from io_scene_dtst3d.tsmesh import *
from io_scene_dtst3d.tsalloc import *

#from tsmesh import *

class MeshType:
    StandardMeshType = 0
    SkinMeshType = 1
    DecalMeshType = 2
    SortedMeshType = 3
    NullMeshType = 4

    TypeMask = 7  # result of 0 | 1 | 2 | 3 | 4

class TQuaternionF:
    x: float
    y: float
    z: float
    w: float

    def __init__(self, x, y, z, w):
        self.x = x
        self.y = y
        self.z = z
        self.w = w

class TQuaternion16:
    x: int
    y: int
    z: int
    w: int

    MAX_VALUE = 0x7fff 

    def __init__(self, x, y, z, w):
        self.x = x
        self.y = y
        self.z = z
        self.w = w   

    def to_quat_f(self):
        return TQuaternionF(self.x / TQuaternion16.MAX_VALUE,
                            self.y / TQuaternion16.MAX_VALUE,
                            self.z / TQuaternion16.MAX_VALUE,
                            self.w / TQuaternion16.MAX_VALUE)

class ShapeNode:
    def __init__(self):
        self.name_index = -1
        self.parent_index = -1

        self.translation = (0, 0, 0)
        self.rotation = TQuaternion16(0, 0, 0, TQuaternion16.MAX_VALUE)

    def assemble(self, ts_alloc):
        self.name_index = ts_alloc.read32()
        self.parent_index = ts_alloc.read32()

        # runtime computed apparently
        ts_alloc.read32()
        ts_alloc.read32()
        ts_alloc.read32()

class ShapeObject:
    def __init__(self):
        self.name_index = -1
        self.num_meshes = -1
        self.start_mesh_index = -1
        self.node_index = -1

    def assemble(self, ts_alloc):
        self.name_index = ts_alloc.read32()
        self.num_meshes = ts_alloc.read32()
        self.start_mesh_index = ts_alloc.read32()
        self.node_index = ts_alloc.read32()

        # runtime computed apparently
        ts_alloc.read32()
        ts_alloc.read32()

class TSMaterial:
    def __init__(self, name):
        self.name = name

class TSShape:
    def __init__(self):
        self._meshes: List[TSMesh] = []
        self._nodes: List[ShapeNode] = []
        self._objects: List[ShapeObject] = []
        self._names: List[str] = []
        self._materials: List[TSMaterial] = []

    @property
    def materials(self) -> List[TSMaterial]:
        return self._materials
    
    @property
    def meshes(self) -> List[TSMesh]:
        return self._meshes
    
    @property
    def nodes(self) -> List[ShapeNode]:
        return self._nodes
    
    @property
    def objects(self) -> List[ShapeObject]:
        return self._objects
    
    @property
    def names(self) -> List[str]:
        return self._names

    def read(self, stream: BinaryIO):
        reader = stream

        version = struct.unpack('<i', reader.read(4))[0] & 0xFF
        if version < 19:
            raise Exception("This DTS file is too old")
        if version >= 27:
            raise Exception("This DTS file is too new, please file an issue report with the problem file attached.")

        size_mem_buffer = struct.unpack('<i', reader.read(4))[0]
        start_u16 = struct.unpack('<i', reader.read(4))[0]
        start_u8 = struct.unpack('<i', reader.read(4))[0]

        buf = reader.read(size_mem_buffer * 4)
        ts_alloc = TSAlloc(buf, size_mem_buffer, start_u16, start_u8)

        self.assemble(ts_alloc, version)

        # sequences
        num_sequences = struct.unpack('<i', reader.read(4))[0]
        for _ in range(num_sequences):
            raise NotImplementedError("Sequences")

        # materials
        mat_list_version = struct.unpack('<B', reader.read(1))[0]
        mat_count = struct.unpack('<i', reader.read(4))[0]
        
        for x in range(mat_count):
            mat_name_length = struct.unpack('<B', reader.read(1))[0]
            mat_name_bytes = reader.read(mat_name_length)
            mat_name = mat_name_bytes.decode('utf-8')
            
            self._materials.append(TSMaterial(mat_name))
            
        # see Torque3D material list parsing if properties are desired

    def read_from_path(self, path: str):
        with open(path, "rb") as f:
            self.read(f)

    def assemble(self, ts_alloc, version: int):
        num_nodes = ts_alloc.read32()
        num_objects = ts_alloc.read32()
        num_decals = ts_alloc.read32()
        num_sub_shapes = ts_alloc.read32()
        num_ifl_materials = ts_alloc.read32()

        if version < 22:
            num_node_rots = num_node_trans = ts_alloc.read32() - num_nodes
            num_node_uniform_scales = num_node_aligned_scales = num_node_arbitrary_scales = 0
        else:
            num_node_rots = ts_alloc.read32()
            num_node_trans = ts_alloc.read32()
            num_node_uniform_scales = ts_alloc.read32()
            num_node_aligned_scales = ts_alloc.read32()
            num_node_arbitrary_scales = ts_alloc.read32()

        num_ground_frames = ts_alloc.read32() if version > 23 else 0
        num_object_states = ts_alloc.read32()
        num_decal_states = ts_alloc.read32()
        num_triggers = ts_alloc.read32()
        num_details = ts_alloc.read32()
        num_meshes = ts_alloc.read32()

        num_skins = ts_alloc.read32() if version < 23 else 0

        num_names = ts_alloc.read32()
        m_smallest_visible_size = ts_alloc.read_float()
        m_smallest_visible_dl = ts_alloc.read32()

        ts_alloc.check_guard()

        radius = ts_alloc.read_float()
        tube_radius = ts_alloc.read_float()
        center = [ts_alloc.read_float() for _ in range(3)]
        bounds_min = [ts_alloc.read_float() for _ in range(3)]
        bounds_max = [ts_alloc.read_float() for _ in range(3)]

        ts_alloc.check_guard()

        # Node data
        for _ in range(num_nodes):
            node = ShapeNode()
            node.assemble(ts_alloc)
            self._nodes.append(node)
            
        ts_alloc.check_guard()

        # Object data
        for _ in range(num_objects):
            obj = ShapeObject()
            obj.assemble(ts_alloc)
            self._objects.append(obj)

        if num_skins > 0:
            for _ in range(num_skins):
                for _ in range(6):
                    ts_alloc.read32()

        ts_alloc.check_guard()

        # Deprecated decals
        for _ in range(num_decals):
            for _ in range(5):
                ts_alloc.read32()

        ts_alloc.check_guard()

        # Deprecated IFL decals
        for _ in range(num_decals):
            for _ in range(5):
                ts_alloc.read32()

        ts_alloc.check_guard()

        # Subshape reading
        for _ in range(num_sub_shapes):
            ts_alloc.read32()  # first node
        for _ in range(num_sub_shapes):
            ts_alloc.read32()  # first object
        for _ in range(num_sub_shapes):
            ts_alloc.read32()  # deprecated subShapeFirstDecal
        ts_alloc.check_guard()

        for _ in range(num_sub_shapes):
            ts_alloc.read32()  # num nodes
        for _ in range(num_sub_shapes):
            ts_alloc.read32()  # num objects
        for _ in range(num_sub_shapes):
            ts_alloc.read32()  # deprecated subShapeNumDecals
        ts_alloc.check_guard()

        # Default rotations and translations
        for x in range(num_nodes):
            quat = TQuaternion16(ts_alloc.read16(), ts_alloc.read16(), ts_alloc.read16(), ts_alloc.read16())
            self._nodes[x].rotation = quat
                
        ts_alloc.align32()

        for x in range(num_nodes):
            self._nodes[x].translation = (ts_alloc.read_float(), ts_alloc.read_float(), ts_alloc.read_float())

        # Node sequence data
        for _ in range(num_node_trans):
            for _ in range(3):
                ts_alloc.read32()

        for _ in range(num_node_rots):
            for _ in range(4):
                ts_alloc.read16()

        ts_alloc.align32()
        ts_alloc.check_guard()

        if version > 21:
            for _ in range(num_node_uniform_scales):
                ts_alloc.read32()

            for _ in range(num_node_aligned_scales):
                for _ in range(3):
                    ts_alloc.read32()

            for _ in range(num_node_arbitrary_scales):
                for _ in range(3):
                    ts_alloc.read32()
            for _ in range(num_node_arbitrary_scales):
                for _ in range(4):
                    ts_alloc.read16()

            ts_alloc.align32()
            ts_alloc.check_guard()

        if version > 23:
            for _ in range(num_ground_frames):
                for _ in range(3):
                    ts_alloc.read32()
            for _ in range(num_ground_frames):
                for _ in range(4):
                    ts_alloc.read16()
            ts_alloc.align32()
            ts_alloc.check_guard()

        for _ in range(num_object_states):
            for _ in range(3):
                ts_alloc.read32()
        ts_alloc.check_guard()

        for _ in range(num_decal_states):
            ts_alloc.read32()
        ts_alloc.check_guard()

        for _ in range(num_triggers):
            ts_alloc.read32()
            ts_alloc.read32()
        ts_alloc.check_guard()

        num_detail_fields = 13 if version >= 26 else 7
        for _ in range(num_details):
            for _ in range(num_detail_fields):
                ts_alloc.read32()
        ts_alloc.check_guard()

        if version >= 27:
            raise NotImplementedError("Vertex format")

        # Meshes
        for _ in range(num_meshes):
            mesh_type_raw = ts_alloc.read32()

            mesh_type = mesh_type_raw & MeshType.TypeMask
            mesh_flags = mesh_type_raw & ~MeshType.TypeMask

            if mesh_type == MeshType.StandardMeshType:
                mesh = TSMesh()
                mesh.assemble(ts_alloc, version)
                self._meshes.append(mesh)
            elif mesh_type == MeshType.NullMeshType:
                mesh = TSNullMesh()
                self._meshes.append(mesh)
            else:
                raise NotImplementedError(f"Can't parse mesh of type {mesh_type}")

        ts_alloc.check_guard()

        # Names
        for _ in range(num_names):
            chars = []
            while True:
                b = ts_alloc.read8()
                if b == 0:
                    break
                chars.append(chr(b))
            self._names.append(''.join(chars))

        ts_alloc.align32()
        ts_alloc.check_guard()

        if version < 23:
            raise NotImplementedError("Skin information")