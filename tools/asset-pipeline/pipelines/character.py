"""Humanoid character pipeline."""

from __future__ import annotations

from math import radians

import bpy

from . import common


def create_armature(spec: dict) -> bpy.types.Object:
    bpy.ops.object.armature_add(enter_editmode=True, location=(0, 0, 0))
    armature = bpy.context.object
    safe_name = spec["slug"].replace("-", "_")
    armature.name = f"RIG_{safe_name}_BasicArmature"
    armature.data.name = f"ARM_{safe_name}_Humanoid"
    armature.show_in_front = True
    rig_collection = common.collection("RIG")
    for source in list(armature.users_collection):
        source.objects.unlink(armature)
    rig_collection.objects.link(armature)

    bones = armature.data.edit_bones
    root = bones[0]
    root.name = "root"
    root.head = (0, 0, 0.04)
    root.tail = (0, 0, 0.35)

    def bone(name, head, tail, parent):
        edit_bone = bones.new(name)
        edit_bone.head = head
        edit_bone.tail = tail
        edit_bone.parent = bones[parent]
        return edit_bone

    bone("pelvis", (0, 0, 0.45), (0, 0, 0.78), "root")
    bone("spine", (0, 0, 0.78), (0, -0.02, 1.34), "pelvis")
    bone("chest", (0, -0.02, 1.34), (0, -0.03, 1.62), "spine")
    bone("neck", (0, -0.03, 1.62), (0, -0.04, 1.78), "chest")
    bone("head", (0, -0.04, 1.78), (0, -0.06, 2.24), "neck")
    bone("upper_arm.L", (-0.28, -0.02, 1.42), (-0.58, -0.08, 1.18), "chest")
    bone("forearm.L", (-0.58, -0.08, 1.18), (-0.78, -0.1, 0.94), "upper_arm.L")
    bone("hand.L", (-0.78, -0.1, 0.94), (-0.86, -0.1, 0.86), "forearm.L")
    bone("upper_arm.R", (0.28, -0.02, 1.42), (0.58, -0.08, 1.18), "chest")
    bone("forearm.R", (0.58, -0.08, 1.18), (0.78, -0.1, 0.94), "upper_arm.R")
    bone("hand.R", (0.78, -0.1, 0.94), (0.86, -0.1, 0.86), "forearm.R")
    bone("thigh.L", (-0.18, 0, 0.48), (-0.24, 0, 0.2), "pelvis")
    bone("shin.L", (-0.24, 0, 0.2), (-0.22, -0.02, 0.04), "thigh.L")
    bone("foot.L", (-0.22, -0.02, 0.04), (-0.22, -0.24, 0.02), "shin.L")
    bone("thigh.R", (0.18, 0, 0.48), (0.24, 0, 0.2), "pelvis")
    bone("shin.R", (0.24, 0, 0.2), (0.22, -0.02, 0.04), "thigh.R")
    bone("foot.R", (0.22, -0.02, 0.04), (0.22, -0.24, 0.02), "shin.R")
    bpy.ops.object.mode_set(mode="OBJECT")
    return armature


def bind_whole_part(obj: bpy.types.Object, armature: bpy.types.Object, bone_name: str) -> None:
    if obj.type != "MESH":
        return
    group = obj.vertex_groups.new(name=bone_name)
    group.add(list(range(len(obj.data.vertices))), 1.0, "ADD")
    mod = obj.modifiers.new("ARM_whole_part_deform", "ARMATURE")
    mod.object = armature
    obj.parent = armature


def create_pose_action(armature: bpy.types.Object, name: str, frames: list[tuple[int, dict]], end: int) -> None:
    action = bpy.data.actions.new(name)
    action.use_fake_user = True
    animation_data = armature.animation_data_create()
    animation_data.action = action
    affected = {bone_name for _, frame in frames for bone_name in frame}
    for frame_index, transforms in frames:
        bpy.context.scene.frame_set(frame_index)
        for bone_name in affected:
            bone = armature.pose.bones.get(bone_name)
            if bone:
                bone.rotation_mode = "XYZ"
                bone.rotation_euler = (0, 0, 0)
                bone.location = (0, 0, 0)
                bone.scale = (1, 1, 1)
        for bone_name, rotation in transforms.items():
            bone = armature.pose.bones.get(bone_name)
            if bone:
                bone.rotation_mode = "XYZ"
                bone.rotation_euler = rotation
        for bone_name in affected:
            bone = armature.pose.bones.get(bone_name)
            if bone:
                bone.keyframe_insert(data_path="rotation_euler", frame=frame_index)
    animation_data.action = None
    track = animation_data.nla_tracks.new()
    track.name = name
    strip = track.strips.new(name, 1, action)
    strip.frame_start = 1
    strip.frame_end = end


