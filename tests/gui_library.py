import json
from pathlib import Path
import sys
import tempfile
import traceback
from types import SimpleNamespace
from unittest.mock import patch
import bpy

ROOT=Path(__file__).resolve().parents[1]
sys.dont_write_bytecode=True
sys.path.insert(0,str(ROOT))
bpy.context.preferences.view.show_splash=False


def run():
    passed=[]
    def check(condition,label):
        if not condition:raise AssertionError(label)
        passed.append(label)
    try:
        import devil_designer
        from devil_designer import editor,library,garment
        from devil_designer.core import Document,Session
        from devil_designer.linked_editing import clone_twin
        from tools.workspace import prepare_scratch
        devil_designer.register()
        scene=bpy.context.scene
        scene.dd_avatar=scene.objects['Cube']
        scene.dd_spacing=.04
        area=next(area for area in bpy.context.screen.areas if area.type=='VIEW_3D')
        region=next(region for region in area.regions if region.type=='WINDOW')
        with tempfile.TemporaryDirectory(dir=prepare_scratch(),prefix='library-ui-') as temporary,bpy.context.temp_override(area=area,region=region):
            scene.dd_library_dir=temporary
            bpy.ops.devil_designer.pattern_editor('INVOKE_DEFAULT')
            workspace=editor._active
            check(workspace.minimal_ui,'Library coverage uses the active minimal interface')
            def event(kind,point=None,text='',ctrl=False):
                point=point or workspace.pointer
                return SimpleNamespace(type=kind,value='PRESS',mouse_x=point[0]+region.x,mouse_y=point[1]+region.y,
                                       ctrl=ctrl,shift=False,alt=False,unicode=text)
            def click(point):
                workspace.handle_event(bpy.context,event('LEFTMOUSE',point))
            def control(key):
                return next(rect for rect,row in workspace.minimal_card()[2] if row[0]==key or row[0]=='MENU' and row[1]==key)
            def card_click(key):
                bounds=control(key)
                click((bounds.x+bounds.w/2,bounds.y+bounds.h/2))
            def button(key):
                workspace.canvas_layout=workspace.make_layout()
                bounds=workspace.canvas_layout.buttons[key][0]
                click((bounds.x+bounds.w/2,bounds.y+bounds.h/2))
            def text_field(key,text):
                card_click(key)
                check(bool(workspace.library_edit),key+' receives text focus')
                draw(key+' focused')
                workspace.handle_event(bpy.context,event('A',ctrl=True))
                workspace.handle_event(bpy.context,event('TEXTINPUT',text=text) if text else event('BACK_SPACE'))
                draw(key+' editing')
                workspace.handle_event(bpy.context,event('RET'))
            def draw(label):
                workspace.handle_event(bpy.context,event('TIMER'))
                workspace.canvas_layout=workspace.make_layout()
                workspace.error_message=''
                workspace.renderer.draw(workspace)
                check(not workspace.error_message,label+' draw: '+str(workspace.error_message))
                card=workspace.minimal_card()
                if card:
                    outer=card[0]
                    check(all(bounds.x>=outer.x and bounds.y>=outer.y and bounds.x+bounds.w<=outer.x+outer.w+1 and
                              bounds.y+bounds.h<=outer.y+outer.h for bounds,row in card[2]),label+' controls fit shared hit bounds')
            def shot(name):
                bpy.ops.wm.redraw_timer(type='DRAW_WIN_SWAP',iterations=1)
                bpy.ops.screen.screenshot(filepath=str(ROOT/'scratch'/('ui-pass-'+name+'.png')))
            scale=workspace.canvas_layout.scale
            tool=workspace.canvas_layout.buttons['SELECT'][0]
            rail=workspace.canvas_layout.rail
            from devil_designer.ui_system import MinimalMetrics,RADIUS_CONTROL,RADIUS_DOCK_ITEM,RADIUS_CARD,RADIUS_DOCK
            check(abs(rail.w/scale-56)<1,'Native dock envelope is 56 pixels')
            check(abs(tool.w/scale-40)<1 and abs(tool.h/scale-33)<1 and abs((tool.x-rail.x)/scale-8)<1,
                  'Native toolbar targets are 40 pixels centered with 8-pixel inner padding')
            garment_btn=workspace.canvas_layout.buttons.get('GARMENT')
            check(garment_btn and abs(garment_btn[0].w/scale-40)<1 and abs((garment_btn[0].x-rail.x)/scale-8)<1,
                  'Garment settings button resides in 40-pixel centered column')
            check(all(r==4.0 for r in (RADIUS_CONTROL,RADIUS_DOCK_ITEM,RADIUS_CARD,RADIUS_DOCK)),
                  'Legacy constant fallbacks remain 4px')
            metrics=MinimalMetrics.resolve()
            ui=bpy.context.preferences.themes[0].user_interface
            check(abs(metrics.toolbar_item-0.5*ui.wcol_toolbar_item.roundness*20.0)<1e-4,
                  'Toolbar corner radius matches role formula .5 * RNA roundness * 20')
            check(abs(metrics.regular-0.5*ui.wcol_regular.roundness*20.0)<1e-4,
                  'Regular corner radius matches role formula')
            check(abs(metrics.menu_back-0.5*ui.wcol_menu_back.roundness*20.0)<1e-4,
                  'Menu back corner radius matches role formula')
            check(abs(metrics.menu_item-0.5*ui.wcol_menu_item.roundness*20.0)<1e-4,
                  'Menu item corner radius matches role formula')
            check(abs(metrics.text-0.5*ui.wcol_text.roundness*20.0)<1e-4,
                  'Text corner radius matches role formula')
            check(abs(metrics.box-0.5*ui.wcol_box.roundness*20.0)<1e-4,
                  'Box corner radius matches role formula')
            check(abs(metrics.tooltip-0.5*ui.wcol_tooltip.roundness*20.0)<1e-4,
                  'Tooltip corner radius matches role formula')
            orig_roundness=ui.wcol_toolbar_item.roundness
            try:
                ui.wcol_toolbar_item.roundness=0.0
                check(abs(MinimalMetrics.resolve().toolbar_item)<1e-4,'Theme roundness zero produces square corners')
                ui.wcol_toolbar_item.roundness=0.8
                check(abs(MinimalMetrics.resolve().toolbar_item-8.0)<1e-4,'Theme roundness 0.8 produces 8px corner radius')
            finally:
                ui.wcol_toolbar_item.roundness=orig_roundness
            check(ui.wcol_toolbar_item.roundness==orig_roundness,'Theme preferences restored cleanly without mutation')
            fake_ctx=SimpleNamespace(preferences=SimpleNamespace(system=SimpleNamespace(ui_scale=0.0),view=bpy.context.preferences.view),screen=bpy.context.screen)
            with patch.object(editor,'bpy',SimpleNamespace(context=fake_ctx)):
                workspace.canvas_layout=workspace.make_layout()
                expected_scale=max(0.5,bpy.context.preferences.view.ui_scale)
                check(abs(workspace.canvas_layout.scale-expected_scale)<1e-4,
                      'system.ui_scale zero falls back to view.ui_scale')
            workspace.canvas_layout=workspace.make_layout()
            workspace.show_card('LIBRARY_TAGS')
            menu_card=workspace.minimal_card()
            check(menu_card and menu_card[0].w/scale>=180,'Menu card enforces native minimum 180px width')
            check(all(abs(bounds.h/scale-20)<=2 for bounds,row in menu_card[2] if row[0].startswith('LIBRARY_TAG_')),
                  'Menu items use native 20px row heights')
            workspace.show_card('GARMENT')
            garment_card=workspace.minimal_card()
            check(garment_card and garment_card[0].w/scale>=280,'Property card enforces native nominal 280px minimum width')
            from devil_designer.minimal import minimal_layout,text_unscaled_width
            workspace.show_card('INTERNAL_EDGE')
            internal_card=workspace.minimal_card()
            fold_bounds,fold_row=next((bounds,row) for bounds,row in internal_card[2] if row[0]=='MENU')
            fold_required=text_unscaled_width(fold_row[2],11)+text_unscaled_width(fold_row[3],10)+38
            check(fold_bounds.w/scale>=fold_required-1,'Default Fold or pleat label and its full displayed value fit the measured menu row')
            workspace.show_card('CANVAS_MENU')
            canvas_menu=workspace.minimal_card()
            check(all(bounds.h/scale>=48 for bounds,row in canvas_menu[2] if row[0]=='CHOICES'),
                  'Labeled choice rows reserve their complete label and chip height')
            check(canvas_menu[2][0][0].y+canvas_menu[2][0][0].h<=canvas_menu[0].y+canvas_menu[0].h-30*scale,
                  'Context menu divider stays above the first clickable item')
            workspace.card_kind=None
            icons_dir=ROOT/'devil_designer'/'assets'/'icons'
            geom_data=json.loads((icons_dir/'geometry.json').read_text(encoding='utf-8'))
            sources_data=json.loads((icons_dir/'sources.json').read_text(encoding='utf-8'))
            from devil_designer.icons import ICON_ALIASES
            required_icons=['SELECT','RECTANGLE','ELLIPSE','POLYGON','INTERNAL','KNIFE','RULER',
                           'SNAP_ON','SNAP_OFF','HIDE_OFF','HIDE_ON','LIBRARY','CLOSE','PLAY','PAUSE',
                           'SAVE','CHECK','SETTINGS','FIT','DISCLOSURE','UNDO','REDO']
            check(all(name in geom_data and bool(geom_data[name]) for name in required_icons),
                  'All required stock icons have spans in geometry.json')
            check(all(name in sources_data and sources_data[name].get('license')=='GPL-2.0-or-later' for name in required_icons),
                  'All required stock icons have valid GPL provenance in sources.json')
            check(ICON_ALIASES.get('LENGTHS')=='RULER','LENGTHS is genuine stock ruler alias')
            check(ICON_ALIASES.get('GRID')=='LIBRARY','GRID is genuine stock library alias')
            check(ICON_ALIASES.get('DRAW_RECTANGLE')=='RECTANGLE','DRAW_RECTANGLE is genuine stock rectangle alias')
            check(abs(workspace.canvas_layout.buttons['SIMULATE'][0].h/scale-28)<1,'Main actions use compact native-style button proportions')
            button('LIBRARY')
            draw('Empty library')
            check(not workspace.library_items,'Empty library is actionable without fixture garments')
            card_click('LIBRARY_TAGS');draw('Empty tag filter');card_click('LIBRARY_TAG_ALL')
            card_click('LIBRARY_SAVE');card_click('LIBRARY_WRITE')
            draw('Save without a design')
            check(not workspace.library_items and workspace.card_kind=='LIBRARY_SAVE','Saving no garment is blocked without leaving the named-save surface')
            workspace.card_kind=None
            workspace.session=Session(Document())
            workspace.session.add([(0,0),(.3,0),(.3,.4),(0,.4)])
            workspace.persist()
            button('LIBRARY')
            card_click('LIBRARY_SAVE')
            draw('Save As dialog')
            text_field('LIBRARY_NAME','Artist fitted tee')
            text_field('LIBRARY_TAG_EDIT','VRChat, fitted')
            draw('Named and tagged save')
            shot('save')
            card_click('LIBRARY_WRITE')
            check(workspace.card_kind=='LIBRARY' and len(workspace.library_items)==1,'Save appears immediately in the still-running library')
            saved=workspace.library_items[0]
            data=json.loads(saved.read_text(encoding='utf-8'))
            check(data['library']['thumbnail'] and data['library']['tags']==['VRChat','fitted'] and data['library']['body']==scene.dd_avatar.name,
                  'Save automatically captures thumbnail, tags and actual body without changing version 2 storage')
            check(data['version']==2 and data['document']==json.loads(workspace.session.document.dumps()),'Saved editable pattern data is unchanged by presentation metadata')
            draw('Single garment grid')
            before=workspace.session.document.dumps()
            for index in range(7):library.save(bpy.context,f'Garment {index}',[f'Tag {index}'])
            draw('Live externally populated grid')
            check(len(workspace.library_items)==8,'Open library sees new files without reload or restart')
            shot('library')
            first_page=[row[0] for rect,row in workspace.minimal_card()[2] if row[0].startswith('LOAD_')]
            card_click('PAGE_LIBRARY')
            check(first_page!=[row[0] for rect,row in workspace.minimal_card()[2] if row[0].startswith('LOAD_')],'Grid paginates without closing')
            draw('Second library page')
            text_field('LIBRARY_SEARCH','Artist')
            draw('Search results')
            check(len(workspace.library_matches())==1,'Search finds chosen garment name')
            text_field('LIBRARY_SEARCH','does-not-exist')
            draw('No search results')
            check(not workspace.library_matches(),'Unmatched search never falls back to unrelated garments')
            text_field('LIBRARY_SEARCH','')
            card_click('LIBRARY_TAGS')
            draw('Tag filter menu')
            card_click('PAGE_LIBRARY_TAGS')
            draw('Second tag page')
            key=next(row[0] for rect,row in workspace.minimal_card()[2] if row[0].startswith('LIBRARY_TAG_') and row[0]!='LIBRARY_TAG_ALL')
            card_click(key)
            draw('Filtered garment grid')
            check(workspace.library_filter and len(workspace.library_matches())==1,'Tag filter is applied and returns to grid')
            card_click('LIBRARY_TAGS');card_click('LIBRARY_TAG_ALL')
            text_field('LIBRARY_SEARCH','Artist')
            key=next(row[0] for rect,row in workspace.minimal_card()[2] if row[0].startswith('LOAD_'))
            card_click(key)
            draw('Selected garment preview')
            shot('preview')
            check(workspace.session.document.dumps()==before and not workspace.confirm_action,'Preview is non-destructive and never loads on tile click')
            card_click('LIBRARY_ACCEPT_LOAD')
            draw('Replace confirmation')
            check(workspace.confirm_action=='LIBRARY_LOAD' and workspace.session.document.dumps()==before,'Load waits for explicit replace confirmation')
            button('CANCEL_ACTION')
            check(workspace.session.document.dumps()==before and workspace.library_load_path is None,'Cancel preserves current source and clears pending library target')
            workspace.show_card('LIBRARY');card_click(key);card_click('LIBRARY_ACCEPT_LOAD')
            scene.dd_avatar.scale.z*=1.5
            bpy.context.view_layer.update()
            button('CONFIRM_ACTION')
            check(abs(workspace.session.document.patterns[0].points[1][0]-.45)<1e-5,'Confirmed library load preserves existing body-height scale refit')
            scene.dd_avatar.scale.z/=1.5
            bpy.context.view_layer.update()
            workspace.show_card('LIBRARY');card_click('LIBRARY_SAVE')
            text_field('LIBRARY_NAME','Artist fitted tee')
            card_click('LIBRARY_WRITE')
            draw('Overwrite confirmation')
            check(workspace.confirm_action=='LIBRARY_SAVE','Saving an existing name requires replace confirmation')
            button('CANCEL_ACTION')
            check(json.loads(saved.read_text(encoding='utf-8'))==data,'Cancelled overwrite leaves saved garment byte-equivalent')
            workspace.show_card('LIBRARY_SAVE')
            text_field('LIBRARY_TAG_EDIT','updated')
            card_click('LIBRARY_WRITE');button('CONFIRM_ACTION')
            draw('Immediate overwritten metadata')
            check(workspace.library_previews[saved]['tags']==['updated'],'Overwrite invalidates thumbnail and metadata cache immediately')
            text_field('LIBRARY_SEARCH','Artist')
            key=next(row[0] for rect,row in workspace.minimal_card()[2] if row[0].startswith('LOAD_'))
            card_click(key);card_click('LIBRARY_ACCEPT_LOAD')
            source_before=workspace.session.document.dumps()
            replacement=Session(Document())
            replacement.add([(0,0),(.2,0),(.2,.2),(0,.2)])
            replacement.add([(.3,0),(.5,0),(.5,.2),(.3,.2)])
            external=json.loads(saved.read_text(encoding='utf-8'))
            external['document']=json.loads(replacement.document.dumps())
            external['library']['thumbnail']=[pattern.outline() for pattern in replacement.document.patterns]
            saved.write_text(json.dumps(external),encoding='utf-8')
            button('CONFIRM_ACTION')
            draw('Saved file changed during replace confirmation')
            check(workspace.session.document.dumps()==source_before and not workspace.confirm_action,
                  'A file changed after preview cannot silently replace the open garment')
            workspace.show_card('LIBRARY')
            draw('Live external overwrite')
            check(workspace.library_previews[saved]['pieces']==2 and len(workspace.library_previews[saved]['loops'])==2,
                  'External overwrite refreshes both thumbnail geometry and piece count')
            workspace.show_card('LIBRARY_SAVE')
            text_field('LIBRARY_NAME','!!!')
            card_click('LIBRARY_WRITE')
            draw('Invalid save name')
            check(workspace.card_kind=='LIBRARY_SAVE' and not workspace.confirm_action,'Invalid save remains editable and creates no file')
            workspace.show_card('LIBRARY');text_field('LIBRARY_SEARCH','')
            legacy=Path(temporary)/'Legacy.garment.json'
            legacy_data=dict(data)
            legacy_data.pop('library');legacy_data['version']=1;legacy_data['name']='Legacy design'
            legacy.write_text(json.dumps(legacy_data),encoding='utf-8')
            draw('Live legacy garment')
            check(workspace.library_previews[legacy]['pieces']==1 and workspace.library_previews[legacy]['loops'],
                  'Version 1 files without presentation metadata get automatic fallback thumbnails')
            text_field('LIBRARY_SEARCH','Legacy')
            legacy_key=next(row[0] for rect,row in workspace.minimal_card()[2] if row[0].startswith('LOAD_'))
            card_click(legacy_key);card_click('LIBRARY_ACCEPT_LOAD');button('CONFIRM_ACTION')
            check(len(workspace.session.document.patterns)==1 and scene.dd_library_name=='Legacy design','Legacy library loads through minimal preview and real load action')
            workspace.show_card('LIBRARY');text_field('LIBRARY_SEARCH','Legacy');card_click(legacy_key)
            legacy.unlink()
            draw('Preview removed externally')
            check(not any(row[0]=='LIBRARY_ACCEPT_LOAD' for rect,row in workspace.minimal_card()[2]),'Deleted preview cannot load a different index')
            corrupt=Path(temporary)/'Broken.garment.json'
            corrupt.write_text('{broken',encoding='utf-8')
            workspace.show_card('LIBRARY');text_field('LIBRARY_SEARCH','Broken')
            draw('Invalid file tile')
            broken_key=next(row[0] for rect,row in workspace.minimal_card()[2] if row[0].startswith('LOAD_'))
            card_click(broken_key)
            draw('Invalid file preview')
            check(not any(row[0]=='LIBRARY_ACCEPT_LOAD' for rect,row in workspace.minimal_card()[2]),'Invalid file is visible but cannot replace a garment')
            blocker=Path(temporary)/'not-a-folder'
            blocker.write_text('fixture',encoding='utf-8')
            scene.dd_library_dir=str(blocker)
            workspace.show_card('LIBRARY')
            draw('Unavailable library folder')
            check(workspace.library_error and not workspace.library_items,'Unavailable folder shows an error rather than stale saved entries')
            scene.dd_library_dir=temporary
            workspace.show_card('LIBRARY')
            check(not workspace.library_error and workspace.library_items,'Library recovers immediately when its folder is available again')
            for width,height in ((620,440),(480,400)):
                workspace.full=False;workspace.window_rect=(12,12,width,height)
                workspace.library_query=''
                for kind in ('LIBRARY','LIBRARY_SAVE','LIBRARY_TAGS','LIBRARY_PREVIEW'):
                    workspace.show_card(kind)
                    draw(f'{width}x{height} {kind}')
            from devil_designer.canvas import Layout
            real_layout=workspace.canvas_layout
            try:
                for region_height in (400,320):
                    probe_layout=Layout(1500,region_height,1,True)
                    minimal_layout(probe_layout)
                    workspace.canvas_layout=probe_layout
                    workspace.library_query=''
                    workspace.show_card('LIBRARY')
                    outer,title,controls=workspace.minimal_card()
                    panel=probe_layout.panel
                    check(outer.y>=panel.y and outer.y+outer.h<=panel.y+panel.h,
                          f'Library fits actual {region_height}px editor region, not a resized-window proxy')
                    check(all(bounds.y>=outer.y and bounds.y+bounds.h<=outer.y+outer.h for bounds,row in controls),
                          f'All library actions and cards fit actual {region_height}px editor region')
                    workspace.error_message=''
                    workspace.renderer.draw(workspace)
                    check(not workspace.error_message,f'Actual {region_height}px library GPU draw has no error')
                    workspace.library_preview_path=saved
                    for kind in ('LIBRARY_PREVIEW','CANVAS_MENU'):
                        workspace.show_card(kind)
                        outer,title,controls=workspace.minimal_card()
                        check(outer.y>=panel.y and outer.y+outer.h<=panel.y+panel.h,
                              f'{kind} fits actual {region_height}px editor region')
                        check(all(bounds.y>=outer.y and bounds.y+bounds.h<=outer.y+outer.h for bounds,row in controls),
                              f'{kind} keeps every control inside its clickable card at {region_height}px')
                        workspace.error_message=''
                        workspace.renderer.draw(workspace)
                        check(not workspace.error_message,f'{kind} actual {region_height}px GPU draw has no error')
                        if kind=='CANVAS_MENU':
                            check(any(row[0]=='INSP_FIT' for bounds,row in controls),
                                  f'Compact canvas menu retains Fit design at {region_height}px')
                            check(all(bounds.h>=48 for bounds,row in controls if row[0]=='CHOICES'),
                                  f'Compact canvas menu retains readable choices at {region_height}px')
                    workspace.show_card('LIBRARY_PREVIEW')
                    load_bounds=control('LIBRARY_ACCEPT_LOAD')
                    workspace.minimal_event(bpy.context,event('LEFTMOUSE',(load_bounds.x+load_bounds.w/2,load_bounds.y+load_bounds.h/2)))
                    check(workspace.confirm_action=='LIBRARY_LOAD' and workspace.library_load_path==saved,
                          f'Compact preview Load garment is actionable at {region_height}px')
                    workspace.confirm_action=None
                    workspace.library_load_path=None
                    workspace.show_card('LIBRARY_PREVIEW')
                    back_bounds=control('MENU_LIBRARY')
                    workspace.minimal_event(bpy.context,event('LEFTMOUSE',(back_bounds.x+back_bounds.w/2,back_bounds.y+back_bounds.h/2)))
                    check(workspace.card_kind=='LIBRARY',f'Compact preview Back returns to library at {region_height}px')
            finally:
                workspace.canvas_layout=real_layout
            workspace.full=True;workspace.canvas_layout=workspace.make_layout();workspace.card_kind=None
            workspace.session=Session(Document.loads(before))
            workspace.session.selected=workspace.session.document.patterns[0].id
            clone_twin(workspace.session,False)
            workspace.persist();workspace.fit();scene.dd_lengths_visible=True
            workspace.session.selected=None;workspace.session.selected_patterns.clear()
            workspace.pointer=(-100,-100)
            draw('Idle linked pieces with edge lengths')
            check(workspace.twin_tethers and not workspace.twin_label_ids,'Idle twins use a thin tether without permanent Twin text')
            workspace.session.selected=workspace.session.document.patterns[0].id
            workspace.session.document.patterns[0].name='Very long fitted garment pattern name with many words to reserve space for Twin'
            draw('Selected linked pieces with edge lengths')
            check(bool(workspace.twin_label_ids),'Selected pair reveals Twin text')
            check(bool(workspace.measurement_rects) and bool(workspace.piece_label_rects),
                  'Measurement clear-zone coverage contains actual labels and actual edge dimensions')
            check(all(not (label.x<measure.x+measure.w+5 and label.x+label.w>measure.x-5 and
                           label.y<measure.y+measure.h+5 and label.y+label.h>measure.y-5)
                      for label in workspace.piece_label_rects for measure in workspace.measurement_rects),
                  'All piece labels and Twin markers preserve measurement clear zones')
            shot('labels')
            workspace.session.selected=None
            workspace.pointer=workspace.view.screen((.1,.1),workspace.canvas_layout.canvas)
            draw('Hovered linked pair')
            check(bool(workspace.twin_label_ids),'Hover reveals Twin text without changing selection')
            check(workspace.session.selected is None,'Presentation hover never mutates active editing selection')
            widget_roles=('toolbar_item','regular','menu_back','menu_item','text','box','tooltip')
            saved_roundness={role:getattr(ui,'wcol_'+role).roundness for role in widget_roles}
            painted_radii=[]
            original_round_rect=workspace.renderer.round_rect
            original_round_outline=workspace.renderer.round_rect_outline
            def record_round_rect(bounds,color,radius=8):
                painted_radii.append(radius)
                return original_round_rect(bounds,color,radius=radius)
            def record_round_outline(bounds,color,radius=8,width=1):
                painted_radii.append(radius)
                return original_round_outline(bounds,color,radius=radius,width=width)
            try:
                for role in widget_roles:
                    getattr(ui,'wcol_'+role).roundness=0.0
                workspace.renderer.round_rect=record_round_rect
                workspace.renderer.round_rect_outline=record_round_outline
                workspace.show_card('CANVAS_MENU')
                draw('Square-theme shell, callouts and contextual menu use actual GPU drawing')
                check(painted_radii and all(radius==0 for radius in painted_radii),
                      'Every painted minimal shell, callout, card and menu corner follows zero-roundness theme')
                workspace.card_kind=None
                workspace.choose_tool('SELECT')
                canvas=workspace.canvas_layout.canvas
                workspace.gesture=dict(mode='BOX_SELECT',start=(canvas.x+80,canvas.y+80))
                workspace.pointer=(canvas.x+240,canvas.y+240)
                painted_radii.clear()
                draw('Square-theme active selection gesture')
                check(painted_radii and all(radius==0 for radius in painted_radii),
                      'Active selection rectangle and canvas labels preserve native square corners')
                workspace.gesture=None
            finally:
                workspace.renderer.round_rect=original_round_rect
                workspace.renderer.round_rect_outline=original_round_outline
                workspace.card_kind=None
                workspace.gesture=None
                for role,value in saved_roundness.items():
                    getattr(ui,'wcol_'+role).roundness=value
                workspace.canvas_layout=workspace.make_layout()
            source_before_modes=workspace.session.document.dumps()
            for tool in ('SELECT','RECTANGLE','POLYGON','ELLIPSE','INTERNAL','DART','KNIFE','SEW','PIN','TACK'):
                workspace.choose_tool(tool)
                draw('No-mock real geometry '+tool+' mode')
            workspace.choose_tool('SEW')
            first,second=workspace.session.document.patterns
            workspace.pending_edge=workspace.session.document.edges(first.id)[0]
            hover_edge=workspace.session.document.edges(second.id)[0]
            workspace.pointer=workspace.view.screen(workspace.session.document.edge_point(hover_edge,.5),workspace.canvas_layout.canvas)
            draw('No-mock pending sewing selection and real hovered partner edge')
            check(workspace.pending_edge.pattern==first.id,'Pending sewing draw retains its real selected edge')
            workspace.pending_edge=None
            workspace.choose_tool('SELECT')
            canvas=workspace.canvas_layout.canvas
            workspace.gesture=dict(mode='BOX_SELECT',start=(canvas.x+80,canvas.y+80))
            workspace.pointer=(canvas.x+240,canvas.y+240)
            draw('No-mock active box selection on real linked pieces')
            workspace.gesture=None
            for stage in ('DRAFT','SEW','ARRANGE','SIMULATE'):
                workspace.stage=stage
                draw('No-mock '+stage+' stage')
            check(workspace.session.document.dumps()==source_before_modes,'Every editor mode and active-gesture draw preserves editable pattern data')
            check(garment.generated(scene,'panel'),'Real library loads produce real Blender panels, not mocked scene properties')
            workspace.cleanup()
        report=dict(passed=passed)
    except Exception:
        report=dict(passed=passed,error=traceback.format_exc())
        traceback.print_exc()
    (ROOT/'scratch'/'library-report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')


bpy.app.timers.register(run,first_interval=2)
