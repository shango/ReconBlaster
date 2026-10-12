"""Camera discovery and single-frame playblast capture."""

import contextlib
import os

import maya.cmds as cmds

from . import burnin


# (filename suffix, burn-in label, modelEditor settings, shader type or None)
# for each pass that can be written per camera. Passes run in this order, and
# a shader stays on the character once assigned, so the material pass, which
# needs the character's own shaders, must come first.
PASSES = (
    # The character's own shaders and textures.
    (
        "material",
        "Material",
        {
            "wireframeOnShaded": False,
            "useDefaultMaterial": False,
            "displayTextures": True,
        },
        None,
    ),
    # Plain grey lambert, so the form reads without the character's own
    # shading.
    (
        "shaded",
        "Shaded",
        {
            "wireframeOnShaded": False,
            "useDefaultMaterial": False,
            "displayTextures": False,
        },
        "lambert",
    ),
    # A lambert with a checker texture, to show the character's UV layout.
    (
        "checker",
        "Checker",
        {
            "wireframeOnShaded": False,
            "useDefaultMaterial": False,
            "displayTextures": True,
        },
        "checker",
    ),
    # A useBackground shader on the character draws its surface as the plate
    # behind it, but it still hides back-facing wires.
    (
        "wire",
        "Wireframe",
        {
            "wireframeOnShaded": True,
            "useDefaultMaterial": False,
            "displayTextures": False,
        },
        "useBackground",
    ),
    # The image plane on its own: the character's surfaces are hidden, so it
    # runs last and the passes above never need them turned back on.
    (
        "plate",
        "Plate",
        {
            "wireframeOnShaded": False,
            "polymeshes": False,
            "nurbsSurfaces": False,
            "subdivSurfaces": False,
        },
        None,
    ),
)


def scene_cameras():
    """Return long transform paths of every non-startup camera, sorted by name."""
    cameras = []
    for shape in cmds.ls(type="camera", long=True) or []:
        if cmds.camera(shape, query=True, startupCamera=True):
            continue
        parents = cmds.listRelatives(shape, parent=True, fullPath=True)
        if parents:
            cameras.append(parents[0])
    return sorted(set(cameras), key=lambda path: short_name(path).lower())


def short_name(camera):
    """Leaf name of a long DAG path."""
    return camera.rsplit("|", 1)[-1]


def character_shapes(nodes):
    """Long paths of the mesh and NURBS surfaces at or under nodes."""
    shapes = cmds.ls(nodes, type=("mesh", "nurbsSurface"), long=True) or []
    shapes += (
        cmds.listRelatives(
            nodes, allDescendents=True, type=("mesh", "nurbsSurface"), fullPath=True
        )
        or []
    )
    return cmds.ls(shapes, noIntermediate=True, long=True) or []


def image_planes(camera):
    """Image plane shapes attached to the camera."""
    planes = []
    shapes = cmds.listRelatives(camera, shapes=True, type="camera", fullPath=True)
    for shape in shapes or []:
        planes += (
            cmds.listConnections(
                shape + ".imagePlane", source=True, destination=False, shapes=True
            )
            or []
        )
    return planes


def scene_lights():
    """Long transform paths of every light in the scene."""
    shapes = cmds.ls(lights=True, long=True) or []
    if not shapes:
        return []
    return sorted(set(cmds.listRelatives(shapes, parent=True, fullPath=True) or []))


# Lighting rig scene shipped inside the package, imported under its own
# namespace so it is easy to find, adjust and delete.
LIGHT_RIG_FILE = os.path.join(os.path.dirname(__file__), "lighting_rig.ma")
LIGHT_RIG_NAMESPACE = "rbLightRig"


def light_rig_nodes():
    """Top-level nodes of the lighting rig already in the scene, if any."""
    return cmds.ls(LIGHT_RIG_NAMESPACE + ":*", assemblies=True, long=True) or []


def import_light_rig():
    """Import LIGHT_RIG_FILE and return its top-level nodes."""
    cmds.file(
        LIGHT_RIG_FILE, i=True, namespace=LIGHT_RIG_NAMESPACE, ignoreVersion=True
    )
    return light_rig_nodes()


CAPTURE_WIDTH = 3840


def capture_resolution():
    """4K-wide capture size, keeping the render globals' aspect ratio.

    Width is pinned rather than read from the render globals so every shot
    comes out at 4K, but the height still follows Render Settings so the
    framing matches what the shot actually renders.
    """
    width = cmds.getAttr("defaultResolution.width")
    height = cmds.getAttr("defaultResolution.height")
    return (CAPTURE_WIDTH, int(round(CAPTURE_WIDTH * height / float(width))))


