"""Generate the Village Blacksmith NPC asset in Blender.

Run from Blender Python through the live MCP bridge. The script is repeatable:
it creates the source scene, embeds web animation clips, exports the GLB,
writes Mixamo best-effort exports, renders a preview, and writes metadata.
"""

from __future__ import annotations

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
    add_bevel,
    add_weighted_normals,
    bevel_curve,
    bounds_for_objects,
    clear_scene,
    collection,
    cube,
    cylinder,
    ensure_dir,
    look_at,
    make_mat,
    scene_triangle_count,
    uv_sphere,
    write_json,
)

ASSET_SLUG = "village-blacksmith-npc"
ASSET_NAME = "Village Blacksmith NPC"
CLIPS = ("Idle_Stationary", "Walk_InPlace", "Hammering_Loop", "Talking_Gesture")
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
        "skin": make_mat("MAT_Skin_WarmBlacksmith", (0.94, 0.58, 0.38, 1), roughness=0.8),
        "blush": make_mat("MAT_Skin_RuddyForgeBlush", (0.9, 0.26, 0.18, 0.62), roughness=0.84, alpha=0.62),
        "hair": make_mat("MAT_Hair_BeardDeepBrown", (0.16, 0.075, 0.032, 1), roughness=0.78),
        "shirt": make_mat("MAT_Cloth_RolledGrayShirt", (0.47, 0.49, 0.5, 1), roughness=0.86),
        "shirt_dark": make_mat("MAT_Cloth_DarkFoldGray", (0.25, 0.27, 0.28, 1), roughness=0.9),
        "apron": make_mat("MAT_Leather_DarkBrownApron", (0.28, 0.13, 0.055, 1), roughness=0.8),
        "apron_worn": make_mat("MAT_Leather_WornApronEdges", (0.48, 0.25, 0.12, 1), roughness=0.82),
        "glove": make_mat("MAT_Gloves_BlackenedLeather", (0.045, 0.04, 0.035, 1), roughness=0.88),
        "boots": make_mat("MAT_Boots_DarkForgeLeather", (0.09, 0.055, 0.034, 1), roughness=0.84),
        "steel": make_mat("MAT_Prop_HammerBrushedSteel", (0.58, 0.6, 0.62, 1), roughness=0.42, metallic=0.45),
        "blackened_steel": make_mat("MAT_Prop_BlackenedSteel", (0.12, 0.13, 0.13, 1), roughness=0.58, metallic=0.34),
        "wood": make_mat("MAT_Prop_HammerHandleOak", (0.52, 0.29, 0.13, 1), roughness=0.7),
        "brass": make_mat("MAT_Metal_AgedBrassBuckle", (0.72, 0.48, 0.2, 1), roughness=0.5, metallic=0.24),
        "base": make_mat("MAT_Base_ForgeSlate", (0.09, 0.095, 0.09, 1), roughness=0.88),
        "contact": make_mat("MAT_Shadow_BakedSoftContact", (0.022, 0.02, 0.018, 0.56), roughness=0.9, alpha=0.56),
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
    armature.name = "RIG_VillageBlacksmithNPC_BasicArmature"
    armature.data.name = "ARM_VillageBlacksmithNPC_Humanoid"
    armature.show_in_front = True
    link_collection = collection("RIG")
    for source in list(armature.users_collection):
        source.objects.unlink(armature)
    link_collection.objects.link(armature)

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

    bone("pelvis", (0, 0, 0.5), (0, 0, 0.84), "root")
    bone("spine", (0, 0, 0.84), (0, -0.015, 1.38), "pelvis")
    bone("chest", (0, -0.015, 1.38), (0, -0.02, 1.78), "spine")
    bone("neck", (0, -0.02, 1.78), (0, -0.02, 1.98), "chest")
    bone("head", (0, -0.02, 1.98), (0, -0.04, 2.66), "neck")
    bone("hair_beard", (0, -0.03, 2.16), (0, -0.04, 2.82), "head")
    bone("upper_arm.L", (-0.44, -0.02, 1.58), (-0.78, -0.12, 1.22), "chest")
    bone("forearm.L", (-0.78, -0.12, 1.22), (-1.02, -0.26, 0.9), "upper_arm.L")
    bone("hand.L", (-1.02, -0.26, 0.9), (-1.15, -0.34, 0.8), "forearm.L")
    bone("upper_arm.R", (0.44, -0.02, 1.58), (0.78, -0.14, 1.22), "chest")
    bone("forearm.R", (0.78, -0.14, 1.22), (1.02, -0.32, 0.96), "upper_arm.R")
    bone("hand.R", (1.02, -0.32, 0.96), (1.14, -0.42, 0.88), "forearm.R")
    bone("hammer", (1.12, -0.44, 1.0), (1.42, -0.74, 1.3), "hand.R")
    bone("thigh.L", (-0.22, 0.0, 0.56), (-0.28, -0.02, 0.26), "pelvis")
    bone("shin.L", (-0.28, -0.02, 0.26), (-0.28, -0.04, 0.08), "thigh.L")
    bone("foot.L", (-0.28, -0.04, 0.08), (-0.3, -0.32, 0.04), "shin.L")
    bone("thigh.R", (0.22, 0.0, 0.56), (0.28, -0.02, 0.26), "pelvis")
    bone("shin.R", (0.28, -0.02, 0.26), (0.28, -0.04, 0.08), "thigh.R")
    bone("foot.R", (0.28, -0.04, 0.08), (0.3, -0.32, 0.04), "shin.R")
    bone("tool_belt", (0, -0.22, 0.98), (0.0, -0.34, 0.72), "pelvis")

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

    # Broad body and worn work clothes.
    add(uv_sphere("CHR_Head_RuddySquareJaw", (0, -0.05, 2.34), (0.5, 0.45, 0.52), mats["skin"], segments=36, rings=18, collection_name="CHARACTER_BODY"), "head")
    add(uv_sphere("CHR_Nose_StrongProfile", (0, -0.48, 2.32), (0.075, 0.07, 0.105), mats["skin"], segments=16, rings=8, collection_name="FACE"), "head")
    add(uv_sphere("CHR_Chest_BroadGrayShirt", (0, -0.005, 1.42), (0.52, 0.34, 0.44), mats["shirt"], segments=36, rings=18, collection_name="CHARACTER_BODY"), "chest")
    add(uv_sphere("CHR_Belly_SturdyCore", (0, 0.0, 1.04), (0.48, 0.32, 0.34), mats["shirt"], segments=32, rings=16, collection_name="CHARACTER_BODY"), "spine")
    add(uv_sphere("CHR_Hips_WorkPantsUnderApron", (0, 0.01, 0.72), (0.43, 0.29, 0.24), mats["shirt_dark"], segments=28, rings=12, collection_name="CHARACTER_BODY"), "pelvis")

    add(cube("OUT_Apron_BroadDarkLeatherPanel", (0, -0.35, 1.13), (0.42, 0.035, 0.62), mats["apron"], bevel=0.035, collection_name="OUTFIT"), "spine")
    add(cube("OUT_Apron_LowerSplitLeatherPanel", (0, -0.33, 0.66), (0.36, 0.03, 0.34), mats["apron"], bevel=0.028, collection_name="OUTFIT"), "pelvis")
    add(bevel_curve("OUT_Apron_LeftWornEdge", [(-0.42, -0.37, 1.55), (-0.38, -0.36, 1.08), (-0.31, -0.34, 0.48)], mats["apron_worn"], bevel_depth=0.011, bevel_resolution=2, collection_name="OUTFIT"), "spine")
    add(bevel_curve("OUT_Apron_RightWornEdge", [(0.42, -0.37, 1.55), (0.38, -0.36, 1.08), (0.31, -0.34, 0.48)], mats["apron_worn"], bevel_depth=0.011, bevel_resolution=2, collection_name="OUTFIT"), "spine")
    add(bevel_curve("OUT_Apron_NeckStrap", [(-0.22, -0.36, 1.72), (0, -0.39, 1.83), (0.22, -0.36, 1.72)], mats["apron_worn"], bevel_depth=0.018, bevel_resolution=3, collection_name="OUTFIT"), "chest")

    for side, sign in [("L", -1), ("R", 1)]:
        upper_points = [
            (sign * 0.5, -0.03, 1.47),
            (sign * 0.68, -0.08, 1.32),
            (sign * 0.82, -0.14, 1.16),
        ]
        forearm_points = [
            (sign * 0.82, -0.14, 1.16),
            (sign * 0.96, -0.22, 0.98),
            (sign * 1.09, -0.32, 0.82),
        ]
        add(uv_sphere(f"CHR_Shoulder_{side}_MuscularSleeve", (sign * 0.48, -0.035, 1.55), (0.19, 0.14, 0.17), mats["shirt"], segments=24, rings=10, collection_name="OUTFIT"), f"upper_arm.{side}")
        add(bevel_curve(f"CHR_UpperArm_{side}_RolledGraySleeve", upper_points, mats["shirt"], bevel_depth=0.082, bevel_resolution=4, collection_name="CHARACTER_BODY"), f"upper_arm.{side}")
        add(bevel_curve(f"CHR_RolledSleeveCuff_{side}_DarkFold", [(sign * 0.75, -0.12, 1.2), (sign * 0.83, -0.15, 1.15), (sign * 0.9, -0.18, 1.08)], mats["shirt_dark"], bevel_depth=0.026, bevel_resolution=3, collection_name="OUTFIT"), f"upper_arm.{side}")
        add(bevel_curve(f"CHR_Forearm_{side}_StrongSkin", forearm_points, mats["skin"], bevel_depth=0.077, bevel_resolution=4, collection_name="CHARACTER_BODY"), f"forearm.{side}")
        add(uv_sphere(f"OUT_Glove_{side}_BlackenedWorkMitt", (sign * 1.13, -0.36, 0.79), (0.13, 0.1, 0.105), mats["glove"], segments=22, rings=10, collection_name="OUTFIT"), f"hand.{side}")
        add(uv_sphere(f"CHR_Thigh_{side}_HeavyWorkPants", (sign * 0.22, -0.01, 0.38), (0.14, 0.115, 0.28), mats["shirt_dark"], segments=22, rings=10, collection_name="CHARACTER_BODY"), f"thigh.{side}")
        add(uv_sphere(f"CHR_Shin_{side}_DarkPants", (sign * 0.27, -0.025, 0.19), (0.11, 0.095, 0.18), mats["shirt_dark"], segments=20, rings=10, collection_name="CHARACTER_BODY"), f"shin.{side}")
        add(uv_sphere(f"OUT_Boot_{side}_HeavyForgeBoot", (sign * 0.3, -0.16, 0.075), (0.18, 0.27, 0.095), mats["boots"], segments=24, rings=10, collection_name="OUTFIT"), f"foot.{side}")
        add(cube(f"OUT_Boot_{side}_SteelToeScuff", (sign * 0.3, -0.36, 0.08), (0.11, 0.025, 0.035), mats["blackened_steel"], bevel=0.01, collection_name="OUTFIT"), f"foot.{side}")

    # Face, hair, and beard silhouette.
    for side, sign in [("L", -1), ("R", 1)]:
        add(uv_sphere(f"FACE_Eye_{side}_DeepSetWarmWhite", (sign * 0.17, -0.48, 2.42), (0.095, 0.018, 0.07), mats["shirt"], segments=18, rings=8, collection_name="FACE"), "head")
        add(uv_sphere(f"FACE_Eye_{side}_DarkPupil", (sign * 0.17, -0.497, 2.415), (0.034, 0.007, 0.03), mats["blackened_steel"], segments=12, rings=6, collection_name="FACE"), "head")
        add(uv_sphere(f"FACE_Cheek_{side}_ForgeRuddy", (sign * 0.31, -0.45, 2.25), (0.075, 0.009, 0.035), mats["blush"], segments=14, rings=6, collection_name="BAKED_EFFECTS"), "head")
        add(bevel_curve(f"FACE_Brow_{side}_Thick", [(sign * 0.08, -0.51, 2.54), (sign * 0.22, -0.51, 2.55), (sign * 0.32, -0.49, 2.53)], mats["hair"], bevel_depth=0.014, bevel_resolution=2, collection_name="FACE"), "head")

    add(bevel_curve("FACE_Mouth_BeardHiddenSmile", [(-0.07, -0.51, 2.15), (0, -0.525, 2.13), (0.08, -0.51, 2.15)], mats["blackened_steel"], bevel_depth=0.007, bevel_resolution=2, collection_name="FACE"), "head")
    add(uv_sphere("HAIR_Cap_SweptBrown", (0, 0.0, 2.62), (0.52, 0.44, 0.2), mats["hair"], segments=32, rings=12, collection_name="HAIR"), "hair_beard")
    add(uv_sphere("HAIR_Beard_FullRoundedMass", (0, -0.38, 2.08), (0.34, 0.15, 0.28), mats["hair"], segments=30, rings=12, collection_name="HAIR"), "hair_beard")
    for index, x in enumerate([-0.22, -0.11, 0.0, 0.11, 0.22], start=1):
        add(bevel_curve(f"HAIR_Beard_BraidedStrand_{index}", [(x, -0.48, 2.2), (x * 0.8, -0.5, 2.03), (x * 0.55, -0.45, 1.86)], mats["hair"], bevel_depth=0.024, bevel_resolution=3, collection_name="HAIR"), "hair_beard")
    add(bevel_curve("HAIR_Moustache_LeftSweep", [(-0.03, -0.53, 2.22), (-0.19, -0.55, 2.2), (-0.31, -0.49, 2.19)], mats["hair"], bevel_depth=0.026, bevel_resolution=3, collection_name="HAIR"), "hair_beard")
    add(bevel_curve("HAIR_Moustache_RightSweep", [(0.03, -0.53, 2.22), (0.19, -0.55, 2.2), (0.31, -0.49, 2.19)], mats["hair"], bevel_depth=0.026, bevel_resolution=3, collection_name="HAIR"), "hair_beard")

    # Tool belt, pouches, and small smithing tools.
    add(bevel_curve("OUT_ToolBelt_DarkLeatherWrap", [(-0.44, -0.3, 0.98), (-0.1, -0.34, 0.93), (0.44, -0.3, 0.98)], mats["apron_worn"], bevel_depth=0.025, bevel_resolution=3, collection_name="OUTFIT"), "tool_belt")
    add(cube("OUT_ToolBelt_BrassBuckle", (0, -0.38, 0.95), (0.085, 0.018, 0.065), mats["brass"], bevel=0.012, collection_name="OUTFIT"), "tool_belt")
    add(cube("PROP_ToolBelt_LeftPouch", (-0.42, -0.29, 0.82), (0.1, 0.055, 0.14), mats["apron"], bevel=0.018, collection_name="PROPS"), "tool_belt")
    add(cube("PROP_ToolBelt_RightPouch", (0.44, -0.29, 0.82), (0.1, 0.055, 0.14), mats["apron"], bevel=0.018, collection_name="PROPS"), "tool_belt")
    add(cylinder("PROP_ToolBelt_TongsHandle", (-0.58, -0.32, 0.88), 0.012, 0.32, mats["blackened_steel"], vertices=12, rotation=(math.radians(15), 0, math.radians(-12)), bevel=0.002, collection_name="PROPS"), "tool_belt")
    add(cylinder("PROP_ToolBelt_PunchTool", (0.58, -0.32, 0.88), 0.014, 0.26, mats["steel"], vertices=12, rotation=(math.radians(10), 0, math.radians(12)), bevel=0.002, collection_name="PROPS"), "tool_belt")

    # Hammer, carried clearly at the right side for a readable silhouette.
    add(cylinder("PROP_Hammer_OakHandle", (1.28, -0.63, 1.12), 0.035, 0.62, mats["wood"], vertices=18, rotation=(math.radians(48), 0, math.radians(-42)), bevel=0.006, collection_name="PROPS"), "hammer")
    add(cube("PROP_Hammer_SteelHead_Block", (1.53, -0.86, 1.37), (0.25, 0.11, 0.1), mats["steel"], bevel=0.026, collection_name="PROPS"), "hammer")
    add(cube("PROP_Hammer_BlackenedStrikingFace_L", (1.34, -0.72, 1.28), (0.055, 0.055, 0.07), mats["blackened_steel"], bevel=0.012, collection_name="PROPS"), "hammer")
    add(cube("PROP_Hammer_BlackenedStrikingFace_R", (1.7, -0.98, 1.46), (0.055, 0.055, 0.07), mats["blackened_steel"], bevel=0.012, collection_name="PROPS"), "hammer")

    # Display base and soft contact shadow are excluded from Mixamo exports.
    add(cylinder("BASE_DisplayDisc_ForgeSlate", (0, 0, -0.025), 0.82, 0.045, mats["base"], vertices=64, collection_name="BAKED_EFFECTS"), "root")
    add(cylinder("BASE_BakedSoftContactShadow", (0, -0.04, 0.004), 0.6, 0.01, mats["contact"], vertices=64, scale=(1, 0.72, 1), collection_name="BAKED_EFFECTS"), "root")

    for obj in meshes:
        if obj.type == "MESH":
            add_weighted_normals(obj)
            if obj.name.startswith(("OUT_Apron", "PROP_Hammer")):
                add_bevel(obj, 0.002, 1, apply=True)

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
        "head": {"rotation": (0, 0, 0)},
        "hair_beard": {"rotation": (0, 0, 0)},
        "upper_arm.L": {"rotation": (0.02, 0, 0.08)},
        "forearm.L": {"rotation": (-0.03, 0, -0.04)},
        "upper_arm.R": {"rotation": (0.1, 0, -0.06)},
        "forearm.R": {"rotation": (-0.08, 0, 0.02)},
        "hammer": {"rotation": (0, 0, 0)},
        "tool_belt": {"rotation": (0, 0, 0)},
    }
    inhale = {
        "pelvis": {"location": (0, 0, 0.018), "rotation": (0, 0, -0.008)},
        "spine": {"rotation": (0.025, 0, 0.012)},
        "chest": {"rotation": (0.035, 0, 0.014)},
        "head": {"rotation": (-0.018, 0, -0.012)},
        "hair_beard": {"rotation": (0.018, 0, 0.018)},
        "upper_arm.L": {"rotation": (0.04, 0, 0.07)},
        "forearm.L": {"rotation": (-0.02, 0, -0.03)},
        "upper_arm.R": {"rotation": (0.12, 0, -0.07)},
        "forearm.R": {"rotation": (-0.1, 0, 0.035)},
        "hammer": {"rotation": (0.02, 0, 0.025)},
        "tool_belt": {"rotation": (0, 0, 0.02)},
    }
    return [(1, neutral), (30, inhale), (60, neutral)]


