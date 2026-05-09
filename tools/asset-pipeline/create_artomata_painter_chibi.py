"""Generate the Artomata Painter Chibi asset in Blender.

Run from Blender Python, either through the live Blender MCP bridge or a
background Blender process with BLENDER_PATH configured.
"""

from __future__ import annotations

import math
import os
import sys
from pathlib import Path

import bpy
from mathutils import Vector

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
    cube,
    cylinder,
    ensure_dir,
    look_at,
    make_mat,
    scene_triangle_count,
    uv_sphere,
    write_json,
)

ASSET_SLUG = "artomata-painter-chibi"
ASSET_NAME = "Artomata Painter Chibi"


def repo_root() -> Path:
    return SCRIPT_DIR.parents[1]


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
        "skin": make_mat("MAT_Skin_WarmCel", (1.0, 0.72, 0.56, 1), roughness=0.78),
        "blush": make_mat("MAT_Skin_Blush_Baked", (1.0, 0.32, 0.43, 0.72), roughness=0.85, alpha=0.72),
        "hair": make_mat("MAT_Hair_InkViolet", (0.11, 0.08, 0.22, 1), roughness=0.66),
        "eye_white": make_mat("MAT_Eye_SoftWhite", (0.96, 0.98, 1.0, 1), roughness=0.35),
        "eye_iris": make_mat(
            "MAT_Eye_IrisCyanGlow",
            (0.02, 0.67, 0.9, 1),
            roughness=0.38,
            emission=(0.02, 0.38, 0.62, 1),
            emission_strength=0.35,
        ),
        "eye_gloss": make_mat("MAT_Eye_GlossCatchlight", (1, 1, 1, 1), roughness=0.12),
        "jacket": make_mat("MAT_Outfit_JacketTeal", (0.04, 0.38, 0.42, 1), roughness=0.76),
        "apron": make_mat("MAT_Outfit_ApronIvory", (0.92, 0.86, 0.72, 1), roughness=0.84),
        "trim": make_mat("MAT_Outfit_TrimCoral", (0.98, 0.34, 0.28, 1), roughness=0.7),
        "boots": make_mat("MAT_Boots_Charcoal", (0.055, 0.06, 0.075, 1), roughness=0.78),
        "metal": make_mat("MAT_Prop_StylusBrushedMetal", (0.72, 0.73, 0.72, 1), roughness=0.42, metallic=0.45),
        "bristle": make_mat("MAT_Prop_BristleGold", (0.92, 0.68, 0.28, 1), roughness=0.64),
        "satchel": make_mat("MAT_Satchel_LeatherWarm", (0.52, 0.25, 0.12, 1), roughness=0.78),
        "accent": make_mat(
            "MAT_Accent_EmissiveCyan",
            (0.01, 0.85, 0.95, 1),
            roughness=0.44,
            emission=(0.0, 0.7, 1.0, 1),
            emission_strength=0.55,
        ),
        "base": make_mat("MAT_Base_MatteSlate", (0.09, 0.12, 0.14, 1), roughness=0.88),
        "contact": make_mat("MAT_Shadow_BakedSoftContact", (0.02, 0.026, 0.028, 0.62), roughness=0.9, alpha=0.62),
    }


def bind_to_bone(obj: bpy.types.Object, armature: bpy.types.Object, bone_name: str) -> None:
    if obj.type != "MESH":
        return
    group = obj.vertex_groups.new(name=bone_name)
    group.add(list(range(len(obj.data.vertices))), 1.0, "ADD")
    mod = obj.modifiers.new("ARM_basic_chibi_deform", "ARMATURE")
    mod.object = armature
    obj.parent = armature


