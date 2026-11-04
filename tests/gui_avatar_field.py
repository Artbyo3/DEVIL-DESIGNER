import json
import sys
import traceback
from pathlib import Path
from types import SimpleNamespace
import bpy
import gpu
from bpy_extras import view3d_utils

ROOT = Path(__file__).resolve().parents[1]
bpy.context.preferences.view.show_splash = False
sys.dont_write_bytecode = True
sys.path.insert(0, str(ROOT))
import devil_designer
from devil_designer import editor


def cube_at(context, region, view, point, name):
    origin = view3d_utils.region_2d_to_origin_3d(region, view, point)
    direction = view3d_utils.region_2d_to_vector_3d(region, view, point)
    mesh = bpy.data.meshes.new(name)
    size = .05
    mesh.from_pydata([(x * size, y * size, z * size) for x in (-1, 1) for y in (-1, 1) for z in (-1, 1)], [],
                     [(0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)])
    obj = bpy.data.objects.new(name, mesh)
    context.scene.collection.objects.link(obj)
    obj.location = origin + direction * 1.0
    context.view_layer.update()
    return obj


def run():
    passed = []
    report = ROOT / 'scratch' / 'avatar_field-report.json'

    def check(condition, label):
        if not condition:
            raise AssertionError(label)
        passed.append(label)

    try:
        devil_designer.register()
        bpy.ops.devil_designer.demo()
        scene = bpy.context.scene
        body = scene.dd_avatar
        area = next(area for area in bpy.context.screen.areas if area.type == 'VIEW_3D')
        region = next(region for region in area.regions if region.type == 'WINDOW')
        with bpy.context.temp_override(area=area, region=region):
            bpy.ops.devil_designer.pattern_editor('INVOKE_DEFAULT')
            workspace = editor._active
            workspace.reveal_3d()
            workspace.canvas_layout = workspace.make_layout()
            view = area.spaces.active.region_3d
            panel = workspace.canvas_layout.panel
            side = panel.x / 2
            target = cube_at(bpy.context, region, view, (side, region.height * .6), 'Pick target')
            blocked = cube_at(bpy.context, region, view, (side, region.height * .3), 'Generated panel')
            blocked['dd_kind'] = 'panel'
            target_point = view3d_utils.location_3d_to_region_2d(region, view, target.location)
            blocked_point = view3d_utils.location_3d_to_region_2d(region, view, blocked.location)
            empty_point = (side, region.height * .95)
            for index in range(14):
                cube_at(bpy.context, region, view, (side, 10), 'Mesh_%02d' % index).hide_viewport = True
            field = workspace.avatar_field
            workspace.show_card('BODY', (panel.x + 100, panel.y + panel.h - 60))

            def event(kind, point, value='PRESS', **keys):
                return SimpleNamespace(type=kind, value=value, mouse_x=point[0] + region.x, mouse_y=point[1] + region.y,
                                       ctrl=keys.get('ctrl', False), shift=keys.get('shift', False), alt=False,
                                       unicode=keys.get('unicode', ''))

            def send(kind, point, value='PRESS', **keys):
                workspace.handle_event(bpy.context, event(kind, point, value, **keys))

            def click(point, kind='LEFTMOUSE'):
                send(kind, point)
                send(kind, point, 'RELEASE')

            def key(kind, **keys):
                send(kind, name_point(), **keys)
                send(kind, name_point(), 'RELEASE', **keys)

            def box():
                return field.box(field.control())

            def name_point():
                rect = box()
                return (rect.x + 60, rect.y + rect.h / 2)

            def extra_point():
                rect = field.extra_rect(box())
                return (rect.x + rect.w / 2, rect.y + rect.h / 2)

            def draws(label, shot=None):
                workspace.error_message = ''
                workspace.canvas_layout = workspace.make_layout()
                workspace.renderer.draw(workspace)
                check(not workspace.error_message, label + ' draws without error')
                if shot:
                    bpy.ops.wm.redraw_timer(type='DRAW_WIN_SWAP', iterations=2)
                    bpy.ops.screen.screenshot(filepath=str(ROOT / 'scratch' / (shot + '.png')))

            rows = workspace.minimal_card()[2]
            check(rows[0][1][:2] == ('AVATAR_FIELD', 'Avatar'), 'the picker is one field labeled Avatar at the top of the Body card')
            check(not any(row[0].startswith(('BODY_', 'PAGE_BODY')) for rect, row in rows), 'the old row picker is gone')
            check(any(row[0] == 'CHOICES' and row[1] == 'Body opacity' for rect, row in rows), 'the rest of the Body card stays')
            draws('filled field', 'avatar-filled')

            send('MOUSEMOVE', name_point(), 'NOTHING')
            check(field.text_cursor, 'the field shows a text cursor on hover')
            check(not field.tooltip_ready(), 'the tooltip waits instead of appearing instantly')
            field.hover_start -= 1
            check(field.tooltip_ready(), 'the tooltip appears after a pause')
            draws('field tooltip')
            send('MOUSEMOVE', extra_point(), 'NOTHING')
            check(not field.text_cursor, 'the clear button keeps the normal cursor')
            send('LEFTMOUSE', name_point())
            check(field.mode == 'SEARCH', 'pressing the field opens the list without waiting for release')
            check(workspace.pointer[0] < 0, 'nothing behind the open list reacts to hover')
            send('LEFTMOUSE', name_point(), 'RELEASE')
            check(field.mode == 'SEARCH', 'releasing the first click keeps the list open')
            check(field.text == body.name and field.selection() == (0, len(body.name)), 'the current name opens selected, ready to be replaced')
            check(body in field.results and target in field.results and blocked not in field.results, 'the list is filtered by the avatar poll')
            check(field.results[field.active] == body, 'the current avatar is the active row')
            draws('open list', 'avatar-open')
            gpu.state.blend_set('NONE')
            workspace.renderer.smooth_icon('OUTLINER_OB_MESH', 100, 100, 16, (1, 1, 1, 1))
            check(gpu.state.blend_get() == 'ALPHA', 'icons keep soft edges after text turns blending off')

            key('ESC')
            check(field.mode is None and scene.dd_avatar == body and workspace.card_kind == 'BODY', 'Esc closes only the list and keeps the avatar')
            click(name_point())
            click((panel.x + panel.w - 10, panel.y + 10))
            check(field.mode is None and workspace.card_kind == 'BODY', 'clicking outside closes only the list')
            click(name_point())
            click(name_point(), 'RIGHTMOUSE')
            check(field.mode is None and workspace.card_kind == 'BODY', 'right click closes only the list')

            click(name_point())
            field.active = 0
            field.offset = 0
            for _ in range(11):
                key('DOWN_ARROW')
            check(field.active == 11 and field.offset == 2, 'arrow keys walk the list and scroll it')
            draws('scrolled list', 'avatar-scrolled')
            send('WHEELUPMOUSE', name_point())
            check(field.active == 10, 'the wheel moves through the list')
            key('ONE', unicode='1')
            check(field.text == '1' and [obj.name for obj in field.results[:4]] == ['Mesh_10', 'Mesh_11', 'Mesh_12', 'Mesh_13'],
                  'typing replaces the name and ranks word starts first')
            check(field.results[4].name == 'Mesh_00' or field.results[4].name == 'Mesh_01', 'inside matches follow word starts')
            draws('filtered list', 'avatar-filtered')
            key('Z', unicode='z')
            key('Z', unicode='z')
            check(not field.results, 'an unmatched search has no results')
            draws('no results', 'avatar-none')
            key('BACK_SPACE')
            key('BACK_SPACE')
            key('BACK_SPACE')
            check(field.text == '' and len(field.results) >= 15, 'clearing the search shows every candidate again')
            for letter, value in (('M', 'm'), ('E', 'e'), ('S', 's'), ('H', 'h')):
                key(letter, unicode=value)
            check(workspace.tool == 'RECTANGLE' or scene.dd_avatar == body, 'typing never reaches editor shortcuts')
            key('A', ctrl=True)
            check(field.selection() == (0, 4), 'Ctrl A selects the search text')
            key('LEFT_ARROW')
            key('RIGHT_ARROW', shift=True)
            check(field.selection() == (0, 1), 'Shift arrows extend the selection')
            key('ESC')

            click(name_point())
            rect = box()
            text_left = rect.x + 25 * workspace.canvas_layout.scale
            send('LEFTMOUSE', (text_left, rect.y + 5))
            send('MOUSEMOVE', (text_left + 30 * workspace.canvas_layout.scale, rect.y + 5), 'NOTHING')
            send('LEFTMOUSE', (text_left + 30 * workspace.canvas_layout.scale, rect.y + 5), 'RELEASE')
            check(field.selection()[0] == 0 and field.selection()[1] > 0, 'dragging selects text')
            send('LEFTMOUSE', (text_left + 4, rect.y + 5), 'DOUBLE_CLICK')
            check(field.selection() == (0, 2), 'double click selects the word')
            key('ESC')

            click(name_point())
            popup, rows_shown = field.popup(box())
            index = field.results.index(target)
            field.offset = max(0, index - rows_shown + 1)
            row = field.row_rect(popup, index - field.offset)
            point = (row.x + 30, row.y + row.h / 2)
            send('MOUSEMOVE', point, 'NOTHING')
            check(field.active == index, 'hovering a row makes it active')
            click(point)
            check(scene.dd_avatar == target and field.mode is None, 'clicking a row chooses it')
            check(workspace.card_kind == 'BODY', 'the card stays open after choosing, like a native field')

            click(extra_point())
            check(scene.dd_avatar is None, 'X clears the field')
            draws('empty field', 'avatar-empty')

            click(name_point())
            check(field.text == '' and field.active == -1, 'an empty field opens with no active row')
            draws('open empty field')
            key('RET')
            check(field.mode is None and scene.dd_avatar is None, 'Enter with nothing typed keeps the field empty')

            click(extra_point())
            check(field.mode == 'EYEDROPPER', 'the eyedropper button starts picking')
            send('MOUSEMOVE', blocked_point, 'NOTHING')
            check(field.sample is None, 'the eyedropper ignores objects the avatar poll rejects')
            send('MOUSEMOVE', target_point, 'NOTHING')
            check(field.sample == target, 'the eyedropper finds the mesh under the cursor')
            draws('eyedropper sampling', 'avatar-eyedropper')
            send('ESC', target_point)
            check(field.mode is None and scene.dd_avatar is None, 'Esc cancels the eyedropper')

            click(extra_point())
            click(empty_point)
            check(field.mode is None and scene.dd_avatar is None, 'sampling nothing ends the eyedropper with no change')

            click(extra_point())
            send('RIGHTMOUSE', target_point)
            check(field.mode is None and scene.dd_avatar is None, 'right click cancels the eyedropper')

            click(extra_point())
            click(target_point)
            check(scene.dd_avatar == target and field.mode is None, 'the eyedropper picks the mesh from the viewport')

            scene.dd_avatar = body
            workspace.canvas_layout = workspace.make_layout()
            send('E', name_point())
            check(field.mode == 'EYEDROPPER', 'E over a filled field starts the eyedropper')
            send('ESC', name_point())
            send('BACK_SPACE', name_point())
            check(scene.dd_avatar is None, 'Backspace over the field clears it')

            workspace.choose_body(body, bpy.context)
            check(scene.dd_avatar == body, 'the selection still flows through choose_body')
            workspace.cleanup()
        devil_designer.unregister()
        report.write_text(json.dumps(dict(passed=passed), indent=2))
    except Exception:
        report.write_text(json.dumps(dict(error=traceback.format_exc(), passed=passed), indent=2))


bpy.app.timers.register(run, first_interval=.5)
