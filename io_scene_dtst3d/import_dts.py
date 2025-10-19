import bpy, mathutils, bmesh
import time

from io_scene_dtst3d.tsshape import *

#from tsshape import *

######################################################
# HELPERS
######################################################
def triangle_strip_to_list(strip, clockwise):
    """convert a strip of triangles into a list of triangles"""
    triangle_list = []
    for v in range(len(strip) - 2):
        if clockwise:
            triangle_list.extend([strip[v+1], strip[v], strip[v+2]])
        else:
            triangle_list.extend([strip[v], strip[v+1], strip[v+2]])
        clockwise = not clockwise

    return triangle_list


def create_material(material_name):
    # Try to get existing material
    mtl = bpy.data.materials.get(material_name)
    if mtl is None:
        # Material doesn't exist, create a new one
        mtl = bpy.data.materials.new(name=material_name)
        mtl.diffuse_color = (1.0, 1.0, 1.0, 1.0)
        mtl.specular_intensity = 0
        mtl.use_nodes = True
        mtl.use_backface_culling = True

    return mtl


def translate_uv(uv):
    return (uv[0], 1.0 - uv[1])


def translate_vert(vert):
    return (vert[0], vert[1], vert[2])

######################################################
# IMPORT
######################################################
def apply_node_transform_to_object(shape_node, ob):
    ob.location = translate_vert(shape_node.translation)

    rotation_quaternion = shape_node.rotation.to_quat_f()
    rotation_quaternion.x = rotation_quaternion.x * -1.0

    ob.rotation_mode = 'QUATERNION'
    ob.rotation_quaternion =  mathutils.Quaternion((rotation_quaternion.w, 
                                                    rotation_quaternion.x, 
                                                    rotation_quaternion.y,
                                                    rotation_quaternion.z))


def create_dummy_object_from_shape_object(shape, shape_object):
    scn = bpy.context.scene
    
    shape_node = shape.nodes[shape_object.node_index]
    shape_object_name = shape.names[shape_object.name_index]

    # create object
    ob = bpy.data.objects.new(shape_object_name, None)
    apply_node_transform_to_object(shape_node, ob)

    scn.collection.objects.link(ob)

    return ob


def create_mesh_object_from_shape_object(shape, shape_object, shape_mesh_index):
    scn = bpy.context.scene
    
    shape_node = shape.nodes[shape_object.node_index]
    shape_object_name = shape.names[shape_object.name_index]
    shape_mesh = shape.meshes[shape_object.start_mesh_index + shape_mesh_index]

    # create material remap
    material_remap = {}

    # create blender mesh
    me = bpy.data.meshes.new('DTSMesh' + str(shape_object.start_mesh_index + shape_mesh_index))
    
    bm = bmesh.new()
    bm.from_mesh(me)

    uv_layer = None
    uv2_layer = None
    vc_layer = None

    if len(shape_mesh.tvertices) == len(shape_mesh.vertices):
        uv_layer = bm.loops.layers.uv.new()
    if len(shape_mesh.t2vertices) == len(shape_mesh.vertices):
        uv2_layer = bm.loops.layers.uv.new()
    if len(shape_mesh.colors) == len(shape_mesh.vertices):
        vc_layer = bm.loops.layers.color.new()
    
    # create object
    ob = bpy.data.objects.new(shape_object_name, me)
    apply_node_transform_to_object(shape_node, ob)

    scn.collection.objects.link(ob)

    # remap to merge verts with same normals for Blender because DTS is a game-ready format
    # which requires unique vertices for each combination of TVerts/Normals
    vertex_count = len(shape_mesh.vertices)
    vert_remap = {}
    remapped_verts = []    
    
    for x in range(vertex_count):
        position = shape_mesh.vertices[x]
        normal = shape_mesh.normals[x]
        key = (position, normal)
        if not key in vert_remap:
            vert_remap[key] = len(vert_remap)
            remapped_verts.append(bm.verts.new(translate_vert(position)))

    # assemble blender mesh
    mesh_indices = shape_mesh.indices 
    
    for prim in shape_mesh.primitives:
        # setup material (TODO: have a list of mats)
        if not prim.material_index in material_remap:
            ts_material = shape.materials[prim.material_index]
            material_remap[prim.material_index] = len(material_remap)
            ob.data.materials.append(create_material(ts_material.name))

        if prim.type == TSDrawPrimitiveType.Triangles or prim.type == TSDrawPrimitiveType.Strip:
            # get raw primitive indices
            prim_indices = []
            if prim.type == TSDrawPrimitiveType.Triangles:
                prim_indices = mesh_indices[prim.start:prim.start+prim.num_elements]
            else:
                strip_indices = mesh_indices[prim.start:prim.start+prim.num_elements]
                prim_indices = triangle_strip_to_list(strip_indices, False)

            # remap prim indices
            for x in range(len(prim_indices)):
                vert_index = prim_indices[x]
                position = shape_mesh.vertices[vert_index]
                normal = shape_mesh.normals[vert_index]
                key = (position, normal)
                prim_indices[x] = vert_remap[key]

            # create faces
            for x in range(0, len(prim_indices), 3):
                indices = (prim_indices[x + 2], prim_indices[x + 1], prim_indices[x])
                try:
                    bmverts = (remapped_verts[indices[0]], remapped_verts[indices[1]], remapped_verts[indices[2]])
                    face = bm.faces.new(bmverts)

                    if uv_layer is not None:
                        for y in range(3):
                            face.loops[y][uv_layer].uv = translate_uv(shape_mesh.tvertices[indices[y]])
                    if uv2_layer is not None:
                        for y in range(3):
                            face.loops[y][uv2_layer].uv = translate_uv(shape_mesh.t2vertices[indices[y]])
                    if vc_layer is not None:
                        for y in range(3):
                            face.loops[y][vc_layer] = shape_mesh.colors[indices[y]]

                    face.material_index = material_remap[prim.material_index]
                    face.smooth = True
                except Exception as e:
                    print(str(e))
        else:
            print(f"Unsupported prim type {prim.type}, ignoring.")

    # calculate normals
    bm.normal_update()

    # free resources
    bm.to_mesh(me)
    bm.free()

    return ob


