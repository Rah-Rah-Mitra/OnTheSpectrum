"""Generate a standard animated tree asset in Blender.

Run from Blender Python through the live MCP bridge. The script is repeatable:
it creates the source scene, exports an animated GLB, renders a preview, and
writes metadata for the Artomata viewer.
"""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import bpy

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from blender_common import (  # noqa: E402
    add_bevel,
    add_weighted_normals,
    bevel_curve,
    bounds_for_objects,
    clear_scene,
    collection,
    cone,
    cylinder,
    ensure_dir,
    look_at,
    make_mat,
    scene_triangle_count,
    uv_sphere,
    write_json,
)

ASSET_SLUG = "tree"
ASSET_NAME = "Tree"
SWAY_CLIP = "Sway_Gentle"

ASSET_SPEC = {
    "slug": ASSET_SLUG,
    "asset_family": "Botanical",
    "subject": "Standard deciduous tree",
    "visual_style": "Clean procedural studio tree with softened bark detail and layered leaf masses",
    "required_parts": [
        "tapered trunk",
        "root flare",
        "main branches",
        "layered canopy clusters",
        "bark grooves",
        "leaf highlights",
        "soft contact shadow",
    ],
    "material_palette": [
        "warm brown bark",
        "dark bark grooves",
        "deep green leaves",
        "mid-green leaves",
        "light green leaf highlights",
        "soft translucent contact shadow",
    ],
    "rig_target": "simple transform rig",
    "animation_clips": [SWAY_CLIP],
    "viewer_framing": "floor-aligned front-quarter full-tree view centered on trunk and canopy",
}


def repo_root() -> Path:
    return SCRIPT_DIR.parents[1]


def relative(path: str | Path) -> str:
    return str(Path(path).relative_to(repo_root())).replace("\\", "/")


def out_paths() -> dict[str, Path]:
    root = repo_root()
    return {
        "blend": root / "public" / "models" / f"{ASSET_SLUG}.blend",
        "glb": root / "public" / "models" / f"{ASSET_SLUG}.glb",
        "preview": root / "public" / "renders" / f"{ASSET_SLUG}-preview.png",
        "metadata": root / "public" / "models" / f"{ASSET_SLUG}.metadata.json",
        "textures": root / "public" / "textures" / ASSET_SLUG,
    }


def make_materials() -> dict[str, bpy.types.Material]:
    return {
        "bark": make_mat("MAT_Tree_WarmBrownBark", (0.46, 0.255, 0.125, 1), roughness=0.82),
        "bark_dark": make_mat("MAT_Tree_DarkBarkGrooves", (0.19, 0.105, 0.052, 1), roughness=0.88),
        "bark_light": make_mat("MAT_Tree_SoftBarkRidges", (0.62, 0.37, 0.18, 1), roughness=0.78),
        "leaf_deep": make_mat("MAT_Tree_DeepGreenLeaves", (0.055, 0.23, 0.095, 1), roughness=0.8),
        "leaf_mid": make_mat("MAT_Tree_MidGreenLeaves", (0.12, 0.39, 0.14, 1), roughness=0.78),
        "leaf_light": make_mat("MAT_Tree_LightLeafHighlights", (0.48, 0.69, 0.23, 1), roughness=0.75),
        "shadow": make_mat("MAT_Shadow_BakedSoftContact", (0.018, 0.02, 0.016, 0.5), roughness=0.92, alpha=0.5),
    }


def operator_kwargs(operator, kwargs: dict) -> dict:
    accepted = {prop.identifier for prop in operator.get_rna_type().properties if not prop.is_readonly}
    return {key: value for key, value in kwargs.items() if key in accepted}


def run_operator(operator, **kwargs):
    return operator(**operator_kwargs(operator, kwargs))


def select_objects(objects: list[bpy.types.Object]) -> None:
    bpy.ops.object.select_all(action="DESELECT")
    for obj in objects:
        obj.select_set(True)
    bpy.context.view_layer.objects.active = objects[0] if objects else None