def create_armature() -> bpy.types.Object:
    bpy.ops.object.armature_add(enter_editmode=True, location=(0, 0, 0))
    armature = bpy.context.object
    armature.name = "RIG_ArtomataPainter_BasicArmature"
    armature.data.name = "ARM_ArtomataPainter_Chibi"
    armature.show_in_front = True
    link_collection = collection("RIG")
    for source in list(armature.users_collection):
        source.objects.unlink(armature)
    link_collection.objects.link(armature)

    bones = armature.data.edit_bones
    root = bones[0]
    root.name = "root"
    root.head = (0, 0, 0.04)
    root.tail = (0, 0, 0.36)

    def bone(name: str, head: tuple[float, float, float], tail: tuple[float, float, float], parent: str | None = None):
        edit_bone = bones.new(name)
        edit_bone.head = head
        edit_bone.tail = tail
        if parent:
            edit_bone.parent = bones[parent]
        return edit_bone

    bone("pelvis", (0, 0, 0.52), (0, 0, 0.84), "root")
    bone("spine", (0, 0, 0.84), (0, 0, 1.55), "pelvis")
    bone("head", (0, 0, 1.55), (0, -0.02, 2.72), "spine")
    bone("hair", (0, 0.08, 2.38), (0, 0.04, 3.32), "head")
    bone("upper_arm.L", (-0.34, -0.02, 1.35), (-0.74, -0.08, 1.02), "spine")
    bone("forearm.L", (-0.74, -0.08, 1.02), (-0.92, -0.16, 0.82), "upper_arm.L")
    bone("hand.L", (-0.92, -0.16, 0.82), (-1.02, -0.2, 0.72), "forearm.L")
    bone("upper_arm.R", (0.34, -0.02, 1.35), (0.74, -0.08, 1.02), "spine")
    bone("forearm.R", (0.74, -0.08, 1.02), (1.02, -0.18, 0.88), "upper_arm.R")
    bone("hand.R", (1.02, -0.18, 0.88), (1.14, -0.23, 0.78), "forearm.R")
    bone("thigh.L", (-0.2, 0, 0.62), (-0.25, -0.02, 0.28), "pelvis")
    bone("shin.L", (-0.25, -0.02, 0.28), (-0.26, -0.05, 0.08), "thigh.L")
    bone("foot.L", (-0.26, -0.05, 0.08), (-0.26, -0.28, 0.04), "shin.L")
    bone("thigh.R", (0.2, 0, 0.62), (0.25, -0.02, 0.28), "pelvis")
    bone("shin.R", (0.25, -0.02, 0.28), (0.26, -0.05, 0.08), "thigh.R")
    bone("foot.R", (0.26, -0.05, 0.08), (0.26, -0.28, 0.04), "shin.R")
    bone("satchel", (-0.42, -0.14, 1.04), (-0.76, -0.18, 0.72), "spine")
    bone("stylus", (1.02, -0.22, 0.88), (1.35, -0.66, 1.34), "hand.R")

    bpy.ops.object.mode_set(mode="OBJECT")
    return armature


