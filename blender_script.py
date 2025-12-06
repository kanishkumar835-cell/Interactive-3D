import bpy
import json
import os
from math import sqrt, radians, atan2
from mathutils import Vector

# --- CONFIGURATION ---
json_path = r"C:\\Users\\kanis\\pytorch_floorplan\\detections.json"
assets_path = r"C:\\Users\\kanis\\pytorch_floorplan\\assets.blend"
texture_path = r"C:\\Users\\kanis\\pytorch_floorplan\\wood_texture.jpg"

WALL_HEIGHT = 2.5
WALL_THICKNESS = 0.26
SCALE_FACTOR = 0.015
DOOR_HEIGHT = 2.1
WINDOW_HEIGHT = 1.0
WINDOW_BOTTOM_OFFSET = 0.9
FLOOR_THICKNESS = 0.1

# --- Automated Floorplan Builder Functions ---

def clear_scene():
    if bpy.context.object and bpy.context.object.mode != 'OBJECT':
        bpy.ops.object.mode_set(mode='OBJECT')
    bpy.ops.object.select_all(action='DESELECT')
    for obj in bpy.context.scene.objects:
        if obj.type in {'MESH', 'EMPTY', 'LIGHT', 'CAMERA'}:
            obj.select_set(True)
    if bpy.context.selected_objects:
        bpy.ops.object.delete()
    print("Scene cleared.")

def add_sun_light(strength=10.0, angle=radians(3.0)):
    bpy.ops.object.light_add(type='SUN', location=(5, -5, 10))
    sun = bpy.context.object
    sun.data.energy = strength
    sun.data.angle = angle
    sun.data.color = (1, 1, 1)
    print("Sun light added.")

def safe_num(v):
    return float(v[0]) if isinstance(v, tuple) else float(v)

def set_cycles_render_settings():
    scene = bpy.context.scene
    scene.render.engine = 'CYCLES'
    scene.cycles.device = 'GPU'
    scene.cycles.samples = 4096
    scene.cycles.preview_samples = 32
    scene.cycles.use_denoising = True
    if hasattr(scene.cycles, "denoiser"):
        scene.cycles.denoiser = "OPENIMAGEDENOISE"
    view_layer = bpy.context.view_layer
    if hasattr(view_layer, "cycles"):
        view_layer.cycles.use_denoising = True
    scene.render.film_transparent = True
    print("Cycles render settings applied.")

def enable_freestyle():
    scene = bpy.context.scene
    scene.render.use_freestyle = True
    for layer in scene.view_layers:
        layer.use_freestyle = True
    scene.render.line_thickness = 4.0
    print("Freestyle enabled.")

def compute_scene_bounds(detections):
    min_x, min_y = float('inf'), float('inf')
    max_x, max_y = float('-inf'), float('-inf')
    for detection in detections:
        x1, y1, x2, y2 = detection['bbox']
        min_x, min_y = min(min_x, x1), min(min_y, y1)
        max_x, max_y = max(max_x, x2), max(max_y, y2)
    center_x = (min_x + max_x) / 2 * SCALE_FACTOR
    center_y = -(min_y + max_y) / 2 * SCALE_FACTOR
    size_x = (max_x - min_x) * SCALE_FACTOR
    size_y = (max_y - min_y) * SCALE_FACTOR
    return (safe_num(center_x), safe_num(center_y)), float(max(size_x, size_y))

def add_camera_auto(bounds_center, bounds_size):
    for obj in [o for o in bpy.context.scene.objects if o.type == 'CAMERA']:
        bpy.data.objects.remove(obj, do_unlink=True)
    cam_dist = bounds_size * 1.4
    cam_height = max(25, bounds_size * 2.0)
    cam_location = (safe_num(bounds_center[0]) + cam_dist, safe_num(bounds_center[1]) - cam_dist, float(cam_height))
    bpy.ops.object.camera_add(location=cam_location)
    cam = bpy.context.object
    cx = safe_num(bounds_center)
    cy = safe_num(bounds_center[1])
    look_at = Vector((cx, cy, 0))
    direction = look_at - Vector(cam_location)
    cam_direction = direction.normalized()
    rot_quat = cam_direction.to_track_quat('-Z', 'Y')
    cam.rotation_euler = rot_quat.to_euler()
    bpy.context.scene.camera = cam
    print("Camera added.")