def mesh_objects() -> list[bpy.types.Object]:
    return [obj for obj in bpy.data.objects if obj.type == "MESH"]


def geometry_objects() -> list[bpy.types.Object]:
    return [obj for obj in bpy.data.objects if obj.type in {"MESH", "CURVE"}]


def exportable_web_objects() -> list[bpy.types.Object]:
    return [obj for obj in bpy.data.objects if obj.type in {"MESH", "CURVE"} or (obj.type == "EMPTY" and obj.animation_data)]


def material_names(objects: list[bpy.types.Object]) -> list[str]:
    return sorted({slot.material.name for obj in objects for slot in obj.material_slots if slot.material})


def clear_animation_data() -> None:
    for obj in bpy.data.objects:
        obj.animation_data_clear()
    for action in list(bpy.data.actions):
        bpy.data.actions.remove(action)


def parent_keep_world(child: bpy.types.Object, parent: bpy.types.Object) -> None:
    world = child.matrix_world.copy()
    child.parent = parent
    child.matrix_world = world


def make_empty(name: str, loc: tuple[float, float, float], *, collection_name: str = "RIG") -> bpy.types.Object:
    empty = bpy.data.objects.new(name, None)
    bpy.context.scene.collection.objects.link(empty)
    empty.empty_display_type = "PLAIN_AXES"
    empty.empty_display_size = 0.35
    empty.location = loc
    collection(collection_name).objects.link(empty)
    for source in list(empty.users_collection):
        if source.name != collection_name:
            source.objects.unlink(empty)
    return empty


def build_trunk_and_roots(
    mats: dict[str, bpy.types.Material],
    root: bpy.types.Object,
    sway_root: bpy.types.Object,
) -> tuple[list[bpy.types.Object], list[bpy.types.Object]]:
    stable: list[bpy.types.Object] = []
    swaying: list[bpy.types.Object] = []

    lower = cone(
        "PROP_Tree_LowerTrunk_TaperedBark",
        (0, 0, 0.48),
        0.19,
        0.135,
        0.96,
        mats["bark"],
        vertices=28,
        collection_name="PROPS",
    )
    add_bevel(lower, 0.01, 2, apply=True)
    add_weighted_normals(lower)
    stable.append(lower)

    upper = cone(
        "PROP_Tree_UpperTrunk_SwayingBark",
        (0.018, 0, 1.32),
        0.12,
        0.07,
        0.92,
        mats["bark"],
        vertices=28,
        collection_name="PROPS",
    )
    add_bevel(upper, 0.008, 2, apply=True)
    add_weighted_normals(upper)
    swaying.append(upper)

    root_specs = [
        ("Front", [(0, -0.055, 0.095), (0.16, -0.27, 0.04), (0.36, -0.47, 0.025)], 0.032),
        ("Back", [(0, 0.055, 0.09), (-0.12, 0.25, 0.042), (-0.31, 0.43, 0.026)], 0.029),
        ("Left", [(-0.08, 0.015, 0.085), (-0.28, -0.08, 0.038), (-0.48, -0.19, 0.024)], 0.027),
        ("Right", [(0.08, 0.015, 0.085), (0.27, 0.12, 0.04), (0.48, 0.2, 0.024)], 0.027),
    ]
    for side, points, depth in root_specs:
        stable.append(
            bevel_curve(
                f"PROP_Tree_RootFlare_{side}",
                points,
                mats["bark"],
                bevel_depth=depth,
                bevel_resolution=4,
                collection_name="PROPS",
            ),
        )

    groove_specs = [
        ("A", [(-0.055, -0.128, 0.14), (-0.035, -0.142, 0.42), (-0.055, -0.11, 0.86)], 0.0045, False),
        ("B", [(0.06, -0.12, 0.16), (0.08, -0.105, 0.5), (0.045, -0.09, 0.93)], 0.004, False),
        ("C", [(-0.12, 0.02, 0.18), (-0.115, 0.035, 0.52), (-0.075, 0.035, 0.94)], 0.0038, False),
        ("D", [(0.105, 0.04, 0.16), (0.09, 0.055, 0.48), (0.12, 0.035, 0.86)], 0.0038, False),
        ("UpperA", [(-0.03, -0.082, 0.92), (-0.055, -0.09, 1.24), (-0.03, -0.072, 1.69)], 0.0035, True),
        ("UpperB", [(0.055, 0.04, 0.94), (0.065, 0.055, 1.25), (0.04, 0.045, 1.68)], 0.0035, True),
    ]
    for name, points, depth, should_sway in groove_specs:
        groove = bevel_curve(
            f"PROP_Tree_BarkGroove_{name}",
            points,
            mats["bark_dark"],
            bevel_depth=depth,
            bevel_resolution=1,
            collection_name="PROPS",
        )
        (swaying if should_sway else stable).append(groove)

    ridge_specs = [
        ("LowerHighlight", [(0.025, -0.155, 0.22), (0.015, -0.14, 0.56), (0.035, -0.112, 0.88)], 0.0028, False),
        ("UpperHighlight", [(-0.018, -0.088, 1.0), (-0.006, -0.08, 1.33), (0.025, -0.06, 1.68)], 0.0024, True),
    ]
    for name, points, depth, should_sway in ridge_specs:
        ridge = bevel_curve(
            f"PROP_Tree_BarkRidge_{name}",
            points,
            mats["bark_light"],
            bevel_depth=depth,
            bevel_resolution=1,
            collection_name="PROPS",
        )
        (swaying if should_sway else stable).append(ridge)

    shadow = cylinder(
        "BASE_BakedSoftContactShadow",
        (0.025, -0.01, 0.004),
        0.52,
        0.008,
        mats["shadow"],
        vertices=72,
        scale=(1.25, 0.88, 1),
        collection_name="BAKED_EFFECTS",
    )
    stable.append(shadow)

    for obj in stable:
        parent_keep_world(obj, root)
    for obj in swaying:
        parent_keep_world(obj, sway_root)

    return stable, swaying


