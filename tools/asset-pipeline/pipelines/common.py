"""Shared Blender helpers for generated OnTheSpectrum asset pipelines."""

from __future__ import annotations

import json
import math
import shutil
import sys
import zipfile
from pathlib import Path

import bpy

PIPELINE_DIR = Path(__file__).resolve().parent
SCRIPT_DIR = PIPELINE_DIR.parent
REPO_ROOT = SCRIPT_DIR.parents[1]
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from blender_common import (  # noqa: E402
    assign_mat,
    bevel_curve,
    bounds_for_objects,
    clear_scene,
    collection,
    cube,
    cylinder,
    ensure_dir,
    link_to_collection,
    look_at,
    make_mat,
    scene_triangle_count,
    shade_smooth,
    uv_sphere,
    write_json,
)

DEFAULT_BUDGET = {
    "maxTriangles": 100000,
    "maxMaterials": 16,
    "maxGlbMb": 12,
    "approvedOverBudget": False,
}

DEFAULT_STYLE_COLORS = {
    "primary": "#5f95b8",
    "secondary": "#d96f52",
    "accent": "#2ed7e6",
    "neutral": "#22272b",
    "emission": "#45f0ff",
}


def relative(path: str | Path) -> str:
    return str(Path(path).relative_to(REPO_ROOT)).replace("\\", "/")


def out_paths(spec: dict) -> dict[str, Path]:
    slug = spec["slug"]
    exports = REPO_ROOT / "public" / "exports" / slug
    return {
        "blend": REPO_ROOT / "public" / "models" / f"{slug}.blend",
        "glb": REPO_ROOT / "public" / "models" / f"{slug}.glb",
        "preview": REPO_ROOT / "public" / "renders" / f"{slug}-preview.png",
        "metadata": REPO_ROOT / "public" / "models" / f"{slug}.metadata.json",
        "textures": REPO_ROOT / "public" / "textures" / slug,
        "exports": exports,
        "mixamo_fbx": exports / f"{slug}-mixamo.fbx",
        "mixamo_obj_zip": exports / f"{slug}-mixamo-obj.zip",
        "obj_work": exports / "_obj_bundle",
    }


def display_family(spec: dict) -> str:
    family = spec.get("assetFamily", "prop")
    if family == "vfx":
        return "VFX"
    if family == "plant":
        return "Botanical"
    return family[:1].upper() + family[1:]


def hex_to_rgba(value: str | None, fallback: str = "#ffffff", alpha: float = 1.0) -> tuple[float, float, float, float]:
    token = value if isinstance(value, str) and len(value) == 7 and value.startswith("#") else fallback
    try:
        red = int(token[1:3], 16) / 255
        green = int(token[3:5], 16) / 255
        blue = int(token[5:7], 16) / 255
    except ValueError:
        return hex_to_rgba(fallback, "#ffffff", alpha)
    return (red, green, blue, alpha)


def style_colors(spec: dict) -> dict[str, str]:
    colors = ((spec.get("styleConfig") or {}).get("colors") or {}) if isinstance(spec.get("styleConfig"), dict) else {}
    return {key: colors.get(key) or fallback for key, fallback in DEFAULT_STYLE_COLORS.items()}


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


def material_names(objects: list[bpy.types.Object]) -> list[str]:
    return sorted({slot.material.name for obj in objects for slot in obj.material_slots if slot.material})


def clear_animation_data() -> None:
    for obj in bpy.data.objects:
        obj.animation_data_clear()
    for action in list(bpy.data.actions):
        bpy.data.actions.remove(action)


def create_empty(name: str, collection_name: str, loc=(0, 0, 0)) -> bpy.types.Object:
    obj = bpy.data.objects.new(name, None)
    bpy.context.scene.collection.objects.link(obj)
    obj.empty_display_type = "PLAIN_AXES"
    obj.empty_display_size = 0.18
    obj.location = loc
    return link_to_collection(obj, collection_name)


def parent_keep_world(obj: bpy.types.Object, parent: bpy.types.Object) -> None:
    matrix = obj.matrix_world.copy()
    obj.parent = parent
    obj.matrix_parent_inverse = parent.matrix_world.inverted()
    obj.matrix_world = matrix