def build_character(mats: dict[str, bpy.types.Material]) -> tuple[bpy.types.Object, list[bpy.types.Object]]:
    for name in [
        "RIG",
        "CHARACTER_BODY",
        "FACE",
        "HAIR",
        "OUTFIT",
        "PROPS",
        "BAKED_EFFECTS",
        "LIGHTING_CAMERA",
    ]:
        collection(name)

    armature = create_armature()
    meshes: list[bpy.types.Object] = []

    def add(obj: bpy.types.Object, bone_name: str) -> bpy.types.Object:
        meshes.append(obj)
        bind_to_bone(obj, armature, bone_name)
        return obj

    add(uv_sphere("CHR_Head_RoundedChibi", (0, -0.02, 2.35), (0.78, 0.68, 0.74), mats["skin"], segments=48, rings=24, collection_name="CHARACTER_BODY"), "head")
    add(uv_sphere("CHR_Torso_SoftStudioApron", (0, 0.02, 1.16), (0.42, 0.32, 0.5), mats["jacket"], segments=36, rings=18, collection_name="CHARACTER_BODY"), "spine")
    add(uv_sphere("CHR_Hip_ShortsRounded", (0, 0.02, 0.72), (0.42, 0.29, 0.22), mats["boots"], segments=32, rings=14, collection_name="CHARACTER_BODY"), "pelvis")

    for side, sign in [("L", -1), ("R", 1)]:
        add(uv_sphere(f"CHR_Arm_{side}_SleevePuff", (sign * 0.48, -0.04, 1.28), (0.16, 0.13, 0.26), mats["jacket"], segments=28, rings=14, collection_name="OUTFIT"), f"upper_arm.{side}")
        add(bevel_curve(f"CHR_Arm_{side}_Forearm", [(sign * 0.57, -0.08, 1.08), (sign * 0.78, -0.14, 0.9), (sign * 0.9, -0.2, 0.78)], mats["skin"], bevel_depth=0.075, collection_name="CHARACTER_BODY"), f"forearm.{side}")
        add(uv_sphere(f"CHR_Hand_{side}_Mitten", (sign * 0.95, -0.22, 0.75), (0.11, 0.09, 0.1), mats["skin"], segments=24, rings=12, collection_name="CHARACTER_BODY"), f"hand.{side}")
        add(uv_sphere(f"CHR_Leg_{side}_Soft", (sign * 0.2, -0.02, 0.35), (0.12, 0.11, 0.27), mats["skin"], segments=24, rings=12, collection_name="CHARACTER_BODY"), f"thigh.{side}")
        add(uv_sphere(f"CHR_Boot_{side}_Rounded", (sign * 0.23, -0.1, 0.12), (0.17, 0.25, 0.12), mats["boots"], segments=28, rings=12, collection_name="OUTFIT"), f"foot.{side}")
        add(cylinder(f"CHR_Boot_{side}_CoralSole", (sign * 0.23, -0.16, 0.035), 0.13, 0.035, mats["trim"], vertices=28, scale=(1.15, 0.7, 1), collection_name="BAKED_EFFECTS"), f"foot.{side}")

    # Outfit layers and baked cloth-shadow bands.
    add(cube("OUT_Apron_FrontPanel", (0, -0.315, 1.02), (0.34, 0.035, 0.44), mats["apron"], bevel=0.035, collection_name="OUTFIT"), "spine")
    add(cube("OUT_Apron_BottomShadowBand", (0, -0.352, 0.67), (0.32, 0.012, 0.04), mats["boots"], bevel=0.015, collection_name="BAKED_EFFECTS"), "pelvis")
    add(cube("OUT_Collar_CoralTab", (0, -0.34, 1.53), (0.3, 0.025, 0.06), mats["trim"], bevel=0.018, collection_name="OUTFIT"), "spine")
    add(bevel_curve("OUT_Satchel_Strap", [(-0.38, -0.35, 1.48), (-0.05, -0.38, 1.13), (0.34, -0.36, 0.77)], mats["satchel"], bevel_depth=0.025, collection_name="PROPS"), "satchel")
    add(cube("PROP_Satchel_Box", (-0.58, -0.34, 0.76), (0.2, 0.075, 0.17), mats["satchel"], bevel=0.035, collection_name="PROPS"), "satchel")
    add(cube("PROP_Satchel_CyanLatch", (-0.58, -0.392, 0.79), (0.06, 0.011, 0.035), mats["accent"], bevel=0.012, collection_name="PROPS"), "satchel")

    # Face: layered eye geometry rather than shader-only effects.
    for side, sign in [("L", -1), ("R", 1)]:
        add(uv_sphere(f"FACE_Eye_{side}_ScleraOval", (sign * 0.28, -0.64, 2.5), (0.18, 0.024, 0.25), mats["eye_white"], segments=32, rings=16, collection_name="FACE"), "head")
        add(uv_sphere(f"FACE_Eye_{side}_IrisGradientCore", (sign * 0.28, -0.667, 2.48), (0.1, 0.014, 0.15), mats["eye_iris"], segments=28, rings=12, collection_name="FACE"), "head")
        add(uv_sphere(f"FACE_Eye_{side}_PupilDeep", (sign * 0.28, -0.684, 2.465), (0.045, 0.009, 0.075), mats["hair"], segments=24, rings=10, collection_name="FACE"), "head")
        add(uv_sphere(f"FACE_Eye_{side}_Catchlight", (sign * 0.23, -0.695, 2.57), (0.038, 0.007, 0.055), mats["eye_gloss"], segments=16, rings=8, collection_name="FACE"), "head")
        add(uv_sphere(f"FACE_Blush_{side}_BakedOval", (sign * 0.48, -0.646, 2.31), (0.09, 0.011, 0.04), mats["blush"], segments=20, rings=8, collection_name="BAKED_EFFECTS"), "head")

    add(bevel_curve("FACE_Mouth_SmallSmile", [(-0.075, -0.695, 2.23), (0, -0.713, 2.19), (0.075, -0.695, 2.23)], mats["hair"], bevel_depth=0.009, bevel_resolution=2, collection_name="FACE"), "head")
    add(uv_sphere("FACE_Nose_TinyWarmPlane", (0, -0.675, 2.34), (0.026, 0.006, 0.018), mats["blush"], segments=12, rings=6, collection_name="FACE"), "head")

    # Hair cap and asymmetrical locks.
    add(uv_sphere("HAIR_Cap_RoundedInkViolet", (0, -0.01, 2.73), (0.8, 0.69, 0.36), mats["hair"], segments=48, rings=18, collection_name="HAIR"), "hair")
    lock_specs = [
        ("FrontCenter", [(0.0, -0.64, 2.98), (-0.02, -0.78, 2.66), (0.06, -0.72, 2.35)], 0.08),
        ("FrontLeft", [(-0.28, -0.58, 2.92), (-0.42, -0.72, 2.6), (-0.36, -0.68, 2.28)], 0.07),
        ("FrontRightLong", [(0.3, -0.57, 2.96), (0.51, -0.71, 2.58), (0.46, -0.66, 2.18)], 0.074),
        ("SideLeft", [(-0.66, -0.16, 2.64), (-0.83, -0.23, 2.25), (-0.72, -0.18, 1.95)], 0.065),
        ("SideRight", [(0.66, -0.12, 2.66), (0.86, -0.18, 2.3), (0.75, -0.12, 2.02)], 0.06),
        ("BackFlip", [(0.12, 0.48, 2.86), (0.38, 0.64, 2.72), (0.56, 0.52, 2.55)], 0.058),
    ]
    for name, points, depth in lock_specs:
        add(bevel_curve(f"HAIR_Lock_{name}", points, mats["hair"], bevel_depth=depth, bevel_resolution=5, collection_name="HAIR"), "hair")
    add(bevel_curve("HAIR_Cyan_PainterStreak", [(0.18, -0.69, 2.99), (0.28, -0.78, 2.68), (0.26, -0.73, 2.42)], mats["accent"], bevel_depth=0.024, bevel_resolution=3, collection_name="BAKED_EFFECTS"), "hair")
    add(bevel_curve("HAIR_Coral_RibbonTie", [(-0.48, 0.08, 2.82), (-0.67, -0.02, 2.75), (-0.74, -0.05, 2.62)], mats["trim"], bevel_depth=0.035, bevel_resolution=3, collection_name="HAIR"), "hair")

    # Stylus brush prop attached to the right hand.
    add(cylinder("PROP_Stylus_Handle", (1.16, -0.48, 1.08), 0.034, 0.72, mats["metal"], vertices=24, rotation=(math.radians(38), 0, math.radians(-24)), bevel=0.01, collection_name="PROPS"), "stylus")
    add(cone("PROP_Stylus_BristleTip", (1.39, -0.69, 1.34), 0.06, 0.012, 0.18, mats["bristle"], vertices=24, rotation=(math.radians(38), 0, math.radians(-24)), collection_name="PROPS"), "stylus")
    add(uv_sphere("PROP_PaintGlow_Droplet", (1.48, -0.78, 1.45), (0.055, 0.04, 0.075), mats["accent"], segments=18, rings=9, collection_name="BAKED_EFFECTS"), "stylus")

    # Scale cue base and baked contact shadow.
    add(cylinder("BASE_DisplayDisc_MatteSlate", (0, 0, -0.02), 0.78, 0.045, mats["base"], vertices=72, collection_name="BAKED_EFFECTS"), "root")
    add(cylinder("BASE_BakedSoftContactShadow", (0, -0.04, 0.006), 0.61, 0.01, mats["contact"], vertices=72, scale=(1, 0.7, 1), collection_name="BAKED_EFFECTS"), "root")

    return armature, meshes