def build_branches_and_canopy(
    mats: dict[str, bpy.types.Material],
    sway_root: bpy.types.Object,
) -> list[bpy.types.Object]:
    objects: list[bpy.types.Object] = []

    branch_specs = [
        ("LeftLow", [(0.01, -0.01, 1.1), (-0.34, -0.08, 1.58), (-0.72, -0.18, 1.95)], 0.04),
        ("RightLow", [(0.03, 0.02, 1.18), (0.36, 0.16, 1.6), (0.73, 0.25, 1.9)], 0.038),
        ("RearLift", [(-0.02, 0.02, 1.28), (-0.16, 0.42, 1.72), (-0.42, 0.67, 2.04)], 0.032),
        ("FrontLift", [(0.02, -0.03, 1.32), (0.18, -0.38, 1.76), (0.38, -0.66, 2.1)], 0.032),
        ("TopForkL", [(0.01, 0.0, 1.68), (-0.18, -0.08, 2.0), (-0.35, -0.02, 2.35)], 0.026),
        ("TopForkR", [(0.02, 0.0, 1.68), (0.22, 0.08, 2.02), (0.38, 0.0, 2.35)], 0.026),
    ]
    for name, points, depth in branch_specs:
        branch = bevel_curve(
            f"PROP_Tree_MainBranch_{name}",
            points,
            mats["bark"],
            bevel_depth=depth,
            bevel_resolution=4,
            collection_name="PROPS",
        )
        objects.append(branch)

    canopy_specs = [
        ("Core", (0.02, 0.0, 2.38), (0.68, 0.58, 0.54), "leaf_mid"),
        ("Left", (-0.48, -0.08, 2.15), (0.48, 0.43, 0.4), "leaf_deep"),
        ("Right", (0.48, 0.12, 2.14), (0.5, 0.44, 0.42), "leaf_deep"),
        ("Rear", (-0.12, 0.42, 2.2), (0.5, 0.38, 0.42), "leaf_mid"),
        ("Front", (0.16, -0.44, 2.18), (0.48, 0.38, 0.4), "leaf_mid"),
        ("Crown", (0.03, 0.02, 2.72), (0.46, 0.4, 0.36), "leaf_light"),
        ("LeftCrown", (-0.32, 0.16, 2.56), (0.36, 0.32, 0.3), "leaf_mid"),
        ("RightCrown", (0.36, -0.04, 2.54), (0.36, 0.31, 0.3), "leaf_mid"),
        ("LowFront", (-0.1, -0.36, 1.92), (0.34, 0.28, 0.27), "leaf_deep"),
        ("LowBack", (0.15, 0.38, 1.94), (0.33, 0.28, 0.27), "leaf_deep"),
    ]
    for name, loc, scale, mat_key in canopy_specs:
        cluster = uv_sphere(
            f"PROP_Tree_CanopyCluster_{name}",
            loc,
            scale,
            mats[mat_key],
            segments=24,
            rings=12,
            collection_name="PROPS",
        )
        objects.append(cluster)

    highlight_specs = [
        ("A", (-0.28, -0.41, 2.31), (0.13, 0.035, 0.075), (0, 0.25, -0.35)),
        ("B", (0.27, -0.35, 2.45), (0.15, 0.035, 0.08), (0.08, -0.18, 0.28)),
        ("C", (0.2, 0.2, 2.73), (0.12, 0.03, 0.065), (-0.12, 0.1, -0.15)),
        ("D", (-0.45, 0.08, 2.38), (0.11, 0.03, 0.06), (0.06, 0.1, 0.4)),
        ("E", (0.52, 0.12, 2.18), (0.12, 0.032, 0.065), (0.02, -0.1, -0.3)),
        ("F", (-0.06, -0.58, 2.08), (0.1, 0.03, 0.055), (0.0, 0.18, 0.18)),
    ]
    for name, loc, scale, rotation in highlight_specs:
        leaf = uv_sphere(
            f"PROP_Tree_LeafHighlight_{name}",
            loc,
            scale,
            mats["leaf_light"],
            segments=12,
            rings=6,
            collection_name="PROPS",
        )
        leaf.rotation_euler = rotation
        objects.append(leaf)

    for obj in objects:
        parent_keep_world(obj, sway_root)
    return objects


