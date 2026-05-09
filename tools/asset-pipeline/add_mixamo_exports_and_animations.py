"""Add Mixamo exports and default animation clips to the current assets.

Run this from Blender Python, either through the live Blender MCP bridge or a
background Blender process with BLENDER_PATH configured.
"""

from __future__ import annotations

import json
import math
import shutil
import zipfile
from pathlib import Path

import bpy
from mathutils import Vector


SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parents[1]

CHIBI_SLUG = "on_the_spectrum-painter-chibi"
FLOWER_SLUG = "flower"
CHIBI_CLIPS = ("Idle_Stationary", "Walk_InPlace")
FLOWER_CLIPS = ("Sway_Gentle",)
MIXAMO_FBX_AXIS_FORWARD = "Z"
MIXAMO_OBJ_FORWARD_AXIS = "Z"
MIXAMO_AXIS_UP = "Y"
MIXAMO_ORIENTATION_NOTE = (
    "Mixamo exports are front-corrected with a 180-degree forward-axis flip; "
    "the Blender source and web GLB keep the authored -Y front."
)


def ensure_dir(path: str | Path) -> None:
    Path(path).mkdir(parents=True, exist_ok=True)


def write_json(path: str | Path, data: dict) -> None:
    ensure_dir(Path(path).parent)
    Path(path).write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def relative(path: str | Path) -> str:
    return str(Path(path).relative_to(REPO_ROOT)).replace("\\", "/")