def rig_name(camera):
    """Namespace the camera lives in, or the scene name when it has none."""
    leaf = short_name(camera)
    if ":" in leaf:
        return leaf.rsplit(":", 1)[0]
    scene = cmds.file(query=True, sceneName=True, shortName=True)
    return os.path.splitext(scene)[0] if scene else "untitled"


def camera_label(camera):
    """Camera name with its namespace stripped - the rig name already carries it."""
    return short_name(camera).rsplit(":", 1)[-1]


def _file_stem(camera, prefix=""):
    """Camera name with namespace separators made filename-safe, behind any prefix."""
    stem = short_name(camera).replace(":", "_")
    return prefix + "_" + stem if prefix else stem


# Viewport 2.0 settings for every pass: anti-aliasing at its maximum and
# ambient occlusion on. lineAAEnable is the one that smooths wireframe lines;
# multisampling alone leaves them stair-stepped.
VIEWPORT_GLOBALS = {
    "lineAAEnable": True,
    "multiSampleEnable": True,
    "multiSampleCount": 16,
    "ssaoEnable": True,
    "ssaoSamples": 32,
}


@contextlib.contextmanager
def _viewport_globals():
    """Force VIEWPORT_GLOBALS on, restoring the scene's settings after."""
    previous = {}
    try:
        for attribute, value in VIEWPORT_GLOBALS.items():
            plug = "hardwareRenderingGlobals." + attribute
            previous[plug] = cmds.getAttr(plug)
            cmds.setAttr(plug, value)
        yield
    finally:
        for plug, value in previous.items():
            cmds.setAttr(plug, value)


@contextlib.contextmanager
def _undone_after(shapes, color):
    """Undo every scene edit made inside the block when it exits.

    Also gives the character's surfaces the one wireframe colour the user
    picked, unless color is None. The colour and _assign_shader both write
    to the scene, but they are undoable, so one undo restores exactly what
    each object had before - its shading assignments, including per-face ones,
    and any wireframe colour override it already carried.
    """
    undo_was_on = cmds.undoInfo(query=True, state=True)
    if not undo_was_on:
        cmds.undoInfo(state=True)
    cmds.undoInfo(openChunk=True)
    try:
        if color is not None:
            cmds.color(shapes, rgbColor=color)
        yield
    finally:
        cmds.undoInfo(closeChunk=True)
        cmds.undo()
        if not undo_was_on:
            cmds.undoInfo(state=False)


# A 4K window does not fit on a normal monitor, and playblast renders off
# screen at the size it is asked for regardless of how big the panel is. Only
# the aspect ratio has to match, so the framing on screen is the framing
# written to disk.
PANEL_MAX_WIDTH = 1280


def _panel_size(width, height):
    if width <= PANEL_MAX_WIDTH:
        return (width, height)
    return (PANEL_MAX_WIDTH, int(round(PANEL_MAX_WIDTH * height / float(width))))


@contextlib.contextmanager
def _capture_panel(width, height):
    """Temporary model panel in its own window, so the user's viewport is untouched."""
    window = cmds.window(
        title="ReconBlaster capture", widthHeight=_panel_size(width, height)
    )
    try:
        cmds.paneLayout()
        panel = cmds.modelPanel(menuBarVisible=False)
        # Hide everything, then re-enable only what belongs in the frame. This
        # drops locators, joints, curves, lights and the like in one flag.
        cmds.modelEditor(panel, edit=True, allObjects=False)
        cmds.modelEditor(
            panel,
            edit=True,
            # The anti-aliasing settings above are Viewport 2.0 only, so pin
            # the panel to it rather than inheriting whatever is current.
            rendererName="vp2Renderer",
            polymeshes=True,
            nurbsSurfaces=True,
            subdivSurfaces=True,
            imagePlane=True,
            displayAppearance="smoothShaded",
            smoothWireframe=True,
            # Light with the scene's lights when it has any; Maya's default
            # light is all there is otherwise, and it casts no shadows.
            displayLights="all" if scene_lights() else "default",
            shadows=True,
            grid=False,
            headsUpDisplay=False,
            manipulators=False,
            selectionHiliteDisplay=False,
        )
        cmds.showWindow(window)
        yield panel
    finally:
        cmds.deleteUI(window, window=True)


# Checker tiles per 0-1 UV square.
CHECKER_REPEAT = 8