def create_sway_action(sway_root: bpy.types.Object) -> bpy.types.Action:
    action = bpy.data.actions.new(SWAY_CLIP)
    action.use_fake_user = True
    animation_data = sway_root.animation_data_create()
    animation_data.action = action
    sway_root.rotation_mode = "XYZ"

    pivot = tuple(sway_root.location)
    frames = [
        (1, (0, 0, 0), pivot),
        (28, (0.012, -0.02, 0.052), (pivot[0] + 0.018, pivot[1] - 0.01, pivot[2] + 0.014)),
        (56, (-0.008, 0.024, -0.046), (pivot[0] - 0.014, pivot[1] + 0.012, pivot[2] + 0.01)),
        (84, (0, 0, 0), pivot),
    ]
    for frame, rotation, location in frames:
        bpy.context.scene.frame_set(frame)
        sway_root.rotation_euler = rotation
        sway_root.location = location
        sway_root.keyframe_insert(data_path="location", frame=frame)
        sway_root.keyframe_insert(data_path="rotation_euler", frame=frame)

    for curve in getattr(action, "fcurves", []):
        for keyframe in curve.keyframe_points:
            keyframe.interpolation = "BEZIER"

    animation_data.action = None
    track = animation_data.nla_tracks.new()
    track.name = SWAY_CLIP
    strip = track.strips.new(SWAY_CLIP, 1, action)
    strip.name = SWAY_CLIP
    strip.frame_end = 84

    bpy.context.scene.frame_set(1)
    sway_root.location = pivot
    sway_root.rotation_euler = (0, 0, 0)
    return action


