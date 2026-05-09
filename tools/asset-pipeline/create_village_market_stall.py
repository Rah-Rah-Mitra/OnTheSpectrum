"""Generate a static village market stall asset in Blender.

Run from Blender Python through the live MCP bridge or background Blender. The
script is repeatable: it creates the source scene, exports a static GLB,
renders a preview, and writes metadata for the OnTheSpectrum viewer.
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
    cube,
    cylinder,
    ensure_dir,
    link_to_collection,
    look_at,
    make_mat,
    scene_triangle_count,
    shade_smooth,
    write_json,
)

ASSET_SLUG = "village-market-stall"
ASSET_NAME = "Village Market Stall"

ASSET_SPEC = {
    "slug": ASSET_SLUG,
    "asset_family": "Furniture",
    "subject": "Village Market Stall",
    "visual_style": "Stylized fantasy village, colorful and modular, suitable for marketplace scenes",
    "required_parts": [
        "wooden counter",
        "canopy frame",
        "cloth awning",
        "crates",
        "display shelves",
        "hanging hooks",
        "rope ties",
        "baked contact shadow",
    ],
    "material_palette": [
        "light brown wood",
        "faded red-and-cream cloth awning",
        "rope ties",
        "darker crate wood",
        "dark hook metal",
        "soft translucent contact shadow",
    ],
    "rig_target": "none",
    "animation_clips": [],
    "viewer_framing": "front 3/4 view, show counter and canopy, asset centered with all parts visible",
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
    red = make_mat("MAT_VillageMarketStall_FadedRedCloth", (0.72, 0.18, 0.13, 1), roughness=0.86)
    cream = make_mat("MAT_VillageMarketStall_CreamCloth", (0.92, 0.79, 0.55, 1), roughness=0.88)
    for mat in [red, cream]:
        mat.use_backface_culling = False
    return {
        "wood": make_mat("MAT_VillageMarketStall_LightWood", (0.74, 0.46, 0.22, 1), roughness=0.66),
        "crate": make_mat("MAT_VillageMarketStall_DarkCrateWood", (0.38, 0.19, 0.085, 1), roughness=0.76),
        "red_cloth": red,
        "cream_cloth": cream,
        "rope": make_mat("MAT_VillageMarketStall_RopeTie", (0.72, 0.58, 0.32, 1), roughness=0.9),
        "hook": make_mat("MAT_VillageMarketStall_DarkHookMetal", (0.08, 0.075, 0.07, 1), roughness=0.48, metallic=0.35),
        "shadow": make_mat("MAT_Shadow_BakedSoftContact", (0.018, 0.02, 0.023, 0.5), roughness=0.92, alpha=0.5),
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


def add_mesh_object(
    name: str,
    vertices: list[tuple[float, float, float]],
    faces: list[tuple[int, ...]],
    mat: bpy.types.Material,
    *,
    collection_name: str = "PROPS",
    smooth: bool = True,
) -> bpy.types.Object:
    mesh = bpy.data.meshes.new(f"{name}_MESH")
    mesh.from_pydata(vertices, [], faces)
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.scene.collection.objects.link(obj)
    obj.data.materials.append(mat)
    if smooth:
        shade_smooth(obj)
        add_weighted_normals(obj)
    return link_to_collection(obj, collection_name)


def awning_strip(
    name: str,
    x_min: float,
    x_max: float,
    mat: bpy.types.Material,
) -> bpy.types.Object:
    y_values = [-0.72, -0.32, 0.12, 0.58]
    vertices: list[tuple[float, float, float]] = []
    for x in [x_min, x_max]:
        for y in y_values:
            t = (y - y_values[0]) / (y_values[-1] - y_values[0])
            z = 1.78 + (0.36 * t) - (0.035 * math.sin(math.pi * t))
            side_drape = 0.015 if x < 0 else -0.015
            vertices.append((x, y, z + side_drape))
    faces = [(0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6)]
    return add_mesh_object(name, vertices, faces, mat, collection_name="PROPS")


def build_crate(
    name: str,
    loc: tuple[float, float, float],
    scale: tuple[float, float, float],
    mats: dict[str, bpy.types.Material],
) -> list[bpy.types.Object]:
    objects: list[bpy.types.Object] = []
    x, y, z = loc
    sx, sy, sz = scale

    def add(obj: bpy.types.Object) -> bpy.types.Object:
        objects.append(obj)
        return obj

    add(cube(f"{name}_Box", loc, scale, mats["crate"], bevel=0.014, collection_name="PROPS"))
    add(cube(f"{name}_FrontTopSlat", (x, y - sy - 0.012, z + sz * 0.48), (sx * 1.04, 0.018, sz * 0.12), mats["wood"], bevel=0.006, collection_name="PROPS"))
    add(cube(f"{name}_FrontBottomSlat", (x, y - sy - 0.012, z - sz * 0.48), (sx * 1.04, 0.018, sz * 0.12), mats["wood"], bevel=0.006, collection_name="PROPS"))
    add(cube(f"{name}_FrontDiagonalSlat", (x, y - sy - 0.016, z), (sx * 0.95, 0.016, sz * 0.08), mats["wood"], bevel=0.005, collection_name="PROPS"))
    objects[-1].rotation_euler[1] = math.radians(16)
    add(cube(f"{name}_LeftSideRim", (x - sx - 0.012, y, z + sz * 0.04), (0.018, sy * 0.98, sz * 0.9), mats["wood"], bevel=0.006, collection_name="PROPS"))
    add(cube(f"{name}_RightSideRim", (x + sx + 0.012, y, z + sz * 0.04), (0.018, sy * 0.98, sz * 0.9), mats["wood"], bevel=0.006, collection_name="PROPS"))
    return objects


def add_rope_lash(
    name: str,
    center: tuple[float, float, float],
    mats: dict[str, bpy.types.Material],
    *,
    width: float = 0.18,
) -> list[bpy.types.Object]:
    x, y, z = center
    return [
        bevel_curve(
            f"{name}_RopeTieA",
            [(x - width * 0.5, y, z - 0.035), (x, y, z + 0.018), (x + width * 0.5, y, z - 0.035)],
            mats["rope"],
            bevel_depth=0.009,
            bevel_resolution=2,
            collection_name="PROPS",
        ),
        bevel_curve(
            f"{name}_RopeTieB",
            [(x - width * 0.5, y, z + 0.035), (x, y, z - 0.018), (x + width * 0.5, y, z + 0.035)],
            mats["rope"],
            bevel_depth=0.009,
            bevel_resolution=2,
            collection_name="PROPS",
        ),
    ]


def build_market_stall(mats: dict[str, bpy.types.Material]) -> list[bpy.types.Object]:
    for name in ["PROPS", "BAKED_EFFECTS", "LIGHTING_CAMERA"]:
        collection(name)

    objects: list[bpy.types.Object] = []

    def add(obj: bpy.types.Object) -> bpy.types.Object:
        objects.append(obj)
        return obj

    def extend(new_objects: list[bpy.types.Object]) -> None:
        objects.extend(new_objects)

    # Counter body and modular wood plank details.
    add(cube("PROP_VillageMarketStall_CounterTop_BeveledLightWood", (0, -0.28, 0.78), (1.18, 0.36, 0.07), mats["wood"], bevel=0.028, collection_name="PROPS"))
    add(cube("PROP_VillageMarketStall_CounterFrontPanel", (0, -0.66, 0.48), (1.16, 0.055, 0.34), mats["wood"], bevel=0.018, collection_name="PROPS"))
    add(cube("PROP_VillageMarketStall_CounterBackBrace", (0, 0.08, 0.45), (1.06, 0.05, 0.28), mats["crate"], bevel=0.014, collection_name="PROPS"))
    for index, x in enumerate([-0.92, -0.46, 0.0, 0.46, 0.92], start=1):
        add(cube(f"PROP_VillageMarketStall_FrontPlankDivider_{index}", (x, -0.718, 0.48), (0.016, 0.018, 0.33), mats["crate"], bevel=0.004, collection_name="PROPS"))
    for index, z in enumerate([0.35, 0.49, 0.63], start=1):
        add(bevel_curve(f"PROP_VillageMarketStall_CounterWoodGrain_{index}", [(-0.98, -0.722, z), (-0.2, -0.728, z + 0.018), (0.98, -0.722, z - 0.006)], mats["crate"], bevel_depth=0.0032, bevel_resolution=1, collection_name="PROPS"))

    # Canopy posts and crossbeams.
    for side_name, x in [("Left", -1.08), ("Right", 1.08)]:
        for row_name, y in [("Front", -0.66), ("Back", 0.5)]:
            add(cylinder(f"PROP_VillageMarketStall_{row_name}{side_name}_CanopyPost", (x, y, 0.98), 0.042, 1.92, mats["wood"], vertices=18, bevel=0.006, collection_name="PROPS"))
    add(cylinder("PROP_VillageMarketStall_FrontCanopyBeam", (0, -0.66, 1.82), 0.04, 2.34, mats["wood"], vertices=20, rotation=(0, math.radians(90), 0), bevel=0.006, collection_name="PROPS"))
    add(cylinder("PROP_VillageMarketStall_BackCanopyBeam", (0, 0.5, 2.14), 0.04, 2.34, mats["wood"], vertices=20, rotation=(0, math.radians(90), 0), bevel=0.006, collection_name="PROPS"))
    for side_name, x in [("Left", -1.08), ("Right", 1.08)]:
        beam = add(cylinder(f"PROP_VillageMarketStall_{side_name}_SlopedSideBeam", (x, -0.08, 1.98), 0.03, 1.28, mats["wood"], vertices=18, rotation=(math.radians(75), 0, 0), bevel=0.005, collection_name="PROPS"))
        beam.rotation_euler[0] = math.radians(75)

    # Alternating cloth awning strips plus valance.
    stripe_count = 8
    x_start = -1.2
    stripe_width = 2.4 / stripe_count
    for index in range(stripe_count):
        mat = mats["red_cloth"] if index % 2 == 0 else mats["cream_cloth"]
        add(awning_strip(
            f"PROP_VillageMarketStall_AwningStripe_{index + 1:02d}_{'Red' if index % 2 == 0 else 'Cream'}",
            x_start + index * stripe_width,
            x_start + (index + 1) * stripe_width,
            mat,
        ))
    for index in range(stripe_count):
        mat = mats["cream_cloth"] if index % 2 == 0 else mats["red_cloth"]
        x = x_start + index * stripe_width + stripe_width * 0.5
        add(cube(f"PROP_VillageMarketStall_FrontValance_{index + 1:02d}", (x, -0.76, 1.65), (stripe_width * 0.48, 0.025, 0.11), mat, bevel=0.01, collection_name="PROPS"))

    # Display shelves behind the counter.
    add(cube("PROP_VillageMarketStall_LowerDisplayShelf", (0, 0.35, 1.02), (0.98, 0.16, 0.04), mats["wood"], bevel=0.014, collection_name="PROPS"))
    add(cube("PROP_VillageMarketStall_UpperDisplayShelf", (0, 0.37, 1.34), (0.9, 0.14, 0.038), mats["wood"], bevel=0.014, collection_name="PROPS"))
    for index, x in enumerate([-0.82, 0.82], start=1):
        add(cube(f"PROP_VillageMarketStall_ShelfSideSupport_{index}", (x, 0.38, 1.18), (0.035, 0.05, 0.42), mats["wood"], bevel=0.01, collection_name="PROPS"))
    for index, x in enumerate([-0.45, 0.0, 0.45], start=1):
        add(cube(f"PROP_VillageMarketStall_ShelfSmallBin_{index}", (x, 0.2, 1.075), (0.16, 0.12, 0.07), mats["crate"], bevel=0.012, collection_name="PROPS"))

    # Crates staged around the counter footprint.
    extend(build_crate("PROP_VillageMarketStall_LeftFrontCrate", (-0.78, -0.86, 0.18), (0.26, 0.2, 0.16), mats))
    extend(build_crate("PROP_VillageMarketStall_RightStackedCrateLow", (0.78, -0.86, 0.17), (0.24, 0.2, 0.15), mats))
    extend(build_crate("PROP_VillageMarketStall_RightStackedCrateHigh", (0.82, -0.82, 0.48), (0.22, 0.18, 0.14), mats))
    extend(build_crate("PROP_VillageMarketStall_BackSupplyCrate", (-0.72, 0.28, 0.23), (0.24, 0.18, 0.18), mats))

    # Hooks for hanging goods under the front beam.
    for index, x in enumerate([-0.62, -0.22, 0.22, 0.62], start=1):
        add(bevel_curve(
            f"PROP_VillageMarketStall_HangingHook_{index}",
            [(x, -0.69, 1.72), (x, -0.69, 1.58), (x + 0.045, -0.69, 1.51), (x + 0.095, -0.69, 1.56)],
            mats["hook"],
            bevel_depth=0.011,
            bevel_resolution=3,
            collection_name="PROPS",
        ))
        add(cylinder(f"PROP_VillageMarketStall_HookPeg_{index}", (x, -0.66, 1.73), 0.016, 0.08, mats["hook"], vertices=16, rotation=(math.radians(90), 0, 0), bevel=0.003, collection_name="PROPS"))

    # Rope ties lash cloth and beams to the posts.
    for index, (x, y, z) in enumerate([(-1.08, -0.68, 1.78), (1.08, -0.68, 1.78), (-1.08, 0.5, 2.08), (1.08, 0.5, 2.08)], start=1):
        extend(add_rope_lash(f"PROP_VillageMarketStall_CanopyLash_{index}", (x, y, z), mats, width=0.15))
        add(cylinder(f"PROP_VillageMarketStall_RopeWrap_{index}", (x, y, z), 0.052, 0.018, mats["rope"], vertices=18, rotation=(math.radians(90), 0, 0), bevel=0.002, collection_name="PROPS"))

    add(cylinder("BASE_BakedSoftContactShadow", (0, -0.16, 0.004), 0.82, 0.008, mats["shadow"], vertices=80, scale=(1.75, 1.18, 1), collection_name="BAKED_EFFECTS"))
    return objects


def setup_lighting_and_camera() -> None:
    world = bpy.context.scene.world or bpy.data.worlds.new("World")
    bpy.context.scene.world = world
    world.color = (0.028, 0.032, 0.034)

    camera_data = bpy.data.cameras.new("CAM_VillageMarketStall_Preview")
    camera = bpy.data.objects.new("CAM_VillageMarketStall_Preview", camera_data)
    bpy.context.scene.collection.objects.link(camera)
    camera.location = (2.32, -3.15, 1.58)
    camera.data.lens = 46
    camera.data.dof.use_dof = True
    camera.data.dof.focus_distance = 3.7
    camera.data.dof.aperture_fstop = 7.0
    look_at(camera, (0, -0.16, 0.96))
    bpy.context.scene.camera = camera
    for source in list(camera.users_collection):
        source.objects.unlink(camera)
    collection("LIGHTING_CAMERA").objects.link(camera)

    lights = [
        ("LGT_Key_StallWarmMarketSoftbox", "AREA", (-2.6, -3.0, 3.2), 520, 4.1),
        ("LGT_Rim_StallCanopyEdge", "AREA", (2.4, 1.8, 2.25), 180, 2.1),
        ("LGT_Fill_StallFrontCounter", "POINT", (1.5, -1.7, 1.3), 76, 0),
    ]
    for name, kind, loc, energy, size in lights:
        data = bpy.data.lights.new(name, kind)
        obj = bpy.data.objects.new(name, data)
        bpy.context.scene.collection.objects.link(obj)
        obj.location = loc
        data.energy = energy
        if hasattr(data, "size") and size:
            data.size = size
        look_at(obj, (0, -0.16, 0.98))
        for source in list(obj.users_collection):
            source.objects.unlink(obj)
        collection("LIGHTING_CAMERA").objects.link(obj)


def configure_scene() -> None:
    scene = bpy.context.scene
    scene.name = "SCN_VillageMarketStall"
    scene.unit_settings.system = "METRIC"
    scene.frame_start = 1
    scene.frame_end = 1
    scene.render.resolution_x = 1000
    scene.render.resolution_y = 1000
    scene.render.film_transparent = False
    scene.view_settings.view_transform = "Filmic"
    scene.view_settings.look = "Medium High Contrast"
    scene.view_settings.exposure = 0
    scene.view_settings.gamma = 1
    scene.render.engine = "BLENDER_WORKBENCH"
    if hasattr(scene, "display") and hasattr(scene.display, "shading"):
        scene.display.shading.light = "STUDIO"
        scene.display.shading.color_type = "MATERIAL"


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


def render_preview(path: Path) -> None:
    bpy.context.scene.render.filepath = str(path)
    try:
        bpy.ops.render.render(write_still=True)
    except Exception:
        bpy.context.scene.render.engine = "BLENDER_WORKBENCH"
        bpy.ops.render.render(write_still=True)


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
    render_preview(paths["preview"])


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
            "Village Market Stall generated procedurally in Blender.",
            "Intentionally static furniture asset: no rig, no embedded animation clips, and no Mixamo exports.",
            "Stylized modular market prop with wooden counter, canopy frame, striped cloth awning, crates, shelves, rope ties, hooks, and baked contact shadow.",
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
    build_market_stall(mats)
    setup_lighting_and_camera()
    export_asset(paths)
    metadata = collect_metadata(paths)
    write_json(paths["metadata"], metadata)
    return metadata


if __name__ == "__main__":
    result = main()
    print(json.dumps(result, indent=2))