def paths_for(slug: str) -> dict[str, Path]:
    exports_dir = REPO_ROOT / "public" / "exports" / slug
    return {
        "blend": REPO_ROOT / "public" / "models" / f"{slug}.blend",
        "glb": REPO_ROOT / "public" / "models" / f"{slug}.glb",
        "metadata": REPO_ROOT / "public" / "models" / f"{slug}.metadata.json",
        "preview": REPO_ROOT / "public" / "renders" / f"{slug}-preview.png",
        "exports": exports_dir,
        "mixamo_fbx": exports_dir / f"{slug}-mixamo.fbx",
        "mixamo_obj_zip": exports_dir / f"{slug}-mixamo-obj.zip",
        "obj_work": exports_dir / "_obj_bundle",
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


def armature_objects() -> list[bpy.types.Object]:
    return [obj for obj in bpy.data.objects if obj.type == "ARMATURE"]


def scene_triangle_count(objects: list[bpy.types.Object] | None = None) -> int:
    depsgraph = bpy.context.evaluated_depsgraph_get()
    total = 0
    for obj in objects or geometry_objects():
        if obj.type not in {"MESH", "CURVE"}:
            continue
        evaluated = obj.evaluated_get(depsgraph)
        mesh = evaluated.to_mesh()
        if not mesh:
            continue
        try:
            total += sum(max(1, len(poly.vertices) - 2) for poly in mesh.polygons)
        finally:
            evaluated.to_mesh_clear()
    return total


def bounds_for_objects(objects: list[bpy.types.Object]) -> dict[str, list[float]] | None:
    geometries = [obj for obj in objects if obj.type in {"MESH", "CURVE"}]
    if not geometries:
        return None

    min_v = Vector((math.inf, math.inf, math.inf))
    max_v = Vector((-math.inf, -math.inf, -math.inf))
    for obj in geometries:
        for corner in obj.bound_box:
            world = obj.matrix_world @ Vector(corner)
            min_v.x = min(min_v.x, world.x)
            min_v.y = min(min_v.y, world.y)
            min_v.z = min(min_v.z, world.z)
            max_v.x = max(max_v.x, world.x)
            max_v.y = max(max_v.y, world.y)
            max_v.z = max(max_v.z, world.z)

    size = max_v - min_v
    center = (min_v + max_v) * 0.5
    return {
        "min": [round(value, 4) for value in min_v],
        "max": [round(value, 4) for value in max_v],
        "size": [round(value, 4) for value in size],
        "center": [round(value, 4) for value in center],
    }


def material_names(objects: list[bpy.types.Object]) -> list[str]:
    return sorted({slot.material.name for obj in objects for slot in obj.material_slots if slot.material})


def remove_actions(names: tuple[str, ...]) -> None:
    for action in list(bpy.data.actions):
        if action.name in names or any(action.name.startswith(f"{name}.") for name in names):
            bpy.data.actions.remove(action)


def clear_nla_tracks(obj: bpy.types.Object, names: tuple[str, ...]) -> None:
    if not obj.animation_data:
        return
    if obj.animation_data.action and obj.animation_data.action.name in names:
        obj.animation_data.action = None
    for track in list(obj.animation_data.nla_tracks):
        if track.name in names or any(track.name.startswith(f"{name}.") for name in names):
            obj.animation_data.nla_tracks.remove(track)


def reset_pose_bones(armature: bpy.types.Object, bone_names: set[str]) -> None:
    for bone_name in bone_names:
        bone = armature.pose.bones.get(bone_name)
        if not bone:
            continue
        bone.rotation_mode = "XYZ"
        bone.location = (0, 0, 0)
        bone.rotation_euler = (0, 0, 0)
        bone.scale = (1, 1, 1)


def apply_bone_transforms(armature: bpy.types.Object, transforms: dict[str, dict]) -> None:
    for bone_name, transform in transforms.items():
        bone = armature.pose.bones.get(bone_name)
        if not bone:
            continue
        bone.rotation_mode = "XYZ"
        if "location" in transform:
            bone.location = transform["location"]
        if "rotation" in transform:
            bone.rotation_euler = transform["rotation"]
        if "scale" in transform:
            bone.scale = transform["scale"]


def keyframe_pose_bones(armature: bpy.types.Object, bone_names: set[str], frame: int) -> None:
    for bone_name in bone_names:
        bone = armature.pose.bones.get(bone_name)
        if not bone:
            continue
        bone.keyframe_insert(data_path="location", frame=frame)
        bone.keyframe_insert(data_path="rotation_euler", frame=frame)
        bone.keyframe_insert(data_path="scale", frame=frame)


def polish_action_curves(action: bpy.types.Action) -> None:
    for curve in getattr(action, "fcurves", []):
        for keyframe in curve.keyframe_points:
            keyframe.interpolation = "BEZIER"


def create_pose_action(
    armature: bpy.types.Object,
    name: str,
    frames: list[tuple[int, dict[str, dict]]],
) -> bpy.types.Action:
    bone_names = {bone_name for _, transforms in frames for bone_name in transforms}
    action = bpy.data.actions.new(name)
    action.use_fake_user = True
    animation_data = armature.animation_data_create()
    animation_data.action = action

    for frame, transforms in frames:
        bpy.context.scene.frame_set(frame)
        reset_pose_bones(armature, bone_names)
        apply_bone_transforms(armature, transforms)
        keyframe_pose_bones(armature, bone_names, frame)

    polish_action_curves(action)
    animation_data.action = None
    reset_pose_bones(armature, bone_names)
    return action


def push_action_to_nla(obj: bpy.types.Object, action: bpy.types.Action, start: int, end: int) -> None:
    animation_data = obj.animation_data_create()
    track = animation_data.nla_tracks.new()
    track.name = action.name
    strip = track.strips.new(action.name, start, action)
    strip.name = action.name
    strip.frame_end = end


def chibi_idle_frames() -> list[tuple[int, dict[str, dict]]]:
    neutral: dict[str, dict] = {
        "pelvis": {"location": (0, 0, 0), "rotation": (0, 0, 0)},
        "spine": {"rotation": (0, 0, 0)},
        "head": {"rotation": (0, 0, 0)},
        "hair": {"rotation": (0, 0, 0)},
        "upper_arm.L": {"rotation": (0, 0, 0)},
        "upper_arm.R": {"rotation": (0, 0, 0)},
        "forearm.L": {"rotation": (0, 0, 0)},
        "forearm.R": {"rotation": (0, 0, 0)},
        "satchel": {"rotation": (0, 0, 0)},
        "stylus": {"rotation": (0, 0, 0)},
    }
    inhale = {
        "pelvis": {"location": (0, 0, 0.025), "rotation": (0.0, 0.0, -0.01)},
        "spine": {"rotation": (0.028, 0.0, 0.018)},
        "head": {"rotation": (-0.022, 0.0, -0.018)},
        "hair": {"rotation": (0.035, 0.0, 0.026)},
        "upper_arm.L": {"rotation": (0.03, 0.0, -0.035)},
        "upper_arm.R": {"rotation": (0.025, 0.0, 0.03)},
        "forearm.L": {"rotation": (-0.018, 0.0, 0.012)},
        "forearm.R": {"rotation": (-0.014, 0.0, -0.01)},
        "satchel": {"rotation": (0.0, 0.0, 0.024)},
        "stylus": {"rotation": (0.0, 0.0, -0.018)},
    }
    return [(1, neutral), (30, inhale), (60, neutral)]


def walk_pose(
    left_forward: bool,
    *,
    bob: float = 0.0,
    lean: float = 0.0,
) -> dict[str, dict]:
    leg = 1 if left_forward else -1
    return {
        "pelvis": {"location": (0, 0, bob), "rotation": (0.0, 0.0, 0.035 * leg)},
        "spine": {"rotation": (0.055 + lean, 0.0, -0.04 * leg)},
        "head": {"rotation": (-0.035 - lean, 0.0, 0.025 * leg)},
        "upper_arm.L": {"rotation": (-0.5 * leg, 0.0, 0.05)},
        "forearm.L": {"rotation": (-0.18 * leg, 0.0, -0.04)},
        "upper_arm.R": {"rotation": (0.5 * leg, 0.0, -0.05)},
        "forearm.R": {"rotation": (0.18 * leg, 0.0, 0.04)},
        "thigh.L": {"rotation": (0.46 * leg, 0.0, 0.02)},
        "shin.L": {"rotation": (-0.28 if left_forward else 0.36, 0.0, 0.0)},
        "foot.L": {"rotation": (-0.18 if left_forward else 0.14, 0.0, 0.0)},
        "thigh.R": {"rotation": (-0.46 * leg, 0.0, -0.02)},
        "shin.R": {"rotation": (0.36 if left_forward else -0.28, 0.0, 0.0)},
        "foot.R": {"rotation": (0.14 if left_forward else -0.18, 0.0, 0.0)},
        "satchel": {"rotation": (0.0, 0.0, -0.08 * leg)},
        "stylus": {"rotation": (0.04 * leg, 0.0, 0.05 * leg)},
        "hair": {"rotation": (0.06, 0.0, 0.05 * leg)},
    }


def chibi_walk_frames() -> list[tuple[int, dict[str, dict]]]:
    passing = {
        "pelvis": {"location": (0, 0, 0.04), "rotation": (0, 0, 0)},
        "spine": {"rotation": (0.035, 0, 0)},
        "head": {"rotation": (-0.025, 0, 0)},
        "upper_arm.L": {"rotation": (0, 0, 0.035)},
        "forearm.L": {"rotation": (0, 0, 0)},
        "upper_arm.R": {"rotation": (0, 0, -0.035)},
        "forearm.R": {"rotation": (0, 0, 0)},
        "thigh.L": {"rotation": (0, 0, 0)},
        "shin.L": {"rotation": (0.18, 0, 0)},
        "foot.L": {"rotation": (0, 0, 0)},
        "thigh.R": {"rotation": (0, 0, 0)},
        "shin.R": {"rotation": (0.18, 0, 0)},
        "foot.R": {"rotation": (0, 0, 0)},
        "satchel": {"rotation": (0, 0, 0)},
        "stylus": {"rotation": (0, 0, 0)},
        "hair": {"rotation": (0.035, 0, 0)},
    }
    return [
        (1, walk_pose(True, bob=0.0, lean=0.012)),
        (9, passing),
        (17, walk_pose(False, bob=0.0, lean=0.012)),
        (25, passing),
        (33, walk_pose(True, bob=0.0, lean=0.012)),
    ]


def add_chibi_actions(armature: bpy.types.Object) -> None:
    clear_nla_tracks(armature, CHIBI_CLIPS)
    remove_actions(CHIBI_CLIPS)
    idle = create_pose_action(armature, "Idle_Stationary", chibi_idle_frames())
    walk = create_pose_action(armature, "Walk_InPlace", chibi_walk_frames())
    push_action_to_nla(armature, idle, 1, 60)
    push_action_to_nla(armature, walk, 1, 33)


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


def is_mixamo_excluded(obj: bpy.types.Object) -> bool:
    name = obj.name.lower()
    return (
        name.startswith("base_")
        or "display_base" in name
        or "displaydisc" in name
        or "contactshadow" in name
        or "contact_shadow" in name
    )


def mixamo_objects() -> list[bpy.types.Object]:
    armatures = armature_objects()
    meshes = [obj for obj in mesh_objects() if not is_mixamo_excluded(obj)]
    return armatures + meshes


def export_mixamo_fbx(path: Path, objects: list[bpy.types.Object]) -> None:
    ensure_dir(path.parent)
    select_objects(objects)
    run_operator(
        bpy.ops.export_scene.fbx,
        filepath=str(path),
        use_selection=True,
        object_types={"ARMATURE", "MESH"},
        add_leaf_bones=False,
        use_armature_deform_only=True,
        bake_anim=False,
        embed_textures=True,
        path_mode="COPY",
        axis_forward=MIXAMO_FBX_AXIS_FORWARD,
        axis_up=MIXAMO_AXIS_UP,
        apply_unit_scale=True,
        use_mesh_modifiers=True,
        mesh_smooth_type="FACE",
    )


def export_mixamo_obj_zip(zip_path: Path, work_dir: Path, objects: list[bpy.types.Object]) -> None:
    if work_dir.exists():
        shutil.rmtree(work_dir)
    ensure_dir(work_dir)
    ensure_dir(zip_path.parent)
    obj_path = work_dir / f"{CHIBI_SLUG}-mixamo.obj"

    select_objects([obj for obj in objects if obj.type == "MESH"])
    run_operator(
        bpy.ops.wm.obj_export,
        filepath=str(obj_path),
        export_selected_objects=True,
        export_materials=True,
        export_uv=True,
        export_normals=True,
        apply_modifiers=True,
        path_mode="COPY",
        forward_axis=MIXAMO_OBJ_FORWARD_AXIS,
        up_axis=MIXAMO_AXIS_UP,
    )

    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as bundle:
        for exported in sorted(work_dir.rglob("*")):
            if exported.is_file():
                bundle.write(exported, exported.relative_to(work_dir))
    shutil.rmtree(work_dir)


def exportable_web_objects() -> list[bpy.types.Object]:
    return armature_objects() + geometry_objects() + [obj for obj in bpy.data.objects if obj.type == "EMPTY" and obj.animation_data]


def clean_flower_sway_root(root: bpy.types.Object) -> None:
    existing = bpy.data.objects.get("ANIM_Flower_SwayRoot")
    if not existing:
        return
    for child in list(existing.children):
        world = child.matrix_world.copy()
        child.parent = root
        child.matrix_world = world
    bpy.data.objects.remove(existing, do_unlink=True)


def add_flower_sway_action() -> bpy.types.Object:
    root = bpy.data.objects.get("flower_model_root")
    if not root:
        root = bpy.data.objects.new("flower_model_root", None)
        bpy.context.scene.collection.objects.link(root)

    clean_flower_sway_root(root)
    remove_actions(FLOWER_CLIPS)

    sway_root = bpy.data.objects.new("ANIM_Flower_SwayRoot", None)
    bpy.context.scene.collection.objects.link(sway_root)
    sway_root.empty_display_type = "PLAIN_AXES"
    sway_root.empty_display_size = 0.35
    sway_root.parent = root

    for child in list(root.children):
        if child == sway_root or child.type not in {"MESH", "CURVE"} or child.name.lower() == "thin_display_base":
            continue
        world = child.matrix_world.copy()
        child.parent = sway_root
        child.matrix_world = world

    action = bpy.data.actions.new("Sway_Gentle")
    action.use_fake_user = True
    animation_data = sway_root.animation_data_create()
    animation_data.action = action

    for frame, angle, lift in [(1, 0.0, 0.0), (30, 0.075, 0.012), (60, -0.065, 0.008), (90, 0.0, 0.0)]:
        bpy.context.scene.frame_set(frame)
        sway_root.rotation_mode = "XYZ"
        sway_root.rotation_euler = (math.radians(1.2), math.radians(0.8), angle)
        sway_root.location = (0.018 * math.sin(frame / 90 * math.tau), 0, lift)
        sway_root.keyframe_insert(data_path="location", frame=frame)
        sway_root.keyframe_insert(data_path="rotation_euler", frame=frame)

    polish_action_curves(action)
    animation_data.action = None
    push_action_to_nla(sway_root, action, 1, 90)
    bpy.context.scene.frame_set(1)
    sway_root.location = (0, 0, 0)
    sway_root.rotation_euler = (0, 0, 0)
    return sway_root


def file_size(path: Path) -> int:
    return path.stat().st_size if path.exists() else 0


def collect_metadata(slug: str, asset_name: str, extra_paths: dict[str, Path] | None = None) -> dict:
    paths = paths_for(slug)
    meshes = mesh_objects()
    geometries = geometry_objects()
    armatures = armature_objects()
    actions = sorted(action.name for action in bpy.data.actions)
    data = {
        "asset": asset_name,
        "slug": slug,
        "generator": Path(__file__).name,
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
            "bones": sum(len(arm.data.bones) for arm in armatures),
            "animations": len(actions),
        },
        "materials": material_names(geometries),
        "animations": {
            "clips": actions,
            "default": actions[0] if actions else None,
            "embedded_in_glb": True,
        },
        "bounds": bounds_for_objects(geometries),
        "budgets": {
            "triangle_warning": 100000,
            "glb_size_warning_bytes": 12 * 1024 * 1024,
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
        "notes": [],
    }
    if armatures:
        data["armature"] = {
            "objects": [arm.name for arm in armatures],
            "bones": sorted({bone.name for arm in armatures for bone in arm.data.bones}),
        }
    if extra_paths:
        data["exports"] = {key: relative(value) for key, value in extra_paths.items()}
        data["file_sizes"].update({f"{key}_bytes": file_size(value) for key, value in extra_paths.items()})
    return data


def process_chibi() -> dict:
    paths = paths_for(CHIBI_SLUG)
    ensure_dir(paths["exports"])
    bpy.ops.wm.open_mainfile(filepath=str(paths["blend"]))
    armatures = armature_objects()
    if not armatures:
        raise RuntimeError("OnTheSpectrum Painter Chibi blend does not contain an armature.")

    armature = bpy.data.objects.get("RIG_OnTheSpectrumPainter_BasicArmature") or armatures[0]
    add_chibi_actions(armature)
    bpy.ops.wm.save_as_mainfile(filepath=str(paths["blend"]))
    export_glb(paths["glb"], armature_objects() + mesh_objects())
    mixamo = mixamo_objects()
    export_mixamo_fbx(paths["mixamo_fbx"], mixamo)
    export_mixamo_obj_zip(paths["mixamo_obj_zip"], paths["obj_work"], mixamo)

    metadata = collect_metadata(
        CHIBI_SLUG,
        "OnTheSpectrum Painter Chibi",
        {
            "mixamo_fbx": paths["mixamo_fbx"],
            "mixamo_obj_zip": paths["mixamo_obj_zip"],
        },
    )
    metadata["animations"]["default"] = "Idle_Stationary"
    metadata["notes"] = [
        "Default clips are embedded in the web GLB: Idle_Stationary and Walk_InPlace.",
        "Mixamo FBX is a best-effort upload file using the current stylized rig.",
        MIXAMO_ORIENTATION_NOTE,
        "Display base and contact-shadow extras are excluded from Mixamo exports.",
    ]
    write_json(paths["metadata"], metadata)
    return metadata


def process_flower() -> dict:
    paths = paths_for(FLOWER_SLUG)
    bpy.ops.wm.open_mainfile(filepath=str(paths["blend"]))
    add_flower_sway_action()
    bpy.ops.wm.save_as_mainfile(filepath=str(paths["blend"]))
    export_glb(paths["glb"], exportable_web_objects())

    metadata = collect_metadata(FLOWER_SLUG, "Blender MCP Flower")
    metadata["animations"]["default"] = "Sway_Gentle"
    metadata["notes"] = [
        "Flower sway is embedded as a non-Mixamo transform animation.",
        "Mixamo exports are intentionally omitted because Mixamo auto-rigging is humanoid-only.",
    ]
    write_json(paths["metadata"], metadata)
    return metadata


def main() -> dict:
    return {
        "chibi": process_chibi(),
        "flower": process_flower(),
    }


if __name__ == "__main__":
    print(json.dumps(main(), indent=2))
