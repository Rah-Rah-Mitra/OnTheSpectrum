"""Reusable Blender helpers for Artomata procedural asset generation.

These functions are intended to be imported from Blender's Python runtime.
Keep them dependency-free so they work through the live MCP bridge and through
background Blender when BLENDER_PATH is configured.
"""

from __future__ import annotations

import json
import math
import os
from pathlib import Path

import bpy
from mathutils import Vector


def ensure_dir(path: str | os.PathLike[str]) -> None:
    Path(path).mkdir(parents=True, exist_ok=True)


def clear_scene() -> None:
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete()
    for block in (
        bpy.data.meshes,
        bpy.data.materials,
        bpy.data.images,
        bpy.data.curves,
        bpy.data.armatures,
        bpy.data.cameras,
        bpy.data.lights,
    ):
        for item in list(block):
            if item.users == 0:
                block.remove(item)


def collection(name: str) -> bpy.types.Collection:
    existing = bpy.data.collections.get(name)
    if existing:
        return existing
    new_collection = bpy.data.collections.new(name)
    bpy.context.scene.collection.children.link(new_collection)
    return new_collection


def link_to_collection(obj: bpy.types.Object, name: str) -> bpy.types.Object:
    target = collection(name)
    if obj.name not in target.objects:
        target.objects.link(obj)
    for source in list(obj.users_collection):
        if source != target:
            source.objects.unlink(obj)
    return obj


def make_mat(
    name: str,
    base_color: tuple[float, float, float, float],
    *,
    roughness: float = 0.72,
    metallic: float = 0.0,
    alpha: float = 1.0,
    emission: tuple[float, float, float, float] | None = None,
    emission_strength: float = 0.0,
) -> bpy.types.Material:
    mat = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    mat.use_nodes = True
    mat.diffuse_color = base_color
    mat.blend_method = "BLEND" if alpha < 1 else "OPAQUE"
    mat.use_screen_refraction = False

    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    if bsdf:
        if "Base Color" in bsdf.inputs:
            bsdf.inputs["Base Color"].default_value = base_color
        if "Alpha" in bsdf.inputs:
            bsdf.inputs["Alpha"].default_value = alpha
        if "Roughness" in bsdf.inputs:
            bsdf.inputs["Roughness"].default_value = roughness
        if "Metallic" in bsdf.inputs:
            bsdf.inputs["Metallic"].default_value = metallic
        if emission:
            if "Emission Color" in bsdf.inputs:
                bsdf.inputs["Emission Color"].default_value = emission
            if "Emission Strength" in bsdf.inputs:
                bsdf.inputs["Emission Strength"].default_value = emission_strength
    return mat


def assign_mat(obj: bpy.types.Object, mat: bpy.types.Material) -> bpy.types.Object:
    obj.data.materials.clear()
    obj.data.materials.append(mat)
    return obj


def shade_smooth(obj: bpy.types.Object) -> bpy.types.Object:
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)
    try:
        bpy.ops.object.shade_smooth()
    finally:
        obj.select_set(False)
    return obj


def apply_transform(obj: bpy.types.Object, *, location: bool = False, rotation: bool = False, scale: bool = True) -> None:
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)
    bpy.ops.object.transform_apply(location=location, rotation=rotation, scale=scale)
    obj.select_set(False)


def add_bevel(obj: bpy.types.Object, amount: float, segments: int = 2, *, apply: bool = False) -> bpy.types.Object:
    bevel = obj.modifiers.new("BVL_softened_asset_edges", "BEVEL")
    bevel.width = amount
    bevel.segments = segments
    bevel.affect = "EDGES"
    bevel.profile = 0.55
    if apply:
        bpy.context.view_layer.objects.active = obj
        obj.select_set(True)
        bpy.ops.object.modifier_apply(modifier=bevel.name)
        obj.select_set(False)
    return obj


def add_weighted_normals(obj: bpy.types.Object, *, apply: bool = True) -> bpy.types.Object:
    mod = obj.modifiers.new("NRM_weighted_export_normals", "WEIGHTED_NORMAL")
    mod.keep_sharp = True
    if apply:
        bpy.context.view_layer.objects.active = obj
        obj.select_set(True)
        bpy.ops.object.modifier_apply(modifier=mod.name)
        obj.select_set(False)
    return obj


def uv_sphere(
    name: str,
    loc: tuple[float, float, float],
    scale: tuple[float, float, float],
    mat: bpy.types.Material,
    *,
    segments: int = 32,
    rings: int = 16,
    collection_name: str = "CHARACTER",
) -> bpy.types.Object:
    bpy.ops.mesh.primitive_uv_sphere_add(segments=segments, ring_count=rings, radius=1.0, location=loc)
    obj = bpy.context.object
    obj.name = name
    obj.data.name = f"{name}_MESH"
    obj.scale = scale
    assign_mat(obj, mat)
    apply_transform(obj)
    shade_smooth(obj)
    add_weighted_normals(obj)
    return link_to_collection(obj, collection_name)


def cube(
    name: str,
    loc: tuple[float, float, float],
    scale: tuple[float, float, float],
    mat: bpy.types.Material,
    *,
    bevel: float = 0.04,
    collection_name: str = "CHARACTER",
) -> bpy.types.Object:
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=loc)
    obj = bpy.context.object
    obj.name = name
    obj.data.name = f"{name}_MESH"
    obj.scale = scale
    assign_mat(obj, mat)
    apply_transform(obj)
    if bevel > 0:
        add_bevel(obj, bevel, 4, apply=True)
    shade_smooth(obj)
    add_weighted_normals(obj)
    return link_to_collection(obj, collection_name)