def create_action(
    obj: bpy.types.Object,
    name: str,
    frames: list[tuple[int, dict]],
    *,
    start: int = 1,
    end: int = 72,
) -> bpy.types.Action:
    action = bpy.data.actions.new(name)
    action.use_fake_user = True
    animation_data = obj.animation_data_create()
    animation_data.action = action
    for frame, transform in frames:
        bpy.context.scene.frame_set(frame)
        if "location" in transform:
            obj.location = transform["location"]
            obj.keyframe_insert(data_path="location", frame=frame)
        if "rotation" in transform:
            obj.rotation_euler = transform["rotation"]
            obj.keyframe_insert(data_path="rotation_euler", frame=frame)
        if "scale" in transform:
            obj.scale = transform["scale"]
            obj.keyframe_insert(data_path="scale", frame=frame)
    for curve in getattr(action, "fcurves", []):
        for key in curve.keyframe_points:
            key.interpolation = "BEZIER"
    animation_data.action = None
    track = animation_data.nla_tracks.new()
    track.name = name
    strip = track.strips.new(name, start, action)
    strip.frame_start = start
    strip.frame_end = end
    return action


def configure_scene(spec: dict, *, frame_end: int = 72, fps: int = 24) -> None:
    scene = bpy.context.scene
    scene.name = f"SCN_{spec['slug'].replace('-', '_')}"
    scene.unit_settings.system = "METRIC"
    scene.frame_start = 1
    scene.frame_end = frame_end
    scene.render.fps = fps
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


def setup_lighting_and_camera(spec: dict, *, camera_loc=(2.2, -5.0, 2.0), target=(0, 0, 1.0)) -> None:
    world = bpy.context.scene.world or bpy.data.worlds.new("World")
    bpy.context.scene.world = world
    world.color = (0.025, 0.027, 0.03)

    camera_data = bpy.data.cameras.new(f"CAM_{spec['slug'].replace('-', '_')}_Preview")
    camera = bpy.data.objects.new(camera_data.name, camera_data)
    bpy.context.scene.collection.objects.link(camera)
    camera.location = camera_loc
    camera.data.lens = 50
    camera.data.dof.use_dof = True
    camera.data.dof.focus_distance = 5.5
    camera.data.dof.aperture_fstop = 7.5
    look_at(camera, target)
    bpy.context.scene.camera = camera
    for source in list(camera.users_collection):
        source.objects.unlink(camera)
    collection("LIGHTING_CAMERA").objects.link(camera)

    lights = [
        ("LGT_KeySoftbox", "AREA", (-2.6, -3.2, 3.7), 430, 3.6),
        ("LGT_CyanRim", "AREA", (2.6, 1.3, 2.8), 170, 2.2),
        ("LGT_WarmFill", "POINT", (0.6, -2.0, 1.4), 70, 0),
    ]
    for name, kind, loc, energy, size in lights:
        data = bpy.data.lights.new(f"{name}_{spec['slug']}", kind)
        obj = bpy.data.objects.new(data.name, data)
        bpy.context.scene.collection.objects.link(obj)
        obj.location = loc
        data.energy = energy
        if size and hasattr(data, "size"):
            data.size = size
        look_at(obj, target)
        for source in list(obj.users_collection):
            source.objects.unlink(obj)
        collection("LIGHTING_CAMERA").objects.link(obj)