def walk_pose(left_forward: bool, *, bob: float = 0.0) -> dict[str, dict]:
    leg = 1 if left_forward else -1
    return {
        "pelvis": {"location": (0, 0, bob), "rotation": (0, 0, 0.035 * leg)},
        "spine": {"rotation": (0.04, 0, -0.035 * leg)},
        "chest": {"rotation": (0.05, 0, -0.045 * leg)},
        "head": {"rotation": (-0.025, 0, 0.022 * leg)},
        "hair_beard": {"rotation": (0.025, 0, 0.03 * leg)},
        "upper_arm.L": {"rotation": (-0.38 * leg, 0, 0.08)},
        "forearm.L": {"rotation": (-0.13 * leg, 0, -0.04)},
        "upper_arm.R": {"rotation": (0.34 * leg, 0, -0.08)},
        "forearm.R": {"rotation": (0.12 * leg, 0, 0.04)},
        "hammer": {"rotation": (0.08 * leg, 0, 0.09 * leg)},
        "thigh.L": {"rotation": (0.42 * leg, 0, 0.02)},
        "shin.L": {"rotation": (-0.26 if left_forward else 0.32, 0, 0)},
        "foot.L": {"rotation": (-0.16 if left_forward else 0.12, 0, 0)},
        "thigh.R": {"rotation": (-0.42 * leg, 0, -0.02)},
        "shin.R": {"rotation": (0.32 if left_forward else -0.26, 0, 0)},
        "foot.R": {"rotation": (0.12 if left_forward else -0.16, 0, 0)},
        "tool_belt": {"rotation": (0, 0, -0.055 * leg)},
    }


