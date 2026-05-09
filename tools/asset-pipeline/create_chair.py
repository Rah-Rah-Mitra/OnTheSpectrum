"""Generate a standard static chair asset in Blender.

Run from Blender Python through the live MCP bridge. The script is repeatable:
it creates the source scene, exports a static GLB, renders a preview, and
writes metadata for the Artomata viewer.
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

ASSET_SLUG = "chair"
ASSET_NAME = "Chair"


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
        "oak": make_mat("MAT_Chair_WarmOak", (0.78, 0.48, 0.22, 1), roughness=0.64),
        "endgrain": make_mat("MAT_Chair_OakEndgrain", (0.52, 0.29, 0.12, 1), roughness=0.72),
        "fabric": make_mat("MAT_Chair_CharcoalFabric", (0.055, 0.06, 0.07, 1), roughness=0.9),
        "shadow": make_mat("MAT_Shadow_BakedSoftContact", (0.018, 0.02, 0.023, 0.56), roughness=0.92, alpha=0.56),
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


def softened_leg(name: str, loc: tuple[float, float, float], mats: dict[str, bpy.types.Material]) -> bpy.types.Object:
    leg = cone(
        name,
        loc,
        0.028,
        0.041,
        0.46,
        mats["oak"],
        vertices=18,
        collection_name="PROPS",
    )
    add_bevel(leg, 0.006, 2, apply=True)
    add_weighted_normals(leg)
    return leg


def build_chair(mats: dict[str, bpy.types.Material]) -> list[bpy.types.Object]:
    for name in ["PROPS", "BAKED_EFFECTS", "LIGHTING_CAMERA"]:
        collection(name)

    objects: list[bpy.types.Object] = []

    def add(obj: bpy.types.Object) -> bpy.types.Object:
        objects.append(obj)
        return obj

    # Seat assembly.
    add(cube("PROP_Chair_SeatBase_BeveledOak", (0, 0, 0.47), (0.55, 0.5, 0.07), mats["oak"], bevel=0.03, collection_name="PROPS"))
    add(cube("PROP_Chair_Cushion_CharcoalPad", (0, -0.018, 0.53), (0.48, 0.42, 0.075), mats["fabric"], bevel=0.045, collection_name="PROPS"))
    add(cube("PROP_Chair_FrontEndgrainLip", (0, -0.268, 0.475), (0.55, 0.025, 0.075), mats["endgrain"], bevel=0.01, collection_name="PROPS"))
    add(cube("PROP_Chair_LeftEndgrainLip", (-0.288, 0, 0.475), (0.025, 0.48, 0.07), mats["endgrain"], bevel=0.01, collection_name="PROPS"))
    add(cube("PROP_Chair_RightEndgrainLip", (0.288, 0, 0.475), (0.025, 0.48, 0.07), mats["endgrain"], bevel=0.01, collection_name="PROPS"))

    cushion_edges = [
        ("Front", [(-0.21, -0.236, 0.572), (0.0, -0.246, 0.574), (0.21, -0.236, 0.572)]),
        ("Back", [(-0.21, 0.196, 0.572), (0.0, 0.206, 0.574), (0.21, 0.196, 0.572)]),
        ("Left", [(-0.252, -0.18, 0.57), (-0.258, -0.02, 0.574), (-0.252, 0.15, 0.57)]),
        ("Right", [(0.252, -0.18, 0.57), (0.258, -0.02, 0.574), (0.252, 0.15, 0.57)]),
    ]
    for edge_name, points in cushion_edges:
        add(bevel_curve(f"PROP_Chair_Cushion_{edge_name}SoftPiping", points, mats["fabric"], bevel_depth=0.006, bevel_resolution=2, collection_name="PROPS"))

    # Legs, apron rails, and foot stretchers.
    for side_name, x in [("Left", -0.235), ("Right", 0.235)]:
        for row_name, y in [("Front", -0.205), ("Back", 0.215)]:
            add(softened_leg(f"PROP_Chair_{row_name}{side_name}_TaperedOakLeg", (x, y, 0.23), mats))

    add(cube("PROP_Chair_FrontApronRail", (0, -0.25, 0.405), (0.52, 0.045, 0.08), mats["oak"], bevel=0.016, collection_name="PROPS"))
    add(cube("PROP_Chair_BackApronRail", (0, 0.26, 0.405), (0.52, 0.045, 0.08), mats["oak"], bevel=0.016, collection_name="PROPS"))
    add(cube("PROP_Chair_LeftSideApronRail", (-0.268, 0.005, 0.405), (0.045, 0.48, 0.08), mats["oak"], bevel=0.016, collection_name="PROPS"))
    add(cube("PROP_Chair_RightSideApronRail", (0.268, 0.005, 0.405), (0.045, 0.48, 0.08), mats["oak"], bevel=0.016, collection_name="PROPS"))

    add(cylinder("PROP_Chair_FrontFootStretcher", (0, -0.205, 0.18), 0.016, 0.45, mats["oak"], vertices=18, rotation=(0, math.radians(90), 0), bevel=0.004, collection_name="PROPS"))
    add(cylinder("PROP_Chair_BackFootStretcher", (0, 0.215, 0.2), 0.016, 0.45, mats["oak"], vertices=18, rotation=(0, math.radians(90), 0), bevel=0.004, collection_name="PROPS"))
    add(cylinder("PROP_Chair_LeftFootStretcher", (-0.235, 0.005, 0.22), 0.014, 0.42, mats["oak"], vertices=18, rotation=(math.radians(90), 0, 0), bevel=0.004, collection_name="PROPS"))
    add(cylinder("PROP_Chair_RightFootStretcher", (0.235, 0.005, 0.22), 0.014, 0.42, mats["oak"], vertices=18, rotation=(math.radians(90), 0, 0), bevel=0.004, collection_name="PROPS"))

    # Back posts, slats, and crest rail.
    add(cube("PROP_Chair_BackPost_L", (-0.235, 0.25, 0.78), (0.065, 0.07, 0.64), mats["oak"], bevel=0.022, collection_name="PROPS"))
    add(cube("PROP_Chair_BackPost_R", (0.235, 0.25, 0.78), (0.065, 0.07, 0.64), mats["oak"], bevel=0.022, collection_name="PROPS"))
    add(cube("PROP_Chair_Backrest_CurvedOakPanel", (0, 0.248, 0.915), (0.48, 0.065, 0.16), mats["oak"], bevel=0.026, collection_name="PROPS"))
    add(cube("PROP_Chair_Backrest_TopCrestRail", (0, 0.248, 1.06), (0.55, 0.08, 0.08), mats["oak"], bevel=0.026, collection_name="PROPS"))

    for index, x in enumerate([-0.14, 0.0, 0.14], start=1):
        add(cube(f"PROP_Chair_Backrest_Slat_{index}", (x, 0.225, 0.75), (0.045, 0.045, 0.3), mats["oak"], bevel=0.018, collection_name="PROPS"))

    for index, z in enumerate([0.895, 0.93, 0.965, 1.075], start=1):
        add(bevel_curve(f"PROP_Chair_Backrest_VisibleWoodGrain_{index}", [(-0.2, 0.205, z), (-0.03, 0.198, z + 0.006), (0.2, 0.205, z - 0.002)], mats["endgrain"], bevel_depth=0.0032, bevel_resolution=1, collection_name="PROPS"))

    for index, y in enumerate([-0.15, -0.015, 0.12], start=1):
        add(bevel_curve(f"PROP_Chair_SeatRim_SubtleWoodGrain_{index}", [(-0.245, y, 0.512), (-0.03, y + 0.015, 0.514), (0.24, y - 0.006, 0.512)], mats["endgrain"], bevel_depth=0.0028, bevel_resolution=1, collection_name="PROPS"))

    add(cylinder("BASE_BakedSoftContactShadow", (0, 0.02, 0.004), 0.42, 0.008, mats["shadow"], vertices=64, scale=(1.05, 0.78, 1), collection_name="BAKED_EFFECTS"))
    return objects


def setup_lighting_and_camera() -> None:
    world = bpy.context.scene.world or bpy.data.worlds.new("World")
    bpy.context.scene.world = world
    world.color = (0.026, 0.031, 0.034)

    camera_data = bpy.data.cameras.new("CAM_Chair_Preview")
    camera = bpy.data.objects.new("CAM_Chair_Preview", camera_data)
    bpy.context.scene.collection.objects.link(camera)
    camera.location = (1.18, -2.28, 0.98)
    camera.data.lens = 58
    camera.data.dof.use_dof = True
    camera.data.dof.focus_distance = 2.65
    camera.data.dof.aperture_fstop = 6.5
    look_at(camera, (0, 0.03, 0.58))
    bpy.context.scene.camera = camera
    for source in list(camera.users_collection):
        source.objects.unlink(camera)
    collection("LIGHTING_CAMERA").objects.link(camera)

    lights = [
        ("LGT_Key_ChairSoftbox", "AREA", (-1.8, -2.4, 2.6), 390, 3.2),
        ("LGT_Rim_ChairWarmEdge", "AREA", (1.75, 1.25, 1.85), 130, 1.8),
        ("LGT_Fill_ChairStudio", "POINT", (1.2, -1.4, 1.1), 62, 0),
    ]
    for name, kind, loc, energy, size in lights:
        data = bpy.data.lights.new(name, kind)
        obj = bpy.data.objects.new(name, data)
        bpy.context.scene.collection.objects.link(obj)
        obj.location = loc
        data.energy = energy
        if hasattr(data, "size") and size:
            data.size = size
        look_at(obj, (0, 0.04, 0.55))
        for source in list(obj.users_collection):
            source.objects.unlink(obj)
        collection("LIGHTING_CAMERA").objects.link(obj)


def configure_scene() -> None:
    scene = bpy.context.scene
    scene.name = "SCN_StandardChair"
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
            "source": "Blender MCP live bridge",
        },
        "notes": [
            "Standard dining-style chair generated procedurally in Blender.",
            "Intentionally static furniture asset: no rig, no embedded animation clips, and no Mixamo exports.",
            "Warm oak frame, visible geometric wood grain, charcoal cushion, foot stretchers, and baked contact shadow.",
        ],
    }


def main() -> dict:
    paths = out_paths()
    clear_scene()
    configure_scene()
    mats = make_materials()
    build_chair(mats)
    setup_lighting_and_camera()
    export_asset(paths)
    metadata = collect_metadata(paths)
    write_json(paths["metadata"], metadata)
    return metadata


if __name__ == "__main__":
    result = main()
    print(json.dumps(result, indent=2))
