"""Generate a static blacksmith forge workbench asset in Blender.

Run from Blender Python through the live MCP bridge or background Blender. The
script is repeatable: it creates the source scene, exports a static GLB,
renders a preview, and writes metadata for the Artomata viewer.
"""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import bpy

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from blender_common import (  # noqa: E402
    add_bevel,
    add_weighted_normals,
    apply_transform,
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
    write_json,
)

ASSET_SLUG = "blacksmith-forge-workbench"
ASSET_NAME = "Blacksmith Forge Workbench"

ASSET_SPEC = {
    "slug": ASSET_SLUG,
    "asset_family": "Furniture",
    "subject": "Blacksmith forge workbench",
    "visual_style": "Stylized fantasy workshop furniture, rugged, functional, and game-ready",
    "required_parts": [
        "heavy wooden bench",
        "anvil surface",
        "scattered tools",
        "hammer rack",
        "tongs",
        "metal scraps",
        "orange ember accents",
        "soot marks",
    ],
    "material_palette": [
        "dark rough wood",
        "dark endgrain and soot stains",
        "blackened iron",
        "brushed steel tool heads",
        "orange ember emission accents",
        "soft translucent contact shadow",
    ],
    "rig_target": "none",
    "animation_clips": [],
    "viewer_framing": "3/4 view with a slightly elevated camera so the tabletop tools read clearly",
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


def make_materials() -> dict[str, bpy.types.Material]:
    return {
        "wood": make_mat("MAT_ForgeBench_DarkRoughWood", (0.18, 0.082, 0.035, 1), roughness=0.84),
        "endgrain": make_mat("MAT_ForgeBench_DarkEndgrain", (0.072, 0.034, 0.018, 1), roughness=0.92),
        "iron": make_mat("MAT_ForgeBench_BlackenedIron", (0.035, 0.038, 0.04, 1), roughness=0.78, metallic=0.62),
        "steel": make_mat("MAT_ForgeBench_BrushedSteelTools", (0.55, 0.56, 0.52, 1), roughness=0.48, metallic=0.88),
        "steel_dark": make_mat("MAT_ForgeBench_DarkSteelWear", (0.22, 0.225, 0.215, 1), roughness=0.62, metallic=0.82),
        "ember": make_mat(
            "MAT_ForgeBench_EmberOrangeGlow",
            (1.0, 0.31, 0.055, 1),
            roughness=0.5,
            emission=(1.0, 0.22, 0.035, 1),
            emission_strength=1.7,
        ),
        "soot": make_mat("MAT_ForgeBench_SootMarks", (0.01, 0.009, 0.007, 0.58), roughness=0.94, alpha=0.58),
        "shadow": make_mat("MAT_Shadow_BakedSoftContact", (0.018, 0.02, 0.023, 0.54), roughness=0.92, alpha=0.54),
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


def material_names(objects: list[bpy.types.Object]) -> list[str]:
    return sorted({slot.material.name for obj in objects for slot in obj.material_slots if slot.material})


def clear_animation_data() -> None:
    for obj in bpy.data.objects:
        obj.animation_data_clear()
    for action in list(bpy.data.actions):
        bpy.data.actions.remove(action)


def rotated_cube(
    name: str,
    loc: tuple[float, float, float],
    scale: tuple[float, float, float],
    mat: bpy.types.Material,
    *,
    rotation: tuple[float, float, float] = (0, 0, 0),
    bevel: float = 0.015,
    collection_name: str = "PROPS",
) -> bpy.types.Object:
    obj = cube(name, loc, scale, mat, bevel=bevel, collection_name=collection_name)
    obj.rotation_euler = rotation
    apply_transform(obj, rotation=True, scale=False)
    add_weighted_normals(obj)
    return obj


def add_plank_grain(
    objects: list[bpy.types.Object],
    mats: dict[str, bpy.types.Material],
    *,
    x_offset: float,
    y: float,
    z: float,
    index: int,
) -> None:
    points = [
        (x_offset - 0.42, y, z),
        (x_offset - 0.12, y + 0.018, z + 0.002),
        (x_offset + 0.18, y - 0.014, z + 0.001),
        (x_offset + 0.42, y + 0.01, z),
    ]
    objects.append(
        bevel_curve(
            f"PROP_ForgeBench_Tabletop_WoodGrain_{index:02d}",
            points,
            mats["endgrain"],
            bevel_depth=0.0035,
            bevel_resolution=1,
            collection_name="PROPS",
        )
    )


def add_hammer(
    objects: list[bpy.types.Object],
    mats: dict[str, bpy.types.Material],
    name: str,
    loc: tuple[float, float, float],
    *,
    handle_length: float,
    angle_z: float,
    resting: bool,
) -> None:
    handle_rotation = (0, math.radians(90 if resting else 0), angle_z)
    if resting:
        objects.append(
            cylinder(
                f"PROP_ForgeBench_{name}_WoodHandle",
                loc,
                0.017,
                handle_length,
                mats["wood"],
                vertices=14,
                rotation=handle_rotation,
                bevel=0.003,
                collection_name="PROPS",
            )
        )
        head_x = loc[0] + math.cos(angle_z) * handle_length * 0.48
        head_y = loc[1] + math.sin(angle_z) * handle_length * 0.48
        objects.append(
            rotated_cube(
                f"PROP_ForgeBench_{name}_SteelHammerHead",
                (head_x, head_y, loc[2]),
                (0.075, 0.035, 0.04),
                mats["steel"],
                rotation=(0, 0, angle_z),
                bevel=0.012,
            )
        )
    else:
        objects.append(
            cylinder(
                f"PROP_ForgeBench_{name}_HangingWoodHandle",
                loc,
                0.014,
                handle_length,
                mats["wood"],
                vertices=14,
                rotation=(0, 0, 0),
                bevel=0.003,
                collection_name="PROPS",
            )
        )
        objects.append(
            rotated_cube(
                f"PROP_ForgeBench_{name}_HangingSteelHammerHead",
                (loc[0], loc[1], loc[2] + handle_length * 0.52),
                (0.075, 0.032, 0.038),
                mats["steel"],
                rotation=(0, 0, angle_z),
                bevel=0.012,
            )
        )


def add_tongs(objects: list[bpy.types.Object], mats: dict[str, bpy.types.Material]) -> None:
    left = [(-0.36, -0.18, 0.82), (-0.26, -0.1, 0.84), (-0.12, -0.035, 0.855), (0.08, 0.015, 0.865)]
    right = [(-0.35, -0.105, 0.823), (-0.23, -0.075, 0.84), (-0.1, -0.02, 0.852), (0.105, 0.048, 0.862)]
    objects.append(bevel_curve("PROP_ForgeBench_Tongs_LeftArm", left, mats["iron"], bevel_depth=0.011, bevel_resolution=2, collection_name="PROPS"))
    objects.append(bevel_curve("PROP_ForgeBench_Tongs_RightArm", right, mats["iron"], bevel_depth=0.011, bevel_resolution=2, collection_name="PROPS"))
    objects.append(cylinder("PROP_ForgeBench_Tongs_Rivet", (-0.16, -0.04, 0.857), 0.027, 0.012, mats["steel"], vertices=24, bevel=0.002, collection_name="PROPS"))
    for side, y in [("Left", 0.011), ("Right", 0.058)]:
        objects.append(
            rotated_cube(
                f"PROP_ForgeBench_Tongs_{side}FlatJaw",
                (0.16, y, 0.862),
                (0.09, 0.018, 0.012),
                mats["steel_dark"],
                rotation=(0, 0, math.radians(16 if side == "Left" else 24)),
                bevel=0.005,
            )
        )


def add_anvil(objects: list[bpy.types.Object], mats: dict[str, bpy.types.Material]) -> None:
    objects.append(cube("PROP_ForgeBench_Anvil_BlockTop", (0.48, 0.02, 0.92), (0.24, 0.14, 0.055), mats["steel_dark"], bevel=0.022, collection_name="PROPS"))
    objects.append(cube("PROP_ForgeBench_Anvil_Waist", (0.48, 0.02, 0.85), (0.14, 0.095, 0.06), mats["iron"], bevel=0.018, collection_name="PROPS"))
    objects.append(cube("PROP_ForgeBench_Anvil_Foot", (0.48, 0.02, 0.79), (0.24, 0.16, 0.04), mats["iron"], bevel=0.014, collection_name="PROPS"))
    objects.append(
        cone(
            "PROP_ForgeBench_Anvil_TaperedHorn",
            (0.77, 0.02, 0.92),
            0.072,
            0.014,
            0.22,
            mats["steel_dark"],
            vertices=24,
            rotation=(0, math.radians(90), 0),
            collection_name="PROPS",
        )
    )
    objects.append(cylinder("PROP_ForgeBench_Anvil_HardyHole", (0.37, -0.075, 0.978), 0.018, 0.008, mats["soot"], vertices=20, collection_name="PROPS"))


def add_ember_tray(objects: list[bpy.types.Object], mats: dict[str, bpy.types.Material]) -> None:
    objects.append(cube("PROP_ForgeBench_EmberTray_BlackIronBase", (-0.5, 0.16, 0.815), (0.19, 0.12, 0.018), mats["iron"], bevel=0.012, collection_name="PROPS"))
    objects.append(cube("PROP_ForgeBench_EmberTray_BackLip", (-0.5, 0.275, 0.845), (0.19, 0.018, 0.04), mats["iron"], bevel=0.006, collection_name="PROPS"))
    objects.append(cube("PROP_ForgeBench_EmberTray_FrontLip", (-0.5, 0.045, 0.845), (0.19, 0.018, 0.04), mats["iron"], bevel=0.006, collection_name="PROPS"))
    objects.append(cube("PROP_ForgeBench_EmberTray_LeftLip", (-0.7, 0.16, 0.845), (0.018, 0.12, 0.04), mats["iron"], bevel=0.006, collection_name="PROPS"))
    objects.append(cube("PROP_ForgeBench_EmberTray_RightLip", (-0.3, 0.16, 0.845), (0.018, 0.12, 0.04), mats["iron"], bevel=0.006, collection_name="PROPS"))
    ember_points = [
        (-0.58, 0.12, 0.872),
        (-0.52, 0.19, 0.878),
        (-0.46, 0.12, 0.872),
        (-0.42, 0.21, 0.874),
    ]
    for index, loc in enumerate(ember_points, start=1):
        objects.append(cylinder(f"PROP_ForgeBench_EmberCoal_Glow_{index}", loc, 0.024, 0.018, mats["ember"], vertices=10, bevel=0.004, collection_name="PROPS"))
    objects.append(cylinder("PROP_ForgeBench_EmberTray_SootHalo", (-0.5, 0.16, 0.886), 0.155, 0.004, mats["soot"], vertices=42, scale=(1.25, 0.78, 1), collection_name="PROPS"))


def add_fastener_and_scratch_details(objects: list[bpy.types.Object], mats: dict[str, bpy.types.Material]) -> None:
    rivet_index = 1
    for y in [-0.375, 0.375]:
        for x in [-0.68, -0.42, -0.16, 0.16, 0.42, 0.68]:
            objects.append(
                cylinder(
                    f"PROP_ForgeBench_Tabletop_BlackIronRivet_{rivet_index:02d}",
                    (x, y, 0.822),
                    0.014,
                    0.007,
                    mats["iron"],
                    vertices=18,
                    bevel=0.0025,
                    collection_name="PROPS",
                )
            )
            rivet_index += 1

    for x in [-0.62, -0.28, 0.06]:
        objects.append(
            cylinder(
                f"PROP_ForgeBench_HammerRack_BeamFaceRivet_{rivet_index:02d}",
                (x, 0.347, 1.25),
                0.012,
                0.007,
                mats["iron"],
                vertices=18,
                rotation=(math.radians(90), 0, 0),
                bevel=0.002,
                collection_name="PROPS",
            )
        )
        rivet_index += 1

    scratch_sets = [
        [(-0.62, -0.07, 0.825), (-0.51, -0.08, 0.828), (-0.4, -0.055, 0.826)],
        [(-0.16, 0.13, 0.826), (-0.04, 0.11, 0.829), (0.12, 0.145, 0.827)],
        [(0.34, -0.12, 0.827), (0.48, -0.15, 0.83), (0.62, -0.115, 0.828)],
        [(0.33, 0.13, 0.925), (0.48, 0.12, 0.927), (0.63, 0.145, 0.926)],
    ]
    for index, points in enumerate(scratch_sets, start=1):
        objects.append(
            bevel_curve(
                f"PROP_ForgeBench_ToolWear_BrightScratch_{index:02d}",
                points,
                mats["steel"],
                bevel_depth=0.0024,
                bevel_resolution=1,
                collection_name="PROPS",
            )
        )


def add_scattered_scraps(objects: list[bpy.types.Object], mats: dict[str, bpy.types.Material]) -> None:
    scraps = [
        ("FlatOffcut_01", (-0.05, 0.23, 0.82), (0.075, 0.026, 0.009), math.radians(-18), "steel"),
        ("FlatOffcut_02", (0.18, 0.2, 0.821), (0.06, 0.02, 0.008), math.radians(24), "steel_dark"),
        ("BentPlate_03", (0.3, -0.2, 0.822), (0.08, 0.025, 0.01), math.radians(8), "iron"),
        ("ShortRod_04", (0.03, -0.26, 0.834), (0.015, 0.015, 0.19), math.radians(68), "steel_dark"),
        ("ShortRod_05", (0.25, 0.3, 0.834), (0.014, 0.014, 0.16), math.radians(102), "steel"),
    ]
    for name, loc, scale, angle, mat_name in scraps:
        if "Rod" in name:
            objects.append(cylinder(f"PROP_ForgeBench_MetalScrap_{name}", loc, scale[0], scale[2], mats[mat_name], vertices=12, rotation=(math.radians(90), 0, angle), bevel=0.003, collection_name="PROPS"))
        else:
            objects.append(rotated_cube(f"PROP_ForgeBench_MetalScrap_{name}", loc, scale, mats[mat_name], rotation=(0, 0, angle), bevel=0.004))
    for index, (x, y, angle) in enumerate([(-0.18, 0.28, 12), (0.1, 0.31, -22), (0.38, 0.23, 31)], start=1):
        objects.append(
            cone(
                f"PROP_ForgeBench_MetalScrap_TriangularShard_{index}",
                (x, y, 0.826),
                0.055,
                0.055,
                0.012,
                mats["steel_dark" if index % 2 else "steel"],
                vertices=3,
                rotation=(0, 0, math.radians(angle)),
                scale=(1.0, 0.55, 1),
                collection_name="PROPS",
            )
        )


def build_workbench(mats: dict[str, bpy.types.Material]) -> list[bpy.types.Object]:
    for name in ["PROPS", "BAKED_EFFECTS", "LIGHTING_CAMERA"]:
        collection(name)

    objects: list[bpy.types.Object] = []

    def add(obj: bpy.types.Object) -> bpy.types.Object:
        objects.append(obj)
        return obj

    # Heavy bench frame.
    add(cube("PROP_ForgeBench_Tabletop_DarkWoodSlab", (0, 0, 0.74), (0.86, 0.42, 0.065), mats["wood"], bevel=0.035, collection_name="PROPS"))
    add(cube("PROP_ForgeBench_FrontEndgrainBand", (0, -0.435, 0.72), (0.86, 0.025, 0.085), mats["endgrain"], bevel=0.012, collection_name="PROPS"))
    add(cube("PROP_ForgeBench_BackEndgrainBand", (0, 0.435, 0.72), (0.86, 0.025, 0.085), mats["endgrain"], bevel=0.012, collection_name="PROPS"))
    add(cube("PROP_ForgeBench_LeftEndgrainBand", (-0.885, 0, 0.72), (0.025, 0.42, 0.085), mats["endgrain"], bevel=0.012, collection_name="PROPS"))
    add(cube("PROP_ForgeBench_RightEndgrainBand", (0.885, 0, 0.72), (0.025, 0.42, 0.085), mats["endgrain"], bevel=0.012, collection_name="PROPS"))
    add(cube("PROP_ForgeBench_Underside_BlackIronBrace", (0, 0, 0.66), (0.72, 0.32, 0.028), mats["iron"], bevel=0.012, collection_name="PROPS"))

    for side_name, x in [("Left", -0.66), ("Right", 0.66)]:
        for row_name, y in [("Front", -0.28), ("Back", 0.28)]:
            add(cube(f"PROP_ForgeBench_{row_name}{side_name}_ChunkyWoodLeg", (x, y, 0.33), (0.075, 0.075, 0.33), mats["wood"], bevel=0.024, collection_name="PROPS"))
            add(cylinder(f"PROP_ForgeBench_{row_name}{side_name}_IronFootBand", (x, y, 0.06), 0.067, 0.04, mats["iron"], vertices=20, bevel=0.005, collection_name="PROPS"))

    add(cube("PROP_ForgeBench_FrontLowerRail_DarkWood", (0, -0.31, 0.25), (0.66, 0.04, 0.055), mats["wood"], bevel=0.014, collection_name="PROPS"))
    add(cube("PROP_ForgeBench_BackLowerRail_DarkWood", (0, 0.31, 0.25), (0.66, 0.04, 0.055), mats["wood"], bevel=0.014, collection_name="PROPS"))
    add(cube("PROP_ForgeBench_LeftSideLowerRail_DarkWood", (-0.69, 0, 0.25), (0.04, 0.28, 0.055), mats["wood"], bevel=0.014, collection_name="PROPS"))
    add(cube("PROP_ForgeBench_RightSideLowerRail_DarkWood", (0.69, 0, 0.25), (0.04, 0.28, 0.055), mats["wood"], bevel=0.014, collection_name="PROPS"))

    for index, y in enumerate([-0.31, -0.18, -0.04, 0.11, 0.27], start=1):
        add_plank_grain(objects, mats, x_offset=0.0, y=y, z=0.809, index=index)
    for index, (x, y, sx, sy) in enumerate([(-0.36, -0.3, 0.18, 0.07), (0.08, -0.06, 0.23, 0.095), (0.55, 0.28, 0.16, 0.06)], start=1):
        add(cylinder(f"PROP_ForgeBench_Tabletop_SootSmudge_{index}", (x, y, 0.814), sx, 0.004, mats["soot"], vertices=38, scale=(1, sy / sx, 1), collection_name="PROPS"))

    add_fastener_and_scratch_details(objects, mats)
    add_anvil(objects, mats)
    add_ember_tray(objects, mats)
    add_tongs(objects, mats)
    add_hammer(objects, mats, "RestingHammer_01", (-0.05, -0.27, 0.86), handle_length=0.44, angle_z=math.radians(18), resting=True)
    add_hammer(objects, mats, "RestingHammer_02", (0.26, -0.29, 0.855), handle_length=0.35, angle_z=math.radians(-24), resting=True)
    add_scattered_scraps(objects, mats)

    # Rear hammer rack and hanging tools.
    add(cube("PROP_ForgeBench_HammerRack_LeftPost", (-0.72, 0.39, 1.04), (0.04, 0.035, 0.34), mats["wood"], bevel=0.014, collection_name="PROPS"))
    add(cube("PROP_ForgeBench_HammerRack_RightPost", (0.15, 0.39, 1.04), (0.04, 0.035, 0.34), mats["wood"], bevel=0.014, collection_name="PROPS"))
    add(cube("PROP_ForgeBench_HammerRack_BackBeam", (-0.285, 0.39, 1.25), (0.49, 0.035, 0.045), mats["wood"], bevel=0.014, collection_name="PROPS"))
    for index, x in enumerate([-0.62, -0.4, -0.18, 0.04], start=1):
        add(cylinder(f"PROP_ForgeBench_HammerRack_IronPeg_{index}", (x, 0.35, 1.18), 0.013, 0.13, mats["iron"], vertices=14, rotation=(math.radians(90), 0, 0), bevel=0.002, collection_name="PROPS"))
    add_hammer(objects, mats, "RackHammer_01", (-0.56, 0.332, 1.0), handle_length=0.27, angle_z=math.radians(4), resting=False)
    add_hammer(objects, mats, "RackHammer_02", (-0.32, 0.332, 0.98), handle_length=0.31, angle_z=math.radians(-7), resting=False)
    add(cylinder("PROP_ForgeBench_RackPunchTool", (-0.08, 0.333, 1.035), 0.012, 0.31, mats["steel_dark"], vertices=12, bevel=0.002, collection_name="PROPS"))

    add(cylinder("BASE_BakedSoftContactShadow", (0, 0, 0.004), 0.72, 0.008, mats["shadow"], vertices=72, scale=(1.45, 0.9, 1), collection_name="BAKED_EFFECTS"))
    return objects


def setup_lighting_and_camera() -> None:
    world = bpy.context.scene.world or bpy.data.worlds.new("World")
    bpy.context.scene.world = world
    world.color = (0.024, 0.025, 0.024)

    camera_data = bpy.data.cameras.new("CAM_BlacksmithForgeWorkbench_Preview")
    camera = bpy.data.objects.new("CAM_BlacksmithForgeWorkbench_Preview", camera_data)
    bpy.context.scene.collection.objects.link(camera)
    camera.location = (2.35, -2.85, 1.72)
    camera.data.lens = 52
    camera.data.dof.use_dof = True
    camera.data.dof.focus_distance = 3.35
    camera.data.dof.aperture_fstop = 7.0
    look_at(camera, (0.02, 0.02, 0.76))
    bpy.context.scene.camera = camera
    for source in list(camera.users_collection):
        source.objects.unlink(camera)
    collection("LIGHTING_CAMERA").objects.link(camera)

    lights = [
        ("LGT_Key_ForgeWorkbenchSoftbox", "AREA", (-2.4, -2.8, 2.75), 420, 3.4),
        ("LGT_EmberWarmFill", "POINT", (-0.58, 0.08, 1.08), 95, 0),
        ("LGT_Rim_ForgeMetalEdges", "AREA", (2.2, 1.35, 1.95), 180, 1.7),
    ]
    for name, kind, loc, energy, size in lights:
        data = bpy.data.lights.new(name, kind)
        obj = bpy.data.objects.new(name, data)
        bpy.context.scene.collection.objects.link(obj)
        obj.location = loc
        data.energy = energy
        if hasattr(data, "size") and size:
            data.size = size
        look_at(obj, (0, 0.04, 0.68))
        for source in list(obj.users_collection):
            source.objects.unlink(obj)
        collection("LIGHTING_CAMERA").objects.link(obj)


def configure_scene() -> None:
    scene = bpy.context.scene
    scene.name = "SCN_BlacksmithForgeWorkbench"
    scene.unit_settings.system = "METRIC"
    scene.frame_start = 1
    scene.frame_end = 1
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
        export_animations=False,
        export_lights=False,
        export_cameras=False,
        export_materials="EXPORT",
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
    export_glb(paths["glb"], geometry_objects())

    bpy.context.scene.render.filepath = str(paths["preview"])
    bpy.ops.render.render(write_still=True)


def collect_metadata(paths: dict[str, Path]) -> dict:
    meshes = mesh_objects()
    geometries = geometry_objects()
    actions = sorted(action.name for action in bpy.data.actions)
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
            "animations": len(actions),
        },
        "materials": material_names(geometries),
        "animations": {
            "clips": actions,
            "default": None,
            "embedded_in_glb": False,
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
            "animations": False,
            "source": "Blender MCP live bridge or background Blender",
        },
        "notes": [
            "Blacksmith forge workbench generated procedurally in Blender.",
            "Intentionally static furniture asset: no rig, no embedded animation clips, and no Mixamo exports.",
            "Includes heavy dark-wood bench, anvil surface, hammer rack, tongs, scattered tools, steel scraps, soot marks, ember accents, and baked contact shadow.",
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
    build_workbench(mats)
    setup_lighting_and_camera()
    export_asset(paths)
    metadata = collect_metadata(paths)
    write_json(paths["metadata"], metadata)
    return metadata


if __name__ == "__main__":
    result = main()
    print(json.dumps(result, indent=2))
