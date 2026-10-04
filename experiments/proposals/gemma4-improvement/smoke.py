"""Pure request/validation/repair helpers. No client, generation, or host execution."""
import copy
import json
from pathlib import Path, PurePosixPath
from jsonschema import Draft202012Validator

HERE = Path(__file__).resolve().parent
DESIGN = json.loads((HERE / 'design.json').read_text())


def strict_json(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError('duplicate_key')
            result[key] = value
        return result
    def nonfinite(_):
        raise ValueError('nonfinite')
    return json.loads(raw, object_pairs_hook=pairs, parse_constant=nonfinite)


def resolve_file(file_id, catalog, root):
    if file_id not in catalog:
        raise ValueError('unknown_file_id')
    relative = catalog[file_id]
    if not isinstance(relative, str) or not relative or '\\' in relative or ':' in relative:
        raise ValueError('unsafe_path')
    path = PurePosixPath(relative)
    if path.is_absolute() or '..' in path.parts or '.' == relative:
        raise ValueError('unsafe_path')
    root = Path(root).resolve()
    target = (root / relative).resolve()
    if target == root or not target.is_relative_to(root):
        raise ValueError('unsafe_path')
    return target  # Planning only. Does not open or execute the path.


def inspect(raw, example, root):
    try:
        if not isinstance(raw, str) or len(raw) > 16000:
            raise ValueError('size')
        obj = strict_json(raw)
    except (ValueError, TypeError, RecursionError):
        return ['invalid_json']
    if not Draft202012Validator(example['response_schema']).is_valid(obj):
        return ['schema_mismatch']
    errors = set()
    for item in obj['plan']:
        try:
            resolve_file(item['file_id'], example['file_catalog'], root)
        except ValueError as exc:
            errors.add(str(exc))
    return sorted(errors)


def request(example, arm, previous=None, feedback=None):
    schema = copy.deepcopy(example['response_schema'])
    messages = [{'role': 'system', 'content': 'Return JSON matching the response schema. Plan only; do not execute code or commands.'},
                {'role': 'user', 'content': json.dumps({k: example[k] for k in ('task', 'file_catalog', 'response_schema')}, ensure_ascii=False)}]
    if arm['file_id_validation']:
        messages[0]['content'] += ' Choose only provided file IDs. Do not invent paths or IDs.'
        schema['properties']['plan']['items']['properties']['file_id']['enum'] = sorted(example['file_catalog'])
    if previous is not None:
        if not arm['bounded_repair']:
            raise ValueError('repair_disabled')
        allowed = {'invalid_json', 'schema_mismatch', 'unknown_file_id', 'unsafe_path'}
        if not feedback or set(feedback) - allowed:
            raise ValueError('feedback_must_be_public_codes')
        messages += [{'role': 'assistant', 'content': previous},
                     {'role': 'user', 'content': 'Repair once using these public contract errors: ' + ', '.join(sorted(feedback))}]
    result = {'messages': messages, 'temperature': 0, 'seed': 104, 'max_tokens': 384,
              'chat_template_kwargs': {'enable_thinking': False}, 'cache_prompt': False}
    if arm['json_schema']:
        result['response_format'] = {'type': 'json_schema', 'json_schema': {'name': 'plan', 'strict': True, 'schema': schema}}
    return result


def permit_repair(arm, errors, calls, output_tokens, input_tokens, next_input_tokens, elapsed, ambiguous=False):
    """Caller must supply exact observed usage/tokenizer counts; no estimates."""
    counts = (calls, output_tokens, input_tokens, next_input_tokens)
    if any(type(n) is not int or n < 0 for n in counts):
        raise ValueError('exact_nonnegative_counts_required')
    if not isinstance(elapsed, (int, float)) or isinstance(elapsed, bool) or not 0 <= elapsed < float('inf'):
        raise ValueError('elapsed_required')
    budget = DESIGN['budget']
    if ambiguous or not arm['bounded_repair'] or not errors or calls != 1:
        return False
    if not arm['file_id_validation'] and all(e in ('unknown_file_id', 'unsafe_path') for e in errors):
        return False  # F0 does not receive file gate feedback; common scorer still records it.
    return (output_tokens + budget['repair_output_tokens'] <= budget['total_output_tokens_max']
            and input_tokens + next_input_tokens <= budget['input_tokens_total_cap']
            and next_input_tokens + budget['repair_output_tokens'] + 8 <= budget['context_tokens']
            and elapsed < budget['wall_seconds_cap'])
