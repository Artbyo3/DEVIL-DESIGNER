import json
import math
import unittest
from pathlib import Path
from devil_designer.core import Session,Document,arrangement_record

try:
    import bpy
except ModuleNotFoundError:
    bpy=None


@unittest.skipUnless(bpy is not None,'Requires Blender')
class LivePanelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import devil_designer
        cls.owns_registration=not hasattr(bpy.types.Scene,'dd_document')
        if cls.owns_registration:devil_designer.register()

    @classmethod
    def tearDownClass(cls):
        if cls.owns_registration:
            import devil_designer
            devil_designer.unregister()

    def setUp(self):
        self.scene=bpy.context.scene
        self.scene.dd_avatar=None;self.scene.dd_document=''
        for obj in list(self.scene.objects):bpy.data.objects.remove(obj,do_unlink=True)
        bpy.ops.mesh.primitive_cube_add(size=1,location=(0,0,1))
        self.body=bpy.context.object;self.body.scale=(.5,.3,2)
        bpy.ops.object.transform_apply(location=False,rotation=False,scale=True)
        self.scene.dd_spacing=.06;self.scene.dd_avatar=self.body
        self.session=Session();self.session.add([(-.15,1.1),(.15,1.1),(.15,1.4),(-.15,1.4)])
        self.scene.dd_document=self.session.document.dumps()

    def panels(self):
        from devil_designer import garment,live_panels
        live_panels.sync(bpy.context)
        bpy.context.view_layer.update()
        return garment.generated(self.scene,'panel')

    def test_closed_piece_edit_move_and_delete_update_live_panels(self):
        from devil_designer import garment,live_panels
        panel=self.panels()[0];identity=panel.as_pointer();first_mesh=panel.data.as_pointer()
        self.assertAlmostEqual(panel.location.y,-.18,places=5)
        self.assertAlmostEqual(panel.location.z,1.25,places=5)
        self.session.selected=self.session.document.patterns[0].id
        self.session.move([(-.2,1.1),(.2,1.1),(.2,1.4),(-.2,1.4)])
        self.scene.dd_document=self.session.document.dumps();panel=self.panels()[0]
        self.assertEqual(panel.as_pointer(),identity);self.assertNotEqual(panel.data.as_pointer(),first_mesh)
        self.session.move([(.8,1.1),(1.2,1.1),(1.2,1.4),(.8,1.4)])
        self.scene.dd_document=self.session.document.dumps();panel=self.panels()[0]
        self.assertAlmostEqual(panel.location.x,1,places=5)
        self.scene.dd_document=Document().dumps();live_panels.sync(bpy.context)
        self.assertFalse(garment.generated(self.scene,'panel'))

    def test_linked_back_clone_live_panels_library_refit_and_reopen(self):
        from mathutils import Vector
        from devil_designer import garment,live_panels,arrangement,library
        from devil_designer.linked_editing import clone_twin
        live_panels.arrange_piece(bpy.context,self.session.selected,'chest','front')
        session=Session(garment.document(self.scene));source=session.document.patterns[0].id;session.selected=source
        clone=clone_twin(session,True);self.scene.dd_document=session.document.dumps()
        panels={panel['dd_pattern_id']:panel for panel in self.panels()}
        self.assertEqual(len(panels),2);self.assertFalse(garment.document(self.scene).seams)
        for identity,point in ((source,'front'),(clone.id,'back')):
            resolved=arrangement.resolve_point(bpy.context,'chest',point)
            self.assertLess((panels[identity].matrix_world.translation-Vector(resolved['point'])).length,1e-5)
            self.assertGreater((panels[identity].matrix_world.to_3x3() @ Vector((0,0,1))).dot(Vector(resolved['normal'])),.999)
        session.selected=source;session.corner=1;session.move_selection(.01,.01)
        self.scene.dd_document=session.document.dumps();self.assertEqual(len(self.panels()),2)
        self.scene.dd_library_dir=str(Path(__file__).resolve().parents[1]/'scratch'/'linked-library')
        self.scene.dd_library_refit=True
        saved=library.save(bpy.context,'Linked back')
        expected=garment.document(self.scene).linked_pairs
        self.assertEqual(json.loads(saved.read_text(encoding='utf-8'))['document']['linked_pairs'],expected)
        self.body.scale.z=1.5;bpy.context.view_layer.update()
        loaded=library.load(bpy.context,self.scene.dd_library_selected)
        self.assertEqual(loaded.linked_pairs[0]['mapping'],expected[0]['mapping'])
        self.assertAlmostEqual(loaded.linked_pairs[0]['transform'][0],expected[0]['transform'][0]*1.5)
        edited=Session(loaded);edited.selected=source;edited.corner=1;edited.move_selection(.01,.01)
        first,second=edited.document.patterns
        self.assertAlmostEqual(first.vertices[1].x+second.vertices[1].x,edited.document.linked_pairs[0]['transform'][0])
        self.scene.dd_document=edited.document.dumps();self.panels()
        expected=self.scene.dd_document
        output=Path(__file__).resolve().parents[1]/'scratch'/'linked-roundtrip.blend'
        bpy.ops.wm.save_as_mainfile(filepath=str(output));bpy.ops.wm.open_mainfile(filepath=str(output))
        self.scene=bpy.context.scene
        self.assertEqual(self.scene.dd_document,expected)
        self.assertEqual(len(self.panels()),2);self.assertFalse(garment.document(self.scene).seams)
        garment.compile_garment(bpy.context)
        self.assertEqual(len(garment.document(self.scene).patterns),2);self.assertFalse(garment.document(self.scene).seams)

    def test_arranged_front_back_are_outward_and_keep_outline_and_uv(self):
        from mathutils import Vector
        from devil_designer import garment,live_panels,arrangement
        original=self.session.document.patterns[0].points
        initial=self.panels()[0]
        original_uv=[tuple(uv.uv) for uv in initial.data.uv_layers.active.data]
        for point in ('front','back'):
            live_panels.arrange_piece(bpy.context,self.session.selected,'chest',point)
            panel=garment.generated(self.scene,'panel')[0]
            bpy.context.view_layer.update()
            target=arrangement.resolve_point(bpy.context,'chest',point)
            self.assertLess((panel.matrix_world.translation-Vector(target['point'])).length,1e-5)
            self.assertGreater((panel.matrix_world.to_3x3() @ Vector((0,0,1))).dot(Vector(target['normal'])),.9999)
            self.assertGreater(panel.matrix_world.to_3x3().determinant(),.999)
            self.assertEqual(garment.document(self.scene).patterns[0].points,original)
            self.assertEqual([tuple(uv.uv) for uv in panel.data.uv_layers.active.data],original_uv)
            for vertex in panel.data.vertices:
                world=panel.matrix_world @ vertex.co
                self.assertGreater(max(abs(world.x)/.25,abs(world.y)/.15),1)

    def test_native_gr_deltas_survive_save_and_point_rearrangement(self):
        from devil_designer import garment,live_panels,arrangement
        live_panels.arrange_piece(bpy.context,self.session.selected,'chest','front',True)
        panel=self.panels()[0];panel.location.x+=.04;panel.rotation_euler.rotate_axis('Y',.15)
        bpy.context.view_layer.update();document=live_panels.capture(bpy.context)
        self.assertGreater(sum(abs(value) for value in document.patterns[0].arrangement['translation']),.03)
        self.assertGreater(sum(abs(value) for value in document.patterns[0].arrangement['rotation']),.1)
        serialized=self.scene.dd_document
        output=Path(__file__).resolve().parents[1]/'scratch'/'live-arrangement.blend'
        output.parent.mkdir(exist_ok=True)
        bpy.ops.wm.save_as_mainfile(filepath=str(output))
        bpy.ops.wm.open_mainfile(filepath=str(output));self.scene=bpy.context.scene
        self.assertEqual(self.scene.dd_document,serialized)
        self.assertEqual(garment.document(self.scene).patterns[0].arrangement,Document.loads(serialized).patterns[0].arrangement)
        identity=garment.document(self.scene).patterns[0].id
        live_panels.arrange_piece(bpy.context,identity,'chest','back',True)
        self.assertEqual(garment.document(self.scene).patterns[0].arrangement['translation'],[0.0]*3)
        self.assertTrue(arrangement.ensure_volumes(bpy.context)['volumes'])

    def test_unarranged_simulates_current_layout_and_reset_keeps_arrangements(self):
        from devil_designer import garment,live_panels
        panel=self.panels()[0];expected=[tuple(panel.matrix_world @ vertex.co) for vertex in panel.data.vertices]
        simulation=garment.compile_garment(bpy.context)
        self.assertEqual([tuple(vertex.co) for vertex in simulation.data.vertices],expected)
        self.assertTrue(next(modifier for modifier in simulation.modifiers if modifier.type=='CLOTH').settings.use_sewing_springs)
        garment.reset(bpy.context)
        live_panels.arrange_piece(bpy.context,self.session.selected,'chest','front')
        arranged=garment.document(self.scene).patterns[0].arrangement
        garment.compile_garment(bpy.context);garment.reset(bpy.context)
        self.assertEqual(garment.document(self.scene).patterns[0].arrangement,arranged)
        session=Session(garment.document(self.scene));live_panels.reset_piece(session,session.document.patterns[0].id)
        self.scene.dd_document=session.document.dumps();panel=self.panels()[0]
        self.assertIsNone(garment.document(self.scene).patterns[0].arrangement)
        self.assertAlmostEqual(panel.location.y,-.18,places=5)

    def test_library_retargets_records_to_second_avatar_and_reports_missing_point(self):
        from mathutils import Vector
        from devil_designer import garment,live_panels,library,arrangement
        self.scene.dd_library_dir=str(Path(__file__).resolve().parents[1]/'scratch'/'point-library')
        self.scene.dd_library_refit=True
        live_panels.arrange_piece(bpy.context,self.session.selected,'chest','back')
        original_panel=garment.generated(self.scene,'panel')[0]
        original_panel.location.x+=.02;bpy.context.view_layer.update()
        path=library.save(bpy.context,'Point refit')
        data=json.loads(path.read_text(encoding='utf-8'))
        saved_record=data['document']['patterns'][0]['arrangement']
        self.assertFalse(data['panels']);self.assertNotIn('dd_arrangement_volumes',path.read_text(encoding='utf-8'))
        bpy.ops.mesh.primitive_cube_add(size=1,location=(3,0,1.5))
        body=bpy.context.object;body.scale=(.8,.6,3)
        bpy.ops.object.transform_apply(location=False,rotation=False,scale=True)
        self.scene.dd_avatar=body;library.load(bpy.context,self.scene.dd_library_selected)
        bpy.context.view_layer.update();target=arrangement.resolve_point(bpy.context,'chest','back')
        panel=garment.generated(self.scene,'panel')[0]
        frame,_=live_panels.point_frame(bpy.context,saved_record)
        expected=Vector(target['point'])+frame.to_3x3() @ Vector(saved_record['translation'])
        self.assertLess((panel.matrix_world.translation-expected).length,1e-5)
        self.assertEqual(garment.document(self.scene).patterns[0].arrangement,saved_record)
        arrangement.edit_point(bpy.context,'chest','back',action='DELETE')
        library.load(bpy.context,self.scene.dd_library_selected)
        self.assertIn('2D layout',self.scene['dd_arrangement_message'])

    def test_older_design_keeps_exact_legacy_panel_start(self):
        from devil_designer import garment
        payload=json.loads(self.session.document.dumps());payload['version']=3
        self.scene.dd_reference_placed=True;self.scene.dd_reference_x=.2;self.scene.dd_reference_y=.4
        self.scene.dd_document=json.dumps(payload)
        panel=garment.build_panels(bpy.context)[0]
        self.assertAlmostEqual(panel.location.x,-.2,places=5)
        self.assertAlmostEqual(panel.location.z,.85,places=5)
        self.assertAlmostEqual(panel.location.y,-.18,places=5)
        simulation=garment.compile_garment(bpy.context)
        cloth=next(modifier for modifier in simulation.modifiers if modifier.type=='CLOTH')
        self.assertEqual(cloth.settings.sewing_force_max,50)
        self.assertAlmostEqual(cloth.collision_settings.distance_min,.003,places=6)
        self.assertEqual(cloth.collision_settings.collision_quality,4)

    def test_spiral_wrap_is_finite_and_outside_volume(self):
        from devil_designer import garment,arrangement
        self.session=Session();self.session.add([(-2,1),(2,1),(2,1.1),(-2,1.1)])
        self.session.document.patterns[0].arrangement=arrangement_record('chest','front')
        self.scene.dd_document=self.session.document.dumps();panel=self.panels()[0]
        target=arrangement.resolve_point(bpy.context,'chest','front')
        self.assertTrue(all(math.isfinite(value) for vertex in panel.data.vertices for value in vertex.co))
        self.assertGreater(max(math.hypot(vertex.co.x,vertex.co.z+target['radius']) for vertex in panel.data.vertices),target['radius'])
        self.assertIsNotNone(garment.document(self.scene).uv_layout)

    def test_intersecting_unarranged_panel_warns_but_simulates(self):
        from devil_designer import garment,live_panels
        panel=self.panels()[0];panel.location.y=0;bpy.context.view_layer.update()
        warnings=live_panels.intersection_warnings(bpy.context)
        self.assertEqual(len(warnings),1)
        self.assertIn(self.session.document.patterns[0].name,warnings[0])
        self.assertIn('intersects',warnings[0])
        self.assertIsNotNone(garment.compile_garment(bpy.context))

    def test_avatar_transform_repositions_arranged_panel_without_changing_deltas(self):
        from mathutils import Vector
        from devil_designer import garment,live_panels,arrangement
        live_panels.arrange_piece(bpy.context,self.session.selected,'chest','front',True)
        panel=self.panels()[0];panel.location.x+=.04;bpy.context.view_layer.update()
        record=live_panels.capture(bpy.context).patterns[0].arrangement
        self.body.location.x+=2;self.body.scale=(1.2,.8,1.1);bpy.context.view_layer.update()
        resolved=arrangement.resolve_point(bpy.context,'chest','front')
        frame,_=live_panels.point_frame(bpy.context,record)
        expected=Vector(resolved['point'])+frame.to_3x3() @ Vector(record['translation'])
        self.assertLess((panel.matrix_world.translation-expected).length,1e-5)
        self.assertEqual(garment.document(self.scene).patterns[0].arrangement,record)

    def test_cut_retains_both_arranged_and_legacy_panel_geometry(self):
        from devil_designer import garment,live_panels
        for mode in ('FLAT','WRAPPED','LEGACY'):
            with self.subTest(mode=mode):
                session=Session();session.add([(-.15,1.1),(.15,1.1),(.15,1.4),(-.15,1.4)])
                if mode=='LEGACY':session.document.patterns[0].placement_mode='LEGACY'
                self.scene.dd_document=session.document.dumps();source=garment.build_panels(bpy.context)[0]
                if mode!='LEGACY':live_panels.arrange_piece(bpy.context,session.selected,'chest','front',mode=='FLAT')
                else:source.location=(1,-1,2);source.rotation_euler=(1.4,.2,.3)
                bpy.context.view_layer.update()
                original={tuple(round(value,6) for value in rest.vector[:2]):source.matrix_world @ vertex.co
                          for vertex,rest in zip(source.data.vertices,source.data.attributes['dd_rest'].data)}
                session=Session(garment.document(self.scene));session.selected=session.document.patterns[0].id
                session.knife_cut([(-.3,1.25),(.3,1.25)])
                self.scene.dd_document=session.document.dumps();panels=garment.build_panels(bpy.context)
                bpy.context.view_layer.update();self.assertEqual(len(panels),2)
                for panel in panels:
                    matched=0
                    for vertex,rest in zip(panel.data.vertices,panel.data.attributes['dd_rest'].data):
                        key=tuple(round(value,6) for value in rest.vector[:2])
                        if key in original:
                            matched+=1;self.assertLess(((panel.matrix_world @ vertex.co)-original[key]).length,1e-5)
                    self.assertGreaterEqual(matched,2)
