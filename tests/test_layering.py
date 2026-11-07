import ast
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from devil_designer import layering


def garment_source():
    return (Path(__file__).resolve().parents[1]/'devil_designer'/'garment.py').read_text(encoding='utf-8')


class LayeringTests(unittest.TestCase):
    def kept(self,name,enabled=True):
        return SimpleNamespace(name=name,type='MESH',modifiers=[],get=lambda key,default=None:enabled if key=='dd_wear_over' else 'final')

    def scene(self,objects,avatar):
        return SimpleNamespace(dd_avatar=avatar,objects=objects)

    def test_body_and_worn_garments_are_the_collision_bodies(self):
        body=SimpleNamespace(type='MESH',modifiers=[],get=lambda key,default=None:default)
        shirt=self.kept('Shirt')
        skipped=self.kept('Skirt',False)
        with patch.object(layering,'kept_garments',return_value=[shirt,skipped]):
            bodies=layering.collision_bodies(self.scene([body,shirt,skipped],body))
        self.assertEqual(bodies,[body,shirt])

    def test_artist_collision_objects_stay_in_the_simulation(self):
        body=SimpleNamespace(type='MESH',modifiers=[],get=lambda key,default=None:default)
        prop=SimpleNamespace(type='MESH',modifiers=[SimpleNamespace(type='COLLISION',show_viewport=True)],get=lambda key,default=None:default)
        plain=SimpleNamespace(type='MESH',modifiers=[],get=lambda key,default=None:default)
        with patch.object(layering,'kept_garments',return_value=[]):
            bodies=layering.collision_bodies(self.scene([body,prop,plain],body))
        self.assertEqual(bodies,[body,prop])

    def test_signature_change_is_limited_to_wear_over_selection(self):
        source=garment_source()
        function=next(node for node in ast.parse(source).body if isinstance(node,ast.FunctionDef) and node.name=='signature')
        segment=ast.get_source_segment(source,function)
        extension='    selection=layering.wear_over_selection(scene)\n    if selection:\n        data.append(selection)\n'
        self.assertEqual(segment.count(extension),1)
        baseline={}
        namespace=dict(hashlib=hashlib,json=json,layering=layering,metres_per_unit=lambda scene:1)
        exec(segment,namespace)
        exec(segment.replace(extension,'',1),namespace,baseline)
        scene=SimpleNamespace(dd_document='',dd_spacing=.02,dd_skin_offset=.003,dd_quality=24,dd_self_collision=True,dd_pin_top=False,dd_avatar=None,dd_friction=.3)
        with patch.object(layering,'kept_garments',return_value=[]):
            self.assertEqual(namespace['signature'](scene,[]),namespace['signature'](scene,[]))
        shirt=self.kept('Shirt')
        with patch.object(layering,'kept_garments',return_value=[shirt]):
            enabled=namespace['signature'](scene,[])
            shirt.get=lambda key,default=None:False
            self.assertNotEqual(namespace['signature'](scene,[]),enabled)