def create_palette(spec: dict) -> dict[str, bpy.types.Material]:
    colors = style_colors(spec)
    primary = make_mat("MAT_Agent_Primary", hex_to_rgba(colors["primary"]), roughness=0.72)
    secondary = make_mat("MAT_Agent_Secondary", hex_to_rgba(colors["secondary"]), roughness=0.74)
    accent = make_mat(
        "MAT_Agent_AccentGlow",
        hex_to_rgba(colors["accent"], alpha=0.72),
        roughness=0.34,
        alpha=0.72,
        emission=hex_to_rgba(colors["emission"]),
        emission_strength=1.5,
    )
    accent.blend_method = "BLEND"
    dark = make_mat("MAT_Agent_DarkTrim", hex_to_rgba(colors["neutral"]), roughness=0.84)
    base = make_mat("MAT_Agent_DisplayBase", hex_to_rgba(colors["neutral"], alpha=1.0), roughness=0.9)
    shadow = make_mat("MAT_Shadow_BakedSoftContact", (0.018, 0.02, 0.023, 0.52), roughness=0.92, alpha=0.52)
    return {
        "primary": primary,
        "secondary": secondary,
        "accent": accent,
        "dark": dark,
        "base": base,
        "shadow": shadow,
        "skin": make_mat(
            "MAT_Agent_SkinTone",
            hex_to_rgba((spec.get("character") or {}).get("skinTone"), "#d9a77f"),
            roughness=0.68,
        ),
        "hair": make_mat(
            "MAT_Agent_Hair",
            hex_to_rgba((spec.get("character") or {}).get("hairColor"), colors["neutral"]),
            roughness=0.76,
        ),
    }


def add_contact_shadow(name: str, radius: float = 0.9) -> bpy.types.Object:
    mat = make_mat("MAT_Shadow_BakedSoftContact", (0.018, 0.02, 0.023, 0.48), roughness=0.92, alpha=0.48)
    obj = cylinder(name, (0, 0, 0.012), radius, 0.012, mat, vertices=64, collection_name="PROPS")
    obj.scale.y = 0.72
    return obj


def file_size(path: Path) -> int:
    return path.stat().st_size if path.exists() else 0


def export_glb(path: Path, objects: list[bpy.types.Object], *, animations: bool) -> None:
    ensure_dir(path.parent)
    select_objects(objects)
    run_operator(
        bpy.ops.export_scene.gltf,
        filepath=str(path),
        export_format="GLB",
        use_selection=True,
        export_yup=True,
        export_apply=True,
        export_animations=animations,
        export_animation_mode="NLA_TRACKS",
        export_nla_strips=True,
        export_lights=False,
        export_cameras=False,
        export_materials="EXPORT",
        export_force_sampling=True,
    )


def export_obj_zip(zip_path: Path, work_dir: Path, objects: list[bpy.types.Object]) -> None:
    ensure_dir(work_dir)
    for item in work_dir.glob("*"):
        if item.is_file():
            item.unlink()
    obj_path = work_dir / f"{zip_path.stem}.obj"
    select_objects(objects)
    if hasattr(bpy.ops.wm, "obj_export"):
        run_operator(bpy.ops.wm.obj_export, filepath=str(obj_path), export_selected_objects=True)
    elif hasattr(bpy.ops.export_scene, "obj"):
        run_operator(bpy.ops.export_scene.obj, filepath=str(obj_path), use_selection=True)
    else:
        return
    ensure_dir(zip_path.parent)
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for item in work_dir.glob("*"):
            if item.is_file():
                archive.write(item, arcname=item.name)


def export_mixamo(paths: dict[str, Path], objects: list[bpy.types.Object]) -> None:
    ensure_dir(paths["exports"])
    select_objects(objects)
    run_operator(
        bpy.ops.export_scene.fbx,
        filepath=str(paths["mixamo_fbx"]),
        use_selection=True,
        object_types={"ARMATURE", "MESH"},
        axis_forward="Z",
        axis_up="Y",
        apply_unit_scale=True,
        bake_space_transform=True,
        add_leaf_bones=False,
        bake_anim=False,
    )
    export_obj_zip(paths["mixamo_obj_zip"], paths["obj_work"], [obj for obj in objects if obj.type == "MESH"])
    if paths["obj_work"].exists():
        shutil.rmtree(paths["obj_work"], ignore_errors=True)


def export_asset(
    spec: dict,
    export_objects: list[bpy.types.Object],
    *,
    animations: bool,
    frame: int = 24,
    mixamo_objects: list[bpy.types.Object] | None = None,
) -> dict[str, Path]:
    paths = out_paths(spec)
    for key in ("blend", "glb", "preview", "textures"):
        ensure_dir(paths[key].parent if key != "textures" else paths[key])
    bpy.ops.wm.save_as_mainfile(filepath=str(paths["blend"]))
    export_glb(paths["glb"], export_objects, animations=animations)
    if mixamo_objects:
        export_mixamo(paths, mixamo_objects)
    bpy.context.scene.frame_set(frame)
    bpy.context.scene.render.filepath = str(paths["preview"])
    bpy.ops.render.render(write_still=True)
    bpy.context.scene.frame_set(1)
    return paths