def walk_frames() -> list[tuple[int, dict[str, dict]]]:
    passing = {
        "pelvis": {"location": (0, 0, 0.035), "rotation": (0, 0, 0)},
        "spine": {"rotation": (0.035, 0, 0)},
        "chest": {"rotation": (0.04, 0, 0)},
        "head": {"rotation": (-0.02, 0, 0)},
        "hair_beard": {"rotation": (0.02, 0, 0)},
        "upper_arm.L": {"rotation": (0, 0, 0.06)},
        "forearm.L": {"rotation": (0, 0, -0.03)},
        "upper_arm.R": {"rotation": (0, 0, -0.06)},
        "forearm.R": {"rotation": (0, 0, 0.03)},
        "hammer": {"rotation": (0, 0, 0)},
        "thigh.L": {"rotation": (0, 0, 0)},
        "shin.L": {"rotation": (0.16, 0, 0)},
        "foot.L": {"rotation": (0, 0, 0)},
        "thigh.R": {"rotation": (0, 0, 0)},
        "shin.R": {"rotation": (0.16, 0, 0)},
        "foot.R": {"rotation": (0, 0, 0)},
        "tool_belt": {"rotation": (0, 0, 0)},
    }
    return [
        (1, walk_pose(True, bob=0.0)),
        (9, passing),
        (17, walk_pose(False, bob=0.0)),
        (25, passing),
        (33, walk_pose(True, bob=0.0)),
    ]


