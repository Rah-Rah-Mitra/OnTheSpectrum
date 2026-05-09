"""Generate the Violet Rift Portal VFX asset in Blender.

Run from Blender Python through the live MCP bridge when available, or through
background Blender via run_blender_asset.py when BLENDER_PATH is configured.
The script is repeatable: it creates the source scene, exports an animated GLB,
renders a preview, and writes metadata for the Artomata viewer.
"""

from __future__ import annotations

import json
import math
import random
import sys
from pathlib import Path

import bpy
from mathutils import Euler, Vector

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from blender_common import (  # noqa: E402
    add_bevel,
    add_weighted_normals,
    assign_mat,
    bevel_curve,
    bounds_for_objects,
    clear_scene,
    collection,
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

ASSET_SLUG = "violet-rift-portal"
ASSET_NAME = "Violet Rift Portal"
LOOP_CLIP = "Loop_PortalSwirl"
FRAME_START = 1
FRAME_END = 97
FPS = 24
PORTAL_CENTER_Z = 1.22

ASSET_SPEC = {
    "slug": ASSET_SLUG,
    "asset_family": "VFX",
    "vfx_family": "portal",
    "subject": "Free-floating vertical fantasy rift portal",
    "visual_style": "Stylized fantasy VFX, readable from the existing Three.js viewer",
    "required_parts": [
        "floating broken stone ring",
        "swirling inner energy disk",
        "small orbiting sparks",
        "faint ground glow",
    ],
    "material_palette": [
        "violet emissive core",
        "cyan emissive highlights",
        "dark basalt opaque stones",
        "soft white spark tips",
        "transparent violet and cyan glow planes",
    ],
    "rig_target": "simple transform rig",
    "animation_clips": [LOOP_CLIP],
    "duration_seconds": 4.0,
    "loop": True,
    "emission_source": "free-floating vertical ring",
    "transparency_style": "additive-style emissive transparent glow mixed with opaque stone meshes",
    "viewer_framing": "centered 3/4 front view showing the full vertical ring and faint ground glow",
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


def tune_translucent(mat: bpy.types.Material) -> bpy.types.Material:
    mat.blend_method = "BLEND"
    mat.show_transparent_back = True
    mat.use_screen_refraction = False
    mat.use_backface_culling = False
    if hasattr(mat, "surface_render_method"):
        mat.surface_render_method = "BLENDED"
    return mat


def make_materials() -> dict[str, bpy.types.Material]:
    mats = {
        "basalt": make_mat("MAT_VioletRift_DarkBasaltStone", (0.055, 0.052, 0.066, 1), roughness=0.86),
        "basalt_edge": make_mat("MAT_VioletRift_BasaltVioletEdge", (0.17, 0.12, 0.24, 1), roughness=0.82),
        "core": make_mat(
            "MAT_VioletRift_TransparentVioletCore",
            (0.58, 0.18, 0.95, 0.42),
            roughness=0.34,
            alpha=0.42,
            emission=(0.76, 0.24, 1.0, 1),
            emission_strength=1.7,
        ),
        "core_bright": make_mat(
            "MAT_VioletRift_BrightVioletRibbon",
            (0.78, 0.26, 1.0, 0.72),
            roughness=0.28,
            alpha=0.72,
            emission=(0.86, 0.33, 1.0, 1),
            emission_strength=2.4,
        ),
        "cyan": make_mat(
            "MAT_VioletRift_CyanHighlight",
            (0.1, 0.84, 1.0, 0.68),
            roughness=0.26,
            alpha=0.68,
            emission=(0.1, 0.92, 1.0, 1),
            emission_strength=2.7,
        ),
        "spark": make_mat(
            "MAT_VioletRift_SoftWhiteSparkTip",
            (0.94, 0.98, 1.0, 0.86),
            roughness=0.2,
            alpha=0.86,
            emission=(0.96, 0.98, 1.0, 1),
            emission_strength=3.0,
        ),
        "ground": make_mat(
            "MAT_VioletRift_FaintGroundGlow",
            (0.34, 0.08, 0.72, 0.28),
            roughness=0.52,
            alpha=0.28,
            emission=(0.38, 0.12, 0.9, 1),
            emission_strength=0.9,
        ),
    }
    for key in ("core", "core_bright", "cyan", "spark", "ground"):
        tune_translucent(mats[key])
    return mats


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
    return [
        obj
        for obj in bpy.data.objects
        if obj.type in {"MESH", "CURVE"} or (obj.type == "EMPTY" and obj.animation_data)
    ]


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
    empty.empty_display_size = 0.28
    empty.location = loc
    target = collection(collection_name)
    if empty.name not in target.objects:
        target.objects.link(empty)
    for source in list(empty.users_collection):
        if source != target:
            source.objects.unlink(empty)
    return empty


def create_rock_mesh(
    name: str,
    loc: tuple[float, float, float],
    dims: tuple[float, float, float],
    rotation: tuple[float, float, float],
    mat: bpy.types.Material,
    *,
    rng: random.Random,
    collection_name: str = "PROPS",
) -> bpy.types.Object:
    dx, dy, dz = (value * 0.5 for value in dims)
    verts = []
    for x in (-dx, dx):
        for y in (-dy, dy):
            for z in (-dz, dz):
                jitter = (
                    rng.uniform(-0.035, 0.035),
                    rng.uniform(-0.02, 0.02),
                    rng.uniform(-0.035, 0.035),
                )
                verts.append((x + jitter[0], y + jitter[1], z + jitter[2]))
    faces = [
        (0, 1, 3, 2),
        (4, 6, 7, 5),
        (0, 4, 5, 1),
        (2, 3, 7, 6),
        (0, 2, 6, 4),
        (1, 5, 7, 3),
    ]
    mesh = bpy.data.meshes.new(f"{name}_MESH")
    mesh.from_pydata(verts, [], faces)
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.scene.collection.objects.link(obj)
    obj.location = loc
    obj.rotation_euler = rotation
    assign_mat(obj, mat)
    link_to_collection(obj, collection_name)
    add_bevel(obj, 0.015, 1, apply=True)
    shade_smooth(obj)
    add_weighted_normals(obj)
    return obj


def vertical_disk(
    name: str,
    radius: float,
    depth: float,
    mat: bpy.types.Material,
    *,
    loc: tuple[float, float, float] = (0, 0, PORTAL_CENTER_Z),
    vertices: int = 96,
) -> bpy.types.Object:
    obj = cylinder(
        name,
        loc,
        radius,
        depth,
        mat,
        vertices=vertices,
        rotation=(math.radians(90), 0, 0),
        bevel=0,
        collection_name="BAKED_EFFECTS",
    )
    return obj


def arc_points(radius: float, start: float, end: float, steps: int, *, y: float = -0.032) -> list[tuple[float, float, float]]:
    return [
        (math.cos(angle) * radius, y, PORTAL_CENTER_Z + math.sin(angle) * radius)
        for angle in [start + (end - start) * index / (steps - 1) for index in range(steps)]
    ]


def spiral_points(
    phase: float,
    *,
    radius_min: float,
    radius_max: float,
    turns: float,
    steps: int,
    y: float,
) -> list[tuple[float, float, float]]:
    points = []
    for index in range(steps):
        t = index / (steps - 1)
        radius = radius_min + (radius_max - radius_min) * t
        angle = phase + math.tau * turns * t
        points.append((math.cos(angle) * radius, y, PORTAL_CENTER_Z + math.sin(angle) * radius))
    return points


def build_broken_ring(
    mats: dict[str, bpy.types.Material],
    ring_root: bpy.types.Object,
) -> list[bpy.types.Object]:
    rng = random.Random(1327)
    stones: list[bpy.types.Object] = []
    skipped = {3, 9, 15}
    for index in range(22):
        if index in skipped:
            continue
        angle = math.tau * index / 22 + rng.uniform(-0.035, 0.035)
        radius = rng.uniform(1.04, 1.14)
        loc = (
            math.cos(angle) * radius,
            rng.uniform(-0.045, 0.045),
            PORTAL_CENTER_Z + math.sin(angle) * radius,
        )
        dims = (
            rng.uniform(0.20, 0.34),
            rng.uniform(0.11, 0.18),
            rng.uniform(0.20, 0.33),
        )
        rotation = (
            rng.uniform(-0.34, 0.34),
            -angle + rng.uniform(-0.24, 0.24),
            rng.uniform(-0.42, 0.42),
        )
        stone = create_rock_mesh(
            f"PROP_VioletRift_BrokenBasaltShard_{index + 1:02d}",
            loc,
            dims,
            rotation,
            mats["basalt"],
            rng=rng,
        )
        stones.append(stone)

        if index % 4 == 0:
            chip_angle = angle + rng.uniform(-0.11, 0.11)
            chip_radius = radius + rng.uniform(-0.16, 0.12)
            chip = create_rock_mesh(
                f"PROP_VioletRift_FloatingEdgeChip_{index + 1:02d}",
                (
                    math.cos(chip_angle) * chip_radius,
                    rng.uniform(-0.08, 0.08),
                    PORTAL_CENTER_Z + math.sin(chip_angle) * chip_radius,
                ),
                (
                    rng.uniform(0.08, 0.14),
                    rng.uniform(0.06, 0.1),
                    rng.uniform(0.08, 0.15),
                ),
                (
                    rng.uniform(-0.5, 0.5),
                    -chip_angle + rng.uniform(-0.35, 0.35),
                    rng.uniform(-0.7, 0.7),
                ),
                mats["basalt_edge"],
                rng=rng,
            )
            stones.append(chip)

    for segment, start, end in [
        ("A", math.radians(18), math.radians(92)),
        ("B", math.radians(143), math.radians(214)),
        ("C", math.radians(250), math.radians(335)),
    ]:
        arc = bevel_curve(
            f"VFX_VioletRift_CyanRunicInnerArc_{segment}",
            arc_points(0.93, start, end, 18),
            mats["cyan"],
            bevel_depth=0.012,
            bevel_resolution=3,
            resolution=8,
            collection_name="BAKED_EFFECTS",
        )
        stones.append(arc)

    for obj in stones:
        parent_keep_world(obj, ring_root)
    return stones


def build_inner_swirl(
    mats: dict[str, bpy.types.Material],
    root: bpy.types.Object,
    swirl_root: bpy.types.Object,
) -> list[bpy.types.Object]:
    objects: list[bpy.types.Object] = []

    aura = vertical_disk(
        "VFX_VioletRift_TransparentEnergyDisk",
        0.86,
        0.018,
        mats["core"],
        vertices=112,
    )
    objects.append(aura)

    inner = vertical_disk(
        "VFX_VioletRift_BrightInnerPulseDisk",
        0.42,
        0.012,
        mats["core_bright"],
        vertices=80,
    )
    objects.append(inner)

    rim = bevel_curve(
        "VFX_VioletRift_VioletInnerRim",
        arc_points(0.76, 0.0, math.tau, 80, y=-0.04),
        mats["core_bright"],
        bevel_depth=0.018,
        bevel_resolution=4,
        resolution=12,
        collection_name="BAKED_EFFECTS",
    )
    objects.append(rim)

    for index, phase in enumerate([0.2, 2.2, 4.1], start=1):
        ribbon = bevel_curve(
            f"VFX_VioletRift_SwirlVioletRibbon_{index:02d}",
            spiral_points(
                phase,
                radius_min=0.1,
                radius_max=0.76,
                turns=0.72,
                steps=42,
                y=-0.065 - index * 0.004,
            ),
            mats["core_bright"],
            bevel_depth=0.022,
            bevel_resolution=4,
            resolution=12,
            collection_name="BAKED_EFFECTS",
        )
        objects.append(ribbon)

    for index, phase in enumerate([1.1, 3.28], start=1):
        ribbon = bevel_curve(
            f"VFX_VioletRift_CyanSwirlHighlight_{index:02d}",
            spiral_points(
                phase,
                radius_min=0.2,
                radius_max=0.68,
                turns=0.56,
                steps=34,
                y=-0.092 - index * 0.005,
            ),
            mats["cyan"],
            bevel_depth=0.012,
            bevel_resolution=3,
            resolution=10,
            collection_name="BAKED_EFFECTS",
        )
        objects.append(ribbon)

    for obj in objects:
        parent_keep_world(obj, swirl_root if "Swirl" in obj.name or "Rim" in obj.name else root)
    return objects


def build_sparks(
    mats: dict[str, bpy.types.Material],
    outer_root: bpy.types.Object,
    inner_root: bpy.types.Object,
) -> list[bpy.types.Object]:
    rng = random.Random(9841)
    objects: list[bpy.types.Object] = []
    for index in range(18):
        angle = math.tau * index / 18 + rng.uniform(-0.12, 0.12)
        radius = rng.uniform(0.72, 1.36)
        z_offset = rng.uniform(-0.82, 0.82)
        if abs(z_offset) > 0.72:
            radius *= 0.74
        loc = (
            math.cos(angle) * radius,
            rng.uniform(-0.18, 0.16),
            PORTAL_CENTER_Z + z_offset,
        )
        spark = uv_sphere(
            f"VFX_VioletRift_OrbitingSparkTip_{index + 1:02d}",
            loc,
            (
                rng.uniform(0.018, 0.034),
                rng.uniform(0.018, 0.034),
                rng.uniform(0.018, 0.034),
            ),
            mats["spark"] if index % 3 else mats["cyan"],
            segments=10,
            rings=5,
            collection_name="BAKED_EFFECTS",
        )
        objects.append(spark)
        parent_keep_world(spark, outer_root if index % 2 else inner_root)

        if index % 4 == 0:
            tail_angle = angle - 0.12
            tail = bevel_curve(
                f"VFX_VioletRift_DriftingSparkTrail_{index + 1:02d}",
                [
                    loc,
                    (
                        math.cos(tail_angle) * (radius - 0.12),
                        loc[1] + rng.uniform(-0.035, 0.035),
                        loc[2] - rng.uniform(0.04, 0.1),
                    ),
                ],
                mats["cyan"],
                bevel_depth=0.006,
                bevel_resolution=2,
                resolution=3,
                collection_name="BAKED_EFFECTS",
            )
            objects.append(tail)
            parent_keep_world(tail, outer_root)
    return objects


def build_ground_glow(
    mats: dict[str, bpy.types.Material],
    root: bpy.types.Object,
) -> list[bpy.types.Object]:
    glow = cylinder(
        "BASE_VioletRift_FaintVioletGroundGlow",
        (0, 0, 0.006),
        0.78,
        0.012,
        mats["ground"],
        vertices=96,
        scale=(1.28, 0.78, 1),
        collection_name="BAKED_EFFECTS",
    )
    cyan_ring = cylinder(
        "BASE_VioletRift_CyanGroundHalo",
        (0, 0, 0.012),
        0.52,
        0.006,
        mats["cyan"],
        vertices=72,
        scale=(1.2, 0.68, 1),
        collection_name="BAKED_EFFECTS",
    )
    for obj in (glow, cyan_ring):
        parent_keep_world(obj, root)
    return [glow, cyan_ring]


def polish_action_curves(action: bpy.types.Action, *, interpolation: str = "LINEAR") -> None:
    for curve in getattr(action, "fcurves", []):
        for keyframe in curve.keyframe_points:
            keyframe.interpolation = interpolation


def add_loop_track(obj: bpy.types.Object, action: bpy.types.Action) -> None:
    animation_data = obj.animation_data_create()
    animation_data.action = None
    track = animation_data.nla_tracks.new()
    track.name = LOOP_CLIP
    strip = track.strips.new(LOOP_CLIP, FRAME_START, action)
    strip.name = LOOP_CLIP
    strip.frame_end = FRAME_END


def create_rotation_loop(
    obj: bpy.types.Object,
    action_name: str,
    axis: int,
    turns: float,
    *,
    base_rotation: tuple[float, float, float] = (0, 0, 0),
) -> bpy.types.Action:
    action = bpy.data.actions.new(action_name)
    action.use_fake_user = True
    animation_data = obj.animation_data_create()
    animation_data.action = action
    obj.rotation_mode = "XYZ"
    for index, frame in enumerate([FRAME_START, 25, 49, 73, FRAME_END]):
        angle = math.tau * turns * index / 4
        rotation = list(base_rotation)
        rotation[axis] += angle
        bpy.context.scene.frame_set(frame)
        obj.rotation_euler = rotation
        obj.keyframe_insert(data_path="rotation_euler", frame=frame)
    polish_action_curves(action, interpolation="LINEAR")
    add_loop_track(obj, action)
    bpy.context.scene.frame_set(FRAME_START)
    obj.rotation_euler = base_rotation
    return action


def create_pulse_loop(obj: bpy.types.Object, action_name: str, scale_values: list[tuple[int, float]]) -> bpy.types.Action:
    action = bpy.data.actions.new(action_name)
    action.use_fake_user = True
    base_scale = obj.scale.copy()
    animation_data = obj.animation_data_create()
    animation_data.action = action
    for frame, factor in scale_values:
        bpy.context.scene.frame_set(frame)
        obj.scale = base_scale * factor
        obj.keyframe_insert(data_path="scale", frame=frame)
    polish_action_curves(action, interpolation="SINE" if False else "BEZIER")
    add_loop_track(obj, action)
    bpy.context.scene.frame_set(FRAME_START)
    obj.scale = base_scale
    return action


def build_portal(mats: dict[str, bpy.types.Material]) -> dict[str, bpy.types.Object | list[bpy.types.Object]]:
    for name in ["RIG", "PROPS", "BAKED_EFFECTS", "LIGHTING_CAMERA"]:
        collection(name)

    root = make_empty("violet_rift_portal_model_root", (0, 0, 0), collection_name="RIG")
    ring_root = make_empty("ANIM_VioletRift_RingShardRoot", (0, 0, PORTAL_CENTER_Z), collection_name="RIG")
    swirl_root = make_empty("ANIM_VioletRift_InnerSwirlRoot", (0, 0, PORTAL_CENTER_Z), collection_name="RIG")
    sparks_outer = make_empty("ANIM_VioletRift_OuterSparkOrbitRoot", (0, 0, PORTAL_CENTER_Z), collection_name="RIG")
    sparks_inner = make_empty("ANIM_VioletRift_InnerSparkDriftRoot", (0, 0, PORTAL_CENTER_Z), collection_name="RIG")
    for control in (ring_root, swirl_root, sparks_outer, sparks_inner):
        control.parent = root

    ring_parts = build_broken_ring(mats, ring_root)
    swirl_parts = build_inner_swirl(mats, root, swirl_root)
    spark_parts = build_sparks(mats, sparks_outer, sparks_inner)
    ground_parts = build_ground_glow(mats, root)

    create_rotation_loop(ring_root, "ACT_VioletRift_RingShardRoot_Loop", 1, 1.0)
    create_rotation_loop(swirl_root, "ACT_VioletRift_InnerSwirlRoot_Loop", 1, -1.55)
    create_rotation_loop(sparks_outer, "ACT_VioletRift_OuterSparkOrbitRoot_Loop", 1, 1.25)
    create_rotation_loop(sparks_inner, "ACT_VioletRift_InnerSparkDriftRoot_Loop", 1, -0.75)
    for obj, phase in [(swirl_parts[0], 1.0), (swirl_parts[1], 1.08)]:
        create_pulse_loop(
            obj,
            f"ACT_{obj.name}_Pulse",
            [
                (FRAME_START, 1.0),
                (25, phase),
                (49, 0.94),
                (73, 1.06),
                (FRAME_END, 1.0),
            ],
        )

    return {
        "root": root,
        "ring_root": ring_root,
        "swirl_root": swirl_root,
        "sparks_outer": sparks_outer,
        "sparks_inner": sparks_inner,
        "parts": ring_parts + swirl_parts + spark_parts + ground_parts,
    }


def setup_lighting_and_camera() -> None:
    world = bpy.context.scene.world or bpy.data.worlds.new("World")
    bpy.context.scene.world = world
    world.color = (0.018, 0.014, 0.026)

    camera_data = bpy.data.cameras.new("CAM_VioletRiftPortal_Preview")
    camera = bpy.data.objects.new("CAM_VioletRiftPortal_Preview", camera_data)
    bpy.context.scene.collection.objects.link(camera)
    camera.location = (2.45, -5.15, 2.05)
    camera.data.lens = 52
    camera.data.dof.use_dof = True
    camera.data.dof.focus_distance = 5.6
    camera.data.dof.aperture_fstop = 7.0
    look_at(camera, (0, 0, 1.08))
    bpy.context.scene.camera = camera
    for source in list(camera.users_collection):
        source.objects.unlink(camera)
    collection("LIGHTING_CAMERA").objects.link(camera)

    lights = [
        ("LGT_VioletRift_KeySoftbox", "AREA", (-2.3, -3.2, 3.2), 320, 3.2),
        ("LGT_VioletRift_CyanRim", "AREA", (2.4, 1.1, 2.6), 160, 2.2),
        ("LGT_VioletRift_LowVioletFill", "POINT", (0.0, -1.6, 0.8), 95, 0),
    ]
    for name, kind, loc, energy, size in lights:
        data = bpy.data.lights.new(name, kind)
        obj = bpy.data.objects.new(name, data)
        bpy.context.scene.collection.objects.link(obj)
        obj.location = loc
        data.energy = energy
        if hasattr(data, "size") and size:
            data.size = size
        look_at(obj, (0, 0, 1.1))
        for source in list(obj.users_collection):
            source.objects.unlink(obj)
        collection("LIGHTING_CAMERA").objects.link(obj)


def configure_scene() -> None:
    scene = bpy.context.scene
    scene.name = "SCN_VioletRiftPortal"
    scene.unit_settings.system = "METRIC"
    scene.frame_start = FRAME_START
    scene.frame_end = FRAME_END
    scene.render.fps = FPS
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
        export_animation_mode="NLA_TRACKS",
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

    bpy.context.scene.frame_set(31)
    bpy.context.scene.render.filepath = str(paths["preview"])
    bpy.ops.render.render(write_still=True)
    bpy.context.scene.frame_set(FRAME_START)


def collect_metadata(paths: dict[str, Path]) -> dict:
    meshes = mesh_objects()
    geometries = geometry_objects()
    action_names = sorted(action.name for action in bpy.data.actions)
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
            "animations": 1,
            "authored_actions": len(action_names),
        },
        "materials": material_names(geometries),
        "animations": {
            "clips": [LOOP_CLIP],
            "default": LOOP_CLIP,
            "embedded_in_glb": True,
            "duration_seconds": 4.0,
            "loop": True,
            "authored_actions": action_names,
        },
        "rig": {
            "type": "simple transform rig",
            "root": "violet_rift_portal_model_root",
            "animated_controls": [
                "ANIM_VioletRift_RingShardRoot",
                "ANIM_VioletRift_InnerSwirlRoot",
                "ANIM_VioletRift_OuterSparkOrbitRoot",
                "ANIM_VioletRift_InnerSparkDriftRoot",
            ],
            "stable_parts": ["ground glow", "base energy disk"],
            "animated_parts": ["broken ring shards", "swirl ribbons", "orbiting sparks"],
        },
        "vfx": {
            "family": "portal",
            "emission_source": "free-floating vertical ring",
            "transparency_style": "GLB-compatible emissive alpha-blended meshes approximating additive glow",
            "texture_dependencies": [],
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
            "source": "Blender procedural asset pipeline",
        },
        "notes": [
            "Violet Rift Portal generated procedurally in Blender as the VFX source of truth.",
            "The portal uses GLB-compatible baked meshes, bevelled curves converted to mesh, transparent emissive disks, and transform animation.",
            "Particle-like sparks are authored as small animated mesh spheres and curve trails, not browser-only particles.",
            "Mixamo exports are intentionally omitted because this is a non-humanoid VFX asset.",
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
    build_portal(mats)
    setup_lighting_and_camera()
    export_asset(paths)
    metadata = collect_metadata(paths)
    write_json(paths["metadata"], metadata)
    return metadata


if __name__ == "__main__":
    result = main()
    print(json.dumps(result, indent=2))
