import hashlib
import json

from .core import Document


HISTORY_LIMIT = 100
HISTORY_VERSION = 1


def _reject_constant(value):
    raise ValueError("History contains a non-finite number.")


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("History contains duplicate fields.")
        result[key] = value
    return result


def _decode(raw):
    if not isinstance(raw, str) or not raw.strip():
        raise ValueError("A saved snapshot is empty or is not text.")
    return json.loads(raw, parse_constant=_reject_constant, object_pairs_hook=_unique_object)


def _fingerprint(document):
    canonical = json.dumps(_decode(document.dumps()), sort_keys=True,
                           separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _snapshot(raw):
    data = _decode(raw)
    if not isinstance(data, dict) or type(data.get("version")) is not int:
        raise ValueError("A saved snapshot has an invalid document format.")
    if not isinstance(data.get("patterns"), list):
        raise ValueError("A saved snapshot has no pattern list.")
    document = Document.loads(raw)
    for pattern in document.patterns:
        if not isinstance(pattern.features, list):
            raise ValueError("A saved snapshot has invalid construction features.")
        for feature in pattern.features:
            if not isinstance(feature, dict) or any(
                not isinstance(feature.get(key), str) or not feature[key]
                for key in ("id", "type")
            ):
                raise ValueError("A saved snapshot has an invalid construction feature.")
            if any(key in feature and not isinstance(feature[key], str)
                   for key in ("seam", "apex")):
                raise ValueError("A saved snapshot has an invalid feature reference.")
        for path in pattern.paths:
            if not isinstance(path.name, str) or type(path.closed) is not bool:
                raise ValueError("A saved snapshot has invalid path metadata.")
    return document.dumps()


def _stack(values):
    if not isinstance(values, list):
        raise ValueError("Saved undo and redo stacks must be lists.")
    return [_snapshot(value) for value in values[-HISTORY_LIMIT:]]


def _clear(session, message):
    session.undo_stack = []
    session.redo_stack = []
    session.history_message = message


def store(session):
    try:
        undo = _stack(session.undo_stack)
        redo = _stack(session.redo_stack)
        payload = dict(version=HISTORY_VERSION, current=_fingerprint(session.document),
                       undo=undo, redo=redo)
        selected = session.selected
        if isinstance(selected, str) and session.document.find(selected) is not None:
            payload["selected"] = selected
        raw = json.dumps(payload, separators=(",", ":"), allow_nan=False)
    except Exception:
        _clear(session, "Undo history could not be saved and was reset. Your current pattern document is unchanged; you can keep editing.")
        return ""
    session.history_message = ""
    return raw


def restore(session, raw):
    if raw == "" or raw is None:
        _clear(session, "")
        return False
    try:
        payload = _decode(raw)
        if not isinstance(payload, dict) or type(payload.get("version")) is not int:
            raise ValueError("Invalid saved history format.")
        if payload["version"] != HISTORY_VERSION:
            raise ValueError("Unsupported saved history version.")
        current = payload.get("current")
        if not isinstance(current, str) or current != _fingerprint(session.document):
            _clear(session, "Saved undo history belongs to a different pattern document and was reset. Your current document is unchanged; you can keep editing.")
            return False
        undo = _stack(payload["undo"])
        redo = _stack(payload["redo"])
        selected = payload.get("selected")
        if selected is not None and not isinstance(selected, str):
            raise ValueError("Invalid saved pattern selection.")
        if selected is not None and session.document.find(selected) is None:
            raise ValueError("The saved pattern selection no longer exists.")
    except Exception:
        _clear(session, "Saved undo history is damaged or unsupported and was reset. Your current pattern document is unchanged; you can keep editing.")
        return False
    session.undo_stack = undo
    session.redo_stack = redo
    if "selected" in payload:
        session.selected = selected
        session.corner = None
        session.path = "OUTER"
        session.segment = None
        session.point_selection = []
    session.history_message = ""
    return True