def read_dts_file(file, filepath):
    time1 = time.perf_counter()

    # read shape
    shape = TSShape()
    shape.read_from_path(filepath)

    print("   parsed shape file in %.4f sec." % (time.perf_counter() - time1))
    time1 = time.perf_counter()

    for sequence in shape.sequences:
        if sequence.name_index >= 0:
            sequence_name = shape.names[sequence.name_index]
            print(f"Found sequence: {sequence_name}, {sequence.num_keyframes} keyframes")
        else:
            print(f"Found unnamed sequence with {sequence.num_keyframes} keyframes")

    # create Blender representation
    hierarchy = {}

    for shape_index, shape_object in enumerate(shape.objects):
        shape_object_name = shape.names[shape_object.name_index]
        print(f"Importing shape object {shape_object_name} with {shape_object.num_meshes} meshes")
        if shape_object.num_meshes > 0:
            shape_mesh = shape.meshes[shape_object.start_mesh_index]
            shape_node = shape.nodes[shape_object.node_index]

            parent = None if shape_node.parent_index < 0 else hierarchy.get(shape_node.parent_index)
            created_object = None
            if isinstance(shape_mesh, TSMesh) or isinstance(shape_mesh, TSSkinnedMesh):
                created_object = create_mesh_object_from_shape_object(shape, shape_object, 0)
            elif isinstance(shape_mesh, TSNullMesh):
                created_object = create_dummy_object_from_shape_object(shape, shape_object)
            else:
                print(f"Not creating object for {shape_object_name}: unsupported TSMesh type")

            if created_object is not None:
                hierarchy[shape_object.node_index] = created_object
                if parent is not None:
                    created_object.parent = parent
                    created_object.matrix_parent_inverse = parent.matrix_world.inverted()
        else:
            print(f"Not creating object for {shape_object_name}: no assigned mesh")

    print("   created objects in %.4f sec." % (time.perf_counter() - time1))

######################################################
# IMPORT
######################################################
def load_dts(filepath,
             context):

    print("importing DTS: %r..." % (filepath))

    time1 = time.perf_counter()
    file = open(filepath, 'rb')

    # start reading our bnd file
    read_dts_file(file, filepath)

    print(" done in %.4f sec." % (time.perf_counter() - time1))
    file.close()


def load(operator,
         context,
         filepath="",
         ):

    load_dts(filepath,
             context,
             )

    return {'FINISHED'}