def default_viewer(spec: dict) -> dict:
    family = spec.get("assetFamily")
    if family == "furniture":
        camera = {
            "desktop": {"position": [1.9, 0.9, 3.1], "target": [0, 0.55, 0]},
            "mobile": {"position": [0.95, 0.82, 3.8], "target": [0, 0.55, 0]},
            "focus": {"position": [1.1, 0.78, 2.0], "target": [0, 0.62, 0]},
        }
    elif family == "vfx":
        camera = {
            "desktop": {"position": [2.35, 1.38, 5.0], "target": [0, 1.18, 0]},
            "mobile": {"position": [1.08, 1.28, 6.05], "target": [0, 1.2, 0]},
            "focus": {"position": [1.18, 1.32, 3.2], "target": [0, 1.2, 0]},
        }
    else:
        camera = {
            "desktop": {"position": [2.0, 1.45, 6.2], "target": [0, 1.35, 0]},
            "mobile": {"position": [1.05, 1.25, 6.8], "target": [0, 1.45, 0]},
            "focus": {"position": [1.0, 1.85, 4.05], "target": [0, 1.95, 0]},
        }
    return {
        "placement": {"mode": "floor-y", "offset": [0, 0, 0]},
        "initialTransform": {"rotation": [0, -0.22, 0], "scale": 1},
        "camera": camera,
    }


def collect_metadata(
    spec: dict,
    paths: dict[str, Path],
    *,
    rig: dict,
    notes: list[str],
    viewer: dict | None = None,
    vfx: dict | None = None,
) -> dict:
    geometries = geometry_objects()
    meshes = mesh_objects()
    armatures = armature_objects()
    actions = sorted(action.name for action in bpy.data.actions)
    budget = {**DEFAULT_BUDGET, **(spec.get("budget") or {})}
    metadata = {
        "asset": spec["name"],
        "slug": spec["slug"],
        "generator": f"create_{spec['slug'].replace('-', '_')}.py",
        "spec": spec,
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
            "bones": sum(len(armature.data.bones) for armature in armatures),
            "animations": len(actions),
        },
        "materials": material_names(geometries),
        "style": spec.get("styleConfig") or {},
        "animations": {
            "clips": [clip["name"] for clip in spec.get("animationClips", [])],
            "default": spec.get("animationClips", [{}])[0].get("name", "") if spec.get("animationClips") else "",
            "embedded_in_glb": bool(spec.get("animationClips")),
            "authored_actions": actions,
        },
        "rig": rig,
        "rig_plan": spec.get("rigPlan") or {},
        "authored": {
            "family": display_family(spec),
            "target": f"{display_family(spec)} asset-generation showcase",
            "effects": ", ".join([*(spec.get("requiredParts") or []), *(spec.get("materialPalette") or [])]),
        },
        "viewer": viewer or default_viewer(spec),
        "bounds": bounds_for_objects(geometries),
        "budgets": {
            "triangle_warning": budget["maxTriangles"],
            "glb_size_warning_bytes": int(float(budget["maxGlbMb"]) * 1024 * 1024),
            "material_warning": budget["maxMaterials"],
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
            "animations": bool(spec.get("animationClips")),
            "source": "OnTheSpectrum generated Blender pipeline",
        },
        "notes": notes,
    }
    if vfx:
        metadata["vfx"] = vfx
    write_json(paths["metadata"], metadata)
    return metadata


def prepare_scene(spec: dict, *, frame_end: int = 72, fps: int = 24) -> dict[str, bpy.types.Material]:
    if bpy.context.object and bpy.context.object.mode != "OBJECT":
        bpy.ops.object.mode_set(mode="OBJECT")
    clear_scene()
    clear_animation_data()
    configure_scene(spec, frame_end=frame_end, fps=fps)
    return create_palette(spec)
