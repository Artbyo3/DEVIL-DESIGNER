import json
from pathlib import Path
import sys
import time
import traceback

import bpy
from bpy_extras import view3d_utils
from mathutils import Vector


ROOT = Path(__file__).resolve().parents[1]
sys.dont_write_bytecode = True
sys.path.insert(0, str(ROOT))
from tools.workspace import prepare_scratch


bpy.context.preferences.view.show_splash = False


class MouseProof:
    def __init__(self):
        self.stage = 0
        self.started = time.monotonic()
        self.passed = []
        self.workspace = None
        self.point = None
        self.before_keep = None
        self.directory = prepare_scratch()
        self.report = self.directory / 'cloth_shaping-report.json'

    def check(self, condition, label):
        if not condition:
            raise AssertionError(label)
        self.passed.append(label)

    def event(self, kind, point=None, value='PRESS'):
        point = point or self.point
        region = self.workspace._region
        self.window.event_simulate(type=kind, value=value,
                                  x=round(point[0] + region.x), y=round(point[1] + region.y))

    def click(self, point):
        self.event('MOUSEMOVE', point, 'NOTHING')
        self.event('LEFTMOUSE', point)
        self.event('LEFTMOUSE', point, 'RELEASE')

    def button(self, key):
        layout = self.workspace.make_layout()
        rect = layout.buttons[key][0]
        self.click((rect.x + rect.w / 2, rect.y + rect.h / 2))

    def strip_button(self, key):
        rects = getattr(self.workspace, 'shaping_strip_rects', {})
        if not rects and hasattr(self.workspace, 'shaping_controls_layout'):
            rects = self.workspace.shaping_strip_rects = self.workspace.shaping_controls_layout()
        rect = rects[key]
        self.click((rect.x + rect.w / 2, rect.y + rect.h / 2))

    def card_action(self, key):
        card = self.workspace.visible_cards()[0]
        rect = next(rect for rect, row in card[2] if row[0] == key)
        self.click((rect.x + rect.w / 2, rect.y + rect.h / 2))

    def tick(self):
        try:
            from devil_designer import editor, garment, cloth_shaping
            if time.monotonic() - self.started > 180:
                raise TimeoutError(f'native mouse proof timed out at stage {self.stage}')
            if self.workspace:
                self.check(self.workspace.error_message is None, 'minimal editor draw has no render error')
            scene = bpy.context.scene
            if self.stage == 0:
                import devil_designer
                bpy.context.preferences.view.show_splash = False
                devil_designer.register()
                bpy.ops.devil_designer.demo()
                scene.dd_spacing = .02
                scene.dd_quality = 12
                scene.dd_frames = 120
                scene.dd_thickness = 0
                self.source = garment.compile_garment(bpy.context)
                for frame in range(1, 122):
                    scene.frame_set(frame)
                    cloth_shaping.points(self.source)
                self.window = bpy.context.window
                self.area = next(area for area in bpy.context.screen.areas if area.type == 'VIEW_3D')
                self.region = next(region for region in self.area.regions if region.type == 'WINDOW')
                with bpy.context.temp_override(area=self.area, region=self.region):
                    bpy.ops.devil_designer.pattern_editor('INVOKE_DEFAULT')
                    self.workspace = editor._active
                    bpy.ops.devil_designer.shape_cloth()
                    bpy.ops.view3d.view_axis(type='FRONT')
                self.check(self.workspace.tool == 'SHAPE', 'registered operator activates minimal shaping canvas')
                draped = cloth_shaping.points(self.source)
                desired = Vector((0, -.11, min(point.z for point in draped) +
                                  (max(point.z for point in draped) - min(point.z for point in draped)) * .12))
                self.center = min(range(len(draped)), key=lambda index: (draped[index] - desired).length_squared)
                view = self.area.spaces.active.region_3d
                view.view_location = Vector((0, 0, 1.25))
                view.view_distance = 1.1
                view.view_perspective = 'ORTHO'
                self.stage = 1
            elif self.stage == 1:
                view = self.area.spaces.active.region_3d
                position = self.source.matrix_world @ cloth_shaping.points(self.source)[self.center]
                self.point = tuple(view3d_utils.location_3d_to_region_2d(self.region, view, position))
                self.check(self.workspace.shape_cursor == 'HAND', 'idle cursor uses native open hand')
                self.event('MOUSEMOVE', self.point, 'NOTHING')
                self.event('LEFTMOUSE')
                self.stage = 2
            elif self.stage == 2:
                self.check(self.workspace.shaping.phase == cloth_shaping.Phase.HELD,
                           f'native press holds cloth, message {self.workspace.message}')
                self.check(self.workspace.shape_cursor == 'HAND_CLOSED', 'held cursor uses native closed gripping hand')
                self.check(bpy.context.screen.is_animation_playing, 'cloth playback is active during genuine mouse stroke')
                self.event('MOUSEMOVE', (self.point[0], self.point[1] + 60), 'NOTHING')
                self.stage = 3
            elif self.stage == 3:
                self.check(self.workspace.shaping.strength > 0, 'genuine mouse motion updates signed native target')
                self.check(not self.workspace.shaping.cloth().point_cache.is_outdated, 'native mouse motion does not invalidate cache')
                if scene.frame_current < 31:
                    return .05
                self.event('LEFTMOUSE', (self.point[0], self.point[1] + 60), 'RELEASE')
                self.stage = 4
            elif self.stage == 4:
                self.check(self.workspace.shaping.phase == cloth_shaping.Phase.RELEASED, 'genuine release returns cloth to free simulation')
                self.check(self.workspace.shape_cursor == 'HAND', 'release restores native open hand')
                self.check(self.source.vertex_groups.get('DD Shape Hold') is None, 'release removes transient native pin group')
                self.check(self.source.data.shape_keys.animation_data is None, 'release removes target driver')
                garment.stop(bpy.context)
                for frame in range(scene.frame_current + 1, scene.frame_current + 121):
                    scene.frame_set(frame)
                    cloth_shaping.points(self.source)
                self.check(self.workspace.shaping.phase == cloth_shaping.Phase.RELEASED, 'released GUI stroke survives 120 free frames')
                bpy.ops.screen.screenshot(filepath=str(self.directory / 'shape-released.png'))
                self.strip_button('RESET')
                self.stage = 6
            elif self.stage == 6:
                plain = [item.co.copy() for item in self.source.data.shape_keys.key_blocks['DD Shape Plain'].data]
                restored = cloth_shaping.points(self.source)
                self.check(max((point - expected).length for point, expected in zip(restored, plain)) < 1e-7,
                           'minimal UI registered reset restores plain drape')
                for frame in range(2, 12):
                    scene.frame_set(frame)
                    cloth_shaping.points(self.source)
                self.button('SHAPE')
                self.strip_button('MODE_TOGGLE')
                self.stage = 8
            elif self.stage == 8:
                self.event('MOUSEMOVE', self.point, 'NOTHING')
                self.event('LEFTMOUSE')
                self.stage = 9
            elif self.stage == 9:
                self.check(self.workspace.shaping.phase == cloth_shaping.Phase.HELD, 'second native stroke is held')
                self.event('MOUSEMOVE', (self.point[0], self.point[1] - 30), 'NOTHING')
                self.stage = 10
            elif self.stage == 10:
                self.check(self.workspace.shaping.strength < 0, 'native downward motion requests push')
                self.event('ESC')
                self.stage = 11
            elif self.stage == 11:
                self.check(self.workspace.shaping.phase == cloth_shaping.Phase.IDLE, 'escape cancels held stroke')
                self.check(self.workspace.shape_cursor == 'HAND', 'cancel restores native open hand')
                self.check(self.source.vertex_groups.get('DD Shape Hold') is None, 'cancel scrubs transient pins')
                self.toggles = (self.workspace.snap, scene.dd_reference_visible, scene.dd_lengths_visible)
                for key in ('S', 'H', 'L', 'P'):
                    self.event(key)
                self.stage = 'shortcuts'
            elif self.stage == 'shortcuts':
                current = (self.workspace.snap, scene.dd_reference_visible, scene.dd_lengths_visible)
                self.check(all(before != after for before, after in zip(self.toggles, current)), 'native S H L shortcuts remain functional while shaping')
                self.check(self.workspace.tool == 'POLYGON' and self.workspace.shape_cursor is None, 'native P shortcut exits shaping and restores cursor')
                bpy.ops.devil_designer.shape_cloth()
                for frame in range(2, 12):
                    scene.frame_set(frame)
                    cloth_shaping.points(self.source)
                self.event('LEFTMOUSE')
                self.stage = 'interrupt_press'
            elif self.stage == 'interrupt_press':
                self.check(self.workspace.shaping.phase == cloth_shaping.Phase.HELD, 'context interruption starts from genuine held stroke')
                self.closed_state = vars(self.workspace)
                self.check(self.closed_state['shape_cursor'] == 'HAND_CLOSED', 'interrupted editor exposes the actual held cursor state')
                self.original_scene = scene
                self.other_scene = bpy.data.scenes.new('Shaping context interruption')
                self.other_scene.frame_set(17)
                self.window.scene = self.other_scene
                self.event('MOUSEMOVE', self.point, 'NOTHING')
                self.workspace = None
                self.stage = 'interrupt_cleanup'
            elif self.stage == 'interrupt_cleanup':
                self.check(self.closed_state['_closed'] and editor._active is None, 'scene switch closes the original minimal editor')
                self.check(self.closed_state['shape_cursor'] is None, 'scene switch restores native cursor')
                self.check(self.source.vertex_groups.get('DD Shape Hold') is None and not self.source.get('dd_shape_held'), 'scene switch removes transient pins and held flag')
                self.check(self.source.data.shape_keys.animation_data is None, 'scene switch removes live target driver')
                self.check(self.other_scene.frame_current == 17, 'scene switch cleanup does not reset the destination scene')
                self.check(self.original_scene.frame_current == self.original_scene.frame_start, 'scene switch restores the source stroke baseline')
                self.window.scene = self.original_scene
                scene = self.original_scene
                bpy.data.scenes.remove(self.other_scene)
                with bpy.context.temp_override(area=self.area, region=self.region):
                    bpy.ops.devil_designer.pattern_editor('INVOKE_DEFAULT')
                    self.workspace = editor._active
                    bpy.ops.devil_designer.shape_cloth()
                    self.strip_button('MODE_TOGGLE')
                for frame in range(2, 12):
                    scene.frame_set(frame)
                    cloth_shaping.points(self.source)
                self.event('LEFTMOUSE')
                self.stage = 12
            elif self.stage == 12:
                self.check(self.workspace.shaping.phase == cloth_shaping.Phase.HELD, 'third native stroke is held')
                self.event('MOUSEMOVE', (self.point[0], self.point[1] - 30), 'NOTHING')
                self.stage = 13
            elif self.stage == 13:
                self.check(self.workspace.shaping.strength < 0, 'repeated native push is signed before release')
                if scene.frame_current < 31:
                    return .05
                self.event('LEFTMOUSE', value='RELEASE')
                self.stage = 14
            elif self.stage == 14:
                if getattr(self.workspace, 'pending_release', False):
                    return .05
                garment.stop(bpy.context)
                for frame in range(scene.frame_current + 1, scene.frame_current + 121):
                    scene.frame_set(frame)
                    cloth_shaping.points(self.source)
                self.before_keep = cloth_shaping.points(self.source)
                self.check(self.workspace.shaping.phase == cloth_shaping.Phase.RELEASED, 'repeated released stroke remains safe')
                self.button('KEEP')
                self.stage = 15
            elif self.stage == 15:
                finals = garment.generated(scene, 'final')
                self.check(bool(finals), f'minimal UI registered Keep bakes shaping, message {self.workspace.message}')
                final = finals[-1]
                self.check('Pattern UV' in final.data.uv_layers, 'Keep preserves garment UV data')
                self.check(len(final.data.materials) == len(self.source.data.materials), 'Keep preserves materials')
                self.check(final.vertex_groups.get('DD Shape Hold') is None, 'Keep contains no transient brush group')
                self.check(min((vertex.co - self.before_keep[self.center]).length for vertex in final.data.vertices) < 1e-6,
                           'Keep extracts the evaluated shaped mesh')
                self.workspace.cleanup()
                self.check(self.workspace.shape_cursor is None, 'workspace cleanup restores cursor')
                self.report.write_text(json.dumps(dict(passed=self.passed), indent=2), encoding='utf-8')
                return None
            return .1
        except Exception:
            self.report.write_text(json.dumps(dict(error=traceback.format_exc(), stage=self.stage,
                                                  passed=self.passed), indent=2), encoding='utf-8')
            return None


proof = MouseProof()
bpy.app.timers.register(proof.tick, first_interval=.5)
