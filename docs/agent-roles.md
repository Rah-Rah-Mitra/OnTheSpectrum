# Asset Agent Roles

Use one owner per file area. Coordinate through the asset spec and metadata JSON rather than ad hoc notes.

## Roles

- Asset Director: owns the brief, asset spec, slug, target audience, success criteria, and acceptance checklist.
- Blender Modeler: owns procedural geometry, named collections, mesh layout, armature scaffold, and source `.blend`.
- Bake/Export Agent: owns export-safe effects, preview render, `.glb`, metadata JSON, and budget checks.
- Viewer Agent: owns React/Three integration, asset manifest, camera presets, controls, inspector, and responsive layout.
- QA Agent: owns build, browser smoke tests, console checks, desktop/mobile screenshots, and control verification.
- Documentation Steward: promotes only reusable lessons into skills and docs.

## Ownership Rule

Only one agent should edit a file at a time. Keep Blender scripts, viewer source, generated assets, and docs as separate work items unless the coordinator explicitly merges them.
