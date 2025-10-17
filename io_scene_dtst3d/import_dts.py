import bpy, mathutils, bmesh
import time

from io_scene_dtst3d.tsshape import *

#from tsshape import *

######################################################
# HELPERS
######################################################
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

        # Set Base Color in Principled BSDF
        bsdf = mtl.node_tree.nodes.get("Principled BSDF")
        if bsdf:
            bsdf.inputs['Base Color'].default_value = (1.0, 1.0, 1.0, 1.0)

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


def create_mesh_object_from_shape_object(shape, shape_object):
    scn = bpy.context.scene
    
    shape_node = shape.nodes[shape_object.node_index]
    shape_object_name = shape.names[shape_object.name_index]
    shape_mesh = shape.meshes[shape_object.start_mesh_index]

    # create material remap
    material_remap = {}

    # create blender mesh
    me = bpy.data.meshes.new('DTSMesh' + str(shape_object.start_mesh_index))
    
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

    # assemble blender mesh
    mesh_indices = shape_mesh.indices
    
    vertices = []
    for vert in shape_mesh.vertices:
        vertices.append(bm.verts.new(translate_vert(vert)))
    
    for prim in shape_mesh.primitives:
        # setup material (TODO: have a list of mats)
        if not prim.material_index in material_remap:
            ts_material = shape.materials[prim.material_index]
            material_remap[prim.material_index] = len(material_remap)
            ob.data.materials.append(create_material(ts_material.name))


        if prim.type == TSDrawPrimitiveType.Triangles:
            for x in range(0, prim.num_elements, 3):
                indices = (mesh_indices[prim.start + x + 2], mesh_indices[prim.start + x + 1], mesh_indices[prim.start + x])
                try:
                    bmverts = (vertices[indices[0]], vertices[indices[1]], vertices[indices[2]])
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
    # read shape
    shape = TSShape()
    shape.read_from_path(filepath)

    # create Blender representation
    hierarchy = {}

    for shape_index, shape_object in enumerate(shape.objects):
        if shape_object.num_meshes > 0:
            shape_mesh = shape.meshes[shape_object.start_mesh_index]
            shape_node = shape.nodes[shape_object.node_index]

            parent = None if shape_node.parent_index < 0 else hierarchy.get(shape_node.parent_index)
            created_object = None
            if isinstance(shape_mesh, TSMesh):
                created_object = create_mesh_object_from_shape_object(shape, shape_object)
            elif isinstance(shape_mesh, TSNullMesh):
                created_object = create_dummy_object_from_shape_object(shape, shape_object)

            if created_object is not None:
                hierarchy[shape_object.node_index] = created_object
                if parent is not None:
                    created_object.parent = parent
                    created_object.matrix_parent_inverse = parent.matrix_world.inverted()


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