def build_tree(mats: dict[str, bpy.types.Material]) -> dict[str, bpy.types.Object | list[bpy.types.Object]]:
    for name in ["RIG", "PROPS", "BAKED_EFFECTS", "LIGHTING_CAMERA"]:
        collection(name)

    root = make_empty("tree_model_root", (0, 0, 0), collection_name="RIG")
    sway_root = make_empty("ANIM_Tree_SwayRoot", (0, 0, 0.58), collection_name="RIG")
    sway_root.parent = root

    stable, trunk_swaying = build_trunk_and_roots(mats, root, sway_root)
    canopy_swaying = build_branches_and_canopy(mats, sway_root)
    create_sway_action(sway_root)
    return {
        "root": root,
        "sway_root": sway_root,
        "stable": stable,
        "swaying": trunk_swaying + canopy_swaying,
    }


def setup_lighting_and_camera() -> None:
    world = bpy.context.scene.world or bpy.data.worlds.new("World")
    bpy.context.scene.world = world
    world.color = (0.025, 0.031, 0.027)

    camera_data = bpy.data.cameras.new("CAM_Tree_Preview")
    camera = bpy.data.objects.new("CAM_Tree_Preview", camera_data)
    bpy.context.scene.collection.objects.link(camera)
    camera.location = (2.55, -5.85, 2.35)
    camera.data.lens = 48
    camera.data.dof.use_dof = True
    camera.data.dof.focus_distance = 6.4
    camera.data.dof.aperture_fstop = 7.5
    look_at(camera, (0, 0, 1.48))
    bpy.context.scene.camera = camera
    for source in list(camera.users_collection):
        source.objects.unlink(camera)
    collection("LIGHTING_CAMERA").objects.link(camera)

    lights = [
        ("LGT_Key_TreeSoftbox", "AREA", (-2.8, -3.2, 4.2), 470, 3.8),
        ("LGT_Rim_TreeLeafEdge", "AREA", (2.8, 1.9, 3.1), 170, 2.2),
        ("LGT_Fill_TreeStudio", "POINT", (1.4, -2.0, 2.0), 70, 0),
    ]
    for name, kind, loc, energy, size in lights:
        data = bpy.data.lights.new(name, kind)
        obj = bpy.data.objects.new(name, data)
        bpy.context.scene.collection.objects.link(obj)
        obj.location = loc
        data.energy = energy
        if hasattr(data, "size") and size:
            data.size = size
        look_at(obj, (0, 0, 1.45))
        for source in list(obj.users_collection):
            source.objects.unlink(obj)
        collection("LIGHTING_CAMERA").objects.link(obj)


def configure_scene() -> None:
    scene = bpy.context.scene
    scene.name = "SCN_StandardTree"
    scene.unit_settings.system = "METRIC"
    scene.frame_start = 1
    scene.frame_end = 84
    scene.render.resolution_x = 1600
    scene.render.resolution_y = 1600
    scene.render.film_transparent = False
    scene.view_settings.view_transform = "Filmic"
    scene.view_settings.look = "Medium High Contrast"
    scene.view_settings.exposure = 0
    scene.view_settings.gamma = 1
    try:
        scene.render.engine = "BLENDER_EEVEE_NEXT"
    except TypeError:
        scene.render.engine = "BLENDER_EEVEE"
    if hasattr(scene, "eevee"):
        scene.eevee.taa_render_samples = 64


def file_size(path: Path) -> int:
    return path.stat().st_size if path.exists() else 0


