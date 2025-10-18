import struct
from typing import List, BinaryIO

from io_scene_dtst3d.tsalloc import *

class TSDrawPrimitiveType:
    Triangles = 0 << 30
    Strip = 1 << 30
    Fan = 2 << 30

    Indexed = 1 << 29
    NoMaterial = 1 << 28

    MaterialMask = ~(Strip|Fan|Triangles|Indexed|NoMaterial)
    TypeMask     = Strip|Fan|Triangles

class TSDrawPrimitive:
    def __init__(self, start, num_elements, material_and_flags):
        self.start = start
        self.num_elements = num_elements
        self.material_index = material_and_flags

        self.has_no_material = (material_and_flags & TSDrawPrimitiveType.NoMaterial) == TSDrawPrimitiveType.NoMaterial
        self.type = material_and_flags & TSDrawPrimitiveType.TypeMask
        self.material_index = material_and_flags & TSDrawPrimitiveType.MaterialMask

        
class TSNullMesh:
    pass

class TSMesh:
    def __init__(self):
            self._vertices = []
            self._tvertices = []
            self._t2vertices = []
            self._colors = []
            self._primitives: List[TSDrawPrimitive] = []
            self._indices = []

    @property
    def vertices(self):
        return self._vertices
    
    @property
    def tvertices(self):
        return self._tvertices
    
    @property
    def t2vertices(self):
        return self._t2vertices
    
    @property
    def colors(self):
        return self._colors
    
    @property
    def primitives(self) -> List[TSDrawPrimitive]:
        return self._primitives
    
    @property
    def indices(self):
        return self._indices
    
    def copy_data_from(self, other):
        """Copies mesh data from a parent mesh"""
        self._vertices = other._vertices.copy()
        self._tvertices = other._tvertices.copy()
        self._t2vertices = other._t2vertices.copy()
        self._primitives = other._primitives.copy()
        self._colors = other._colors.copy()

    def assemble(self, ts_alloc, version):
        ts_alloc.check_guard()

        num_frames = ts_alloc.read32()
        num_mat_names = ts_alloc.read32()
        parent_mesh = ts_alloc.read32()

        bounds = [ts_alloc.read_float() for _ in range(6)]
        center = [ts_alloc.read_float() for _ in range(3)]
        radius = ts_alloc.read_float()

        vert_offset = 0
        offset_num_verts = 0
        offset_vert_size = 0

        if version >= 27:
            vert_offset = ts_alloc.read32()
            offset_num_verts = ts_alloc.read32()
            offset_vert_size = ts_alloc.read32()

        # verts and texture coords
        num_verts = ts_alloc.read32()

        if parent_mesh < 0:
            # independent mesh: read vertices
            for _ in range(num_verts):
                vertex = (ts_alloc.read_float(), ts_alloc.read_float(), ts_alloc.read_float())
                self._vertices.append(vertex)

        num_tverts = ts_alloc.read32()
        if parent_mesh < 0:
            # read texture coords
            for _ in range(num_tverts):
                tvertex = (ts_alloc.read_float(), ts_alloc.read_float())
                self._tvertices.append(tvertex)

        # 2nd texture channel and colors
        if version > 25:
            num_t2verts = ts_alloc.read32()
            if parent_mesh < 0:
                for _ in range(num_t2verts):
                    tvertex = (ts_alloc.read_float(), ts_alloc.read_float())
                    self._t2vertices.append(tvertex)

            num_vcolors = ts_alloc.read32()
            if parent_mesh < 0:
                for _ in range(num_vcolors):
                    packed_color = ts_alloc.read32()

                    red   =  packed_color & 0xFF
                    green = (packed_color >> 8)  & 0xFF
                    blue  = (packed_color >> 16) & 0xFF
                    alpha = (packed_color >> 24) & 0xFF

                    self._colors.append((red / 255.0, green / 255.0, blue / 255.0, alpha / 255.0))


        # normals
        if version > 21:
            if parent_mesh < 0:
                for _ in range(num_verts):
                    normal = (ts_alloc.read_float(), ts_alloc.read_float(), ts_alloc.read_float())
                for _ in range(num_verts):
                    ts_alloc.read8()  # encoded normals, skip
        else:
            if parent_mesh < 0:
                for _ in range(num_verts):
                    normal = (ts_alloc.read_float(), ts_alloc.read_float(), ts_alloc.read_float())

        # primitives and indices
        sz_prim_in = 0
        sz_ind_in = 0

        starts = []
        elements = []
        material_indices = []
        
        if version > 25:
            # mesh primitives (start, numElements) and indices are stored as 32 bit values
            sz_prim_in = ts_alloc.read32()
            for _ in range(sz_prim_in):
                starts.append(ts_alloc.read32())
                elements.append(ts_alloc.read32())
                material_indices.append(ts_alloc.read32())

            sz_ind_in = ts_alloc.read32()
            for _ in range(sz_ind_in):
                self._indices.append(ts_alloc.read32())
        else:
            # mesh primitives (start, numElements) indices are stored as 16 bit values
            sz_prim_in = ts_alloc.read32()
            for _ in range(sz_prim_in):
                starts.append(ts_alloc.read16())
                elements.append(ts_alloc.read16())
            for _ in range(sz_prim_in):
                material_indices.append(ts_alloc.read32())

            sz_ind_in = ts_alloc.read32()
            for _ in range(sz_ind_in):
                self._indices.append(ts_alloc.read16())

        # setup primitives from data
        for x in range(sz_prim_in):
            start = starts[x]
            num_elements = elements[x]
            material_index = material_indices[x]

            prim = TSDrawPrimitive(start, num_elements, material_index)
            self._primitives.append(prim)
            
        # merge indices (deprecated)
        num_merge_indices = ts_alloc.read32()
        for _ in range(num_merge_indices):
            ts_alloc.read16()

        ts_alloc.align32()

        verts_per_frame = ts_alloc.read32()
        flags = ts_alloc.read32()

        ts_alloc.check_guard()