"""Check publication files without printing private values or file contents.

This is a targeted repository hygiene check, not a general-purpose secret detector.
Generated artifacts and local settings must never be committed.
"""
from pathlib import Path
import re
import subprocess
import sys
import struct
import zlib
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]
ALIAS = 'Artbyo3'
EMAIL = '170281415+'+ALIAS+'@users.noreply.github.com'
FORBIDDEN_SUFFIXES = {'.blend','.blend1','.zip','.pyc','.pyo','.pem','.key'}
PUBLIC_IDENTITIES = {(ALIAS, EMAIL), ('T3 Code', 't3code@users.noreply.github.com')}


def inspect_payload(name, payload, errors):
    if name.startswith('devil_designer/assets/icons/') and name.endswith('.png'):
        if not payload.startswith(b'\x89PNG\r\n\x1a\n'):
            errors.append(name+': invalid icon image')
            return
        offset = 8
        chunk_types = []
        while offset + 12 <= len(payload):
            length = int.from_bytes(payload[offset:offset+4], 'big')
            chunk_type = payload[offset+4:offset+8]
            chunk_data = payload[offset+8:offset+8+length]
            checksum = payload[offset+8+length:offset+12+length]
            if len(checksum) != 4 or int.from_bytes(checksum, 'big') != zlib.crc32(chunk_type+chunk_data):
                errors.append(name+': corrupt icon image')
                return
            if chunk_type not in {b'IHDR', b'IDAT', b'IEND'}:
                errors.append(name+': unexpected image metadata')
            if chunk_type == b'IHDR' and (length != 13 or struct.unpack('>II', chunk_data[:8]) != (64, 64)):
                errors.append(name+': unexpected icon dimensions')
            chunk_types.append(chunk_type)
            offset += length + 12
        if offset != len(payload) or not chunk_types or chunk_types[0] != b'IHDR' or chunk_types[-1] != b'IEND' or b'IDAT' not in chunk_types:
            errors.append(name+': incomplete icon image')
        return
    try:
        data = payload.decode('utf-8')
    except UnicodeDecodeError:
        errors.append(name+': unexpected binary publication file')
        return
    inspect_text(name, data, errors)


def inspect_text(name,data,errors):
    private_name = Path.home().name
    if private_name.lower() not in {ALIAS.lower(),'runner','root','user','administrator'}:
        if re.search(r'(?i)\b'+re.escape(private_name)+r'\b',data):
            errors.append(name+': local account name')
    if re.search(r'(?i)[a-z]:[\\/]Users[\\/][^\\/\r\n]+',data):
        errors.append(name+': absolute user directory')
    if str(ROOT) in data or ROOT.as_posix() in data:
        errors.append(name+': absolute workspace path')
    for email in re.findall(r'[A-Za-z0-9_.+%-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}',data):
        if email not in {identity[1] for identity in PUBLIC_IDENTITIES}:
            errors.append(name+': unapproved email address')
    secret_patterns = [r'gh' + r'[opusr]_[A-Za-z0-9]{25,}',
                       r'github_' + r'pat_[A-Za-z0-9_]{25,}',
                       '-----BEGIN ' + r'(?:RSA |EC |OPENSSH )?PRIVATE KEY-----']
    if any(re.search(pattern,data) for pattern in secret_patterns):
        errors.append(name+': possible credential')


def main():
    result = subprocess.run(['git','ls-files','--cached','--others','--exclude-standard','-z'],
                            cwd=ROOT,capture_output=True,check=True)
    files = sorted(set(n for n in result.stdout.decode().split('\0') if n))
    errors = []
    for name in files:
        p=ROOT/name
        if not p.is_file():
            continue
        if p.suffix.lower() in FORBIDDEN_SUFFIXES or name.startswith(('build/','.venv/','.idea/','.vscode/')):
            errors.append(name+': generated or machine-specific file')
            continue
        inspect_payload(name, p.read_bytes(), errors)
    for archive in (ROOT/'build').glob('devil_designer-*.zip'):
        with ZipFile(archive) as z:
            for member in z.namelist():
                if member.startswith(('/','\\')) or '..' in Path(member).parts:
                    errors.append('extension archive: unsafe member path')
                    continue
                before = len(errors)
                inspect_payload('devil_designer/'+member, z.read(member), errors)
                errors[before:] = ['extension archive/'+error for error in errors[before:]]
    commits=subprocess.run(['git','log','--all','--format=%an%x00%ae%x00%cn%x00%ce'],cwd=ROOT,capture_output=True,text=True)
    if commits.returncode==0:
        for line in commits.stdout.splitlines():
            fields=line.split('\0')
            if len(fields) != 4 or tuple(fields[:2]) not in PUBLIC_IDENTITIES or tuple(fields[2:]) not in PUBLIC_IDENTITIES:
                errors.append('commit metadata: identity differs from approved public alias')
    messages=subprocess.run(['git','log','--all','--format=%B'],cwd=ROOT,capture_output=True,text=True)
    if messages.returncode==0:
        inspect_text('commit messages',messages.stdout,errors)
    objects = subprocess.run(['git', 'rev-list', '--objects', '--all'], cwd=ROOT, capture_output=True, text=True, check=True)
    history_count = 0
    for entry in objects.stdout.splitlines():
        object_id, separator, name = entry.partition(' ')
        if not separator:
            continue
        result = subprocess.run(['git', 'cat-file', '-t', object_id], cwd=ROOT, capture_output=True, text=True, check=True)
        if result.stdout.strip() != 'blob':
            continue
        payload = subprocess.run(['git', 'cat-file', 'blob', object_id], cwd=ROOT, capture_output=True, check=True).stdout
        inspect_payload(name, payload, errors)
        history_count += 1
    if errors:
        print('Publication check failed:')
        print('\n'.join(sorted(set(errors))))
        return 1
    print(f'Publication check passed: {len(files)} source paths, {history_count} historical blobs, archives, and public commit identities checked.')
    return 0

if __name__=='__main__':
    sys.exit(main())
