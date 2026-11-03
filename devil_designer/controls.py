from dataclasses import dataclass
import math

@dataclass(frozen=True)
class Setting:
    key: str
    label: str
    factor: float
    unit: str
    step: float
    low: float
    high: float
    integer: bool = False

    def format(self, value):
        value = value * self.factor
        return f"{int(value)}" if self.integer else f"{value:.15g}"

    def display(self, value):
        value = value * self.factor
        return f"{int(value)}" if self.integer else f"{value:.6g}"

    def parse(self, text):
        try:
            value = float(text.replace(',', '.'))
        except ValueError as exc:
            raise ValueError('Enter a number for ' + self.label.lower() + '.') from exc
        value /= self.factor
        if not math.isfinite(value) or not self.low <= value <= self.high:
            raise ValueError(f'{self.label}: enter {self.low * self.factor:g} to {self.high * self.factor:g} {self.unit}.')
        if self.integer and not value.is_integer():
            raise ValueError(self.label + ' needs a whole number.')
        return int(value) if self.integer else value

SETTINGS = {
    spec.key: spec for spec in (
        Setting('dd_point_x', 'Point X', 100, 'cm', 1, -100, 100),
        Setting('dd_point_y', 'Point Y', 100, 'cm', 1, -100, 100),
        Setting('dd_width', 'Width', 100, 'cm', 1, .001, 100),
        Setting('dd_height', 'Height', 100, 'cm', 1, .001, 100),
        Setting('dd_segment_length', 'Segment length', 100, 'cm', .1, .0001, 100),
        Setting('dd_offset', 'Outline offset', 100, 'cm', .1, -1, 1),
        Setting('dd_wrap_radius', 'Wrap radius', 100, 'cm', .5, 0, 10),
        Setting('dd_sew_a0', 'Side A start', 100, '%', 1, 0, 1),
        Setting('dd_sew_a1', 'Side A end', 100, '%', 1, 0, 1),
        Setting('dd_sew_b0', 'Side B start', 100, '%', 1, 0, 1),
        Setting('dd_sew_b1', 'Side B end', 100, '%', 1, 0, 1),
        Setting('dd_reference_opacity', 'Silhouette opacity', 100, '%', 5, 0, .65),
        Setting('dd_reference_x', 'Reference X', 100, 'cm', 1, -100, 100),
        Setting('dd_reference_y', 'Reference Y', 100, 'cm', 1, -100, 100),
        Setting('dd_spacing', 'Mesh spacing', 100, 'cm', .1, .003, .2),
        Setting('dd_clearance', 'Body clearance', 100, 'cm', .5, .005, .3),
        Setting('dd_quality', 'Quality steps', 1, '', 1, 5, 40, True),
        Setting('dd_frames', 'Frames', 1, '', 10, 10, 1000, True),
        Setting('dd_weld_distance', 'Weld distance', 1000, 'mm', .5, .0001, .05),
        Setting('dd_thickness', 'Thickness', 1000, 'mm', .1, 0, .01),
    )
}

LOCAL_SETTINGS = {
    spec.key: spec for spec in (
        Setting('dd_trace_length', 'Measured length', 100, 'cm', .1, .000001, 1000),
        Setting('dd_trace_width', 'Image width', 100, 'cm', 1, .000001, 1000),
        Setting('dd_trace_x', 'Image X', 100, 'cm', 1, -1000, 1000),
        Setting('dd_trace_y', 'Image Y', 100, 'cm', 1, -1000, 1000),
        Setting('dd_fabric_structural', 'Stretch stiffness', 1, '', 1, .1, 500),
        Setting('dd_fabric_shear', 'Shear stiffness', 1, '', 1, .1, 500),
        Setting('dd_fabric_bending', 'Bending stiffness', 1, '', .05, .001, 120),
        Setting('dd_fabric_density', 'Mass density', 1, '', .05, .01, 10),
    )
}

@dataclass(frozen=True)
class TextSetting:
    key: str
    label: str
    unit: str = ''
    maximum: int = 80
    allow_empty: bool = False
    def format(self, value):
        return value
    def parse(self, text):
        if (not text.strip() and not self.allow_empty) or len(text) > self.maximum:
            raise ValueError(f'{self.label}: use up to {self.maximum} characters.')
        return text.strip()

    def display(self, value):
        return value

SETTINGS['dd_library_name'] = TextSetting('dd_library_name', 'Garment name')
SETTINGS['dd_library_dir'] = TextSetting('dd_library_dir', 'Library folder', maximum=4096, allow_empty=True)
CONTROL_SETTINGS = {**SETTINGS, **LOCAL_SETTINGS}