def hammering_frames() -> list[tuple[int, dict[str, dict]]]:
    windup = {
        "pelvis": {"location": (0, 0, 0.01), "rotation": (0.02, 0, -0.02)},
        "spine": {"rotation": (-0.08, 0, 0.04)},
        "chest": {"rotation": (-0.16, 0, 0.07)},
        "head": {"rotation": (0.08, 0, -0.04)},
        "upper_arm.R": {"rotation": (-0.85, 0, -0.4)},
        "forearm.R": {"rotation": (-0.58, 0, 0.22)},
        "hand.R": {"rotation": (-0.12, 0, 0.06)},
        "hammer": {"rotation": (-0.42, 0, -0.48)},
        "upper_arm.L": {"rotation": (-0.18, 0, 0.42)},
        "forearm.L": {"rotation": (-0.3, 0, -0.18)},
        "tool_belt": {"rotation": (0, 0, 0.025)},
    }
    strike = {
        "pelvis": {"location": (0, 0, -0.005), "rotation": (0.06, 0, 0.035)},
        "spine": {"rotation": (0.18, 0, -0.05)},
        "chest": {"rotation": (0.28, 0, -0.1)},
        "head": {"rotation": (-0.1, 0, 0.045)},
        "upper_arm.R": {"rotation": (0.44, 0, -0.18)},
        "forearm.R": {"rotation": (0.32, 0, 0.06)},
        "hand.R": {"rotation": (0.1, 0, -0.04)},
        "hammer": {"rotation": (0.52, 0, 0.2)},
        "upper_arm.L": {"rotation": (0.06, 0, 0.32)},
        "forearm.L": {"rotation": (-0.18, 0, -0.14)},
        "tool_belt": {"rotation": (0, 0, -0.025)},
    }
    recover = {
        "pelvis": {"location": (0, 0, 0.012), "rotation": (0.02, 0, 0)},
        "spine": {"rotation": (0.04, 0, 0.01)},
        "chest": {"rotation": (0.02, 0, 0.02)},
        "head": {"rotation": (-0.02, 0, 0)},
        "upper_arm.R": {"rotation": (-0.12, 0, -0.22)},
        "forearm.R": {"rotation": (-0.06, 0, 0.12)},
        "hand.R": {"rotation": (0, 0, 0)},
        "hammer": {"rotation": (0.06, 0, -0.12)},
        "upper_arm.L": {"rotation": (0, 0, 0.32)},
        "forearm.L": {"rotation": (-0.2, 0, -0.12)},
        "tool_belt": {"rotation": (0, 0, 0)},
    }
    return [(1, windup), (14, strike), (24, recover), (36, windup)]