def create_and_assign_material(obj, name, color):
    material = bpy.data.materials.new(name=name)
    material.use_nodes = True
    principled_bsdf = material.node_tree.nodes.get('Principled BSDF')
    if principled_bsdf:
        principled_bsdf.inputs['Base Color'].default_value = color
    if obj.data.materials:
        obj.data.materials[0] = material
    else:
        obj.data.materials.append(material)

def create_textured_floor(detections):
    min_x, min_y = float('inf'), float('inf')
    max_x, max_y = float('-inf'), float('-inf')
    wall_detections = [d for d in detections if d['class'] == 'wall']
    if not wall_detections:
        print("No walls detected; skipping floor creation")
        return None
    for detection in wall_detections:
        x1, y1, x2, y2 = detection['bbox']
        min_x, min_y = min(min_x, x1), min(min_y, y1)
        max_x, max_y = max(max_x, x2), max(max_y, y2)
    floor_size_x = (max_x - min_x) * SCALE_FACTOR
    floor_size_y = (max_y - min_y) * SCALE_FACTOR
    floor_center_x = (min_x + max_x) / 2 * SCALE_FACTOR
    floor_center_y = -(min_y + max_y) / 2 * SCALE_FACTOR
    bpy.ops.mesh.primitive_cube_add(
        size=1,
        location=(floor_center_x, floor_center_y, -FLOOR_THICKNESS * 2),
        scale=(floor_size_x, floor_size_y, FLOOR_THICKNESS)
    )
    floor_object = bpy.context.object
    mat = bpy.data.materials.new(name="WoodFloorMaterial")
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get('Principled BSDF')
    texImage = mat.node_tree.nodes.new('ShaderNodeTexImage')
    if os.path.exists(texture_path):
        texImage.image = bpy.data.images.load(texture_path)
        mat.node_tree.links.new(bsdf.inputs['Base Color'], texImage.outputs['Color'])
    else:
        bsdf.inputs['Base Color'].default_value = (0.37, 0.22, 0.11, 1.0)
    floor_object.data.materials.append(mat)
    print("Created textured floor.")
    return floor_object

def create_wall(detection):
    bbox = detection['bbox']
    x1, y1, x2, y2 = bbox
    dx = x2 - x1
    dy = y2 - y1
    wall_angle = atan2(dy, dx)
    length = sqrt(dx * dx + dy * dy) * SCALE_FACTOR
    wall_depth = WALL_THICKNESS
    center_x = (x1 + x2) / 2 * SCALE_FACTOR
    center_y = -(y1 + y2) / 2 * SCALE_FACTOR
    bpy.ops.mesh.primitive_cube_add(
        size=1,
        location=(center_x, center_y, WALL_HEIGHT / 2),
        scale=(length, wall_depth, WALL_HEIGHT)
    )
    wall_object = bpy.context.object
    wall_object.rotation_euler = (0, 0, wall_angle)
    wall_object["wall_angle"] = wall_angle
    wall_object["is_floorplan_wall"] = True
    create_and_assign_material(wall_object, "WallMaterial", (0.96, 0.96, 0.96, 1))
    return wall_object

def create_opening_and_place_asset(detection, wall_objects):
    obj_class = detection['class']
    bbox = detection['bbox']
    x1, y1, x2, y2 = bbox
    obj_center_x = (x1 + x2) / 2 * SCALE_FACTOR
    obj_center_y = -(y1 + y2) / 2 * SCALE_FACTOR
    closest_wall = None
    min_dist = float('inf')
    for wall in wall_objects:
        dist = sqrt((obj_center_x - wall.location.x)**2 + (obj_center_y - wall.location.y)**2)
        if dist < min_dist:
            min_dist = dist
            closest_wall = wall
    if closest_wall is None:
        print(f"No wall found close to {obj_class} at ({obj_center_x}, {obj_center_y})")
        return
    cutter_width = (x2 - x1) * SCALE_FACTOR + 0.1
    cutter_depth = (y2 - y1) * SCALE_FACTOR + 0.1
    if obj_class == 'door':
        cutter_height, cutter_center_z = DOOR_HEIGHT, DOOR_HEIGHT / 2
        asset_name = "MyDoor"
    else:
        cutter_height, cutter_center_z = WINDOW_HEIGHT, WINDOW_BOTTOM_OFFSET + (WINDOW_HEIGHT / 2)
        asset_name = "MyWindow"
    bpy.ops.mesh.primitive_cube_add(location=(obj_center_x, obj_center_y, cutter_center_z), scale=(cutter_width, cutter_depth, cutter_height))
    cutter = bpy.context.object
    bool_mod = closest_wall.modifiers.new(name='BooleanCutter', type='BOOLEAN')
    bool_mod.operation = 'DIFFERENCE'
    bool_mod.object = cutter
    bpy.context.view_layer.objects.active = closest_wall
    bpy.ops.object.modifier_apply(modifier=bool_mod.name)
    bpy.data.objects.remove(cutter)
    if os.path.exists(assets_path):
        with bpy.data.libraries.load(assets_path, link=False) as (data_from, data_to):
            if asset_name in data_from.objects:
                data_to.objects = [asset_name]
                print(f"Loading asset {asset_name} from assets blend file.")
            else:
                print(f"Asset {asset_name} not found in assets blend file.")
                return
        if data_to.objects:
            asset = data_to.objects[0]
            bpy.context.collection.objects.link(asset)
            asset.location = (obj_center_x, obj_center_y, cutter_center_z)
            wall_angle = closest_wall.get('wall_angle', 0)
            asset.rotation_euler = (0, 0, wall_angle)
            asset.scale = (1, 1, 1)
            print(f"Placed {asset_name} at {asset.location}")
    else:
        print("Assets blend file not found:", assets_path)

