#!/usr/bin/env python3
"""Offline source/configuration smoke checks; does not execute application code."""
import ast, json, os, pathlib, subprocess, xml.etree.ElementTree as ET
root = pathlib.Path(__file__).resolve().parents[1]
skip = {'.git', 'node_modules', '.venv', 'venv', '__pycache__', '.next', 'dist', 'build', '.terraform', '.dart_tool', 'records', 'profile', 'visits', 'logs', 'memory', 'secrets', 'data', 'state', 'screenshots', 'output', 'outputs', 'references', '.openclaw', '.wrangler', '_archive'}
counts = {'python': 0, 'json': 0, 'shell': 0, 'javascript': 0, 'xml': 0}
for directory, children, files in os.walk(root):
    children[:] = [d for d in children if d not in skip and not d.startswith('venv') and not pathlib.Path(directory, d).is_symlink()]
    for name in files:
        path = pathlib.Path(directory, name)
        if path.is_symlink() or path.stat().st_size > 2_000_000:
            continue
        rel = str(path.relative_to(root))
        if name.endswith('.py'):
            ast.parse(path.read_text(), filename=rel); counts['python'] += 1
        elif name in {'package.json', 'manifest.json', 'devcontainer.json', 'cloud.json'} or name == 'Contents.json':
            if name == 'devcontainer.json' and rel != json.loads((root / '.codex/cloud.json').read_text())['container']:
                continue  # Existing alternate containers may use JSONC.
            json.loads(path.read_text()); counts['json'] += 1
        elif name.endswith('.sh'):
            subprocess.run(['bash', '-n', str(path)], check=True); counts['shell'] += 1
        elif name.endswith(('.js', '.mjs', '.cjs')) and name not in {'next-env.d.ts'}:
            if __import__('shutil').which('node'):
                subprocess.run(['node', '--check', str(path)], check=True); counts['javascript'] += 1
        elif name.endswith(('.plist', '.entitlements')):
            ET.parse(path); counts['xml'] += 1
print('Offline source/configuration checks:', json.dumps(counts, sort_keys=True))
print('These smoke checks do not prove application behavior, native builds, or live integrations.')