def cylinder(
    name: str,
    loc: tuple[float, float, float],
    radius: float,
    depth: float,
    mat: bpy.types.Material,
    *,
    vertices: int = 32,
    rotation: tuple[float, float, float] = (0, 0, 0),
    scale: tuple[float, float, float] = (1, 1, 1),
    bevel: float = 0.0,
    collection_name: str = "CHARACTER",
) -> bpy.types.Object:
    bpy.ops.mesh.primitive_cylinder_add(vertices=vertices, radius=radius, depth=depth, location=loc, rotation=rotation)
    obj = bpy.context.object
    obj.name = name
    obj.data.name = f"{name}_MESH"
    obj.scale = scale
    assign_mat(obj, mat)
    apply_transform(obj, rotation=False, scale=True)
    if bevel > 0:
        add_bevel(obj, bevel, 3, apply=True)
    shade_smooth(obj)
    add_weighted_normals(obj)
    return link_to_collection(obj, collection_name)


def cone(
    name: str,
    loc: tuple[float, float, float],
    radius1: float,
    radius2: float,
    depth: float,
    mat: bpy.types.Material,
    *,
    vertices: int = 32,
    rotation: tuple[float, float, float] = (0, 0, 0),
    scale: tuple[float, float, float] = (1, 1, 1),
    collection_name: str = "CHARACTER",
) -> bpy.types.Object:
    bpy.ops.mesh.primitive_cone_add(
        vertices=vertices,
        radius1=radius1,
        radius2=radius2,
        depth=depth,
        location=loc,
        rotation=rotation,
    )
    obj = bpy.context.object
    obj.name = name
    obj.data.name = f"{name}_MESH"
    obj.scale = scale
    assign_mat(obj, mat)
    apply_transform(obj, rotation=False, scale=True)
    shade_smooth(obj)
    add_weighted_normals(obj)
    return link_to_collection(obj, collection_name)


def bevel_curve(
    name: str,
    points: list[tuple[float, float, float]],
    mat: bpy.types.Material,
    *,
    bevel_depth: float = 0.04,
    bevel_resolution: int = 4,
    resolution: int = 20,
    collection_name: str = "CHARACTER",
    convert: bool = True,
) -> bpy.types.Object:
    curve = bpy.data.curves.new(f"{name}_CURVE", "CURVE")
    curve.dimensions = "3D"
    curve.resolution_u = resolution
    curve.bevel_depth = bevel_depth
    curve.bevel_resolution = bevel_resolution
    spline = curve.splines.new("BEZIER")
    spline.bezier_points.add(len(points) - 1)
    for point, co in zip(spline.bezier_points, points):
        point.co = co
        point.handle_left_type = "AUTO"
        point.handle_right_type = "AUTO"
    obj = bpy.data.objects.new(name, curve)
    bpy.context.scene.collection.objects.link(obj)
    assign_mat(obj, mat)
    link_to_collection(obj, collection_name)
    if convert:
        bpy.context.view_layer.objects.active = obj
        obj.select_set(True)
        bpy.ops.object.convert(target="MESH")
        obj = bpy.context.object
        obj.name = name
        obj.data.name = f"{name}_MESH"
        shade_smooth(obj)
        add_weighted_normals(obj)
        obj.select_set(False)
    return obj


def look_at(obj: bpy.types.Object, target: tuple[float, float, float]) -> None:
    direction = Vector(target) - obj.location
    obj.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()


def scene_triangle_count(objects: list[bpy.types.Object] | None = None) -> int:
    depsgraph = bpy.context.evaluated_depsgraph_get()
    total = 0
    for obj in objects or list(bpy.data.objects):
        if obj.type != "MESH":
            continue
        evaluated = obj.evaluated_get(depsgraph)
        mesh = evaluated.to_mesh()
        try:
            total += sum(max(1, len(poly.vertices) - 2) for poly in mesh.polygons)
        finally:
            evaluated.to_mesh_clear()
    return total


def bounds_for_objects(objects: list[bpy.types.Object]) -> dict[str, list[float]]:
    min_v = Vector((math.inf, math.inf, math.inf))
    max_v = Vector((-math.inf, -math.inf, -math.inf))
    for obj in objects:
        if obj.type != "MESH":
            continue
        for corner in obj.bound_box:
            world = obj.matrix_world @ Vector(corner)
            min_v.x = min(min_v.x, world.x)
            min_v.y = min(min_v.y, world.y)
            min_v.z = min(min_v.z, world.z)
            max_v.x = max(max_v.x, world.x)
            max_v.y = max(max_v.y, world.y)
            max_v.z = max(max_v.z, world.z)
    size = max_v - min_v
    center = (min_v + max_v) * 0.5
    return {
        "min": [round(v, 4) for v in min_v],
        "max": [round(v, 4) for v in max_v],
        "size": [round(v, 4) for v in size],
        "center": [round(v, 4) for v in center],
    }


def write_json(path: str | os.PathLike[str], data: dict) -> None:
    ensure_dir(Path(path).parent)
    Path(path).write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