def build_floorplan():
    clear_scene()
    set_cycles_render_settings()
    enable_freestyle()
    if not os.path.exists(json_path):
        print("Detections JSON file not found:", json_path)
        return
    with open(json_path, 'r') as f:
        data = json.load(f)
        detections = data.get("detections", []) if isinstance(data, dict) else data
    if not detections:
        print("No detections found in JSON.")
        return
    bounds_center, bounds_size = compute_scene_bounds(detections)
    add_sun_light(strength=10.0, angle=radians(3.0))
    add_camera_auto(bounds_center, bounds_size)
    create_textured_floor(detections)
    bpy.ops.object.select_all(action='DESELECT')
    wall_objects = []
    for detection in detections:
        if detection['class'] == 'wall':
            wall = create_wall(detection)
            wall_objects.append(wall)
            bpy.ops.object.select_all(action='DESELECT')
    for detection in detections:
        obj_class = detection['class']
        if obj_class == 'door' or obj_class == 'window':
            create_opening_and_place_asset(detection, wall_objects)
    print("Floor plan generation complete.")

# --- Floorplan Editing UI ---

class FloorplanElement(bpy.types.PropertyGroup):
    obj_ref: bpy.props.PointerProperty(type=bpy.types.Object)

class FP_OT_add_wall(bpy.types.Operator):
    bl_idname = "floorplan.add_wall"
    bl_label = "Add Wall"
    bl_description = "Add a rectangular wall cuboid to the floorplan"

    def execute(self, context):
        bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 0, WALL_HEIGHT / 2))
        wall = context.active_object
        wall.name = "Wall"
        wall["is_floorplan_wall"] = True
        wall.scale = (4.0 / 2, 0.26 / 2, WALL_HEIGHT / 2)
        self.report({'INFO'}, "Wall added")
        return {'FINISHED'}

class FP_OT_remove_selected_floorplan(bpy.types.Operator):
    bl_idname = "floorplan.remove_selected_floorplan"
    bl_label = "Remove Selected Walls/Doors/Windows"
    bl_description = "Remove selected floorplan elements and walls starting with 'Wall'"

    @classmethod
    def poll(cls, context):
        return any(
            obj.get("is_floorplan_wall") or obj.get("is_floorplan_door") or obj.get("is_floorplan_window") or
            obj.name.startswith("Wall")
            for obj in context.selected_objects)

    def execute(self, context):
        removed = 0
        for obj in context.selected_objects:
            if (obj.get("is_floorplan_wall") or obj.get("is_floorplan_door") or obj.get("is_floorplan_window")) or \
               (obj.name.startswith("Wall")):
                bpy.data.objects.remove(obj, do_unlink=True)
                removed += 1
        self.report({'INFO'}, f"Removed {removed} objects")
        return {'FINISHED'}