def _assign_shader(shapes, shader_type):
    """Assign a new shader of shader_type to shapes. Call inside _undone_after.

    A shader_type of "checker" is a lambert with a checker texture in its
    colour.
    """
    if shader_type == "checker":
        shader = cmds.shadingNode("lambert", asShader=True)
        checker = cmds.shadingNode("checker", asTexture=True)
        place = cmds.shadingNode("place2dTexture", asUtility=True)
        cmds.connectAttr(place + ".outUV", checker + ".uvCoord")
        cmds.connectAttr(place + ".outUvFilterSize", checker + ".uvFilterSize")
        cmds.setAttr(place + ".repeatU", CHECKER_REPEAT)
        cmds.setAttr(place + ".repeatV", CHECKER_REPEAT)
        cmds.connectAttr(checker + ".outColor", shader + ".color")
    else:
        shader = cmds.shadingNode(shader_type, asShader=True)
    group = cmds.sets(renderable=True, noSurfaceShader=True, empty=True)
    cmds.connectAttr(shader + ".outColor", group + ".surfaceShader")
    cmds.sets(shapes, edit=True, forceElement=group)


def _turn_on_shadows():
    """Make every light in the scene cast shadows. Call inside _undone_after.

    Viewport 2.0 only draws shadows from lights with depth map shadows on.
    Ambient lights have no such setting, and locked or connected ones are
    left as they are.
    """
    for shape in cmds.ls(lights=True, long=True) or []:
        plug = shape + ".useDepthMapShadows"
        if cmds.objExists(plug) and cmds.getAttr(plug, settable=True):
            cmds.setAttr(plug, True)


def _isolate(panel, nodes):
    """Show only nodes (and what sits under them) in the panel."""
    cmds.select(nodes, replace=True)
    cmds.isolateSelect(panel, state=True)
    cmds.isolateSelect(panel, loadSelected=True)


def capture_batch(
    shots,
    character,
    output_dir,
    prefix="",
    wireframe_color=None,
    passes=None,
    on_progress=None,
):
    """Write the given passes for every camera, each at its own frame.

    shots is a list of (camera, frame) pairs. character is the list of nodes
    whose surfaces make up the character; only they and the camera's image
    planes are drawn.

    prefix, if given, is put in front of every filename, so a prefix of
    both_models and a camera called face_cam gives both_models_face_cam.

    wireframe_color is an (r, g, b) 0-1 tuple applied to the character for the
    duration of the batch, or None to leave its own wireframe colours alone.
    passes is a collection of PASSES suffixes to write, or None for all of
    them; they always run in PASSES order. Returns the list of image paths
    written. on_progress, if given, is called with each path as it is
    finished.
    """
    shapes = character_shapes(character)
    if not shapes:
        raise ValueError("No mesh or NURBS surfaces in the character geometry.")

    os.makedirs(output_dir, exist_ok=True)

    width, height = capture_resolution()
    written = []
    selection = cmds.ls(selection=True, long=True)
    lights = scene_lights()

    try:
        with _viewport_globals(), _undone_after(
            shapes, wireframe_color
        ), _capture_panel(width, height) as panel:
            _turn_on_shadows()
            for suffix, label, settings, shader_type in PASSES:
                if passes is not None and suffix not in passes:
                    continue
                if shader_type:
                    _assign_shader(shapes, shader_type)
                cmds.modelEditor(panel, edit=True, **settings)
                for camera, frame in shots:
                    cmds.modelEditor(panel, edit=True, camera=camera)
                    # Lights go in the isolated set too, so isolate select
                    # cannot switch them off.
                    _isolate(panel, character + image_planes(camera) + lights)
                    # playblast grabs the focused panel.
                    cmds.setFocus(panel)
                    path = os.path.join(
                        output_dir, "%s_%s.png" % (_file_stem(camera, prefix), suffix)
                    )
                    cmds.playblast(
                        format="image",
                        compression="png",
                        completeFilename=path,
                        frame=[frame],
                        widthHeight=(width, height),
                        percent=100,
                        quality=100,
                        forceOverwrite=True,
                        showOrnaments=False,
                        offScreen=True,
                        clearCache=True,
                        viewer=False,
                    )
                    burnin.burn(
                        path,
                        "%s  |  %s  |  %s"
                        % (rig_name(camera), camera_label(camera), label),
                    )
                    written.append(path)
                    if on_progress:
                        on_progress(path)
    finally:
        # _isolate works through the selection, so put the user's back.
        if selection:
            cmds.select(selection, replace=True)
        else:
            cmds.select(clear=True)

    return written