def generate(spec: dict) -> dict:
    mats = common.prepare_scene(spec, frame_end=84)
    armature = create_armature(spec)
    parts = [armature]

    chibi = spec.get("pipelineId") == "character.chibi_mascot"
    head_scale = (0.36, 0.32, 0.36) if chibi else (0.28, 0.25, 0.3)
    torso = common.uv_sphere("CHR_AgentCharacter_Torso", (0, 0, 1.08), (0.34, 0.24, 0.48), mats["primary"], segments=32, rings=16, collection_name="CHARACTER_BODY")
    head = common.uv_sphere("CHR_AgentCharacter_Head", (0, -0.02, 1.76), head_scale, mats["secondary"], segments=32, rings=16, collection_name="CHARACTER_BODY")
    parts.extend([torso, head])
    bind_whole_part(torso, armature, "spine")
    bind_whole_part(head, armature, "head")

    limb_specs = [
        ("CHR_AgentCharacter_UpperArm_L", (-0.42, -0.04, 1.28), "upper_arm.L"),
        ("CHR_AgentCharacter_Forearm_L", (-0.64, -0.06, 1.02), "forearm.L"),
        ("CHR_AgentCharacter_UpperArm_R", (0.42, -0.04, 1.28), "upper_arm.R"),
        ("CHR_AgentCharacter_Forearm_R", (0.64, -0.06, 1.02), "forearm.R"),
        ("CHR_AgentCharacter_Thigh_L", (-0.16, 0, 0.58), "thigh.L"),
        ("CHR_AgentCharacter_Shin_L", (-0.18, -0.02, 0.24), "shin.L"),
        ("CHR_AgentCharacter_Thigh_R", (0.16, 0, 0.58), "thigh.R"),
        ("CHR_AgentCharacter_Shin_R", (0.18, -0.02, 0.24), "shin.R"),
    ]
    for name, loc, bone_name in limb_specs:
        limb = common.uv_sphere(name, loc, (0.105, 0.095, 0.22), mats["dark"], segments=20, rings=10, collection_name="CHARACTER_BODY")
        parts.append(limb)
        bind_whole_part(limb, armature, bone_name)

    for x, bone_name in [(-0.2, "foot.L"), (0.2, "foot.R")]:
        foot = common.cube(f"CHR_AgentCharacter_Foot_{bone_name[-1]}", (x, -0.14, 0.045), (0.18, 0.26, 0.055), mats["dark"], bevel=0.025, collection_name="CHARACTER_BODY")
        parts.append(foot)
        bind_whole_part(foot, armature, bone_name)

    for index, label in enumerate((spec.get("requiredParts") or [])[:6]):
        detail = common.cube(f"OUT_AgentCharacter_Detail_{index + 1}", (-0.26 + index * 0.105, -0.23, 1.24 - (index % 2) * 0.22), (0.055, 0.035, 0.09), mats["accent"], bevel=0.012, collection_name="OUTFIT")
        detail["asset_part_hint"] = label
        parts.append(detail)
        bind_whole_part(detail, armature, "chest" if index < 4 else "pelvis")

    left_eye = common.uv_sphere("FACE_AgentCharacter_Eye_L", (-0.11, -0.285, 1.82), (0.045, 0.016, 0.055), mats["dark"], segments=16, rings=8, collection_name="FACE")
    right_eye = common.uv_sphere("FACE_AgentCharacter_Eye_R", (0.11, -0.285, 1.82), (0.045, 0.016, 0.055), mats["dark"], segments=16, rings=8, collection_name="FACE")
    parts.extend([left_eye, right_eye])
    bind_whole_part(left_eye, armature, "head")
    bind_whole_part(right_eye, armature, "head")
    shadow = common.add_contact_shadow("BASE_AgentCharacter_ContactShadow", 0.55)
    parts.append(shadow)

    clip_names = [clip["name"] for clip in spec.get("animationClips", [])]
    if "Idle_Stationary" in clip_names:
        create_pose_action(
            armature,
            "Idle_Stationary",
            [
                (1, {"spine": (radians(0), 0, 0)}),
                (36, {"spine": (radians(1.8), 0, radians(0.6)), "head": (radians(-1.0), 0, 0)}),
                (72, {"spine": (0, 0, 0)}),
            ],
            72,
        )
    if "Walk_InPlace" in clip_names:
        create_pose_action(
            armature,
            "Walk_InPlace",
            [
                (1, {"thigh.L": (radians(18), 0, 0), "thigh.R": (radians(-18), 0, 0), "upper_arm.L": (radians(-12), 0, 0), "upper_arm.R": (radians(12), 0, 0)}),
                (24, {"thigh.L": (radians(-18), 0, 0), "thigh.R": (radians(18), 0, 0), "upper_arm.L": (radians(12), 0, 0), "upper_arm.R": (radians(-12), 0, 0)}),
                (48, {"thigh.L": (radians(18), 0, 0), "thigh.R": (radians(-18), 0, 0), "upper_arm.L": (radians(-12), 0, 0), "upper_arm.R": (radians(12), 0, 0)}),
            ],
            48,
        )
    for clip in clip_names:
        if clip not in {"Idle_Stationary", "Walk_InPlace"}:
            create_pose_action(
                armature,
                clip,
                [
                    (1, {"chest": (0, 0, 0)}),
                    (24, {"chest": (radians(4), 0, radians(6)), "upper_arm.R": (radians(-28), 0, radians(8))}),
                    (48, {"chest": (0, 0, 0)}),
                ],
                48,
            )

    common.setup_lighting_and_camera(spec, camera_loc=(2.25, -5.4, 2.05), target=(0, 0, 1.35))
    mixamo_objects = [armature] + [obj for obj in parts if obj.type == "MESH" and not obj.name.startswith("BASE_")]
    paths = common.export_asset(spec, parts, animations=bool(clip_names), frame=24, mixamo_objects=mixamo_objects)
    return common.collect_metadata(
        spec,
        paths,
        rig={
            "type": spec.get("rigTarget", "humanoid Mixamo best-effort"),
            "root": armature.name,
            "rig_depth": "basic named humanoid armature with whole-part vertex groups",
        },
        notes=[
            "Generated by the reusable Artomata character pipeline.",
            "Humanoid Mixamo exports are best-effort and may need manual adjustment for stylized proportions.",
            "Display base and contact shadow are excluded from Mixamo exports.",
        ],
    )
