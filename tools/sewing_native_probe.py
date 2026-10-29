import ctypes
import math
import re
import struct
from ctypes import wintypes
from pathlib import Path
import bpy


class ClothPrefix(ctypes.Structure):
    _fields_ = [('vertices', ctypes.c_void_p), ('springs', ctypes.c_void_p), ('spring_count', ctypes.c_uint), ('vertex_count', ctypes.c_uint)]


class Spring(ctypes.Structure):
    _fields_ = [('first', ctypes.c_int), ('second', ctypes.c_int), ('third', ctypes.c_int), ('polygon_a', ctypes.c_void_p), ('polygon_b', ctypes.c_void_p), ('polygon_a_count', ctypes.c_int), ('polygon_b_count', ctypes.c_int), ('rest_length', ctypes.c_float), ('rest_angle', ctypes.c_float), ('spring_type', ctypes.c_int), ('flags', ctypes.c_int), ('linear_stiffness', ctypes.c_float), ('angular_stiffness', ctypes.c_float), ('edit_rest_length', ctypes.c_float), ('target', ctypes.c_float * 3)]


class Memory:
    def __init__(self):
        self.kernel = ctypes.WinDLL('kernel32', use_last_error=True)
        self.kernel.GetCurrentProcess.restype = wintypes.HANDLE
        self.kernel.ReadProcessMemory.argtypes = [wintypes.HANDLE, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_size_t, ctypes.POINTER(ctypes.c_size_t)]
        self.kernel.ReadProcessMemory.restype = wintypes.BOOL
        self.process = self.kernel.GetCurrentProcess()

    def read(self, address, length):
        if not address or address < 65536 or not 0 < length < 1048576:
            raise ValueError('Invalid bounded native read.')
        buffer = ctypes.create_string_buffer(length)
        count = ctypes.c_size_t()
        if not self.kernel.ReadProcessMemory(self.process, address, buffer, length, ctypes.byref(count)) or count.value != length:
            raise OSError(ctypes.get_last_error(), 'Native read failed; no unsafe fallback permitted.')
        return buffer.raw


def modifier_layout(filename):
    blob = Path(filename).read_bytes()
    if blob[:17] != b'BLENDER17-01v0502':
        raise ValueError('Unsupported Blender file header: ' + repr(blob[:12]))
    pointer_size = 8
    offset = 17
    dna = None
    while offset + 32 <= len(blob):
        tag, schema, address, length, count = struct.unpack_from('<4siQqq', blob, offset)
        offset += 32
        if tag == b'DNA1':
            dna = blob[offset:offset + length]
            break
        offset += length
    if dna is None or dna[:8] != b'SDNANAME':
        raise ValueError('Native layout DNA not found.')
    offset = 8
    name_count = struct.unpack_from('<I', dna, offset)[0]
    offset += 4
    names = []
    for index in range(name_count):
        end = dna.index(0, offset)
        names.append(dna[offset:end].decode())
        offset = end + 1
    offset = (offset + 3) & ~3
    if dna[offset:offset + 4] != b'TYPE':
        raise ValueError('Invalid DNA type table.')
    type_count = struct.unpack_from('<I', dna, offset + 4)[0]
    offset += 8
    types = []
    for index in range(type_count):
        end = dna.index(0, offset)
        types.append(dna[offset:end].decode())
        offset = end + 1
    offset = (offset + 3) & ~3
    if dna[offset:offset + 4] != b'TLEN':
        raise ValueError('Invalid DNA length table.')
    lengths = struct.unpack_from('<' + 'H' * type_count, dna, offset + 4)
    offset = (offset + 4 + 2 * type_count + 3) & ~3
    if dna[offset:offset + 4] != b'STRC':
        raise ValueError('Invalid DNA structure table.')
    structure_count = struct.unpack_from('<I', dna, offset + 4)[0]
    offset += 8
    result = {}
    for index in range(structure_count):
        type_index, field_count = struct.unpack_from('<HH', dna, offset)
        offset += 4
        fields = {}
        position = 0
        for field in range(field_count):
            field_type, field_name = struct.unpack_from('<HH', dna, offset)
            offset += 4
            name = names[field_name]
            dimensions = math.prod(int(value) for value in re.findall(r'\[(\d+)\]', name))
            fields[name] = position
            position += (pointer_size if '*' in name else lengths[field_type]) * dimensions
        if types[type_index] in {'ModifierData', 'ClothModifierData'}:
            if position != lengths[type_index]:
                raise ValueError('DNA structure size mismatch.')
            result[types[type_index]] = dict(size=position, fields=fields)
    return result


def snapshot(simulation, layout, context):
    if bpy.app.build_hash != b'e13b728c6880' or ctypes.sizeof(ctypes.c_void_p) != 8:
        raise ValueError('Native inspection is restricted to the verified exact build and ABI.')
    memory = Memory()
    evaluated = simulation.evaluated_get(context.evaluated_depsgraph_get())
    modifier = next(item for item in evaluated.modifiers if item.type == 'CLOTH')
    field_offset = layout['ClothModifierData']['fields']['*clothObject']
    cloth_address = struct.unpack('<Q', memory.read(modifier.as_pointer() + field_offset, 8))[0]
    if not cloth_address:
        raise ValueError('Evaluated native cloth has not initialized.')
    cloth = ClothPrefix.from_buffer_copy(memory.read(cloth_address, ctypes.sizeof(ClothPrefix)))
    if cloth.vertex_count != len(simulation.data.vertices) or not 0 < cloth.spring_count < 1000000:
        raise ValueError('Native cloth prefix failed validation.')
    pointer = cloth.springs
    visited = set()
    springs = []
    while pointer:
        if pointer in visited or len(visited) >= cloth.spring_count:
            raise ValueError('Native spring list is cyclic or exceeds its count.')
        visited.add(pointer)
        pointer, spring_address = struct.unpack('<QQ', memory.read(pointer, 16))
        spring = Spring.from_buffer_copy(memory.read(spring_address, ctypes.sizeof(Spring)))
        if not 0 <= spring.first < cloth.vertex_count or not 0 <= spring.second < cloth.vertex_count or not math.isfinite(spring.rest_length) or not 0 <= spring.spring_type <= 255:
            raise ValueError('Native spring fields failed validation.')
        springs.append(dict(pair=sorted((spring.first, spring.second)), type=spring.spring_type, rest_length=spring.rest_length, linear_stiffness=spring.linear_stiffness))
    components = sum(item['type'].bit_count() for item in springs)
    if components != cloth.spring_count:
        raise ValueError('Native spring component count differs from the initialized count: ' + repr(dict(actual=components, expected=cloth.spring_count)))
    return dict(frame=context.scene.frame_current, native_vertex_count=cloth.vertex_count, native_spring_count=len(springs), native_component_count=cloth.spring_count, modifier_cloth_offset=field_offset, spring_rest_offset=Spring.rest_length.offset, spring_type_offset=Spring.spring_type.offset, springs=springs)
