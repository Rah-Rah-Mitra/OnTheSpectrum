"""Generate the Forest Ranger NPC asset in Blender.

The script is repeatable: it creates the source scene, embeds web animation
clips, exports the GLB, writes Mixamo best-effort exports, renders a preview,
and writes metadata using the existing OnTheSpectrum asset-pipeline conventions.
"""

from __future__ import annotations

import json
import math
import shutil
import sys
import zipfile
from pathlib import Path

import bpy

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from blender_common import (  # noqa: E402
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

ASSET_SLUG = "forest-ranger-npc"
ASSET_NAME = "Forest Ranger NPC"
CLIPS = ("Idle_Stationary", "Walk_InPlace", "Run_InPlace", "DrawBow", "Aim_Hold", "Shoot_Release")
MIXAMO_FBX_AXIS_FORWARD = "Z"
MIXAMO_OBJ_FORWARD_AXIS = "Z"
MIXAMO_AXIS_UP = "Y"
MIXAMO_ORIENTATION_NOTE = (
    "Mixamo exports are front-corrected with a 180-degree forward-axis flip; "
    "the Blender source and web GLB keep the authored -Y front."
)


def repo_root() -> Path:
    return SCRIPT_DIR.parents[1]


def relative(path: str | Path) -> str:
    return str(Path(path).relative_to(repo_root())).replace("\\", "/")


def out_paths() -> dict[str, Path]:
    root = repo_root()
    exports = root / "public" / "exports" / ASSET_SLUG
    return {
        "blend": root / "public" / "models" / f"{ASSET_SLUG}.blend",
        "glb": root / "public" / "models" / f"{ASSET_SLUG}.glb",
        "preview": root / "public" / "renders" / f"{ASSET_SLUG}-preview.png",
        "metadata": root / "public" / "models" / f"{ASSET_SLUG}.metadata.json",
        "textures": root / "public" / "textures" / ASSET_SLUG,
        "exports": exports,
        "mixamo_fbx": exports / f"{ASSET_SLUG}-mixamo.fbx",
        "mixamo_obj_zip": exports / f"{ASSET_SLUG}-mixamo-obj.zip",
        "obj_work": exports / "_obj_bundle",
    }


def make_materials() -> dict[str, bpy.types.Material]:
    return {
        "skin": make_mat("MAT_Skin_WarmFocused", (0.92, 0.62, 0.43, 1), roughness=0.78),
        "hair": make_mat("MAT_Hair_BarkBrown", (0.12, 0.075, 0.04, 1), roughness=0.74),
        "eye_white": make_mat("MAT_Eye_SoftWhite", (0.94, 0.97, 0.93, 1), roughness=0.42),
        "iris": make_mat("MAT_Eye_ForestIris", (0.12, 0.44, 0.25, 1), roughness=0.45),
        "cloak": make_mat("MAT_Cloak_DarkForestGreen", (0.035, 0.19, 0.105, 1), roughness=0.86),
        "cloak_dark": make_mat("MAT_Cloak_ShadowGreen", (0.018, 0.09, 0.058, 1), roughness=0.9),
        "leather": make_mat("MAT_Leather_BrownArmor", (0.37, 0.19, 0.09, 1), roughness=0.78),
        "leather_dark": make_mat("MAT_Leather_DarkTrim", (0.16, 0.09, 0.045, 1), roughness=0.82),
        "straps": make_mat("MAT_Straps_Tan", (0.77, 0.53, 0.29, 1), roughness=0.74),
        "bow": make_mat("MAT_Bow_WarmWood", (0.56, 0.31, 0.13, 1), roughness=0.68),
        "steel": make_mat("MAT_Arrow_SteelTips", (0.62, 0.67, 0.66, 1), roughness=0.36, metallic=0.35),
        "quiver": make_mat("MAT_Quiver_OliveLeather", (0.16, 0.22, 0.12, 1), roughness=0.82),
        "gloves": make_mat("MAT_Gloves_DarkBrown", (0.12, 0.075, 0.04, 1), roughness=0.84),
        "boots": make_mat("MAT_Boots_MudBrown", (0.18, 0.1, 0.055, 1), roughness=0.86),
        "base": make_mat("MAT_Base_MatteMossStone", (0.08, 0.11, 0.095, 1), roughness=0.9),
        "contact": make_mat("MAT_Shadow_BakedSoftContact", (0.018, 0.022, 0.018, 0.56), roughness=0.9, alpha=0.56),
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


def material_names(objects: list[bpy.types.Object]) -> list[str]:
    return sorted({slot.material.name for obj in objects for slot in obj.material_slots if slot.material})


def rotate_object(obj: bpy.types.Object, rotation: tuple[float, float, float]) -> bpy.types.Object:
    obj.rotation_euler = rotation
    return obj


def bind_to_bone(obj: bpy.types.Object, armature: bpy.types.Object, bone_name: str) -> None:
    if obj.type != "MESH":
        return
    group = obj.vertex_groups.new(name=bone_name)
    group.add(list(range(len(obj.data.vertices))), 1.0, "ADD")
    mod = obj.modifiers.new("ARM_whole_part_deform", "ARMATURE")
    mod.object = armature
    obj.parent = armature


def create_armature() -> bpy.types.Object:
    bpy.ops.object.armature_add(enter_editmode=True, location=(0, 0, 0))
    armature = bpy.context.object
    armature.name = "RIG_ForestRangerNPC_BasicArmature"
    armature.data.name = "ARM_ForestRangerNPC_Humanoid"
    armature.show_in_front = True
    rig_collection = collection("RIG")
    for source in list(armature.users_collection):
        source.objects.unlink(armature)
    rig_collection.objects.link(armature)

    bones = armature.data.edit_bones
    root = bones[0]
    root.name = "root"
    root.head = (0, 0, 0.04)
    root.tail = (0, 0, 0.34)

    def bone(name: str, head: tuple[float, float, float], tail: tuple[float, float, float], parent: str | None = None):
        edit_bone = bones.new(name)
        edit_bone.head = head
        edit_bone.tail = tail
        if parent:
            edit_bone.parent = bones[parent]
        return edit_bone

    bone("pelvis", (0, 0, 0.46), (0, 0, 0.78), "root")
    bone("spine", (0, 0, 0.78), (0, -0.018, 1.32), "pelvis")
    bone("chest", (0, -0.018, 1.32), (0, -0.025, 1.66), "spine")
    bone("neck", (0, -0.025, 1.66), (0, -0.035, 1.86), "chest")
    bone("head", (0, -0.035, 1.86), (0, -0.05, 2.42), "neck")
    bone("hood", (0, -0.01, 2.16), (0, -0.03, 2.76), "head")
    bone("upper_arm.L", (-0.34, -0.03, 1.47), (-0.66, -0.21, 1.28), "chest")
    bone("forearm.L", (-0.66, -0.21, 1.28), (-0.88, -0.43, 1.12), "upper_arm.L")
    bone("hand.L", (-0.88, -0.43, 1.12), (-0.98, -0.52, 1.04), "forearm.L")
    bone("bow", (-1.0, -0.53, 1.04), (-1.08, -0.54, 1.65), "hand.L")
    bone("upper_arm.R", (0.34, -0.03, 1.47), (0.66, -0.21, 1.28), "chest")
    bone("forearm.R", (0.66, -0.21, 1.28), (0.88, -0.43, 1.12), "upper_arm.R")
    bone("hand.R", (0.88, -0.43, 1.12), (0.98, -0.52, 1.04), "forearm.R")
    bone("arrow_hand", (0.96, -0.54, 1.1), (0.42, -0.58, 1.17), "hand.R")
    bone("quiver", (0.32, 0.16, 1.12), (0.44, 0.36, 1.92), "chest")
    bone("cloak_back", (0, 0.12, 1.58), (0, 0.28, 0.58), "chest")
    bone("cloak.L", (-0.34, 0.05, 1.42), (-0.5, 0.04, 0.58), "chest")
    bone("cloak.R", (0.34, 0.05, 1.42), (0.5, 0.04, 0.58), "chest")
    bone("thigh.L", (-0.16, 0.0, 0.5), (-0.22, -0.02, 0.25), "pelvis")
    bone("shin.L", (-0.22, -0.02, 0.25), (-0.23, -0.04, 0.08), "thigh.L")
    bone("foot.L", (-0.23, -0.04, 0.08), (-0.25, -0.3, 0.04), "shin.L")
    bone("thigh.R", (0.16, 0.0, 0.5), (0.22, -0.02, 0.25), "pelvis")
    bone("shin.R", (0.22, -0.02, 0.25), (0.23, -0.04, 0.08), "thigh.R")
    bone("foot.R", (0.23, -0.04, 0.08), (0.25, -0.3, 0.04), "shin.R")

    bpy.ops.object.mode_set(mode="OBJECT")
    return armature


def add_arrow(
    add,
    mats: dict[str, bpy.types.Material],
    name: str,
    loc: tuple[float, float, float],
    *,
    length: float,
    bone_name: str,
    rotation: tuple[float, float, float],
    collection_name: str = "PROPS",
) -> None:
    add(
        cylinder(
            f"{name}_Shaft",
            loc,
            0.011,
            length,
            mats["straps"],
            vertices=12,
            rotation=rotation,
            collection_name=collection_name,
        ),
        bone_name,
    )
    tip_offset = (math.sin(rotation[1]) * length * 0.52, 0, math.cos(rotation[1]) * length * 0.52)
    add(
        cone(
            f"{name}_SteelTip",
            (loc[0] + tip_offset[0], loc[1] + tip_offset[1], loc[2] + tip_offset[2]),
            0.028,
            0.0,
            0.08,
            mats["steel"],
            vertices=16,
            rotation=rotation,
            collection_name=collection_name,
        ),
        bone_name,
    )
    feather_offset = (-math.sin(rotation[1]) * length * 0.42, 0, -math.cos(rotation[1]) * length * 0.42)
    feather = cube(
        f"{name}_TanFletching",
        (loc[0] + feather_offset[0], loc[1] + feather_offset[1], loc[2] + feather_offset[2]),
        (0.035, 0.006, 0.055),
        mats["straps"],
        bevel=0.006,
        collection_name=collection_name,
    )
    rotate_object(feather, (0, rotation[1], math.radians(18)))
    add(feather, bone_name)


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

    # Agile body base.
    add(uv_sphere("CHR_Head_CalmFocusedFace", (0, -0.31, 2.17), (0.34, 0.22, 0.38), mats["skin"], segments=32, rings=16, collection_name="CHARACTER_BODY"), "head")
    add(uv_sphere("CHR_Torso_LeanLeatherUnderlayer", (0, -0.02, 1.22), (0.35, 0.25, 0.45), mats["leather"], segments=32, rings=16, collection_name="CHARACTER_BODY"), "spine")
    add(uv_sphere("CHR_Hips_TravelTunic", (0, 0.0, 0.69), (0.31, 0.23, 0.2), mats["leather_dark"], segments=28, rings=12, collection_name="CHARACTER_BODY"), "pelvis")

    # Hood and cloak silhouette.
    add(uv_sphere("OUT_Hood_RoundedDarkGreen", (0, -0.07, 2.23), (0.52, 0.46, 0.52), mats["cloak"], segments=36, rings=16, collection_name="OUTFIT"), "hood")
    add(uv_sphere("FACE_HoodOpening_WarmFaceOval", (0, -0.535, 2.14), (0.29, 0.025, 0.28), mats["skin"], segments=28, rings=12, collection_name="FACE"), "head")
    add(bevel_curve("OUT_Hood_TanRimCord", [(-0.28, -0.52, 2.37), (-0.38, -0.55, 2.14), (-0.25, -0.53, 1.92), (0, -0.54, 1.86), (0.25, -0.53, 1.92), (0.38, -0.55, 2.14), (0.28, -0.52, 2.37)], mats["straps"], bevel_depth=0.014, bevel_resolution=3, collection_name="OUTFIT"), "hood")
    add(uv_sphere("OUT_Cloak_CollarLayer", (0, -0.03, 1.62), (0.55, 0.32, 0.17), mats["cloak"], segments=32, rings=10, collection_name="OUTFIT"), "chest")
    add(cube("OUT_Cloak_BackLongPanel", (0, 0.18, 1.05), (0.55, 0.055, 0.72), mats["cloak"], bevel=0.025, collection_name="OUTFIT"), "cloak_back")
    add(rotate_object(cube("OUT_Cloak_LeftSplitPanel", (-0.4, 0.06, 0.98), (0.22, 0.045, 0.62), mats["cloak_dark"], bevel=0.022, collection_name="OUTFIT"), (0, 0, math.radians(-7))), "cloak.L")
    add(rotate_object(cube("OUT_Cloak_RightSplitPanel", (0.4, 0.06, 0.98), (0.22, 0.045, 0.62), mats["cloak_dark"], bevel=0.022, collection_name="OUTFIT"), (0, 0, math.radians(7))), "cloak.R")

    # Leather armor, straps, belt, and pouches.
    add(uv_sphere("OUT_Leather_ChestArmorPlate", (0, -0.27, 1.39), (0.34, 0.06, 0.25), mats["leather"], segments=30, rings=10, collection_name="OUTFIT"), "chest")
    add(cube("OUT_Leather_CenterGorget", (0, -0.31, 1.58), (0.1, 0.022, 0.12), mats["leather_dark"], bevel=0.018, collection_name="OUTFIT"), "chest")
    add(bevel_curve("OUT_Strap_LeftShoulderToBelt", [(-0.28, -0.35, 1.58), (-0.12, -0.36, 1.25), (0.16, -0.34, 0.94)], mats["straps"], bevel_depth=0.02, bevel_resolution=2, collection_name="OUTFIT"), "chest")
    add(bevel_curve("OUT_Strap_RightShoulderToBelt", [(0.28, -0.35, 1.58), (0.08, -0.36, 1.25), (-0.18, -0.34, 0.94)], mats["straps"], bevel_depth=0.02, bevel_resolution=2, collection_name="OUTFIT"), "chest")
    add(bevel_curve("OUT_Belt_TanUtilityBand", [(-0.35, -0.3, 0.88), (-0.1, -0.34, 0.85), (0.16, -0.33, 0.86), (0.36, -0.29, 0.9)], mats["straps"], bevel_depth=0.025, bevel_resolution=3, collection_name="OUTFIT"), "pelvis")
    add(cube("OUT_BeltPouch_LeftRounded", (-0.43, -0.25, 0.78), (0.09, 0.052, 0.11), mats["leather"], bevel=0.022, collection_name="OUTFIT"), "pelvis")
    add(cube("OUT_BeltPouch_RightRounded", (0.42, -0.25, 0.8), (0.08, 0.052, 0.1), mats["leather"], bevel=0.022, collection_name="OUTFIT"), "pelvis")
    add(cube("OUT_Belt_SteelBuckle", (0, -0.34, 0.88), (0.07, 0.014, 0.052), mats["steel"], bevel=0.01, collection_name="OUTFIT"), "pelvis")

    for side, sign in [("L", -1), ("R", 1)]:
        arm_y = -0.1
        add(uv_sphere(f"CHR_Shoulder_{side}_CloakPad", (sign * 0.39, arm_y, 1.5), (0.14, 0.11, 0.15), mats["cloak"], segments=22, rings=10, collection_name="OUTFIT"), f"upper_arm.{side}")
        add(bevel_curve(f"CHR_UpperArm_{side}_LeatherSleeve", [(sign * 0.43, arm_y, 1.39), (sign * 0.57, arm_y - 0.05, 1.27), (sign * 0.68, arm_y - 0.12, 1.14)], mats["leather"], bevel_depth=0.058, bevel_resolution=4, collection_name="CHARACTER_BODY"), f"upper_arm.{side}")
        add(bevel_curve(f"CHR_Forearm_{side}_TanWrap", [(sign * 0.68, arm_y - 0.12, 1.14), (sign * 0.83, arm_y - 0.22, 1.03), (sign * 0.95, arm_y - 0.31, 0.96)], mats["straps"], bevel_depth=0.047, bevel_resolution=4, collection_name="OUTFIT"), f"forearm.{side}")
        add(uv_sphere(f"CHR_Glove_{side}_DarkLeather", (sign * 0.99, arm_y - 0.34, 0.94), (0.1, 0.08, 0.082), mats["gloves"], segments=20, rings=10, collection_name="OUTFIT"), f"hand.{side}")
        add(uv_sphere(f"CHR_Thigh_{side}_TravelTrouser", (sign * 0.17, -0.02, 0.38), (0.12, 0.095, 0.24), mats["leather_dark"], segments=22, rings=10, collection_name="CHARACTER_BODY"), f"thigh.{side}")
        add(uv_sphere(f"CHR_Shin_{side}_LegWraps", (sign * 0.22, -0.04, 0.19), (0.092, 0.08, 0.16), mats["straps"], segments=18, rings=9, collection_name="OUTFIT"), f"shin.{side}")
        add(uv_sphere(f"CHR_Boot_{side}_MudBrown", (sign * 0.24, -0.15, 0.075), (0.145, 0.22, 0.085), mats["boots"], segments=24, rings=10, collection_name="OUTFIT"), f"foot.{side}")

    # Calm readable face and hair glimpsed under the hood.
    add(uv_sphere("HAIR_Forelock_BarkBrown", (0, -0.48, 2.31), (0.25, 0.045, 0.12), mats["hair"], segments=22, rings=8, collection_name="HAIR"), "head")
    for side, sign in [("L", -1), ("R", 1)]:
        add(uv_sphere(f"FACE_Eye_{side}_SoftWhite", (sign * 0.13, -0.565, 2.17), (0.065, 0.012, 0.06), mats["eye_white"], segments=18, rings=8, collection_name="FACE"), "head")
        add(uv_sphere(f"FACE_Eye_{side}_ForestIris", (sign * 0.13, -0.58, 2.165), (0.03, 0.007, 0.036), mats["iris"], segments=14, rings=7, collection_name="FACE"), "head")
        add(bevel_curve(f"FACE_Brow_{side}_FocusedLine", [(sign * 0.07, -0.585, 2.25), (sign * 0.19, -0.585, 2.23)], mats["hair"], bevel_depth=0.006, bevel_resolution=1, collection_name="FACE"), "head")
    add(bevel_curve("FACE_Mouth_CalmFocus", [(-0.055, -0.58, 2.04), (0.0, -0.59, 2.028), (0.06, -0.58, 2.04)], mats["hair"], bevel_depth=0.006, bevel_resolution=1, collection_name="FACE"), "head")

    # Quiver, arrows, and bow.
    add(cylinder("PROP_Quiver_OliveTube", (0.38, 0.28, 1.48), 0.105, 0.72, mats["quiver"], vertices=24, rotation=(math.radians(15), math.radians(-13), math.radians(-12)), scale=(1.0, 0.72, 1.0), bevel=0.01, collection_name="PROPS"), "quiver")
    add(cylinder("PROP_Quiver_TanRim", (0.47, 0.37, 1.84), 0.118, 0.045, mats["straps"], vertices=24, rotation=(math.radians(15), math.radians(-13), math.radians(-12)), scale=(1.0, 0.72, 1.0), bevel=0.004, collection_name="PROPS"), "quiver")
    for index, x_offset in enumerate([-0.05, 0.0, 0.05]):
        add_arrow(
            add,
            mats,
            f"PROP_QuiverArrow_{index + 1}",
            (0.43 + x_offset, 0.36, 1.94),
            length=0.46,
            bone_name="quiver",
            rotation=(math.radians(8), math.radians(-8 + index * 4), math.radians(-12)),
        )

    add(bevel_curve("PROP_Bow_WarmWoodArc", [(-1.05, -0.55, 1.82), (-1.22, -0.58, 1.42), (-1.04, -0.55, 0.86)], mats["bow"], bevel_depth=0.026, bevel_resolution=4, collection_name="PROPS"), "bow")
    add(bevel_curve("PROP_Bow_TautString", [(-1.05, -0.565, 1.78), (-0.9, -0.62, 1.33), (-1.04, -0.565, 0.9)], mats["straps"], bevel_depth=0.005, bevel_resolution=1, collection_name="PROPS"), "bow")
    add(cube("PROP_Bow_LeatherGrip", (-1.05, -0.57, 1.32), (0.045, 0.018, 0.09), mats["leather_dark"], bevel=0.012, collection_name="PROPS"), "bow")
    add_arrow(add, mats, "PROP_DrawArrow_Ready", (-0.42, -0.6, 1.32), length=1.16, bone_name="arrow_hand", rotation=(0, math.radians(90), 0))

    # Display base and contact shadow are excluded from Mixamo exports.
    add(cylinder("BASE_DisplayDisc_MatteMossStone", (0, 0, -0.025), 0.78, 0.045, mats["base"], vertices=64, collection_name="BAKED_EFFECTS"), "root")
    add(cylinder("BASE_BakedSoftContactShadow", (0, -0.04, 0.004), 0.6, 0.01, mats["contact"], vertices=64, scale=(1, 0.7, 1), collection_name="BAKED_EFFECTS"), "root")

    for obj in meshes:
        if obj.type == "MESH":
            add_weighted_normals(obj, apply=False)
    return armature, meshes


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


def idle_frames() -> list[tuple[int, dict[str, dict]]]:
    neutral = {
        "pelvis": {"location": (0, 0, 0), "rotation": (0, 0, 0)},
        "spine": {"rotation": (0, 0, 0)},
        "chest": {"rotation": (0, 0, 0)},
        "neck": {"rotation": (0, 0, 0)},
        "head": {"rotation": (0, 0, 0)},
        "hood": {"rotation": (0, 0, 0)},
        "upper_arm.L": {"rotation": (0.1, 0, 0.05)},
        "forearm.L": {"rotation": (-0.08, 0, -0.02)},
        "upper_arm.R": {"rotation": (0.08, 0, -0.04)},
        "forearm.R": {"rotation": (-0.04, 0, 0.02)},
        "bow": {"rotation": (0, 0, 0.02)},
        "arrow_hand": {"rotation": (0, 0, 0)},
        "cloak_back": {"rotation": (0, 0, 0)},
        "cloak.L": {"rotation": (0, 0, 0)},
        "cloak.R": {"rotation": (0, 0, 0)},
    }
    breath = {
        "pelvis": {"location": (0, 0, 0.018), "rotation": (0, 0, -0.01)},
        "spine": {"rotation": (0.018, 0, 0.01)},
        "chest": {"rotation": (0.025, 0, -0.008)},
        "neck": {"rotation": (-0.01, 0, 0.008)},
        "head": {"rotation": (-0.012, 0, -0.012)},
        "hood": {"rotation": (0.018, 0, 0.012)},
        "upper_arm.L": {"rotation": (0.12, 0, 0.07)},
        "forearm.L": {"rotation": (-0.1, 0, -0.028)},
        "upper_arm.R": {"rotation": (0.1, 0, -0.035)},
        "forearm.R": {"rotation": (-0.055, 0, 0.028)},
        "bow": {"rotation": (0, 0, 0.012)},
        "arrow_hand": {"rotation": (0, 0, 0.012)},
        "cloak_back": {"rotation": (0.018, 0, -0.008)},
        "cloak.L": {"rotation": (0.012, 0, 0.025)},
        "cloak.R": {"rotation": (0.012, 0, -0.025)},
    }
    return [(1, neutral), (30, breath), (60, neutral)]


def walk_pose(left_forward: bool, *, bob: float, lean: float) -> dict[str, dict]:
    leg = 1 if left_forward else -1
    return {
        "pelvis": {"location": (0, 0, bob), "rotation": (0, 0, 0.03 * leg)},
        "spine": {"rotation": (0.04 + lean, 0, -0.03 * leg)},
        "chest": {"rotation": (0.03 + lean, 0, 0.03 * leg)},
        "neck": {"rotation": (-0.02 - lean, 0, 0)},
        "head": {"rotation": (-0.02 - lean, 0, 0.018 * leg)},
        "hood": {"rotation": (0.03, 0, 0.025 * leg)},
        "upper_arm.L": {"rotation": (-0.32 * leg + 0.04, 0, 0.05)},
        "forearm.L": {"rotation": (-0.13 * leg, 0, -0.04)},
        "upper_arm.R": {"rotation": (0.34 * leg, 0, -0.045)},
        "forearm.R": {"rotation": (0.12 * leg, 0, 0.03)},
        "thigh.L": {"rotation": (0.45 * leg, 0, 0.02)},
        "shin.L": {"rotation": (-0.3 if left_forward else 0.34, 0, 0)},
        "foot.L": {"rotation": (-0.18 if left_forward else 0.13, 0, 0)},
        "thigh.R": {"rotation": (-0.45 * leg, 0, -0.02)},
        "shin.R": {"rotation": (0.34 if left_forward else -0.3, 0, 0)},
        "foot.R": {"rotation": (0.13 if left_forward else -0.18, 0, 0)},
        "bow": {"rotation": (0, 0, 0.035 * leg)},
        "arrow_hand": {"rotation": (0, 0, 0.02 * leg)},
        "quiver": {"rotation": (0.02, 0, 0.025 * leg)},
        "cloak_back": {"rotation": (0.035, 0, -0.025 * leg)},
        "cloak.L": {"rotation": (0.025, 0, 0.05 * leg)},
        "cloak.R": {"rotation": (0.025, 0, -0.05 * leg)},
    }


def walk_frames() -> list[tuple[int, dict[str, dict]]]:
    passing = {
        "pelvis": {"location": (0, 0, 0.035), "rotation": (0, 0, 0)},
        "spine": {"rotation": (0.032, 0, 0)},
        "chest": {"rotation": (0.025, 0, 0)},
        "neck": {"rotation": (-0.018, 0, 0)},
        "head": {"rotation": (-0.02, 0, 0)},
        "hood": {"rotation": (0.02, 0, 0)},
        "upper_arm.L": {"rotation": (0.04, 0, 0.045)},
        "forearm.L": {"rotation": (0, 0, -0.02)},
        "upper_arm.R": {"rotation": (0.08, 0, -0.04)},
        "forearm.R": {"rotation": (-0.05, 0, 0.025)},
        "thigh.L": {"rotation": (0, 0, 0)},
        "shin.L": {"rotation": (0.17, 0, 0)},
        "foot.L": {"rotation": (0, 0, 0)},
        "thigh.R": {"rotation": (0, 0, 0)},
        "shin.R": {"rotation": (0.17, 0, 0)},
        "foot.R": {"rotation": (0, 0, 0)},
        "bow": {"rotation": (0, 0, 0)},
        "arrow_hand": {"rotation": (0, 0, 0)},
        "quiver": {"rotation": (0.02, 0, 0)},
        "cloak_back": {"rotation": (0.03, 0, 0)},
        "cloak.L": {"rotation": (0.018, 0, 0)},
        "cloak.R": {"rotation": (0.018, 0, 0)},
    }
    return [
        (1, walk_pose(True, bob=0.0, lean=0.008)),
        (9, passing),
        (17, walk_pose(False, bob=0.0, lean=0.008)),
        (25, passing),
        (33, walk_pose(True, bob=0.0, lean=0.008)),
    ]


def run_pose(left_forward: bool, *, bob: float, lean: float) -> dict[str, dict]:
    leg = 1 if left_forward else -1
    return {
        "pelvis": {"location": (0, 0, bob), "rotation": (0, 0, 0.055 * leg)},
        "spine": {"rotation": (0.13 + lean, 0, -0.058 * leg)},
        "chest": {"rotation": (0.1 + lean, 0, 0.05 * leg)},
        "neck": {"rotation": (-0.068 - lean, 0, -0.008 * leg)},
        "head": {"rotation": (-0.075 - lean, 0, 0.025 * leg)},
        "hood": {"rotation": (0.095, 0, 0.055 * leg)},
        "upper_arm.L": {"rotation": (-0.56 * leg + 0.05, 0, 0.08)},
        "forearm.L": {"rotation": (-0.24 * leg, 0, -0.07)},
        "upper_arm.R": {"rotation": (0.56 * leg, 0, -0.08)},
        "forearm.R": {"rotation": (0.22 * leg, 0, 0.06)},
        "thigh.L": {"rotation": (0.72 * leg, 0, 0.035)},
        "shin.L": {"rotation": (-0.54 if left_forward else 0.62, 0, 0)},
        "foot.L": {"rotation": (-0.28 if left_forward else 0.2, 0, 0)},
        "thigh.R": {"rotation": (-0.72 * leg, 0, -0.035)},
        "shin.R": {"rotation": (0.62 if left_forward else -0.54, 0, 0)},
        "foot.R": {"rotation": (0.2 if left_forward else -0.28, 0, 0)},
        "bow": {"rotation": (0, 0, 0.065 * leg)},
        "arrow_hand": {"rotation": (0, 0, 0.04 * leg)},
        "quiver": {"rotation": (0.05, 0, 0.045 * leg)},
        "cloak_back": {"rotation": (0.12, 0, -0.04 * leg)},
        "cloak.L": {"rotation": (0.06, 0, 0.08 * leg)},
        "cloak.R": {"rotation": (0.06, 0, -0.08 * leg)},
    }


def run_frames() -> list[tuple[int, dict[str, dict]]]:
    airborne = {
        "pelvis": {"location": (0, 0, 0.08), "rotation": (0, 0, 0)},
        "spine": {"rotation": (0.12, 0, 0)},
        "chest": {"rotation": (0.1, 0, 0)},
        "neck": {"rotation": (-0.066, 0, 0)},
        "head": {"rotation": (-0.074, 0, 0)},
        "hood": {"rotation": (0.1, 0, 0)},
        "upper_arm.L": {"rotation": (0.05, 0, 0.08)},
        "forearm.L": {"rotation": (-0.12, 0, -0.07)},
        "upper_arm.R": {"rotation": (0.12, 0, -0.08)},
        "forearm.R": {"rotation": (-0.12, 0, 0.06)},
        "thigh.L": {"rotation": (0.1, 0, 0)},
        "shin.L": {"rotation": (0.36, 0, 0)},
        "foot.L": {"rotation": (0.04, 0, 0)},
        "thigh.R": {"rotation": (-0.1, 0, 0)},
        "shin.R": {"rotation": (0.36, 0, 0)},
        "foot.R": {"rotation": (0.04, 0, 0)},
        "bow": {"rotation": (0, 0, 0)},
        "arrow_hand": {"rotation": (0, 0, 0)},
        "quiver": {"rotation": (0.055, 0, 0)},
        "cloak_back": {"rotation": (0.14, 0, 0)},
        "cloak.L": {"rotation": (0.075, 0, 0)},
        "cloak.R": {"rotation": (0.075, 0, 0)},
    }
    return [
        (1, run_pose(True, bob=0.02, lean=0.026)),
        (7, airborne),
        (13, run_pose(False, bob=0.02, lean=0.026)),
        (19, airborne),
        (25, run_pose(True, bob=0.02, lean=0.026)),
    ]


def draw_bow_frames() -> list[tuple[int, dict[str, dict]]]:
    ready = {
        "pelvis": {"rotation": (0, 0, -0.02)},
        "spine": {"rotation": (0.03, 0, 0.02)},
        "chest": {"rotation": (0.04, 0, -0.06)},
        "head": {"rotation": (-0.03, 0, -0.06)},
        "upper_arm.L": {"rotation": (-0.22, 0.05, 0.34)},
        "forearm.L": {"rotation": (-0.28, 0.0, -0.2)},
        "hand.L": {"rotation": (0, 0, 0.08)},
        "bow": {"rotation": (0.0, -0.02, 0.08)},
        "upper_arm.R": {"rotation": (0.02, 0.0, -0.15)},
        "forearm.R": {"rotation": (-0.12, 0.0, 0.16)},
        "hand.R": {"rotation": (0, 0, 0.06)},
        "arrow_hand": {"location": (0, 0, 0.0), "rotation": (0, 0, 0.02)},
        "cloak_back": {"rotation": (0.05, 0, 0.02)},
    }
    drawn = {
        "pelvis": {"rotation": (0, 0, -0.045)},
        "spine": {"rotation": (0.05, 0, 0.035)},
        "chest": {"rotation": (0.055, 0, -0.12)},
        "neck": {"rotation": (-0.02, 0, 0.04)},
        "head": {"rotation": (-0.04, 0, -0.11)},
        "upper_arm.L": {"rotation": (-0.34, 0.06, 0.46)},
        "forearm.L": {"rotation": (-0.4, 0.02, -0.28)},
        "hand.L": {"rotation": (0, 0, 0.12)},
        "bow": {"rotation": (0.0, -0.035, 0.13)},
        "upper_arm.R": {"rotation": (-0.2, 0.0, -0.34)},
        "forearm.R": {"rotation": (-0.5, 0.0, 0.36)},
        "hand.R": {"rotation": (0, 0, 0.12)},
        "arrow_hand": {"location": (0.16, 0.02, 0.02), "rotation": (0, 0, 0.04)},
        "quiver": {"rotation": (0.02, 0, -0.02)},
        "cloak_back": {"rotation": (0.07, 0, 0.03)},
    }
    return [(1, ready), (18, drawn), (36, drawn)]


def aim_frames() -> list[tuple[int, dict[str, dict]]]:
    aim = draw_bow_frames()[1][1]
    aim_breath = {**aim, "chest": {"rotation": (0.06, 0, -0.13)}, "head": {"rotation": (-0.045, 0, -0.105)}, "arrow_hand": {"location": (0.17, 0.018, 0.023), "rotation": (0, 0, 0.035)}}
    return [(1, aim), (25, aim_breath), (50, aim)]


def shoot_frames() -> list[tuple[int, dict[str, dict]]]:
    held = draw_bow_frames()[1][1]
    released = {
        "pelvis": {"rotation": (0, 0, -0.025)},
        "spine": {"rotation": (0.035, 0, 0.02)},
        "chest": {"rotation": (0.04, 0, -0.07)},
        "neck": {"rotation": (-0.015, 0, 0.02)},
        "head": {"rotation": (-0.035, 0, -0.055)},
        "upper_arm.L": {"rotation": (-0.34, 0.06, 0.44)},
        "forearm.L": {"rotation": (-0.38, 0.02, -0.25)},
        "bow": {"rotation": (0, -0.02, 0.18)},
        "upper_arm.R": {"rotation": (0.02, 0, -0.22)},
        "forearm.R": {"rotation": (-0.08, 0, 0.22)},
        "hand.R": {"rotation": (0, 0, 0.04)},
        "arrow_hand": {"location": (-0.32, -0.03, 0.0), "rotation": (0, 0, -0.02)},
        "cloak_back": {"rotation": (0.08, 0, -0.02)},
    }
    recover = {
        **released,
        "chest": {"rotation": (0.035, 0, -0.05)},
        "head": {"rotation": (-0.03, 0, -0.045)},
        "bow": {"rotation": (0, -0.015, 0.1)},
        "arrow_hand": {"location": (0, 0, 0), "rotation": (0, 0, 0)},
    }
    return [(1, held), (6, released), (22, recover), (38, recover)]


def add_actions(armature: bpy.types.Object) -> None:
    clear_nla_tracks(armature, CLIPS)
    remove_actions(CLIPS)
    actions = [
        (create_pose_action(armature, "Idle_Stationary", idle_frames()), 1, 60),
        (create_pose_action(armature, "Walk_InPlace", walk_frames()), 1, 33),
        (create_pose_action(armature, "Run_InPlace", run_frames()), 1, 25),
        (create_pose_action(armature, "DrawBow", draw_bow_frames()), 1, 36),
        (create_pose_action(armature, "Aim_Hold", aim_frames()), 1, 50),
        (create_pose_action(armature, "Shoot_Release", shoot_frames()), 1, 38),
    ]
    for action, start, end in actions:
        push_action_to_nla(armature, action, start, end)


def is_mixamo_excluded(obj: bpy.types.Object) -> bool:
    name = obj.name.lower()
    return (
        name.startswith("base_")
        or "displaydisc" in name
        or "contactshadow" in name
        or "contact_shadow" in name
    )


def mixamo_objects() -> list[bpy.types.Object]:
    return armature_objects() + [obj for obj in mesh_objects() if not is_mixamo_excluded(obj)]


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
    obj_path = work_dir / f"{ASSET_SLUG}-mixamo.obj"

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


def setup_lighting_and_camera() -> None:
    world = bpy.context.scene.world or bpy.data.worlds.new("World")
    bpy.context.scene.world = world
    world.color = (0.02, 0.026, 0.022)

    camera_data = bpy.data.cameras.new("CAM_ForestRangerNPC_Preview")
    camera = bpy.data.objects.new("CAM_ForestRangerNPC_Preview", camera_data)
    bpy.context.scene.collection.objects.link(camera)
    camera.location = (2.75, -6.55, 2.15)
    camera.data.lens = 52
    camera.data.dof.use_dof = True
    camera.data.dof.focus_distance = 6.55
    camera.data.dof.aperture_fstop = 5.6
    look_at(camera, (-0.12, -0.18, 1.34))
    bpy.context.scene.camera = camera
    for source in list(camera.users_collection):
        source.objects.unlink(camera)
    collection("LIGHTING_CAMERA").objects.link(camera)

    lights = [
        ("LGT_Key_WarmCanopySoftbox", "AREA", (-2.6, -3.45, 4.0), 560, 4.4),
        ("LGT_Rim_CoolForestEdge", "AREA", (2.85, 1.45, 2.9), 210, 2.4),
        ("LGT_Fill_AmberLeatherBounce", "POINT", (1.6, -2.05, 1.65), 85, 0),
    ]
    for name, kind, loc, energy, size in lights:
        data = bpy.data.lights.new(name, kind)
        obj = bpy.data.objects.new(name, data)
        bpy.context.scene.collection.objects.link(obj)
        obj.location = loc
        data.energy = energy
        if hasattr(data, "size") and size:
            data.size = size
        look_at(obj, (0.0, -0.12, 1.35))
        for source in list(obj.users_collection):
            source.objects.unlink(obj)
        collection("LIGHTING_CAMERA").objects.link(obj)


def configure_scene() -> None:
    scene = bpy.context.scene
    scene.name = "SCN_ForestRangerNPC"
    scene.unit_settings.system = "METRIC"
    scene.frame_start = 1
    scene.frame_end = 60
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


def collect_metadata(paths: dict[str, Path]) -> dict:
    meshes = mesh_objects()
    geometries = geometry_objects()
    armatures = armature_objects()
    actions = sorted(action.name for action in bpy.data.actions)
    return {
        "asset": ASSET_NAME,
        "slug": ASSET_SLUG,
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
            "default": "Idle_Stationary",
            "embedded_in_glb": True,
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
            "mixamo_fbx_bytes": file_size(paths["mixamo_fbx"]),
            "mixamo_obj_zip_bytes": file_size(paths["mixamo_obj_zip"]),
        },
        "export": {
            "format": "GLB",
            "export_yup": True,
            "applied_export_transforms": True,
            "animations": True,
            "source": "Blender MCP live bridge or configured background Blender",
        },
        "exports": {
            "mixamo_fbx": relative(paths["mixamo_fbx"]),
            "mixamo_obj_zip": relative(paths["mixamo_obj_zip"]),
        },
        "armature": {
            "objects": [arm.name for arm in armatures],
            "bones": sorted({bone.name for arm in armatures for bone in arm.data.bones}),
            "rig_depth": "basic humanoid Mixamo best-effort armature with whole-part vertex groups",
        },
        "notes": [
            "Original stylized fantasy adventure ranger with hooded cloak, leather armor, pouches, quiver, bow, gloves, boots, and calm focused face.",
            "Embedded GLB clips: Idle_Stationary, Walk_InPlace, Run_InPlace, DrawBow, Aim_Hold, and Shoot_Release.",
            "Mixamo FBX and OBJ ZIP are best-effort exports; stylized proportions, bow/quiver geometry, cloak pieces, and whole-part weights may need manual Mixamo adjustment.",
            MIXAMO_ORIENTATION_NOTE,
            "Display base and contact-shadow extras are excluded from Mixamo exports.",
        ],
    }


def export_asset(paths: dict[str, Path]) -> None:
    ensure_dir(paths["blend"].parent)
    ensure_dir(paths["glb"].parent)
    ensure_dir(paths["preview"].parent)
    ensure_dir(paths["textures"])
    ensure_dir(paths["exports"])

    for block in (bpy.data.materials, bpy.data.curves, bpy.data.images):
        for item in list(block):
            if item.users == 0:
                block.remove(item)

    bpy.ops.wm.save_as_mainfile(filepath=str(paths["blend"]))
    export_glb(paths["glb"], armature_objects() + mesh_objects())
    mixamo = mixamo_objects()
    export_mixamo_fbx(paths["mixamo_fbx"], mixamo)
    export_mixamo_obj_zip(paths["mixamo_obj_zip"], paths["obj_work"], mixamo)

    bpy.context.scene.render.filepath = str(paths["preview"])
    bpy.ops.render.render(write_still=True)


def main() -> dict:
    paths = out_paths()
    clear_scene()
    configure_scene()
    mats = make_materials()
    armature, _meshes = build_character(mats)
    add_actions(armature)
    setup_lighting_and_camera()
    export_asset(paths)
    metadata = collect_metadata(paths)
    write_json(paths["metadata"], metadata)
    return metadata


if __name__ == "__main__":
    result = main()
    print(json.dumps(result, indent=2))
