import ast
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock,patch
from devil_designer import layering


class LayeringTests(unittest.TestCase):
    def kept(self,name,enabled=True,existing=False):
        modifiers=[]
        if existing:
            modifiers.append(SimpleNamespace(type='COLLISION',name='Artist collider'))
        collection=MagicMock()
        collection.__iter__.side_effect=lambda:iter(modifiers)
        def add(name,kind):
            modifier=SimpleNamespace(type=kind,name=name)
            modifiers.append(modifier)
            return modifier
        collection.new.side_effect=add
        return SimpleNamespace(name=name,modifiers=collection,is_editable=True,get=lambda key,default:enabled)

    def test_default_collision_is_added_once(self):
        garment=self.kept('Shirt')
        with patch.object(layering,'kept_garments',return_value=[garment]):
            layering.prepare_colliders(SimpleNamespace(scene=object()))
            layering.prepare_colliders(SimpleNamespace(scene=object()))
        garment.modifiers.new.assert_called_once_with('DD Garment Collision','COLLISION')

    def test_existing_collision_is_untouched(self):
        garment=self.kept('Shirt',existing=True)
        original=list(garment.modifiers)
        with patch.object(layering,'kept_garments',return_value=[garment]):
            layering.prepare_colliders(SimpleNamespace(scene=object()))
        garment.modifiers.new.assert_not_called()
        self.assertEqual(list(garment.modifiers),original)
        self.assertEqual(vars(original[0]),dict(type='COLLISION',name='Artist collider'))

    def test_disabled_selection_is_not_modified(self):
        garment=self.kept('Shirt',enabled=False)
        with patch.object(layering,'kept_garments',return_value=[garment]):
            layering.prepare_colliders(SimpleNamespace(scene=object()))
        garment.modifiers.new.assert_not_called()

    def test_missing_colliders_are_preflighted_before_changes(self):
        first=self.kept('Shirt')
        second=self.kept('Linked skirt')
        second.is_editable=False
        with patch.object(layering,'kept_garments',return_value=[first,second]):
            with self.assertRaisesRegex(ValueError,'Linked skirt'):
                layering.prepare_colliders(SimpleNamespace(scene=object()))
        first.modifiers.new.assert_not_called()
        second.modifiers.new.assert_not_called()

    def test_existing_linked_collision_does_not_require_edits(self):
        garment=self.kept('Linked shirt',existing=True)
        garment.is_editable=False
        with patch.object(layering,'kept_garments',return_value=[garment]):
            layering.prepare_colliders(SimpleNamespace(scene=object()))
        garment.modifiers.new.assert_not_called()

    def test_signature_change_is_limited_to_wear_over_selection(self):
        source=(Path(__file__).resolve().parents[1]/'devil_designer'/'garment.py').read_text(encoding='utf-8')
        function=next(node for node in ast.parse(source).body if isinstance(node,ast.FunctionDef) and node.name=='signature')
        segment=ast.get_source_segment(source,function)
        extension='    selection=layering.wear_over_selection(scene)\n    if selection:\n        data.append(selection)\n'
        self.assertEqual(segment.count(extension),1)
        baseline={}
        namespace=dict(hashlib=hashlib,json=json,layering=layering,metres_per_unit=lambda scene:1)
        exec(segment,namespace)
        exec(segment.replace(extension,'',1),namespace,baseline)
        scene=SimpleNamespace(dd_document='',dd_spacing=.02,dd_quality=10,dd_frames=120,dd_self_collision=True,dd_pin_top=False,dd_avatar=None)
        with patch.object(layering,'kept_garments',return_value=[]):
            self.assertEqual(namespace['signature'](scene,[]),baseline['signature'](scene,[]))
        shirt=self.kept('Shirt')
        with patch.object(layering,'kept_garments',return_value=[shirt]):
            enabled=namespace['signature'](scene,[])
            shirt.get=lambda key,default:False
            self.assertNotEqual(namespace['signature'](scene,[]),enabled)

    def test_no_kept_garments_leave_collision_collection_untouched(self):
        simulation=SimpleNamespace(modifiers=object())
        with patch.object(layering,'kept_garments',return_value=[]):
            layering.configure_collision_collection(SimpleNamespace(scene=object()),simulation)

    def test_operator_configures_collection_immediately_after_compile(self):
        source=(Path(__file__).resolve().parents[1]/'devil_designer'/'operators.py').read_text(encoding='utf-8')
        tree=ast.parse(source)
        operator=next(node for node in tree.body if isinstance(node,ast.ClassDef) and node.name=='DD_OT_simulate')
        execute=next(node for node in operator.body if isinstance(node,ast.FunctionDef) and node.name=='execute')
        action=next(node for node in execute.body if isinstance(node,ast.FunctionDef) and node.name=='action')
        self.assertEqual(ast.unparse(action.body[0]),'obj = garment.compile_garment(context)')
        self.assertEqual(ast.unparse(action.body[1]),'layering.configure_collision_collection(context, obj)')
