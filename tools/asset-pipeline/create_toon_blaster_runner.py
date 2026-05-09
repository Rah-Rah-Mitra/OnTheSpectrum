"""Generate the Toon Blaster Runner asset in Blender.

Run from Blender Python through the live MCP bridge. The script is intentionally
repeatable: it creates the source scene, embeds web animation clips, exports the
GLB, writes Mixamo best-effort exports, renders a preview, and writes metadata.
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

ASSET_SLUG = "toon-blaster-runner"
ASSET_NAME = "Toon Blaster Runner"
CLIPS = ("Idle_Stationary", "Walk_InPlace", "Run_InPlace")
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
        "skin": make_mat("MAT_Skin_WarmToon", (1.0, 0.68, 0.5, 1), roughness=0.78),
        "blush": make_mat("MAT_Skin_CoralBlush", (1.0, 0.32, 0.38, 0.7), roughness=0.82, alpha=0.7),
        "hair": make_mat("MAT_Hair_DeepInk", (0.055, 0.06, 0.105, 1), roughness=0.68),
        "eye_white": make_mat("MAT_Eye_SoftWhite", (0.97, 0.99, 1.0, 1), roughness=0.36),
        "iris": make_mat(
            "MAT_Eye_CyanIrisGlow",
            (0.02, 0.72, 0.92, 1),
            roughness=0.38,
            emission=(0.0, 0.5, 0.85, 1),
            emission_strength=0.35,
        ),
        "suit": make_mat("MAT_Outfit_TealSuit", (0.02, 0.43, 0.46, 1), roughness=0.76),
        "suit_dark": make_mat("MAT_Outfit_DarkTealPanels", (0.015, 0.19, 0.22, 1), roughness=0.8),
        "coral": make_mat("MAT_Accent_CoralTrim", (0.98, 0.28, 0.22, 1), roughness=0.72),
        "gold": make_mat("MAT_Accent_WarmGold", (1.0, 0.66, 0.18, 1), roughness=0.48, metallic=0.18),
        "boots": make_mat("MAT_Boots_Charcoal", (0.045, 0.05, 0.065, 1), roughness=0.8),
        "gunmetal": make_mat("MAT_Prop_BlasterGunmetal", (0.22, 0.24, 0.28, 1), roughness=0.45, metallic=0.35),
        "blaster_dark": make_mat("MAT_Prop_BlasterDarkGrip", (0.07, 0.08, 0.1, 1), roughness=0.72),
        "energy": make_mat(
            "MAT_Energy_CyanGlow",
            (0.02, 0.9, 1.0, 1),
            roughness=0.32,
            emission=(0.0, 0.76, 1.0, 1),
            emission_strength=0.9,
        ),
        "base": make_mat("MAT_Base_MatteGraphite", (0.08, 0.095, 0.11, 1), roughness=0.88),
        "contact": make_mat("MAT_Shadow_BakedSoftContact", (0.02, 0.024, 0.028, 0.58), roughness=0.9, alpha=0.58),
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
    armature.name = "RIG_ToonBlasterRunner_BasicArmature"
    armature.data.name = "ARM_ToonBlasterRunner_Humanoid"
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

    bone("pelvis", (0, 0, 0.48), (0, 0, 0.82), "root")
    bone("spine", (0, 0, 0.82), (0, -0.015, 1.42), "pelvis")
    bone("chest", (0, -0.015, 1.42), (0, -0.02, 1.74), "spine")
    bone("neck", (0, -0.02, 1.74), (0, -0.02, 1.95), "chest")
    bone("head", (0, -0.02, 1.95), (0, -0.04, 2.72), "neck")
    bone("hair", (0, 0.05, 2.42), (0, 0.02, 3.0), "head")
    bone("upper_arm.L", (-0.35, -0.02, 1.52), (-0.7, -0.12, 1.19), "chest")
    bone("forearm.L", (-0.7, -0.12, 1.19), (-0.94, -0.22, 0.94), "upper_arm.L")
    bone("hand.L", (-0.94, -0.22, 0.94), (-1.05, -0.3, 0.84), "forearm.L")
    bone("upper_arm.R", (0.35, -0.02, 1.52), (0.74, -0.15, 1.24), "chest")
    bone("forearm.R", (0.74, -0.15, 1.24), (1.0, -0.38, 1.05), "upper_arm.R")
    bone("hand.R", (1.0, -0.38, 1.05), (1.14, -0.52, 0.98), "forearm.R")
    bone("blaster", (1.06, -0.48, 1.02), (1.5, -0.9, 1.16), "hand.R")
    bone("thigh.L", (-0.18, 0.0, 0.54), (-0.24, -0.02, 0.24), "pelvis")
    bone("shin.L", (-0.24, -0.02, 0.24), (-0.24, -0.04, 0.08), "thigh.L")
    bone("foot.L", (-0.24, -0.04, 0.08), (-0.25, -0.28, 0.04), "shin.L")
    bone("thigh.R", (0.18, 0.0, 0.54), (0.24, -0.02, 0.24), "pelvis")
    bone("shin.R", (0.24, -0.02, 0.24), (0.24, -0.04, 0.08), "thigh.R")
    bone("foot.R", (0.24, -0.04, 0.08), (0.25, -0.28, 0.04), "shin.R")

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

    # Body and suit.
    add(uv_sphere("CHR_Head_RoundedToon", (0, -0.03, 2.34), (0.62, 0.56, 0.62), mats["skin"], segments=40, rings=20, collection_name="CHARACTER_BODY"), "head")
    add(uv_sphere("CHR_Torso_TealRunnerSuit", (0, 0.0, 1.25), (0.42, 0.3, 0.48), mats["suit"], segments=36, rings=18, collection_name="CHARACTER_BODY"), "spine")
    add(uv_sphere("CHR_Chest_ArmorPlate", (0, -0.23, 1.46), (0.39, 0.08, 0.25), mats["suit_dark"], segments=32, rings=12, collection_name="OUTFIT"), "chest")
    add(cube("OUT_Gold_ChestBolt", (0, -0.325, 1.52), (0.08, 0.018, 0.1), mats["gold"], bevel=0.018, collection_name="OUTFIT"), "chest")
    add(uv_sphere("CHR_Hip_TealUtilityShorts", (0, 0.01, 0.72), (0.37, 0.27, 0.22), mats["suit_dark"], segments=32, rings=14, collection_name="CHARACTER_BODY"), "pelvis")

    for side, sign in [("L", -1), ("R", 1)]:
        arm_y = -0.06 if side == "L" else -0.12
        add(uv_sphere(f"CHR_Shoulder_{side}_CoralPad", (sign * 0.42, arm_y, 1.52), (0.17, 0.13, 0.18), mats["coral"], segments=24, rings=12, collection_name="OUTFIT"), f"upper_arm.{side}")
        add(bevel_curve(f"CHR_UpperArm_{side}_TealSleeve", [(sign * 0.48, arm_y, 1.42), (sign * 0.64, arm_y - 0.04, 1.28), (sign * 0.74, arm_y - 0.08, 1.12)], mats["suit"], bevel_depth=0.075, collection_name="CHARACTER_BODY"), f"upper_arm.{side}")
        add(bevel_curve(f"CHR_Forearm_{side}_Gloved", [(sign * 0.74, arm_y - 0.08, 1.12), (sign * 0.88, arm_y - 0.15, 0.98), (sign * 1.0, arm_y - 0.23, 0.88)], mats["skin"], bevel_depth=0.064, collection_name="CHARACTER_BODY"), f"forearm.{side}")
        add(uv_sphere(f"CHR_Glove_{side}_Coral", (sign * 1.04, arm_y - 0.27, 0.86), (0.12, 0.1, 0.1), mats["coral"], segments=24, rings=12, collection_name="OUTFIT"), f"hand.{side}")
        add(uv_sphere(f"CHR_Thigh_{side}_SuitLeg", (sign * 0.18, -0.01, 0.38), (0.13, 0.11, 0.26), mats["suit"], segments=24, rings=12, collection_name="CHARACTER_BODY"), f"thigh.{side}")
        add(uv_sphere(f"CHR_Shin_{side}_WarmSkin", (sign * 0.22, -0.03, 0.2), (0.095, 0.085, 0.17), mats["skin"], segments=20, rings=10, collection_name="CHARACTER_BODY"), f"shin.{side}")
        add(uv_sphere(f"CHR_Boot_{side}_CharcoalRunner", (sign * 0.24, -0.13, 0.08), (0.16, 0.24, 0.095), mats["boots"], segments=28, rings=12, collection_name="OUTFIT"), f"foot.{side}")
        add(cylinder(f"OUT_Boot_{side}_GoldSole", (sign * 0.24, -0.19, 0.02), 0.115, 0.03, mats["gold"], vertices=24, scale=(1.25, 0.72, 1), collection_name="BAKED_EFFECTS"), f"foot.{side}")

    # Face layers.
    for side, sign in [("L", -1), ("R", 1)]:
        add(uv_sphere(f"FACE_Eye_{side}_WhiteOval", (sign * 0.22, -0.545, 2.42), (0.14, 0.02, 0.19), mats["eye_white"], segments=28, rings=12, collection_name="FACE"), "head")
        add(uv_sphere(f"FACE_Eye_{side}_CyanIris", (sign * 0.22, -0.567, 2.4), (0.07, 0.011, 0.105), mats["iris"], segments=22, rings=10, collection_name="FACE"), "head")
        add(uv_sphere(f"FACE_Eye_{side}_Pupil", (sign * 0.22, -0.582, 2.395), (0.032, 0.007, 0.052), mats["hair"], segments=16, rings=8, collection_name="FACE"), "head")
        add(uv_sphere(f"FACE_Blush_{side}_CoralDash", (sign * 0.38, -0.536, 2.25), (0.072, 0.008, 0.028), mats["blush"], segments=16, rings=8, collection_name="BAKED_EFFECTS"), "head")
    add(bevel_curve("FACE_Mouth_ConfidentSmile", [(-0.06, -0.59, 2.17), (0.0, -0.61, 2.145), (0.075, -0.588, 2.17)], mats["hair"], bevel_depth=0.008, bevel_resolution=2, collection_name="FACE"), "head")

    # Hair silhouette.
    add(uv_sphere("HAIR_Cap_ToonInk", (0, 0.01, 2.66), (0.65, 0.57, 0.28), mats["hair"], segments=40, rings=14, collection_name="HAIR"), "hair")
    hair_locks = [
        ("FrontCyanStreak", [(0.08, -0.48, 2.88), (0.12, -0.62, 2.62), (0.08, -0.54, 2.36)], mats["energy"], 0.036),
        ("FrontLeftSpike", [(-0.2, -0.45, 2.82), (-0.36, -0.62, 2.58), (-0.32, -0.54, 2.32)], mats["hair"], 0.062),
        ("FrontRightSpike", [(0.26, -0.43, 2.84), (0.43, -0.58, 2.6), (0.36, -0.51, 2.38)], mats["hair"], 0.058),
        ("BackKick", [(0.1, 0.42, 2.76), (0.36, 0.6, 2.66), (0.58, 0.47, 2.52)], mats["hair"], 0.058),
        ("SideLeft", [(-0.52, -0.08, 2.58), (-0.68, -0.14, 2.32), (-0.58, -0.08, 2.06)], mats["hair"], 0.052),
        ("SideRight", [(0.52, -0.08, 2.58), (0.7, -0.14, 2.32), (0.62, -0.08, 2.1)], mats["hair"], 0.05),
    ]
    for name, points, mat, depth in hair_locks:
        add(bevel_curve(f"HAIR_Lock_{name}", points, mat, bevel_depth=depth, bevel_resolution=4, collection_name="HAIR"), "hair")

    # Outfit accents and belt pouches.
    add(cube("OUT_Belt_GoldBuckle", (0, -0.29, 0.9), (0.09, 0.02, 0.065), mats["gold"], bevel=0.012, collection_name="OUTFIT"), "pelvis")
    add(bevel_curve("OUT_Coral_SashCurve", [(-0.34, -0.28, 1.02), (-0.05, -0.31, 0.94), (0.36, -0.27, 0.91)], mats["coral"], bevel_depth=0.022, bevel_resolution=3, collection_name="OUTFIT"), "pelvis")
    add(cube("PROP_LeftHip_EnergyCell", (-0.43, -0.22, 0.82), (0.08, 0.045, 0.14), mats["energy"], bevel=0.016, collection_name="PROPS"), "pelvis")

    # Stylized sci-fi blaster attached to the right hand.
    add(cube("PROP_Blaster_MainRoundedBody", (1.25, -0.68, 1.08), (0.26, 0.1, 0.13), mats["gunmetal"], bevel=0.04, collection_name="PROPS"), "blaster")
    add(cylinder("PROP_Blaster_CyanBarrel", (1.53, -0.86, 1.15), 0.052, 0.34, mats["energy"], vertices=24, rotation=(math.radians(76), 0, math.radians(-56)), bevel=0.01, collection_name="PROPS"), "blaster")
    add(cube("PROP_Blaster_DarkGrip", (1.12, -0.62, 0.9), (0.08, 0.055, 0.19), mats["blaster_dark"], bevel=0.025, collection_name="PROPS"), "blaster")
    add(cube("PROP_Blaster_GoldSight", (1.25, -0.74, 1.24), (0.09, 0.03, 0.03), mats["gold"], bevel=0.012, collection_name="PROPS"), "blaster")
    add(uv_sphere("PROP_Blaster_MuzzleGlow", (1.7, -0.98, 1.22), (0.065, 0.048, 0.065), mats["energy"], segments=18, rings=9, collection_name="BAKED_EFFECTS"), "blaster")

    # Display base and contact shadow are excluded from Mixamo exports.
    add(cylinder("BASE_DisplayDisc_MatteGraphite", (0, 0, -0.025), 0.75, 0.045, mats["base"], vertices=64, collection_name="BAKED_EFFECTS"), "root")
    add(cylinder("BASE_BakedSoftContactShadow", (0, -0.04, 0.004), 0.57, 0.01, mats["contact"], vertices=64, scale=(1, 0.68, 1), collection_name="BAKED_EFFECTS"), "root")

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
        "hair": {"rotation": (0, 0, 0)},
        "upper_arm.L": {"rotation": (0, 0, 0.02)},
        "forearm.L": {"rotation": (0, 0, -0.02)},
        "upper_arm.R": {"rotation": (0.08, 0, -0.08)},
        "forearm.R": {"rotation": (-0.08, 0, 0.04)},
        "hand.R": {"rotation": (0.0, 0.0, 0.0)},
        "blaster": {"rotation": (0, 0, 0)},
    }
    inhale = {
        "pelvis": {"location": (0, 0, 0.025), "rotation": (0, 0, -0.012)},
        "spine": {"rotation": (0.022, 0, 0.014)},
        "chest": {"rotation": (0.032, 0, -0.012)},
        "neck": {"rotation": (-0.018, 0, 0.01)},
        "head": {"rotation": (-0.018, 0, -0.018)},
        "hair": {"rotation": (0.035, 0, 0.022)},
        "upper_arm.L": {"rotation": (0.025, 0, 0.045)},
        "forearm.L": {"rotation": (-0.02, 0, -0.025)},
        "upper_arm.R": {"rotation": (0.11, 0, -0.07)},
        "forearm.R": {"rotation": (-0.1, 0, 0.035)},
        "hand.R": {"rotation": (0.0, 0.0, 0.018)},
        "blaster": {"rotation": (0.0, 0.0, -0.015)},
    }
    return [(1, neutral), (30, inhale), (60, neutral)]


def walk_pose(left_forward: bool, *, bob: float = 0.0, lean: float = 0.0) -> dict[str, dict]:
    leg = 1 if left_forward else -1
    return {
        "pelvis": {"location": (0, 0, bob), "rotation": (0.0, 0.0, 0.035 * leg)},
        "spine": {"rotation": (0.045 + lean, 0.0, -0.035 * leg)},
        "chest": {"rotation": (0.03 + lean, 0.0, 0.035 * leg)},
        "neck": {"rotation": (-0.02 - lean, 0.0, 0)},
        "head": {"rotation": (-0.025 - lean, 0.0, 0.02 * leg)},
        "upper_arm.L": {"rotation": (-0.46 * leg, 0.0, 0.04)},
        "forearm.L": {"rotation": (-0.16 * leg, 0.0, -0.04)},
        "upper_arm.R": {"rotation": (0.32 * leg, 0.0, -0.08)},
        "forearm.R": {"rotation": (0.08 * leg, 0.0, 0.04)},
        "hand.R": {"rotation": (0.0, 0.0, 0.05 * leg)},
        "thigh.L": {"rotation": (0.45 * leg, 0.0, 0.025)},
        "shin.L": {"rotation": (-0.28 if left_forward else 0.36, 0.0, 0.0)},
        "foot.L": {"rotation": (-0.18 if left_forward else 0.14, 0.0, 0.0)},
        "thigh.R": {"rotation": (-0.45 * leg, 0.0, -0.025)},
        "shin.R": {"rotation": (0.36 if left_forward else -0.28, 0.0, 0.0)},
        "foot.R": {"rotation": (0.14 if left_forward else -0.18, 0.0, 0.0)},
        "hair": {"rotation": (0.04, 0.0, 0.045 * leg)},
        "blaster": {"rotation": (0.0, 0.0, 0.05 * leg)},
    }


def walk_frames() -> list[tuple[int, dict[str, dict]]]:
    passing = {
        "pelvis": {"location": (0, 0, 0.04), "rotation": (0, 0, 0)},
        "spine": {"rotation": (0.032, 0, 0)},
        "chest": {"rotation": (0.028, 0, 0)},
        "neck": {"rotation": (-0.018, 0, 0)},
        "head": {"rotation": (-0.025, 0, 0)},
        "upper_arm.L": {"rotation": (0, 0, 0.035)},
        "forearm.L": {"rotation": (0, 0, 0)},
        "upper_arm.R": {"rotation": (0.08, 0, -0.05)},
        "forearm.R": {"rotation": (-0.05, 0, 0.025)},
        "thigh.L": {"rotation": (0, 0, 0)},
        "shin.L": {"rotation": (0.18, 0, 0)},
        "foot.L": {"rotation": (0, 0, 0)},
        "thigh.R": {"rotation": (0, 0, 0)},
        "shin.R": {"rotation": (0.18, 0, 0)},
        "foot.R": {"rotation": (0, 0, 0)},
        "hair": {"rotation": (0.03, 0, 0)},
        "blaster": {"rotation": (0, 0, 0)},
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
        "pelvis": {"location": (0, 0, bob), "rotation": (0.0, 0.0, 0.055 * leg)},
        "spine": {"rotation": (0.13 + lean, 0.0, -0.06 * leg)},
        "chest": {"rotation": (0.1 + lean, 0.0, 0.052 * leg)},
        "neck": {"rotation": (-0.07 - lean, 0.0, -0.008 * leg)},
        "head": {"rotation": (-0.08 - lean, 0.0, 0.028 * leg)},
        "upper_arm.L": {"rotation": (-0.82 * leg, 0.0, 0.07)},
        "forearm.L": {"rotation": (-0.32 * leg, 0.0, -0.08)},
        "upper_arm.R": {"rotation": (0.46 * leg, 0.0, -0.14)},
        "forearm.R": {"rotation": (0.2 * leg, 0.0, 0.08)},
        "hand.R": {"rotation": (0.0, 0.0, 0.08 * leg)},
        "thigh.L": {"rotation": (0.72 * leg, 0.0, 0.035)},
        "shin.L": {"rotation": (-0.55 if left_forward else 0.62, 0.0, 0.0)},
        "foot.L": {"rotation": (-0.28 if left_forward else 0.2, 0.0, 0.0)},
        "thigh.R": {"rotation": (-0.72 * leg, 0.0, -0.035)},
        "shin.R": {"rotation": (0.62 if left_forward else -0.55, 0.0, 0.0)},
        "foot.R": {"rotation": (0.2 if left_forward else -0.28, 0.0, 0.0)},
        "hair": {"rotation": (0.09, 0.0, 0.07 * leg)},
        "blaster": {"rotation": (0.0, 0.0, 0.075 * leg)},
    }


def run_frames() -> list[tuple[int, dict[str, dict]]]:
    airborne = {
        "pelvis": {"location": (0, 0, 0.085), "rotation": (0, 0, 0)},
        "spine": {"rotation": (0.12, 0, 0)},
        "chest": {"rotation": (0.1, 0, 0)},
        "neck": {"rotation": (-0.07, 0, 0)},
        "head": {"rotation": (-0.08, 0, 0)},
        "upper_arm.L": {"rotation": (0, 0, 0.08)},
        "forearm.L": {"rotation": (-0.18, 0, -0.08)},
        "upper_arm.R": {"rotation": (0.1, 0, -0.12)},
        "forearm.R": {"rotation": (-0.12, 0, 0.07)},
        "thigh.L": {"rotation": (0.1, 0, 0)},
        "shin.L": {"rotation": (0.36, 0, 0)},
        "foot.L": {"rotation": (0.04, 0, 0)},
        "thigh.R": {"rotation": (-0.1, 0, 0)},
        "shin.R": {"rotation": (0.36, 0, 0)},
        "foot.R": {"rotation": (0.04, 0, 0)},
        "hair": {"rotation": (0.1, 0, 0)},
        "blaster": {"rotation": (0, 0, 0)},
    }
    return [
        (1, run_pose(True, bob=0.02, lean=0.025)),
        (7, airborne),
        (13, run_pose(False, bob=0.02, lean=0.025)),
        (19, airborne),
        (25, run_pose(True, bob=0.02, lean=0.025)),
    ]


def add_actions(armature: bpy.types.Object) -> None:
    clear_nla_tracks(armature, CLIPS)
    remove_actions(CLIPS)
    idle = create_pose_action(armature, "Idle_Stationary", idle_frames())
    walk = create_pose_action(armature, "Walk_InPlace", walk_frames())
    run = create_pose_action(armature, "Run_InPlace", run_frames())
    push_action_to_nla(armature, idle, 1, 60)
    push_action_to_nla(armature, walk, 1, 33)
    push_action_to_nla(armature, run, 1, 25)


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
    world.color = (0.025, 0.032, 0.035)

    camera_data = bpy.data.cameras.new("CAM_ToonBlasterRunner_Preview")
    camera = bpy.data.objects.new("CAM_ToonBlasterRunner_Preview", camera_data)
    bpy.context.scene.collection.objects.link(camera)
    camera.location = (2.45, -6.25, 2.28)
    camera.data.lens = 52
    camera.data.dof.use_dof = True
    camera.data.dof.focus_distance = 6.25
    camera.data.dof.aperture_fstop = 5.6
    look_at(camera, (0.34, -0.2, 1.46))
    bpy.context.scene.camera = camera
    for source in list(camera.users_collection):
        source.objects.unlink(camera)
    collection("LIGHTING_CAMERA").objects.link(camera)

    lights = [
        ("LGT_Key_ToonSoftbox", "AREA", (-2.4, -3.35, 4.1), 540, 4.3),
        ("LGT_Rim_CyanBlaster", "AREA", (2.65, 1.55, 2.8), 190, 2.3),
        ("LGT_Fill_WarmGold", "POINT", (1.55, -2.05, 1.65), 95, 0),
    ]
    for name, kind, loc, energy, size in lights:
        data = bpy.data.lights.new(name, kind)
        obj = bpy.data.objects.new(name, data)
        bpy.context.scene.collection.objects.link(obj)
        obj.location = loc
        data.energy = energy
        if hasattr(data, "size") and size:
            data.size = size
        look_at(obj, (0.08, -0.12, 1.45))
        for source in list(obj.users_collection):
            source.objects.unlink(obj)
        collection("LIGHTING_CAMERA").objects.link(obj)


def configure_scene() -> None:
    scene = bpy.context.scene
    scene.name = "SCN_ToonBlasterRunner"
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
    data = {
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
            "rig_depth": "basic humanoid armature with whole-part vertex groups",
        },
        "notes": [
            "Original bright toon humanoid character carrying a stylized sci-fi blaster.",
            "Embedded GLB clips: Idle_Stationary, Walk_InPlace, and Run_InPlace.",
            "Mixamo FBX and OBJ ZIP are best-effort exports; stylized proportions, weapon geometry, and whole-part weights may need manual Mixamo adjustment.",
            MIXAMO_ORIENTATION_NOTE,
            "Display base and contact-shadow extras are excluded from Mixamo exports.",
        ],
    }
    return data


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