def talking_frames() -> list[tuple[int, dict[str, dict]]]:
    settle = {
        "pelvis": {"location": (0, 0, 0), "rotation": (0, 0, 0)},
        "spine": {"rotation": (0.025, 0, 0.02)},
        "chest": {"rotation": (0.04, 0, 0.03)},
        "head": {"rotation": (-0.03, 0, -0.02)},
        "hair_beard": {"rotation": (0.01, 0, -0.012)},
        "upper_arm.L": {"rotation": (-0.1, 0, 0.28)},
        "forearm.L": {"rotation": (-0.16, 0, -0.18)},
        "hand.L": {"rotation": (0, 0, -0.08)},
        "upper_arm.R": {"rotation": (0.1, 0, -0.06)},
        "forearm.R": {"rotation": (-0.08, 0, 0.02)},
        "hammer": {"rotation": (0, 0, 0)},
    }
    gesture = {
        "pelvis": {"location": (0, 0, 0.012), "rotation": (0, 0, -0.012)},
        "spine": {"rotation": (0.045, 0, -0.025)},
        "chest": {"rotation": (0.055, 0, -0.035)},
        "head": {"rotation": (-0.025, 0, 0.035)},
        "hair_beard": {"rotation": (0.022, 0, 0.025)},
        "upper_arm.L": {"rotation": (-0.42, 0, 0.42)},
        "forearm.L": {"rotation": (-0.46, 0, -0.22)},
        "hand.L": {"rotation": (0.12, 0, -0.2)},
        "upper_arm.R": {"rotation": (0.12, 0, -0.08)},
        "forearm.R": {"rotation": (-0.1, 0, 0.04)},
        "hammer": {"rotation": (0.02, 0, 0.02)},
    }
    return [(1, settle), (18, gesture), (36, settle), (54, gesture), (72, settle)]


