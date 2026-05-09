"""Generate the Goblin Grunt Enemy asset in Blender.

Run from Blender Python through the live MCP bridge or through
run_blender_asset.py when a background Blender executable is configured. The
script is repeatable: it creates the source scene, embeds web animation clips,
exports the GLB, writes Mixamo best-effort exports, renders a preview, and
writes metadata.
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

ASSET_SLUG = "goblin-grunt-enemy"
ASSET_NAME = "Goblin Grunt Enemy"
CLIPS = (
    "Idle_Stationary",
    "Walk_InPlace",
    "Run_InPlace",
    "Attack_Swing",
    "Hit_Reaction",
    "Death",
)
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
        "skin": make_mat("MAT_Skin_OliveGoblin", (0.34, 0.52, 0.18, 1), roughness=0.84),
        "skin_dark": make_mat("MAT_Skin_DarkerOlive", (0.18, 0.33, 0.12, 1), roughness=0.88),
        "eye": make_mat(
            "MAT_Eye_SicklyAmber",
            (1.0, 0.72, 0.16, 1),
            roughness=0.35,
            emission=(1.0, 0.46, 0.02, 1),
            emission_strength=0.22,
        ),
        "pupil": make_mat("MAT_Eye_InkPupil", (0.03, 0.025, 0.018, 1), roughness=0.6),
        "teeth": make_mat("MAT_Teeth_Bone", (0.9, 0.82, 0.62, 1), roughness=0.72),
        "cloth": make_mat("MAT_Cloth_DirtyBrown", (0.34, 0.2, 0.105, 1), roughness=0.93),
        "cloth_dark": make_mat("MAT_Cloth_DarkPatch", (0.16, 0.105, 0.065, 1), roughness=0.95),
        "wood": make_mat("MAT_Wood_DarkClub", (0.24, 0.13, 0.06, 1), roughness=0.82),
        "metal": make_mat("MAT_Metal_DullShieldRim", (0.42, 0.41, 0.36, 1), roughness=0.55, metallic=0.38),
        "shield": make_mat("MAT_Shield_BatteredCore", (0.17, 0.2, 0.16, 1), roughness=0.86),
        "claws": make_mat("MAT_Claws_DarkHorn", (0.075, 0.055, 0.035, 1), roughness=0.74),
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
    armature.name = "RIG_GoblinGruntEnemy_BasicArmature"
    armature.data.name = "ARM_GoblinGruntEnemy_Humanoid"
    armature.show_in_front = True
    rig_collection = collection("RIG")
    for source in list(armature.users_collection):
        source.objects.unlink(armature)
    rig_collection.objects.link(armature)

    bones = armature.data.edit_bones
    root = bones[0]
    root.name = "root"
    root.head = (0, 0, 0.04)
    root.tail = (0, 0, 0.3)

    def bone(name: str, head: tuple[float, float, float], tail: tuple[float, float, float], parent: str | None = None):
        edit_bone = bones.new(name)
        edit_bone.head = head
        edit_bone.tail = tail
        if parent:
            edit_bone.parent = bones[parent]
        return edit_bone

    bone("pelvis", (0, 0, 0.42), (0, 0, 0.66), "root")
    bone("spine", (0, 0, 0.66), (0, -0.02, 1.08), "pelvis")
    bone("chest", (0, -0.02, 1.08), (0, -0.04, 1.34), "spine")
    bone("neck", (0, -0.04, 1.34), (0, -0.05, 1.48), "chest")
    bone("head", (0, -0.05, 1.48), (0, -0.08, 2.05), "neck")
    bone("ear.L", (-0.26, -0.04, 1.72), (-0.73, -0.08, 1.82), "head")
    bone("ear.R", (0.26, -0.04, 1.72), (0.73, -0.08, 1.82), "head")
    bone("upper_arm.L", (-0.28, -0.05, 1.24), (-0.55, -0.2, 1.05), "chest")
    bone("forearm.L", (-0.55, -0.2, 1.05), (-0.75, -0.42, 0.92), "upper_arm.L")
    bone("hand.L", (-0.75, -0.42, 0.92), (-0.86, -0.5, 0.86), "forearm.L")
    bone("shield", (-0.82, -0.49, 0.98), (-0.92, -0.62, 1.16), "hand.L")
    bone("upper_arm.R", (0.28, -0.05, 1.26), (0.58, -0.22, 1.12), "chest")
    bone("forearm.R", (0.58, -0.22, 1.12), (0.82, -0.44, 1.0), "upper_arm.R")
    bone("hand.R", (0.82, -0.44, 1.0), (0.94, -0.52, 0.95), "forearm.R")
    bone("club", (0.9, -0.5, 1.0), (1.28, -0.82, 1.8), "hand.R")
    bone("thigh.L", (-0.14, 0, 0.46), (-0.2, -0.02, 0.24), "pelvis")
    bone("shin.L", (-0.2, -0.02, 0.24), (-0.22, -0.05, 0.08), "thigh.L")
    bone("foot.L", (-0.22, -0.05, 0.08), (-0.28, -0.32, 0.04), "shin.L")
    bone("thigh.R", (0.14, 0, 0.46), (0.2, -0.02, 0.24), "pelvis")
    bone("shin.R", (0.2, -0.02, 0.24), (0.22, -0.05, 0.08), "thigh.R")
    bone("foot.R", (0.22, -0.05, 0.08), (0.28, -0.32, 0.04), "shin.R")

    bpy.ops.object.mode_set(mode="OBJECT")
    return armature


def build_character(mats: dict[str, bpy.types.Material]) -> tuple[bpy.types.Object, list[bpy.types.Object]]:
    for name in [
        "RIG",
        "CHARACTER_BODY",
        "FACE",
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

    # Compact goblin body with a hunched low-poly silhouette.
    add(uv_sphere("CHR_Head_LowPolyGoblin", (0, -0.08, 1.7), (0.46, 0.38, 0.35), mats["skin"], segments=24, rings=12, collection_name="CHARACTER_BODY"), "head")
    add(uv_sphere("CHR_Nose_PointedWartedSnout", (0, -0.45, 1.67), (0.11, 0.1, 0.085), mats["skin_dark"], segments=12, rings=6, collection_name="FACE"), "head")
    add(cone("CHR_Nose_SharpTip", (0, -0.53, 1.68), 0.06, 0.0, 0.18, mats["skin_dark"], vertices=8, rotation=(math.radians(90), 0, 0), collection_name="FACE"), "head")
    add(uv_sphere("CHR_Torso_SquatOliveBody", (0, -0.01, 0.96), (0.36, 0.27, 0.42), mats["skin"], segments=20, rings=10, collection_name="CHARACTER_BODY"), "spine")
    add(uv_sphere("CHR_Hips_SmallGoblinBelly", (0, 0.02, 0.56), (0.31, 0.24, 0.2), mats["skin_dark"], segments=18, rings=8, collection_name="CHARACTER_BODY"), "pelvis")

    for side, sign in [("L", -1), ("R", 1)]:
        ear = add(
            cone(
                f"CHR_Ear_{side}_ExaggeratedPoint",
                (sign * 0.47, -0.07, 1.76),
                0.15,
                0.012,
                0.56,
                mats["skin"],
                vertices=8,
                rotation=(0, math.radians(90 * sign), math.radians(-8 * sign)),
                scale=(1, 0.62, 1),
                collection_name="CHARACTER_BODY",
            ),
            f"ear.{side}",
        )
        add(uv_sphere(f"CHR_Ear_{side}_DarkInner", (sign * 0.41, -0.105, 1.74), (0.11, 0.018, 0.08), mats["skin_dark"], segments=12, rings=6, collection_name="FACE"), f"ear.{side}")

        add(uv_sphere(f"FACE_Eye_{side}_AmberSlit", (sign * 0.16, -0.43, 1.76), (0.105, 0.022, 0.07), mats["eye"], segments=14, rings=6, collection_name="FACE"), "head")
        add(uv_sphere(f"FACE_Eye_{side}_InkPupil", (sign * 0.16, -0.452, 1.755), (0.029, 0.009, 0.055), mats["pupil"], segments=10, rings=5, collection_name="FACE"), "head")
        add(bevel_curve(f"FACE_Brow_{side}_AngrySlash", [(sign * 0.06, -0.47, 1.86), (sign * 0.18, -0.48, 1.89), (sign * 0.29, -0.46, 1.85)], mats["claws"], bevel_depth=0.012, bevel_resolution=1, collection_name="FACE"), "head")

    add(bevel_curve("FACE_Mouth_DarkSnarl", [(-0.18, -0.47, 1.55), (-0.02, -0.5, 1.515), (0.2, -0.46, 1.55)], mats["claws"], bevel_depth=0.013, bevel_resolution=1, collection_name="FACE"), "head")
    for index, x in enumerate([-0.13, -0.04, 0.055, 0.145]):
        add(cone(f"FACE_Tooth_{index + 1}_SharpBone", (x, -0.49, 1.49), 0.028, 0.0, 0.14, mats["teeth"], vertices=7, rotation=(math.radians(180), 0, 0), collection_name="FACE"), "head")

    # Ragged cloth armor and patched tunic layers.
    add(cube("OUT_Tunic_MainDirtyBrown", (0, -0.25, 1.03), (0.32, 0.035, 0.31), mats["cloth"], bevel=0.018, collection_name="OUTFIT"), "spine")
    add(cube("OUT_Tunic_DarkChestPatch", (-0.1, -0.29, 1.17), (0.12, 0.018, 0.1), mats["cloth_dark"], bevel=0.01, collection_name="OUTFIT"), "chest")
    add(bevel_curve("OUT_Tunic_RopeBelt", [(-0.32, -0.28, 0.72), (-0.05, -0.31, 0.68), (0.32, -0.27, 0.72)], mats["cloth_dark"], bevel_depth=0.025, bevel_resolution=2, collection_name="OUTFIT"), "pelvis")
    for index, x in enumerate([-0.22, -0.08, 0.08, 0.23]):
        add(cube(f"OUT_RaggedHem_{index + 1}_TornTab", (x, -0.275, 0.68 - 0.025 * (index % 2)), (0.055, 0.022, 0.11), mats["cloth"], bevel=0.012, collection_name="OUTFIT"), "pelvis")
    add(bevel_curve("OUT_CrossStrap_DarkLeather", [(-0.28, -0.29, 1.27), (-0.06, -0.31, 1.04), (0.24, -0.28, 0.82)], mats["cloth_dark"], bevel_depth=0.026, bevel_resolution=2, collection_name="OUTFIT"), "spine")

    for side, sign in [("L", -1), ("R", 1)]:
        arm_y = -0.08 if side == "L" else -0.1
        add(uv_sphere(f"CHR_Shoulder_{side}_KnobbyOlive", (sign * 0.32, arm_y, 1.22), (0.13, 0.105, 0.13), mats["skin_dark"], segments=14, rings=7, collection_name="CHARACTER_BODY"), f"upper_arm.{side}")
        add(bevel_curve(f"CHR_UpperArm_{side}_SkinnyOlive", [(sign * 0.38, arm_y, 1.16), (sign * 0.52, arm_y - 0.07, 1.04), (sign * 0.62, arm_y - 0.15, 0.94)], mats["skin"], bevel_depth=0.055, bevel_resolution=2, collection_name="CHARACTER_BODY"), f"upper_arm.{side}")
        add(bevel_curve(f"CHR_Forearm_{side}_StringyOlive", [(sign * 0.62, arm_y - 0.15, 0.94), (sign * 0.76, arm_y - 0.25, 0.87), (sign * 0.86, arm_y - 0.35, 0.82)], mats["skin"], bevel_depth=0.052, bevel_resolution=2, collection_name="CHARACTER_BODY"), f"forearm.{side}")
        add(uv_sphere(f"CHR_Hand_{side}_ClawedKnuckles", (sign * 0.89, arm_y - 0.38, 0.8), (0.095, 0.075, 0.07), mats["skin_dark"], segments=12, rings=6, collection_name="CHARACTER_BODY"), f"hand.{side}")
        for claw_index, claw_x in enumerate([-0.035, 0.0, 0.035]):
            add(cone(f"CHR_HandClaw_{side}_{claw_index + 1}_DarkHorn", (sign * (0.91 + claw_x), arm_y - 0.455, 0.775), 0.016, 0.0, 0.08, mats["claws"], vertices=6, rotation=(math.radians(90), 0, 0), collection_name="CHARACTER_BODY"), f"hand.{side}")

        add(uv_sphere(f"CHR_Thigh_{side}_StubbyOlive", (sign * 0.14, -0.02, 0.35), (0.105, 0.09, 0.19), mats["skin"], segments=12, rings=6, collection_name="CHARACTER_BODY"), f"thigh.{side}")
        add(uv_sphere(f"CHR_Shin_{side}_BentGoblinLeg", (sign * 0.2, -0.045, 0.18), (0.085, 0.07, 0.13), mats["skin_dark"], segments=12, rings=6, collection_name="CHARACTER_BODY"), f"shin.{side}")
        add(uv_sphere(f"CHR_Foot_{side}_WideClawed", (sign * 0.25, -0.18, 0.065), (0.14, 0.22, 0.07), mats["skin"], segments=14, rings=6, collection_name="CHARACTER_BODY"), f"foot.{side}")
        for claw_index, offset in enumerate([-0.06, 0.0, 0.06]):
            add(cone(f"CHR_FootClaw_{side}_{claw_index + 1}_DarkHorn", (sign * (0.25 + offset), -0.35, 0.055), 0.022, 0.0, 0.11, mats["claws"], vertices=6, rotation=(math.radians(90), 0, 0), collection_name="CHARACTER_BODY"), f"foot.{side}")

    # Club in right hand and small shield on left arm.
    add(bevel_curve("PROP_Club_DarkWoodCrookedHandle", [(0.9, -0.5, 0.98), (1.05, -0.62, 1.28), (1.24, -0.79, 1.73)], mats["wood"], bevel_depth=0.054, bevel_resolution=2, collection_name="PROPS"), "club")
    add(uv_sphere("PROP_Club_KnottedHead", (1.29, -0.84, 1.84), (0.16, 0.12, 0.19), mats["wood"], segments=14, rings=7, collection_name="PROPS"), "club")
    for index, loc in enumerate([(1.22, -0.9, 1.84), (1.36, -0.82, 1.92), (1.31, -0.77, 1.73)]):
        add(cone(f"PROP_Club_StubbySpike_{index + 1}", loc, 0.035, 0.0, 0.11, mats["claws"], vertices=6, rotation=(math.radians(60), 0, math.radians(22 * index)), collection_name="PROPS"), "club")
    add(cylinder("PROP_Shield_DullMetalRim", (-0.86, -0.56, 1.02), 0.26, 0.045, mats["metal"], vertices=24, rotation=(math.radians(90), 0, 0), scale=(1.0, 1.18, 1), bevel=0.006, collection_name="PROPS"), "shield")
    add(cylinder("PROP_Shield_BatteredCore", (-0.86, -0.585, 1.02), 0.205, 0.052, mats["shield"], vertices=18, rotation=(math.radians(90), 0, 0), scale=(1.0, 1.12, 1), bevel=0.004, collection_name="PROPS"), "shield")
    add(cylinder("PROP_Shield_CenterBoss", (-0.86, -0.62, 1.02), 0.07, 0.035, mats["metal"], vertices=16, rotation=(math.radians(90), 0, 0), bevel=0.006, collection_name="PROPS"), "shield")
    add(bevel_curve("PROP_Shield_ScratchMarks", [(-0.95, -0.635, 1.11), (-0.87, -0.65, 1.05), (-0.78, -0.635, 0.96)], mats["metal"], bevel_depth=0.006, bevel_resolution=1, collection_name="PROPS"), "shield")

    # Display base and contact shadow are excluded from Mixamo exports.
    add(cylinder("BASE_DisplayDisc_MatteGraphite", (0, 0, -0.025), 0.74, 0.045, mats["base"], vertices=56, collection_name="BAKED_EFFECTS"), "root")
    add(cylinder("BASE_BakedSoftContactShadow", (0.02, -0.05, 0.004), 0.58, 0.01, mats["contact"], vertices=56, scale=(1, 0.7, 1), collection_name="BAKED_EFFECTS"), "root")

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
        "spine": {"rotation": (0.06, 0, 0.0)},
        "chest": {"rotation": (0.08, 0, 0.02)},
        "neck": {"rotation": (-0.05, 0, -0.02)},
        "head": {"rotation": (-0.04, 0, -0.02)},
        "ear.L": {"rotation": (0.0, 0.0, -0.02)},
        "ear.R": {"rotation": (0.0, 0.0, 0.02)},
        "upper_arm.L": {"rotation": (0.05, 0, 0.12)},
        "forearm.L": {"rotation": (-0.04, 0, -0.05)},
        "shield": {"rotation": (0, 0, 0.02)},
        "upper_arm.R": {"rotation": (0.08, 0, -0.16)},
        "forearm.R": {"rotation": (-0.08, 0, 0.07)},
        "club": {"rotation": (0.0, 0.0, -0.03)},
    }
    snarl = {
        "pelvis": {"location": (0, 0, 0.018), "rotation": (0, 0, -0.015)},
        "spine": {"rotation": (0.09, 0, 0.018)},
        "chest": {"rotation": (0.105, 0, -0.015)},
        "neck": {"rotation": (-0.075, 0, 0.02)},
        "head": {"rotation": (-0.075, 0, 0.03)},
        "ear.L": {"rotation": (0.03, 0.0, -0.045)},
        "ear.R": {"rotation": (-0.03, 0.0, 0.045)},
        "upper_arm.L": {"rotation": (0.08, 0, 0.16)},
        "forearm.L": {"rotation": (-0.06, 0, -0.07)},
        "shield": {"rotation": (0, 0, 0.04)},
        "upper_arm.R": {"rotation": (0.11, 0, -0.13)},
        "forearm.R": {"rotation": (-0.11, 0, 0.05)},
        "club": {"rotation": (0.0, 0.0, -0.055)},
    }
    return [(1, neutral), (30, snarl), (60, neutral)]


def walk_pose(left_forward: bool, *, bob: float, lean: float) -> dict[str, dict]:
    leg = 1 if left_forward else -1
    return {
        "pelvis": {"location": (0, 0, bob), "rotation": (0.0, 0.0, 0.05 * leg)},
        "spine": {"rotation": (0.09 + lean, 0.0, -0.045 * leg)},
        "chest": {"rotation": (0.08 + lean, 0.0, 0.052 * leg)},
        "neck": {"rotation": (-0.06 - lean, 0.0, -0.012 * leg)},
        "head": {"rotation": (-0.07 - lean, 0.0, 0.03 * leg)},
        "upper_arm.L": {"rotation": (-0.38 * leg, 0.0, 0.11)},
        "forearm.L": {"rotation": (-0.12 * leg, 0.0, -0.08)},
        "shield": {"rotation": (0.02 * leg, 0, 0.04 * leg)},
        "upper_arm.R": {"rotation": (0.42 * leg, 0.0, -0.18)},
        "forearm.R": {"rotation": (0.12 * leg, 0.0, 0.08)},
        "club": {"rotation": (0.0, 0.0, 0.08 * leg)},
        "thigh.L": {"rotation": (0.42 * leg, 0.0, 0.025)},
        "shin.L": {"rotation": (-0.25 if left_forward else 0.32, 0.0, 0.0)},
        "foot.L": {"rotation": (-0.16 if left_forward else 0.13, 0.0, 0.0)},
        "thigh.R": {"rotation": (-0.42 * leg, 0.0, -0.025)},
        "shin.R": {"rotation": (0.32 if left_forward else -0.25, 0.0, 0.0)},
        "foot.R": {"rotation": (0.13 if left_forward else -0.16, 0.0, 0.0)},
        "ear.L": {"rotation": (0.02, 0.0, 0.04 * leg)},
        "ear.R": {"rotation": (-0.02, 0.0, 0.04 * leg)},
    }


def walk_frames() -> list[tuple[int, dict[str, dict]]]:
    passing = {
        "pelvis": {"location": (0, 0, 0.035), "rotation": (0, 0, 0)},
        "spine": {"rotation": (0.08, 0, 0)},
        "chest": {"rotation": (0.07, 0, 0)},
        "neck": {"rotation": (-0.06, 0, 0)},
        "head": {"rotation": (-0.065, 0, 0)},
        "upper_arm.L": {"rotation": (0, 0, 0.12)},
        "forearm.L": {"rotation": (0, 0, -0.06)},
        "upper_arm.R": {"rotation": (0.08, 0, -0.18)},
        "forearm.R": {"rotation": (-0.05, 0, 0.07)},
        "thigh.L": {"rotation": (0, 0, 0)},
        "shin.L": {"rotation": (0.17, 0, 0)},
        "foot.L": {"rotation": (0, 0, 0)},
        "thigh.R": {"rotation": (0, 0, 0)},
        "shin.R": {"rotation": (0.17, 0, 0)},
        "foot.R": {"rotation": (0, 0, 0)},
        "shield": {"rotation": (0, 0, 0)},
        "club": {"rotation": (0, 0, 0)},
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
        "pelvis": {"location": (0, 0, bob), "rotation": (0.0, 0.0, 0.075 * leg)},
        "spine": {"rotation": (0.16 + lean, 0.0, -0.07 * leg)},
        "chest": {"rotation": (0.14 + lean, 0.0, 0.075 * leg)},
        "neck": {"rotation": (-0.09 - lean, 0.0, -0.018 * leg)},
        "head": {"rotation": (-0.1 - lean, 0.0, 0.04 * leg)},
        "upper_arm.L": {"rotation": (-0.68 * leg, 0.0, 0.14)},
        "forearm.L": {"rotation": (-0.24 * leg, 0.0, -0.11)},
        "shield": {"rotation": (0.04 * leg, 0.0, 0.08 * leg)},
        "upper_arm.R": {"rotation": (0.72 * leg, 0.0, -0.22)},
        "forearm.R": {"rotation": (0.28 * leg, 0.0, 0.12)},
        "club": {"rotation": (0.0, 0.0, 0.12 * leg)},
        "thigh.L": {"rotation": (0.68 * leg, 0.0, 0.04)},
        "shin.L": {"rotation": (-0.48 if left_forward else 0.58, 0.0, 0.0)},
        "foot.L": {"rotation": (-0.26 if left_forward else 0.18, 0.0, 0.0)},
        "thigh.R": {"rotation": (-0.68 * leg, 0.0, -0.04)},
        "shin.R": {"rotation": (0.58 if left_forward else -0.48, 0.0, 0.0)},
        "foot.R": {"rotation": (0.18 if left_forward else -0.26, 0.0, 0.0)},
        "ear.L": {"rotation": (0.05, 0.0, 0.06 * leg)},
        "ear.R": {"rotation": (-0.05, 0.0, 0.06 * leg)},
    }


def run_frames() -> list[tuple[int, dict[str, dict]]]:
    airborne = {
        "pelvis": {"location": (0, 0, 0.075), "rotation": (0, 0, 0)},
        "spine": {"rotation": (0.15, 0, 0)},
        "chest": {"rotation": (0.13, 0, 0)},
        "neck": {"rotation": (-0.09, 0, 0)},
        "head": {"rotation": (-0.105, 0, 0)},
        "upper_arm.L": {"rotation": (0, 0, 0.14)},
        "forearm.L": {"rotation": (-0.16, 0, -0.1)},
        "upper_arm.R": {"rotation": (0.12, 0, -0.22)},
        "forearm.R": {"rotation": (-0.12, 0, 0.1)},
        "thigh.L": {"rotation": (0.1, 0, 0)},
        "shin.L": {"rotation": (0.32, 0, 0)},
        "foot.L": {"rotation": (0.04, 0, 0)},
        "thigh.R": {"rotation": (-0.1, 0, 0)},
        "shin.R": {"rotation": (0.32, 0, 0)},
        "foot.R": {"rotation": (0.04, 0, 0)},
        "shield": {"rotation": (0, 0, 0)},
        "club": {"rotation": (0, 0, 0)},
    }
    return [
        (1, run_pose(True, bob=0.02, lean=0.03)),
        (7, airborne),
        (13, run_pose(False, bob=0.02, lean=0.03)),
        (19, airborne),
        (25, run_pose(True, bob=0.02, lean=0.03)),
    ]


def attack_frames() -> list[tuple[int, dict[str, dict]]]:
    ready = {
        "pelvis": {"location": (0, 0, 0), "rotation": (0, 0, -0.08)},
        "spine": {"rotation": (0.12, 0, 0.08)},
        "chest": {"rotation": (0.1, 0, 0.16)},
        "head": {"rotation": (-0.12, 0, -0.12)},
        "upper_arm.R": {"rotation": (-0.48, 0.0, -0.58)},
        "forearm.R": {"rotation": (-0.55, 0.0, 0.22)},
        "hand.R": {"rotation": (0, 0, -0.16)},
        "club": {"rotation": (-0.42, 0.0, -0.56)},
        "upper_arm.L": {"rotation": (0.16, 0, 0.24)},
        "forearm.L": {"rotation": (-0.18, 0, -0.14)},
        "shield": {"rotation": (0.05, 0, 0.14)},
    }
    strike = {
        "pelvis": {"location": (0, 0, 0.025), "rotation": (0, 0, 0.14)},
        "spine": {"rotation": (0.2, 0, -0.16)},
        "chest": {"rotation": (0.19, 0, -0.34)},
        "neck": {"rotation": (-0.09, 0, 0.08)},
        "head": {"rotation": (-0.16, 0, 0.18)},
        "upper_arm.R": {"rotation": (0.82, 0.0, 0.42)},
        "forearm.R": {"rotation": (0.42, 0.0, -0.25)},
        "hand.R": {"rotation": (0, 0, 0.22)},
        "club": {"rotation": (0.78, 0.0, 0.58)},
        "upper_arm.L": {"rotation": (-0.05, 0, 0.18)},
        "forearm.L": {"rotation": (-0.1, 0, -0.08)},
        "shield": {"rotation": (-0.04, 0, 0.05)},
        "thigh.R": {"rotation": (0.18, 0, -0.04)},
        "foot.R": {"rotation": (-0.18, 0, 0)},
    }
    recover = {
        "pelvis": {"location": (0, 0, 0.005), "rotation": (0, 0, 0.03)},
        "spine": {"rotation": (0.11, 0, -0.03)},
        "chest": {"rotation": (0.09, 0, -0.04)},
        "head": {"rotation": (-0.08, 0, 0.04)},
        "upper_arm.R": {"rotation": (0.18, 0, -0.18)},
        "forearm.R": {"rotation": (-0.08, 0, 0.06)},
        "club": {"rotation": (0.12, 0, -0.08)},
        "upper_arm.L": {"rotation": (0.08, 0, 0.14)},
        "forearm.L": {"rotation": (-0.06, 0, -0.06)},
        "shield": {"rotation": (0, 0, 0.04)},
    }
    return [(1, ready), (12, ready), (20, strike), (28, recover), (36, ready)]


def hit_frames() -> list[tuple[int, dict[str, dict]]]:
    brace = {
        "pelvis": {"location": (0, 0, 0), "rotation": (0, 0, 0)},
        "spine": {"rotation": (0.08, 0, 0)},
        "chest": {"rotation": (0.08, 0, 0)},
        "head": {"rotation": (-0.07, 0, 0)},
        "upper_arm.L": {"rotation": (0.08, 0, 0.13)},
        "upper_arm.R": {"rotation": (0.1, 0, -0.15)},
        "club": {"rotation": (0, 0, -0.04)},
    }
    recoil = {
        "pelvis": {"location": (0, 0.015, -0.015), "rotation": (-0.08, 0, -0.1)},
        "spine": {"rotation": (-0.22, 0, 0.14)},
        "chest": {"rotation": (-0.24, 0, 0.18)},
        "neck": {"rotation": (0.16, 0, -0.08)},
        "head": {"rotation": (0.22, 0, -0.12)},
        "ear.L": {"rotation": (-0.1, 0, -0.12)},
        "ear.R": {"rotation": (0.1, 0, 0.12)},
        "upper_arm.L": {"rotation": (-0.32, 0, 0.28)},
        "forearm.L": {"rotation": (0.24, 0, -0.18)},
        "shield": {"rotation": (-0.22, 0, -0.08)},
        "upper_arm.R": {"rotation": (-0.34, 0, -0.34)},
        "forearm.R": {"rotation": (0.22, 0, 0.18)},
        "club": {"rotation": (-0.26, 0, -0.18)},
    }
    return [(1, brace), (8, recoil), (16, brace), (28, brace)]


def death_frames() -> list[tuple[int, dict[str, dict]]]:
    upright = {
        "pelvis": {"location": (0, 0, 0), "rotation": (0, 0, 0)},
        "spine": {"rotation": (0.08, 0, 0)},
        "chest": {"rotation": (0.08, 0, 0)},
        "head": {"rotation": (-0.08, 0, 0)},
        "upper_arm.R": {"rotation": (0.1, 0, -0.16)},
        "forearm.R": {"rotation": (-0.08, 0, 0.06)},
        "club": {"rotation": (0, 0, -0.04)},
        "upper_arm.L": {"rotation": (0.08, 0, 0.12)},
        "shield": {"rotation": (0, 0, 0.04)},
    }
    stagger = {
        "pelvis": {"location": (0, 0.02, -0.06), "rotation": (-0.18, 0, 0.18)},
        "spine": {"rotation": (-0.42, 0, -0.28)},
        "chest": {"rotation": (-0.48, 0, -0.34)},
        "neck": {"rotation": (0.22, 0, 0.1)},
        "head": {"rotation": (0.28, 0, 0.16)},
        "upper_arm.R": {"rotation": (-0.62, 0, -0.22)},
        "forearm.R": {"rotation": (0.36, 0, 0.18)},
        "club": {"rotation": (-0.54, 0, 0.16)},
        "upper_arm.L": {"rotation": (-0.42, 0, 0.24)},
        "forearm.L": {"rotation": (0.3, 0, -0.14)},
        "shield": {"rotation": (-0.28, 0, -0.12)},
    }
    down = {
        "pelvis": {"location": (0, 0.08, -0.2), "rotation": (-0.55, 0, 0.35)},
        "spine": {"rotation": (-1.1, 0.0, -0.42)},
        "chest": {"rotation": (-1.22, 0.0, -0.46)},
        "neck": {"rotation": (0.5, 0, 0.1)},
        "head": {"rotation": (0.62, 0.0, 0.22)},
        "ear.L": {"rotation": (-0.18, 0, -0.08)},
        "ear.R": {"rotation": (0.18, 0, 0.08)},
        "upper_arm.R": {"rotation": (-1.0, 0.0, -0.38)},
        "forearm.R": {"rotation": (0.62, 0.0, 0.25)},
        "club": {"rotation": (-0.95, 0.0, 0.35)},
        "upper_arm.L": {"rotation": (-0.86, 0.0, 0.2)},
        "forearm.L": {"rotation": (0.62, 0.0, -0.1)},
        "shield": {"rotation": (-0.54, 0.0, -0.18)},
        "thigh.L": {"rotation": (0.35, 0.0, 0.15)},
        "shin.L": {"rotation": (0.45, 0.0, 0.0)},
        "foot.L": {"rotation": (0.22, 0.0, 0.0)},
        "thigh.R": {"rotation": (-0.18, 0.0, -0.1)},
        "shin.R": {"rotation": (0.5, 0.0, 0.0)},
        "foot.R": {"rotation": (0.2, 0.0, 0.0)},
    }
    return [(1, upright), (14, stagger), (34, down), (48, down)]


def add_actions(armature: bpy.types.Object) -> None:
    clear_nla_tracks(armature, CLIPS)
    remove_actions(CLIPS)
    idle = create_pose_action(armature, "Idle_Stationary", idle_frames())
    walk = create_pose_action(armature, "Walk_InPlace", walk_frames())
    run = create_pose_action(armature, "Run_InPlace", run_frames())
    attack = create_pose_action(armature, "Attack_Swing", attack_frames())
    hit = create_pose_action(armature, "Hit_Reaction", hit_frames())
    death = create_pose_action(armature, "Death", death_frames())
    push_action_to_nla(armature, idle, 1, 60)
    push_action_to_nla(armature, walk, 1, 33)
    push_action_to_nla(armature, run, 1, 25)
    push_action_to_nla(armature, attack, 1, 36)
    push_action_to_nla(armature, hit, 1, 28)
    push_action_to_nla(armature, death, 1, 48)


def set_nla_tracks_muted(armature: bpy.types.Object, muted: bool) -> None:
    if not armature.animation_data:
        return
    for track in armature.animation_data.nla_tracks:
        track.mute = muted


def set_preview_pose(armature: bpy.types.Object) -> None:
    pose_bones = {bone.name for bone in armature.pose.bones}
    set_nla_tracks_muted(armature, True)
    if armature.animation_data:
        armature.animation_data.action = None
    bpy.context.scene.frame_set(1)
    reset_pose_bones(armature, pose_bones)
    apply_bone_transforms(
        armature,
        {
            "pelvis": {"location": (0, 0, 0.015), "rotation": (0, 0, -0.045)},
            "spine": {"rotation": (0.11, 0, 0.03)},
            "chest": {"rotation": (0.12, 0, 0.07)},
            "neck": {"rotation": (-0.08, 0, -0.015)},
            "head": {"rotation": (-0.09, 0, -0.035)},
            "ear.L": {"rotation": (0.03, 0, -0.055)},
            "ear.R": {"rotation": (-0.03, 0, 0.055)},
            "upper_arm.L": {"rotation": (0.04, 0, 0.18)},
            "forearm.L": {"rotation": (-0.09, 0, -0.09)},
            "shield": {"rotation": (0.02, 0, 0.08)},
            "upper_arm.R": {"rotation": (-0.16, 0, -0.32)},
            "forearm.R": {"rotation": (-0.22, 0, 0.14)},
            "hand.R": {"rotation": (0, 0, -0.08)},
            "club": {"rotation": (-0.18, 0, -0.22)},
            "thigh.L": {"rotation": (0.1, 0, 0.03)},
            "shin.L": {"rotation": (0.1, 0, 0)},
            "foot.L": {"rotation": (-0.04, 0, 0)},
            "thigh.R": {"rotation": (-0.08, 0, -0.04)},
            "shin.R": {"rotation": (0.12, 0, 0)},
            "foot.R": {"rotation": (0.05, 0, 0)},
        },
    )
    bpy.context.view_layer.update()


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
    world.color = (0.03, 0.034, 0.028)

    camera_data = bpy.data.cameras.new("CAM_GoblinGruntEnemy_Preview")
    camera = bpy.data.objects.new("CAM_GoblinGruntEnemy_Preview", camera_data)
    bpy.context.scene.collection.objects.link(camera)
    camera.location = (2.15, -5.05, 1.85)
    camera.data.lens = 58
    camera.data.dof.use_dof = True
    camera.data.dof.focus_distance = 5.1
    camera.data.dof.aperture_fstop = 5.6
    look_at(camera, (0.28, -0.22, 1.05))
    bpy.context.scene.camera = camera
    for source in list(camera.users_collection):
        source.objects.unlink(camera)
    collection("LIGHTING_CAMERA").objects.link(camera)

    lights = [
        ("LGT_Key_GoblinWarmSoftbox", "AREA", (-2.3, -3.15, 3.3), 520, 3.8),
        ("LGT_Rim_ColdShieldEdge", "AREA", (2.6, 1.35, 2.45), 180, 2.2),
        ("LGT_Fill_DungeonAmber", "POINT", (1.35, -2.1, 1.4), 90, 0),
    ]
    for name, kind, loc, energy, size in lights:
        data = bpy.data.lights.new(name, kind)
        obj = bpy.data.objects.new(name, data)
        bpy.context.scene.collection.objects.link(obj)
        obj.location = loc
        data.energy = energy
        if hasattr(data, "size") and size:
            data.size = size
        look_at(obj, (0.06, -0.18, 1.0))
        for source in list(obj.users_collection):
            source.objects.unlink(obj)
        collection("LIGHTING_CAMERA").objects.link(obj)


def configure_scene() -> None:
    scene = bpy.context.scene
    scene.name = "SCN_GoblinGruntEnemy"
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
            "source": "Blender Python asset generator",
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
            "Original stylized low-poly fantasy grunt enemy with exaggerated ears, sharp teeth, ragged cloth armor, club, shield, and claws.",
            "Embedded GLB clips: Idle_Stationary, Walk_InPlace, Run_InPlace, Attack_Swing, Hit_Reaction, and Death.",
            "Mixamo FBX and OBJ ZIP are best-effort exports; stylized proportions, exaggerated ears, weapon geometry, shield geometry, and whole-part weights may need manual Mixamo adjustment.",
            MIXAMO_ORIENTATION_NOTE,
            "Display base and contact-shadow extras are excluded from Mixamo exports.",
        ],
    }


def export_asset(paths: dict[str, Path], armature: bpy.types.Object) -> None:
    ensure_dir(paths["blend"].parent)
    ensure_dir(paths["glb"].parent)
    ensure_dir(paths["preview"].parent)
    ensure_dir(paths["textures"])
    ensure_dir(paths["exports"])

    for block in (bpy.data.materials, bpy.data.curves, bpy.data.images):
        for item in list(block):
            if item.users == 0:
                block.remove(item)

    set_preview_pose(armature)
    bpy.ops.wm.save_as_mainfile(filepath=str(paths["blend"]))

    set_nla_tracks_muted(armature, False)
    export_glb(paths["glb"], armature_objects() + mesh_objects())
    mixamo = mixamo_objects()
    export_mixamo_fbx(paths["mixamo_fbx"], mixamo)
    export_mixamo_obj_zip(paths["mixamo_obj_zip"], paths["obj_work"], mixamo)

    set_preview_pose(armature)
    bpy.context.scene.render.filepath = str(paths["preview"])
    bpy.ops.render.render(write_still=True)


def main() -> dict:
    paths = out_paths()
    clear_scene()
    configure_scene()
    mats = make_materials()
    armature, _meshes = build_character(mats)
    add_actions(armature)
    set_preview_pose(armature)
    setup_lighting_and_camera()
    export_asset(paths, armature)
    metadata = collect_metadata(paths)
    write_json(paths["metadata"], metadata)
    return metadata


if __name__ == "__main__":
    result = main()
    print(json.dumps(result, indent=2))
