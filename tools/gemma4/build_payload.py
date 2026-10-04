"""Offline A/B/C payload builder. No model calls or embedded evaluation items."""
import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()


def render(case, variant):
    if variant not in 'ABC' or len(variant) != 1:
        raise ValueError('Unknown layout')
    keys = list(reversed(case)) if variant == 'C' else list(case)
    separator = '\n\n' if variant == 'A' else '\n'
    prefix = '- ' if variant == 'B' else ''
    return separator.join(prefix + key + ' = ' + canonical(case[key]).decode() for key in keys)


def build(case, split='development'):
    if set(case) != {'case_id', 'instruction', 'data', 'response_schema'}:
        raise ValueError('Expected only public input fields')
    if split not in ('development', 'evaluation'):
        raise ValueError('Unknown split')
    model = json.loads((ROOT / 'configs/gemma4-v1.1.json').read_text())
    prompts = json.loads((ROOT / 'prompts/gemma4-layouts.json').read_text())
    cells = []
    for variant in 'ABC':
        rid = case['case_id'] + '-' + variant
        request = {'request_id': rid,
                   'messages': [{'role': 'system', 'content': prompts['system']},
                                {'role': 'user', 'content': render(case, variant)}],
                   'temperature': model['temperature'], 'seed': model['seed'],
                   'max_tokens': model['max_tokens'], 'cache_prompt': False,
                   'chat_template_kwargs': {'enable_thinking': False}}
        cells.append({'request_id': rid, 'case_id': case['case_id'], 'split': split,
                      'variant': variant, 'request': request,
                      'request_sha256': hashlib.sha256(canonical(request)).hexdigest()})
    return {'model': model, 'requests': cells}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--case', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    payload = build(json.loads(args.case.read_text()))
    # Refuse accidental replacement of a frozen payload.
    with args.out.open('x') as output:
        json.dump(payload, output, ensure_ascii=False, indent=2)
        output.write('\n')