def add_actions(armature: bpy.types.Object) -> None:
    clear_nla_tracks(armature, CLIPS)
    remove_actions(CLIPS)
    idle = create_pose_action(armature, "Idle_Stationary", idle_frames())
    walk = create_pose_action(armature, "Walk_InPlace", walk_frames())
    hammer = create_pose_action(armature, "Hammering_Loop", hammering_frames())
    talk = create_pose_action(armature, "Talking_Gesture", talking_frames())
    push_action_to_nla(armature, idle, 1, 60)
    push_action_to_nla(armature, walk, 1, 33)
    push_action_to_nla(armature, hammer, 1, 36)
    push_action_to_nla(armature, talk, 1, 72)


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
    world.color = (0.028, 0.027, 0.024)

    camera_data = bpy.data.cameras.new("CAM_VillageBlacksmithNPC_Preview")
    camera = bpy.data.objects.new("CAM_VillageBlacksmithNPC_Preview", camera_data)
    bpy.context.scene.collection.objects.link(camera)
    camera.location = (2.3, -6.4, 2.22)
    camera.data.lens = 54
    camera.data.dof.use_dof = True
    camera.data.dof.focus_distance = 6.2
    camera.data.dof.aperture_fstop = 5.6
    look_at(camera, (0.28, -0.22, 1.42))
    bpy.context.scene.camera = camera
    for source in list(camera.users_collection):
        source.objects.unlink(camera)
    collection("LIGHTING_CAMERA").objects.link(camera)

    lights = [
        ("LGT_Key_WarmForgeSoftbox", "AREA", (-2.4, -3.4, 4.2), 520, 4.2),
        ("LGT_Rim_CoolSteelEdge", "AREA", (2.7, 1.65, 2.85), 180, 2.4),
        ("LGT_Fill_AmberForgeBounce", "POINT", (1.35, -2.1, 1.55), 105, 0),
    ]
    for name, kind, loc, energy, size in lights:
        data = bpy.data.lights.new(name, kind)
        obj = bpy.data.objects.new(name, data)
        bpy.context.scene.collection.objects.link(obj)
        obj.location = loc
        data.energy = energy
        if hasattr(data, "size") and size:
            data.size = size
        look_at(obj, (0.08, -0.15, 1.45))
        for source in list(obj.users_collection):
            source.objects.unlink(obj)
        collection("LIGHTING_CAMERA").objects.link(obj)


def configure_scene() -> None:
    scene = bpy.context.scene
    scene.name = "SCN_VillageBlacksmithNPC"
    scene.unit_settings.system = "METRIC"
    scene.frame_start = 1
    scene.frame_end = 72
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
            "source": "Blender MCP live bridge",
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
            "Stylized fantasy village blacksmith NPC with a sturdy build, dark leather apron, rolled gray sleeves, blackened gloves, heavy boots, full beard, tool belt, and visible hammer.",
            "Embedded GLB clips: Idle_Stationary, Walk_InPlace, Hammering_Loop, and Talking_Gesture.",
            "Mixamo FBX and OBJ ZIP are best-effort exports; stylized proportions, hammer geometry, apron pieces, beard pieces, and whole-part weights may need manual Mixamo adjustment.",
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
    print(result)
