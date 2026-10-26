"""Check publication files without printing private values or file contents.

This is a targeted repository hygiene check, not a general-purpose secret detector.
Generated artifacts and local settings must never be committed.
"""
from pathlib import Path
import re
import subprocess
import sys
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]
ALIAS = 'Artbyo3'
EMAIL = '170281415+'+ALIAS+'@users.noreply.github.com'
FORBIDDEN_SUFFIXES = {'.blend','.blend1','.zip','.pyc','.pyo','.pem','.key'}


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
        if email!=EMAIL:
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
        try:
            data=p.read_text(encoding='utf-8')
        except UnicodeDecodeError:
            errors.append(name+': unexpected binary publication file')
            continue
        inspect_text(name,data,errors)
    for archive in (ROOT/'build').glob('devil_designer-*.zip'):
        with ZipFile(archive) as z:
            for member in z.namelist():
                if member.startswith(('/','\\')) or '..' in Path(member).parts:
                    errors.append('extension archive: unsafe member path')
                    continue
                inspect_text('extension archive/'+member,z.read(member).decode('utf-8'),errors)
    commits=subprocess.run(['git','log','--all','--format=%an%x00%ae%x00%cn%x00%ce'],cwd=ROOT,capture_output=True,text=True)
    if commits.returncode==0:
        for line in commits.stdout.splitlines():
            fields=line.split('\0')
            if fields!=[ALIAS,EMAIL,ALIAS,EMAIL]:
                errors.append('commit metadata: identity differs from approved public alias')
    messages=subprocess.run(['git','log','--all','--format=%B'],cwd=ROOT,capture_output=True,text=True)
    if messages.returncode==0:
        inspect_text('commit messages',messages.stdout,errors)
    if errors:
        print('Publication check failed:')
        print('\n'.join(sorted(set(errors))))
        return 1
    print(f'Publication check passed: {len(files)} source files, archives, and commit identities checked.')
    return 0

if __name__=='__main__':
    sys.exit(main())
