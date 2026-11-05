import json
import math

import bpy

from devil_designer import garment
from devil_designer.core import Session


def seam_length(simulation, vertices):
    evaluated = simulation.evaluated_get(bpy.context.evaluated_depsgraph_get())
    coordinates = [evaluated.data.vertices[index].co for index in vertices]
    return sum((second - first).length for first, second in zip(coordinates, coordinates[1:]))


def drape(scene, shrink):
    garment.reset(bpy.context)
    garment.remove_objects(garment.generated(scene, 'panel'))
    session = Session()
    session.add([(0, 0), (.3, 0), (.3, .4), (0, .4)])
    session.add([(.5, 0), (.8, 0), (.8, .4), (.5, .4)])
    first, second = session.document.patterns
    first.placement_mode = second.placement_mode = 'LEGACY'
    session.sew(session.document.edge(first.id, 1), session.document.edge(second.id, 3))
    session.document.seams[0].shrink = shrink
    scene.dd_document = session.document.dumps()
    left, right = garment.build_panels(bpy.context)
    left.location = (-.15, 0, 2)
    right.location = (.15, 0, 2)
    left.rotation_euler = right.rotation_euler = (math.pi / 2, 0, 0)
    bpy.context.view_layer.update()
    simulation = garment.compile_garment(bpy.context)
    pairs = sorted(json.loads(simulation['dd_sewing_pairs']), key=lambda pair: simulation.data.vertices[pair[0]].co.z)
    for frame in range(scene.frame_start, scene.frame_start + 100):
        scene.frame_set(frame)
    return seam_length(simulation, [pair[0] for pair in pairs]), simulation


def run(check):
    scene = bpy.context.scene
    garment.reset(bpy.context)
    previous = scene.dd_avatar, scene.dd_pin_top, scene.dd_spacing
    bpy.ops.mesh.primitive_uv_sphere_add(radius=.02, location=(5, 5, 0))
    scene.dd_avatar = bpy.context.object
    scene.dd_pin_top = True
    scene.dd_spacing = .02
    plain, simulation = drape(scene, 0)
    check(plain > .36, 'unshrunk free seam keeps its sewn length')
    rests = {item.value for item in simulation.data.attributes['rest_length'].data}
    measured = {}
    for shrink in (10, 20, 30):
        measured[shrink], simulation = drape(scene, shrink)
        ratio = 1 - measured[shrink] / plain
        print('SHRINK', shrink, round(ratio, 3), flush=True)
        check(abs(ratio - shrink / 100) < .03, f'{shrink}% Shrink shortens a free seam by that amount')
    check(measured[10] > measured[20] > measured[30], 'stronger Shrink gathers more')
    check(len(rests) > 1, 'seam rest data is compiled into the simulation')
    garment.reset(bpy.context)
    garment.remove_objects(garment.generated(scene, 'panel'))
    scene.dd_avatar, scene.dd_pin_top, scene.dd_spacing = previous
