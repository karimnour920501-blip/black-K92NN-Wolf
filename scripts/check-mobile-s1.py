#!/usr/bin/env python3
"""Fail closed if the real Expo S1 source tree is missing/incomplete."""
import json
import pathlib
import sys


def check(root: pathlib.Path) -> list[str]:
    errors = []
    for rel in ('package.json', 'package-lock.json', 'tsconfig.json'):
        if not (root / rel).is_file():
            errors.append(f'MISSING: {rel}')
    package_path = root / 'package.json'
    if package_path.is_file():
        try:
            pkg = json.loads(package_path.read_text(encoding='utf-8'))
            for script in ('test', 'typecheck'):
                if not pkg.get('scripts', {}).get(script):
                    errors.append(f'MISSING SCRIPT: {script}')
            deps = {**pkg.get('dependencies', {}), **pkg.get('devDependencies', {})}
            for dep in ('expo', 'expo-router', 'react', 'react-native', 'typescript'):
                if dep not in deps:
                    errors.append(f'MISSING DEPENDENCY: {dep}')
        except (ValueError, OSError) as exc:
            errors.append(f'INVALID package.json: {exc}')
    if not (root / 'app').is_dir():
        errors.append('MISSING: app/ Expo Router directory')
    else:
        routes = list((root / 'app').rglob('*.tsx')) + list((root / 'app').rglob('*.ts'))
        if not routes:
            errors.append('MISSING: Expo Router source routes')
    return errors


if __name__ == '__main__':
    root = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else 'BLACK-K92N-WOLF-Mobile-MVP-v1.0-S1')
    problems = check(root)
    if problems:
        print('BLOCKED: source gate failed\n' + '\n'.join(problems), file=sys.stderr)
        sys.exit(1)
    print('PASS: minimum S1 source structure present; functionality is NOT yet verified')
