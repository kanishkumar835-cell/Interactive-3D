import bpy

# Constants for wall dimensions (meters)
WALL_LENGTH = 4.0
WALL_THICKNESS = 0.26
WALL_HEIGHT = 2.5

# --- Property Group to hold object references ---

class FloorplanElement(bpy.types.PropertyGroup):
    obj_ref: bpy.props.PointerProperty(type=bpy.types.Object)

# --- Operators ---

class FP_OT_add_wall(bpy.types.Operator):
    bl_idname = "floorplan.add_wall"
    bl_label = "Add Wall"
    bl_description = "Add a rectangular wall cuboid to the floorplan"

    def execute(self, context):
        bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 0, WALL_HEIGHT / 2))
        wall = context.active_object
        wall.name = "Wall"
        wall["is_floorplan_wall"] = True
        wall.scale = (WALL_LENGTH / 2, WALL_THICKNESS / 2, WALL_HEIGHT / 2)
        self.report({'INFO'}, f"Wall added (L={WALL_LENGTH}m, T={WALL_THICKNESS}m, H={WALL_HEIGHT}m)")
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
        for obj in context.selected_objects:
            if obj.get("is_floorplan_wall") or obj.name.startswith("Wall"):
                matname = "WallMaterial"
                # Either get existing or create new material
                mat = bpy.data.materials.get(matname)
                if mat is None:
                    mat = bpy.data.materials.new(name=matname)
                    mat.use_nodes = True

                # Update shader node tree (Principled BSDF)
                if mat.use_nodes:
                    bsdf = mat.node_tree.nodes.get('Principled BSDF')
                    if bsdf:
                        bsdf.inputs['Base Color'].default_value = (self.color[0], self.color[1], self.color, 1)

                # Assign material to object, replace any old materials
                if not obj.data.materials:
                    obj.data.materials.append(mat)
                else:
                    for i in range(len(obj.data.materials)):
                        obj.data.materials[i] = mat

                # Set viewport display color for Solid mode visibility
                mat.diffuse_color = (self.color[0], self.color[1], self.color, 1)
                mat.preview_render_type = 'CUBE'

        self.report({'INFO'}, "Wall colour set")
        return {'FINISHED'}

# --- UI List ---

class FP_UL_floorplan_elements(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        obj = item.obj_ref
        if obj:
            icon = 'MESH_CUBE' if obj.get("is_floorplan_wall") or obj.name.startswith("Wall") else \
                   'MESH_CIRCLE' if obj.get("is_floorplan_door") else \
                   'MESH_MONKEY' if obj.get("is_floorplan_window") else 'OBJECT_DATAMODE'
            layout.prop(obj, "name", text="", emboss=False, icon=icon)

# --- Panel ---

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

        # Show Transform properties of selected element
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

# --- Helper function to get floorplan elements ---

def get_floorplan_elements(scene):
    return [obj for obj in scene.objects if
            obj.get("is_floorplan_wall") or obj.get("is_floorplan_door") or obj.get("is_floorplan_window") or
            obj.name.startswith("Wall")]

# --- Update collection property ---

def update_floorplan_elements_collection(scene):
    coll = scene.floorplan_elements
    coll.clear()
    for obj in get_floorplan_elements(scene):
        item = coll.add()
        item.obj_ref = obj

def depsgraph_update(scene, depsgraph):
    update_floorplan_elements_collection(scene)

# --- Registration ---

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

def unregister():
    bpy.app.handlers.depsgraph_update_post.remove(depsgraph_update)
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
    del bpy.types.Scene.floorplan_elements
    del bpy.types.Scene.floorplan_elements_index
    del bpy.types.Scene.fp_wall_color

if __name__ == "__main__":
    register()