class FP_OT_set_wall_color(bpy.types.Operator):
    bl_idname = "floorplan.set_wall_color"
    bl_label = "Set Wall Colour"
    bl_description = "Set the colour of selected walls"

    color: bpy.props.FloatVectorProperty(
        name="Wall Color", subtype='COLOR', default=(0.8, 0.8, 0.8), min=0.0, max=1.0, size=3
    )

    def execute(self, context):
        # Ensure each color channel is a float
        color_rgba = tuple(float(c) for c in list(self.color)) + (1.0,)
        for obj in context.selected_objects:
            if obj.get("is_floorplan_wall") or obj.name.startswith("Wall"):
                matname = "WallMaterial"
                mat = bpy.data.materials.get(matname)
                if mat is None:
                    mat = bpy.data.materials.new(name=matname)
                    mat.use_nodes = True
                if not obj.data.materials:
                    obj.data.materials.append(mat)
                else:
                    for i in range(len(obj.data.materials)):
                        obj.data.materials[i] = mat
                if mat.use_nodes:
                    bsdf = mat.node_tree.nodes.get('Principled BSDF')
                    if bsdf:
                        bsdf.inputs['Base Color'].default_value = color_rgba
                mat.diffuse_color = color_rgba
                mat.preview_render_type = 'CUBE'
        self.report({'INFO'}, "Wall colour set")
        return {'FINISHED'}

class FP_UL_floorplan_elements(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        obj = item.obj_ref
        if obj:
            icon = 'MESH_CUBE' if obj.get("is_floorplan_wall") or obj.name.startswith("Wall") else \
                   'MESH_CIRCLE' if obj.get("is_floorplan_door") else \
                   'MESH_MONKEY' if obj.get("is_floorplan_window") else 'OBJECT_DATAMODE'
            layout.prop(obj, "name", text="", emboss=False, icon=icon)

class FP_PT_floorplan_panel(bpy.types.Panel):
    bl_label = "Floorplan Editor"
    bl_idname = "VIEW3D_PT_floorplan_editor"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'Floorplan'

    def draw(self, context):
        layout = self.layout
        scene = context.scene

        row = layout.row()
        row.operator("floorplan.add_wall", icon='MESH_CUBE')
        row.operator("floorplan.remove_selected_floorplan", icon='TRASH')

        layout.separator()
        layout.label(text="Wall Colour:")
        row = layout.row()
        row.prop(scene, "fp_wall_color", text="")
        row.operator("floorplan.set_wall_color", text="Apply Colour").color = scene.fp_wall_color

        layout.separator()
        layout.label(text="Floorplan Elements:")

        layout.template_list(
            "FP_UL_floorplan_elements",
            "",
            scene,
            "floorplan_elements",
            scene,
            "floorplan_elements_index",
            rows=8,
        )

        index = scene.floorplan_elements_index
        coll = scene.floorplan_elements
        if 0 <= index < len(coll):
            obj = coll[index].obj_ref
            if obj:
                layout.separator()
                layout.label(text=f"Selected: {obj.name}")
                col = layout.column(align=True)
                col.prop(obj, "location")
                col.prop(obj, "rotation_euler", text="Rotation")
                col.prop(obj, "scale")

def get_floorplan_elements(scene):
    return [obj for obj in scene.objects if
            obj.get("is_floorplan_wall") or obj.get("is_floorplan_door") or obj.get("is_floorplan_window") or
            obj.name.startswith("Wall")]

def update_floorplan_elements_collection(scene):
    coll = scene.floorplan_elements
    coll.clear()
    for obj in get_floorplan_elements(scene):
        item = coll.add()
        item.obj_ref = obj

def depsgraph_update(scene, depsgraph):
    update_floorplan_elements_collection(scene)

classes = [
    FloorplanElement,
    FP_OT_add_wall,
    FP_OT_remove_selected_floorplan,
    FP_OT_set_wall_color,
    FP_UL_floorplan_elements,
    FP_PT_floorplan_panel,
]

def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.floorplan_elements = bpy.props.CollectionProperty(type=FloorplanElement)
    bpy.types.Scene.floorplan_elements_index = bpy.props.IntProperty(default=0)
    bpy.types.Scene.fp_wall_color = bpy.props.FloatVectorProperty(
        name="Wall Color", subtype='COLOR',
        default=(0.8, 0.8, 0.8), min=0.0, max=1.0, size=3
    )
    bpy.app.handlers.depsgraph_update_post.append(depsgraph_update)
    build_floorplan()

def unregister():
    bpy.app.handlers.depsgraph_update_post.remove(depsgraph_update)
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
    del bpy.types.Scene.floorplan_elements
    del bpy.types.Scene.floorplan_elements_index
    del bpy.types.Scene.fp_wall_color

if __name__ == "__main__":
    register()