def export_glb(path: Path, objects: list[bpy.types.Object]) -> None:
    ensure_dir(path.parent)
    select_objects(objects)
    run_operator(
        bpy.ops.export_scene.gltf,
        filepath=str(path),
        export_format="GLB",
        use_selection=True,
        export_yup=True,
        export_apply=True,
        export_animations=True,
        export_animation_mode="ACTIONS",
        export_nla_strips=True,
        export_lights=False,
        export_cameras=False,
        export_materials="EXPORT",
        export_force_sampling=True,
    )


def export_asset(paths: dict[str, Path]) -> None:
    ensure_dir(paths["blend"].parent)
    ensure_dir(paths["glb"].parent)
    ensure_dir(paths["preview"].parent)
    ensure_dir(paths["textures"])

    for block in (bpy.data.materials, bpy.data.curves, bpy.data.images):
        for item in list(block):
            if item.users == 0:
                block.remove(item)

    bpy.ops.wm.save_as_mainfile(filepath=str(paths["blend"]))
    export_glb(paths["glb"], exportable_web_objects())

    bpy.context.scene.frame_set(24)
    bpy.context.scene.render.filepath = str(paths["preview"])
    bpy.ops.render.render(write_still=True)
    bpy.context.scene.frame_set(1)


def collect_metadata(paths: dict[str, Path]) -> dict:
    meshes = mesh_objects()
    geometries = geometry_objects()
    actions = sorted(action.name for action in bpy.data.actions)
    return {
        "asset": ASSET_NAME,
        "slug": ASSET_SLUG,
        "generator": Path(__file__).name,
        "spec": ASSET_SPEC,
        "paths": {
            "blend": relative(paths["blend"]),
            "glb": relative(paths["glb"]),
            "preview": relative(paths["preview"]),
            "metadata": relative(paths["metadata"]),
        },
        "counts": {
            "objects": len(bpy.data.objects),
            "mesh_objects": len(meshes),
            "geometry_objects": len(geometries),
            "materials": len(material_names(geometries)),
            "triangles": scene_triangle_count(geometries),
            "bones": 0,
            "animations": len(actions),
        },
        "materials": material_names(geometries),
        "animations": {
            "clips": actions,
            "default": SWAY_CLIP,
            "embedded_in_glb": True,
        },
        "rig": {
            "type": "simple transform rig",
            "root": "tree_model_root",
            "animated_control": "ANIM_Tree_SwayRoot",
            "stable_parts": ["root flare", "lower trunk", "contact shadow"],
            "animated_parts": ["upper trunk", "branches", "canopy clusters", "leaf highlights"],
        },
        "bounds": bounds_for_objects(geometries),
        "budgets": {
            "triangle_warning": 100000,
            "glb_size_warning_bytes": 12 * 1024 * 1024,
            "material_warning": 16,
        },
        "file_sizes": {
            "blend_bytes": file_size(paths["blend"]),
            "glb_bytes": file_size(paths["glb"]),
            "preview_bytes": file_size(paths["preview"]),
        },
        "export": {
            "format": "GLB",
            "export_yup": True,
            "applied_export_transforms": True,
            "animations": True,
            "source": "Blender MCP live bridge",
        },
        "notes": [
            "Standard deciduous tree generated procedurally in Blender.",
            "Tree sway is embedded as a non-Mixamo transform animation on ANIM_Tree_SwayRoot.",
            "Mixamo exports are intentionally omitted because this is a non-humanoid botanical asset.",
            "Chosen palette: warm brown bark, dark grooves, layered green leaves, light leaf highlights, and soft contact shadow.",
        ],
    }


def main() -> dict:
    paths = out_paths()
    if bpy.context.object and bpy.context.object.mode != "OBJECT":
        bpy.ops.object.mode_set(mode="OBJECT")
    clear_scene()
    clear_animation_data()
    configure_scene()
    mats = make_materials()
    build_tree(mats)
    setup_lighting_and_camera()
    export_asset(paths)
    metadata = collect_metadata(paths)
    write_json(paths["metadata"], metadata)
    return metadata


if __name__ == "__main__":
    result = main()
    print(json.dumps(result, indent=2))