def setup_lighting_and_camera() -> None:
    world = bpy.context.scene.world or bpy.data.worlds.new("World")
    bpy.context.scene.world = world
    world.color = (0.025, 0.032, 0.035)

    camera_data = bpy.data.cameras.new("CAM_ArtomataPainter_Preview")
    camera = bpy.data.objects.new("CAM_ArtomataPainter_Preview", camera_data)
    bpy.context.scene.collection.objects.link(camera)
    camera.location = (2.2, -5.2, 2.25)
    camera.data.lens = 62
    camera.data.dof.use_dof = True
    camera.data.dof.focus_distance = 5.3
    camera.data.dof.aperture_fstop = 5.6
    look_at(camera, (0, -0.12, 1.62))
    bpy.context.scene.camera = camera
    for source in list(camera.users_collection):
        source.objects.unlink(camera)
    collection("LIGHTING_CAMERA").objects.link(camera)

    lights = [
        ("LGT_Key_LargeSoftbox", "AREA", (-2.4, -3.4, 4.0), 520, 4.2),
        ("LGT_Rim_CyanAccent", "AREA", (2.6, 1.4, 2.7), 160, 2.2),
        ("LGT_Fill_WarmStudio", "POINT", (1.6, -2.0, 1.7), 90, 0),
    ]
    for name, kind, loc, energy, size in lights:
        data = bpy.data.lights.new(name, kind)
        obj = bpy.data.objects.new(name, data)
        bpy.context.scene.collection.objects.link(obj)
        obj.location = loc
        data.energy = energy
        if hasattr(data, "size") and size:
            data.size = size
        look_at(obj, (0, -0.1, 1.5))
        for source in list(obj.users_collection):
            source.objects.unlink(obj)
        collection("LIGHTING_CAMERA").objects.link(obj)


