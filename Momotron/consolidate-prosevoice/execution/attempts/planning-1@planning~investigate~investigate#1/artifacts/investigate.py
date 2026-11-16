# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Read-only source investigation; all fixture writes stay beside this script."""
import importlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

ROOT = Path('/Users/james/workspace/dixson3/blog-voice')
MOMO = Path('/Users/james/workspace/dixson3/momotron')
OUT = Path(__file__).resolve().parent
FIX = OUT / 'fixtures'
FIX.mkdir(exist_ok=True)
sys.dont_write_bytecode = True
sys.path.insert(0, str(ROOT / 'skills/pv-preflight/scripts'))
preflight = importlib.import_module('preflight')
pv_config = importlib.import_module('pv_config')
sys.path.insert(0, str(MOMO / 'skills/momotron/scripts'))
momo_config = importlib.import_module('momotron_lib.config')
skill_root = importlib.import_module('momotron_lib').skill_root

def put(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding='utf-8')
    return path

observations = {}
home = FIX / 'home'
project = FIX / 'project'
project.mkdir(exist_ok=True)
subprocess.run(['git', 'init', '-q', str(project)], check=True)
put(project / '.prose-voice/VOICE.md', 'Project voice\n')
put(home / '.prose-voice/AUDIENCE.md', 'Global reader\n')
put(project / 'guides/reader.md', 'Configured reader\n')
put(project / '.prose-voice/config.json', json.dumps({'guidance': {'AUDIENCE.md': ['missing.md', 'guides/reader.md']}}))
with patch.object(Path, 'home', return_value=home):
    resolved = preflight.resolve(project)
    assert resolved['VOICE.md']['resolved']['level'] == 'project'
    assert resolved['AUDIENCE.md']['resolved']['level'] == 'configured'
    assert resolved['ILLUSTRATIONS.md']['resolved'] is None
    observations['legacy_guidance'] = resolved
    put(project / 'guides/reader.md', '<!-- pv-template: unfilled -->\n')
    assert preflight.resolve(project)['AUDIENCE.md']['resolved']['level'] == 'global'
    observations['unfilled_fallback'] = 'unfilled configured guide falls back independently to global audience'
essay = put(project / 'chapters/one.md', '# One\n\nBody.\n')
put(project / '.prose-voice/.gitignore', '/scratch/\n')
paths = pv_config.prepare_artifacts(essay, project)
pv_config.prepare_artifacts(essay, project)
assert len(paths) == 12
assert (project / '.prose-voice/.gitignore').read_text() == '/scratch/\n/cache/\n'
observations['artifacts'] = {k: str(v.relative_to(project)) for k, v in paths.items()}
put(project / '.prose-voice/config.json', '{"artifacts":{"location":"adjacent"}}')
assert pv_config.artifact_paths(essay, project)['illustrations'].parent == essay.parent
observations['adjacent'] = 'paths remain beside essay when configured'
put(project / '.prose-voice/config.json', '{"artifacts":{"location":"cache"},"artifacts":{"location":"adjacent"}}')
observations['legacy_duplicate_keys'] = pv_config.load_config(project)
put(project / '.prose-voice/config.json', '{"unsupported":true}')
try:
    pv_config.load_config(project)
except ValueError as error:
    observations['legacy_unknown_key'] = str(error)
else:
    raise AssertionError('unknown key accepted')

xdg = FIX / 'xdg'
with patch.dict(os.environ, {'XDG_CONFIG_HOME': str(xdg)}):
    put(xdg / 'momotron/config.json', '{"plans_root":"UserPlans","max_review_cycles":7}')
    put(project / '.momotron/config.json', '{"plans_root":"ProjectPlans"}')
    config = momo_config.resolve(project, ['plans_root=CLIPlans'])
    assert config.values['plans_root'] == 'CLIPlans' and config.provenance['plans_root'] == 'cli'
    assert config.values['max_review_cycles'] == 7 and config.provenance['max_review_cycles'] == 'user'
    observations['momotron_layers'] = {k: {'value': config.values[k], 'tier': config.provenance[k]} for k in ['plans_root', 'max_review_cycles', 'schema_version']}
    put(project / '.momotron/config.json', '{"plans_root":"a","plans_root":"b"}')
    try:
        momo_config.resolve(project)
    except Exception as error:
        observations['momotron_duplicate_keys'] = str(error)
    else:
        raise AssertionError('duplicate key accepted')
    put(project / '.momotron/config.json', '{}')
    first = momo_config.init_project(project)
    second = momo_config.init_project(project)
    assert second['created'] == []
    observations['momotron_init'] = {'first': first, 'second': second}
    observations['momotron_root_fallback'] = str(momo_config.find_project_root(cwd=home))
    observations['momotron_skill_root'] = str(skill_root())

# Reproduce a single installed skill without its former sibling, without modifying source.
installed = FIX / 'installed/skills/pv-prosevoice'
shutil.copytree(ROOT / 'skills/pv-prosevoice', installed, dirs_exist_ok=True)
proc = subprocess.run([sys.executable, '-B', str(installed / 'scripts/ready_preconditions.py'), '--help'], capture_output=True, text=True)
assert proc.returncode != 0 and 'pv-preflight/scripts/pv_config.py' in proc.stderr
observations['single_legacy_skill_failure'] = {'returncode': proc.returncode, 'last_error': proc.stderr.splitlines()[-1]}
observations['malformed_legacy_block'] = {
    'input': 'Keep before\\n' + preflight.BEGIN + '\\nKeep after\\n',
    'stripped': preflight.strip_block('Keep before\n' + preflight.BEGIN + '\nKeep after\n', preflight.BEGIN, preflight.END),
}
assert observations['malformed_legacy_block']['stripped'] == 'Keep before'
observations['python_version'] = sys.version
(OUT / 'probe-results.json').write_text(json.dumps(observations, indent=2) + '\n')
print(json.dumps({'checks': 'passed', 'evidence': str(OUT / 'probe-results.json'), 'observations': list(observations)}, indent=2))
