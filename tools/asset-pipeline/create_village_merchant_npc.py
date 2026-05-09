"""Generate the Village Merchant NPC asset in Blender.

Run from Blender Python through the live MCP bridge. The script is repeatable:
it creates the source scene, embeds default web animation clips, exports the
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

ASSET_SLUG = "village-merchant-npc"
ASSET_NAME = "Village Merchant NPC"
CLIPS = ("Idle_Stationary", "Walk_InPlace")
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
        "skin": make_mat("MAT_Skin_SoftMerchant", (0.96, 0.64, 0.46, 1), roughness=0.78),
        "blush": make_mat("MAT_Skin_RoseBlush", (0.98, 0.34, 0.34, 0.68), roughness=0.84, alpha=0.68),
        "hair": make_mat("MAT_Hair_ChestnutShort", (0.24, 0.12, 0.055, 1), roughness=0.7),
        "eye_white": make_mat("MAT_Eye_WarmWhite", (0.98, 0.97, 0.92, 1), roughness=0.36),
        "iris": make_mat("MAT_Eye_HazelFriendly", (0.23, 0.45, 0.26, 1), roughness=0.42),
        "shirt": make_mat("MAT_Cloth_CreamShirt", (0.86, 0.78, 0.62, 1), roughness=0.84),
        "apron": make_mat("MAT_Apron_MutedMarketGreen", (0.28, 0.45, 0.31, 1), roughness=0.86),
        "apron_shadow": make_mat("MAT_Apron_DarkFoldGreen", (0.13, 0.23, 0.16, 1), roughness=0.9),
        "leather": make_mat("MAT_Leather_WarmBrown", (0.46, 0.23, 0.105, 1), roughness=0.76),
        "brass": make_mat("MAT_Metal_BrassCoins", (0.95, 0.63, 0.22, 1), roughness=0.44, metallic=0.24),
        "boots": make_mat("MAT_Boots_DarkMarketLeather", (0.12, 0.075, 0.045, 1), roughness=0.82),
        "hat": make_mat("MAT_Hat_TawnyFelt", (0.58, 0.38, 0.18, 1), roughness=0.88),
        "base": make_mat("MAT_Base_NeutralSlate", (0.1, 0.11, 0.105, 1), roughness=0.88),
        "contact": make_mat("MAT_Shadow_BakedSoftContact", (0.025, 0.023, 0.02, 0.56), roughness=0.9, alpha=0.56),
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
    armature.name = "RIG_VillageMerchantNPC_BasicArmature"
    armature.data.name = "ARM_VillageMerchantNPC_Humanoid"
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
    bone("spine", (0, 0, 0.82), (0, -0.01, 1.36), "pelvis")
    bone("chest", (0, -0.01, 1.36), (0, -0.02, 1.7), "spine")
    bone("neck", (0, -0.02, 1.7), (0, -0.02, 1.91), "chest")
    bone("head", (0, -0.02, 1.91), (0, -0.04, 2.62), "neck")
    bone("hair_hat", (0, 0.02, 2.35), (0, 0.0, 2.95), "head")
    bone("upper_arm.L", (-0.34, -0.02, 1.47), (-0.64, -0.11, 1.16), "chest")
    bone("forearm.L", (-0.64, -0.11, 1.16), (-0.84, -0.24, 0.9), "upper_arm.L")
    bone("hand.L", (-0.84, -0.24, 0.9), (-0.94, -0.31, 0.8), "forearm.L")
    bone("upper_arm.R", (0.34, -0.02, 1.47), (0.64, -0.11, 1.16), "chest")
    bone("forearm.R", (0.64, -0.11, 1.16), (0.84, -0.24, 0.9), "upper_arm.R")
    bone("hand.R", (0.84, -0.24, 0.9), (0.94, -0.31, 0.8), "forearm.R")
    bone("thigh.L", (-0.17, 0, 0.55), (-0.21, -0.02, 0.27), "pelvis")
    bone("shin.L", (-0.21, -0.02, 0.27), (-0.22, -0.04, 0.08), "thigh.L")
    bone("foot.L", (-0.22, -0.04, 0.08), (-0.23, -0.28, 0.04), "shin.L")
    bone("thigh.R", (0.17, 0, 0.55), (0.21, -0.02, 0.27), "pelvis")
    bone("shin.R", (0.21, -0.02, 0.27), (0.22, -0.04, 0.08), "thigh.R")
    bone("foot.R", (0.22, -0.04, 0.08), (0.23, -0.28, 0.04), "shin.R")
    bone("satchel", (-0.43, -0.18, 1.1), (-0.72, -0.26, 0.72), "chest")
    bone("pouch", (0.43, -0.2, 0.9), (0.62, -0.27, 0.68), "pelvis")

    bpy.ops.object.mode_set(mode="OBJECT")
    return armature


def add_coin(
    name: str,
    loc: tuple[float, float, float],
    mat: bpy.types.Material,
    *,
    radius: float = 0.035,
    bone_name: str = "pouch",
    armature: bpy.types.Object,
    meshes: list[bpy.types.Object],
) -> bpy.types.Object:
    coin = cylinder(
        name,
        loc,
        radius,
        0.012,
        mat,
        vertices=20,
        rotation=(math.radians(90), 0, 0),
        bevel=0.002,
        collection_name="PROPS",
    )
    meshes.append(coin)
    bind_to_bone(coin, armature, bone_name)
    return coin


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

    add(uv_sphere("CHR_Head_FriendlyRounded", (0, -0.04, 2.28), (0.56, 0.5, 0.58), mats["skin"], segments=40, rings=20, collection_name="CHARACTER_BODY"), "head")
    add(uv_sphere("CHR_Torso_CreamTunic", (0, 0.0, 1.22), (0.43, 0.31, 0.47), mats["shirt"], segments=36, rings=18, collection_name="CHARACTER_BODY"), "spine")
    add(uv_sphere("CHR_Hips_TunicRounded", (0, 0.0, 0.72), (0.36, 0.27, 0.22), mats["leather"], segments=32, rings=14, collection_name="CHARACTER_BODY"), "pelvis")
    add(uv_sphere("OUT_Collar_CreamFold", (0, -0.27, 1.53), (0.28, 0.045, 0.11), mats["shirt"], segments=24, rings=10, collection_name="OUTFIT"), "chest")

    for side, sign in [("L", -1), ("R", 1)]:
        add(uv_sphere(f"CHR_Shoulder_{side}_CreamSleeve", (sign * 0.39, -0.04, 1.45), (0.15, 0.12, 0.17), mats["shirt"], segments=24, rings=12, collection_name="OUTFIT"), f"upper_arm.{side}")
        add(bevel_curve(f"CHR_UpperArm_{side}_RolledSleeve", [(sign * 0.43, -0.06, 1.36), (sign * 0.58, -0.1, 1.19), (sign * 0.67, -0.16, 1.05)], mats["shirt"], bevel_depth=0.066, bevel_resolution=4, collection_name="CHARACTER_BODY"), f"upper_arm.{side}")
        add(bevel_curve(f"CHR_Forearm_{side}_SoftSkin", [(sign * 0.68, -0.16, 1.05), (sign * 0.79, -0.22, 0.91), (sign * 0.9, -0.28, 0.81)], mats["skin"], bevel_depth=0.055, bevel_resolution=4, collection_name="CHARACTER_BODY"), f"forearm.{side}")
        add(uv_sphere(f"CHR_Hand_{side}_OpenMitten", (sign * 0.93, -0.31, 0.78), (0.105, 0.085, 0.095), mats["skin"], segments=22, rings=10, collection_name="CHARACTER_BODY"), f"hand.{side}")
        add(uv_sphere(f"CHR_Thigh_{side}_TunicLeg", (sign * 0.16, -0.01, 0.39), (0.12, 0.1, 0.24), mats["shirt"], segments=22, rings=10, collection_name="CHARACTER_BODY"), f"thigh.{side}")
        add(uv_sphere(f"CHR_Shin_{side}_SoftStocking", (sign * 0.2, -0.03, 0.21), (0.09, 0.08, 0.16), mats["skin"], segments=20, rings=10, collection_name="CHARACTER_BODY"), f"shin.{side}")
        add(uv_sphere(f"OUT_Boot_{side}_SimpleLeather", (sign * 0.22, -0.13, 0.08), (0.15, 0.22, 0.09), mats["boots"], segments=26, rings=12, collection_name="OUTFIT"), f"foot.{side}")
        add(cube(f"OUT_Boot_{side}_SoleLip", (sign * 0.22, -0.19, 0.025), (0.14, 0.17, 0.025), mats["leather"], bevel=0.018, collection_name="BAKED_EFFECTS"), f"foot.{side}")

    # Tunic, apron, and market-wear layers.
    add(cube("OUT_Apron_FrontMutedGreen", (0, -0.315, 1.02), (0.33, 0.035, 0.43), mats["apron"], bevel=0.035, collection_name="OUTFIT"), "spine")
    add(cube("OUT_Apron_LowerPocket", (0.11, -0.355, 0.79), (0.13, 0.018, 0.105), mats["apron_shadow"], bevel=0.018, collection_name="OUTFIT"), "pelvis")
    add(cube("OUT_Apron_BottomFoldShadow", (0, -0.36, 0.62), (0.31, 0.012, 0.04), mats["apron_shadow"], bevel=0.012, collection_name="BAKED_EFFECTS"), "pelvis")
    add(bevel_curve("OUT_Apron_NeckStrap", [(-0.18, -0.34, 1.53), (-0.05, -0.37, 1.67), (0.18, -0.34, 1.53)], mats["leather"], bevel_depth=0.015, bevel_resolution=2, collection_name="OUTFIT"), "chest")
    add(bevel_curve("OUT_Belt_WarmLeather", [(-0.38, -0.29, 0.93), (-0.05, -0.32, 0.89), (0.39, -0.29, 0.93)], mats["leather"], bevel_depth=0.032, bevel_resolution=3, collection_name="OUTFIT"), "pelvis")
    add(cube("OUT_Belt_BrassBuckle", (0, -0.335, 0.91), (0.08, 0.018, 0.06), mats["brass"], bevel=0.012, collection_name="OUTFIT"), "pelvis")

    # Pouches, satchel, and brass coin details.
    add(bevel_curve("PROP_Satchel_CrossbodyStrap", [(-0.36, -0.34, 1.58), (-0.08, -0.36, 1.22), (0.33, -0.35, 0.84)], mats["leather"], bevel_depth=0.025, bevel_resolution=3, collection_name="PROPS"), "satchel")
    add(cube("PROP_Satchel_BoxSmall", (-0.58, -0.34, 0.78), (0.19, 0.075, 0.16), mats["leather"], bevel=0.035, collection_name="PROPS"), "satchel")
    add(cube("PROP_Satchel_BrassLatch", (-0.58, -0.392, 0.79), (0.055, 0.012, 0.032), mats["brass"], bevel=0.01, collection_name="PROPS"), "satchel")
    add(cube("PROP_CoinPouch_RoundLeather", (0.48, -0.32, 0.78), (0.13, 0.055, 0.14), mats["leather"], bevel=0.04, collection_name="PROPS"), "pouch")
    add(bevel_curve("PROP_CoinPouch_Drawstring", [(0.39, -0.365, 0.88), (0.48, -0.38, 0.91), (0.57, -0.365, 0.88)], mats["brass"], bevel_depth=0.01, bevel_resolution=2, collection_name="PROPS"), "pouch")
    for index, (x, z) in enumerate([(0.39, 0.73), (0.45, 0.7), (0.52, 0.725), (0.58, 0.695), (0.19, 0.79)]):
        bone_name = "pouch" if x > 0.3 else "pelvis"
        add_coin(
            f"PROP_BrassCoin_{index + 1:02d}",
            (x, -0.39, z),
            mats["brass"],
            radius=0.028 if index < 4 else 0.023,
            bone_name=bone_name,
            armature=armature,
            meshes=meshes,
        )

    # Expressive face, short hair, and merchant hat.
    for side, sign in [("L", -1), ("R", 1)]:
        add(uv_sphere(f"FACE_Eye_{side}_WhiteOval", (sign * 0.2, -0.492, 2.35), (0.115, 0.018, 0.15), mats["eye_white"], segments=26, rings=12, collection_name="FACE"), "head")
        add(uv_sphere(f"FACE_Eye_{side}_HazelIris", (sign * 0.2, -0.512, 2.34), (0.058, 0.01, 0.082), mats["iris"], segments=18, rings=8, collection_name="FACE"), "head")
        add(uv_sphere(f"FACE_Eye_{side}_Pupil", (sign * 0.2, -0.525, 2.335), (0.027, 0.006, 0.042), mats["hair"], segments=14, rings=6, collection_name="FACE"), "head")
        add(bevel_curve(f"FACE_Brow_{side}_FriendlyArch", [(sign * 0.12, -0.526, 2.51), (sign * 0.21, -0.535, 2.535), (sign * 0.31, -0.52, 2.51)], mats["hair"], bevel_depth=0.01, bevel_resolution=2, collection_name="FACE"), "head")
        add(uv_sphere(f"FACE_Blush_{side}_SoftOval", (sign * 0.34, -0.492, 2.2), (0.06, 0.008, 0.026), mats["blush"], segments=14, rings=6, collection_name="BAKED_EFFECTS"), "head")
    add(bevel_curve("FACE_Mouth_OpenFriendlySmile", [(-0.07, -0.535, 2.13), (0, -0.555, 2.095), (0.085, -0.532, 2.13)], mats["hair"], bevel_depth=0.009, bevel_resolution=2, collection_name="FACE"), "head")
    add(uv_sphere("FACE_Nose_TinyWarm", (0, -0.514, 2.23), (0.025, 0.007, 0.018), mats["blush"], segments=12, rings=6, collection_name="FACE"), "head")

    add(uv_sphere("HAIR_Cap_ShortChestnut", (0, -0.015, 2.58), (0.57, 0.51, 0.22), mats["hair"], segments=36, rings=14, collection_name="HAIR"), "hair_hat")
    hair_locks = [
        ("FrontLeft", [(-0.18, -0.43, 2.7), (-0.3, -0.53, 2.52), (-0.25, -0.49, 2.32)], 0.042),
        ("FrontRight", [(0.17, -0.43, 2.71), (0.32, -0.52, 2.54), (0.28, -0.48, 2.34)], 0.04),
        ("SideLeft", [(-0.48, -0.08, 2.55), (-0.58, -0.13, 2.33), (-0.5, -0.1, 2.12)], 0.038),
        ("SideRight", [(0.48, -0.08, 2.55), (0.58, -0.13, 2.33), (0.5, -0.1, 2.12)], 0.038),
    ]
    for name, points, depth in hair_locks:
        add(bevel_curve(f"HAIR_Lock_{name}", points, mats["hair"], bevel_depth=depth, bevel_resolution=4, collection_name="HAIR"), "hair_hat")
    add(cylinder("OUT_Hat_Brim_WideMerchant", (0, -0.02, 2.72), 0.56, 0.045, mats["hat"], vertices=48, scale=(1.08, 0.86, 1), bevel=0.008, collection_name="OUTFIT"), "hair_hat")
    add(cylinder("OUT_Hat_Crown_RoundedFelt", (0, -0.01, 2.88), 0.31, 0.28, mats["hat"], vertices=42, scale=(1.0, 0.86, 1), bevel=0.02, collection_name="OUTFIT"), "hair_hat")
    add(bevel_curve("OUT_Hat_BrassBandCharm", [(-0.22, -0.29, 2.84), (0.0, -0.32, 2.83), (0.22, -0.29, 2.84)], mats["brass"], bevel_depth=0.012, bevel_resolution=2, collection_name="OUTFIT"), "hair_hat")
    add(cube("OUT_Hat_FrontPatch", (0.02, -0.326, 2.86), (0.065, 0.014, 0.04), mats["brass"], bevel=0.008, collection_name="OUTFIT"), "hair_hat")

    # Display base and baked shadow are web-only staging geometry.
    add(cylinder("BASE_DisplayDisc_NeutralSlate", (0, 0, -0.025), 0.72, 0.045, mats["base"], vertices=64, collection_name="BAKED_EFFECTS"), "root")
    add(cylinder("BASE_BakedSoftContactShadow", (0, -0.04, 0.004), 0.55, 0.01, mats["contact"], vertices=64, scale=(1, 0.68, 1), collection_name="BAKED_EFFECTS"), "root")

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
        "hair_hat": {"rotation": (0, 0, 0)},
        "upper_arm.L": {"rotation": (0.05, 0, 0.04)},
        "forearm.L": {"rotation": (-0.03, 0, -0.02)},
        "upper_arm.R": {"rotation": (0.04, 0, -0.04)},
        "forearm.R": {"rotation": (-0.04, 0, 0.02)},
        "satchel": {"rotation": (0, 0, 0)},
        "pouch": {"rotation": (0, 0, 0)},
    }
    inhale = {
        "pelvis": {"location": (0, 0, 0.022), "rotation": (0, 0, -0.01)},
        "spine": {"rotation": (0.018, 0, 0.012)},
        "chest": {"rotation": (0.028, 0, -0.01)},
        "neck": {"rotation": (-0.012, 0, 0.006)},
        "head": {"rotation": (-0.014, 0, -0.016)},
        "hair_hat": {"rotation": (0.022, 0, 0.012)},
        "upper_arm.L": {"rotation": (0.075, 0, 0.055)},
        "forearm.L": {"rotation": (-0.035, 0, -0.032)},
        "upper_arm.R": {"rotation": (0.065, 0, -0.052)},
        "forearm.R": {"rotation": (-0.045, 0, 0.03)},
        "satchel": {"rotation": (0, 0, 0.026)},
        "pouch": {"rotation": (0, 0, -0.018)},
    }
    return [(1, neutral), (30, inhale), (60, neutral)]


def walk_pose(left_forward: bool, *, bob: float = 0.0, lean: float = 0.0) -> dict[str, dict]:
    leg = 1 if left_forward else -1
    return {
        "pelvis": {"location": (0, 0, bob), "rotation": (0, 0, 0.034 * leg)},
        "spine": {"rotation": (0.04 + lean, 0, -0.032 * leg)},
        "chest": {"rotation": (0.028 + lean, 0, 0.03 * leg)},
        "neck": {"rotation": (-0.018 - lean, 0, 0)},
        "head": {"rotation": (-0.024 - lean, 0, 0.02 * leg)},
        "upper_arm.L": {"rotation": (-0.42 * leg, 0, 0.035)},
        "forearm.L": {"rotation": (-0.14 * leg, 0, -0.034)},
        "upper_arm.R": {"rotation": (0.42 * leg, 0, -0.035)},
        "forearm.R": {"rotation": (0.14 * leg, 0, 0.034)},
        "thigh.L": {"rotation": (0.42 * leg, 0, 0.02)},
        "shin.L": {"rotation": (-0.25 if left_forward else 0.34, 0, 0)},
        "foot.L": {"rotation": (-0.16 if left_forward else 0.12, 0, 0)},
        "thigh.R": {"rotation": (-0.42 * leg, 0, -0.02)},
        "shin.R": {"rotation": (0.34 if left_forward else -0.25, 0, 0)},
        "foot.R": {"rotation": (0.12 if left_forward else -0.16, 0, 0)},
        "hair_hat": {"rotation": (0.028, 0, 0.032 * leg)},
        "satchel": {"rotation": (0, 0, -0.075 * leg)},
        "pouch": {"rotation": (0, 0, 0.055 * leg)},
    }


def walk_frames() -> list[tuple[int, dict[str, dict]]]:
    passing = {
        "pelvis": {"location": (0, 0, 0.038), "rotation": (0, 0, 0)},
        "spine": {"rotation": (0.03, 0, 0)},
        "chest": {"rotation": (0.022, 0, 0)},
        "neck": {"rotation": (-0.016, 0, 0)},
        "head": {"rotation": (-0.02, 0, 0)},
        "upper_arm.L": {"rotation": (0, 0, 0.03)},
        "forearm.L": {"rotation": (0, 0, 0)},
        "upper_arm.R": {"rotation": (0, 0, -0.03)},
        "forearm.R": {"rotation": (0, 0, 0)},
        "thigh.L": {"rotation": (0, 0, 0)},
        "shin.L": {"rotation": (0.16, 0, 0)},
        "foot.L": {"rotation": (0, 0, 0)},
        "thigh.R": {"rotation": (0, 0, 0)},
        "shin.R": {"rotation": (0.16, 0, 0)},
        "foot.R": {"rotation": (0, 0, 0)},
        "hair_hat": {"rotation": (0.02, 0, 0)},
        "satchel": {"rotation": (0, 0, 0)},
        "pouch": {"rotation": (0, 0, 0)},
    }
    return [
        (1, walk_pose(True, bob=0.0, lean=0.006)),
        (9, passing),
        (17, walk_pose(False, bob=0.0, lean=0.006)),
        (25, passing),
        (33, walk_pose(True, bob=0.0, lean=0.006)),
    ]


def add_actions(armature: bpy.types.Object) -> None:
    clear_nla_tracks(armature, CLIPS)
    remove_actions(CLIPS)
    idle = create_pose_action(armature, "Idle_Stationary", idle_frames())
    walk = create_pose_action(armature, "Walk_InPlace", walk_frames())
    push_action_to_nla(armature, idle, 1, 60)
    push_action_to_nla(armature, walk, 1, 33)


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
    world.color = (0.025, 0.03, 0.028)

    camera_data = bpy.data.cameras.new("CAM_VillageMerchantNPC_Preview")
    camera = bpy.data.objects.new("CAM_VillageMerchantNPC_Preview", camera_data)
    bpy.context.scene.collection.objects.link(camera)
    camera.location = (2.25, -5.8, 2.2)
    camera.data.lens = 55
    camera.data.dof.use_dof = True
    camera.data.dof.focus_distance = 5.8
    camera.data.dof.aperture_fstop = 6.3
    look_at(camera, (0.08, -0.16, 1.42))
    bpy.context.scene.camera = camera
    for source in list(camera.users_collection):
        source.objects.unlink(camera)
    collection("LIGHTING_CAMERA").objects.link(camera)

    lights = [
        ("LGT_Key_WarmMarketSoftbox", "AREA", (-2.4, -3.4, 4.1), 520, 4.4),
        ("LGT_Rim_CoolSilhouette", "AREA", (2.5, 1.65, 2.75), 165, 2.3),
        ("LGT_Fill_BrassBounce", "POINT", (1.55, -2.05, 1.6), 85, 0),
    ]
    for name, kind, loc, energy, size in lights:
        data = bpy.data.lights.new(name, kind)
        obj = bpy.data.objects.new(name, data)
        bpy.context.scene.collection.objects.link(obj)
        obj.location = loc
        data.energy = energy
        if hasattr(data, "size") and size:
            data.size = size
        look_at(obj, (0.05, -0.12, 1.45))
        for source in list(obj.users_collection):
            source.objects.unlink(obj)
        collection("LIGHTING_CAMERA").objects.link(obj)


def configure_scene() -> None:
    scene = bpy.context.scene
    scene.name = "SCN_VillageMerchantNPC"
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
            "Original stylized fantasy RPG village merchant NPC with tunic, apron, coin pouch, satchel, short hair, and merchant hat.",
            "Embedded GLB clips: Idle_Stationary and Walk_InPlace.",
            "Mixamo FBX and OBJ ZIP are best-effort exports; stylized proportions, modular clothing, hat, and whole-part weights may need manual Mixamo adjustment.",
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