def configure_scene() -> None:
    scene = bpy.context.scene
    scene.name = "SCN_ArtomataPainterChibi"
    scene.unit_settings.system = "METRIC"
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


def collect_metadata(paths: dict[str, Path], meshes: list[bpy.types.Object], armature: bpy.types.Object) -> dict:
    materials = sorted({slot.material.name for obj in meshes for slot in obj.material_slots if slot.material})
    bones = sorted([bone.name for bone in armature.data.bones])
    glb_size = paths["glb"].stat().st_size if paths["glb"].exists() else 0
    blend_size = paths["blend"].stat().st_size if paths["blend"].exists() else 0
    preview_size = paths["preview"].stat().st_size if paths["preview"].exists() else 0
    return {
        "asset": ASSET_NAME,
        "slug": ASSET_SLUG,
        "generator": Path(__file__).name,
        "paths": {
            "blend": str(paths["blend"].relative_to(repo_root())).replace("\\", "/"),
            "glb": str(paths["glb"].relative_to(repo_root())).replace("\\", "/"),
            "preview": str(paths["preview"].relative_to(repo_root())).replace("\\", "/"),
            "metadata": str(paths["metadata"].relative_to(repo_root())).replace("\\", "/"),
        },
        "counts": {
            "objects": len(bpy.data.objects),
            "mesh_objects": len([obj for obj in meshes if obj.type == "MESH"]),
            "materials": len(materials),
            "triangles": scene_triangle_count(meshes),
            "bones": len(bones),
        },
        "materials": materials,
        "armature": {
            "object": armature.name,
            "bones": bones,
            "rig_depth": "basic named armature with whole-part vertex groups",
        },
        "bounds": bounds_for_objects(meshes),
        "budgets": {
            "triangle_target": "35k-80k",
            "triangle_warning": 100000,
            "glb_size_warning_bytes": 12 * 1024 * 1024,
        },
        "file_sizes": {
            "blend_bytes": blend_size,
            "glb_bytes": glb_size,
            "preview_bytes": preview_size,
        },
        "export": {
            "format": "GLB",
            "export_yup": True,
            "applied_export_transforms": True,
            "animations": False,
            "source": "Blender MCP live bridge",
        },
        "notes": [
            "Original anime chibi mascot asset.",
            "Baked visual effects use geometry/material layers: blush, shadow bands, contact shadow, eye highlights, cyan paint glow.",
            "The armature is a future-animation scaffold, not a polished control rig.",
        ],
    }


def export_asset(paths: dict[str, Path], meshes: list[bpy.types.Object], armature: bpy.types.Object) -> None:
    ensure_dir(paths["blend"].parent)
    ensure_dir(paths["glb"].parent)
    ensure_dir(paths["preview"].parent)
    ensure_dir(paths["textures"])

    for block in (bpy.data.materials, bpy.data.curves, bpy.data.images):
        for item in list(block):
            if item.users == 0:
                block.remove(item)

    bpy.ops.wm.save_as_mainfile(filepath=str(paths["blend"]))

    bpy.ops.object.select_all(action="DESELECT")
    armature.select_set(True)
    for obj in meshes:
        obj.select_set(True)
    bpy.context.view_layer.objects.active = armature
    bpy.ops.export_scene.gltf(
        filepath=str(paths["glb"]),
        export_format="GLB",
        use_selection=True,
        export_yup=True,
        export_apply=True,
        export_animations=False,
        export_lights=False,
        export_cameras=False,
        export_materials="EXPORT",
    )

    bpy.context.scene.render.filepath = str(paths["preview"])
    bpy.ops.render.render(write_still=True)


def main() -> dict:
    paths = out_paths()
    clear_scene()
    configure_scene()
    mats = make_materials()
    armature, meshes = build_character(mats)
    setup_lighting_and_camera()
    export_asset(paths, meshes, armature)
    metadata = collect_metadata(paths, meshes, armature)
    write_json(paths["metadata"], metadata)
    return metadata


if __name__ == "__main__":
    result = main()
