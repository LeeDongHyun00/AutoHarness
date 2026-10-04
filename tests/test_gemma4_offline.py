import ast
import copy
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools/gemma4'))
import build_payload as builder
import evaluator
import runner
import score_checkpoint
from safe_expr import strict_json


class OfflineTests(unittest.TestCase):
    def setUp(self):
        self.network = patch('socket.socket', side_effect=AssertionError('Network forbidden'))
        self.network.start()
        self.addCleanup(self.network.stop)
        self.gpu = patch.object(runner, 'runtime_metadata', return_value={'platform': 'offline_fake'})
        self.gpu.start()
        self.addCleanup(self.gpu.stop)
        self.case = json.loads((ROOT / 'examples/synthetic-case.json').read_text())
        self.pack = builder.build(self.case)
        self.oracle = {'kind': 'exact', 'expected': {'count': 3}}
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.payload = self.root / 'payload.json'
        self.payload.write_text(json.dumps(self.pack))
        self.out = self.root / 'out'
        self.out.mkdir()
        lock = json.loads((ROOT / 'configs/runtime-lock.template.json').read_text())
        lock.update(model_sha256='1' * 64, server_sha256='2' * 64, server_version='fake b11382 11fe02151')
        (self.out / 'runtime-lock.json').write_text(json.dumps(lock))
        self.calls = []

    def fake(self, endpoint, body=None):
        self.calls.append(endpoint)
        return {'/lora-adapters': [], '/apply-template': {'prompt': 'synthetic'},
                '/tokenize': {'tokens': [1, 2]}, '/v1/chat/completions/input_tokens': {'input_tokens': 2},
                '/v1/chat/completions': {'choices': [{'message': {'content': '{"count":3}'}, 'finish_reason': 'stop'}],
                                         'usage': {'prompt_tokens': 2, 'completion_tokens': 5}}}[endpoint]

    def run_fake(self, **kwargs):
        return runner.run(self.payload, self.out, confirm_runtime=True, call=kwargs.pop('call', self.fake), **kwargs)

    def test_layout_equivalence_and_hashes(self):
        texts = []
        for cell in self.pack['requests']:
            text = cell['request']['messages'][1]['content']; texts.append(text)
            restored = dict((k, json.loads(v)) for k, v in (line.removeprefix('- ').split(' = ', 1) for line in text.splitlines() if line))
            self.assertEqual(restored, self.case)
            self.assertEqual(hashlib.sha256(builder.canonical(cell['request'])).hexdigest(), cell['request_sha256'])
        self.assertEqual(len(set(texts)), 3)

    def test_private_fields_rejected(self):
        for key in ('expected', 'tests', 'oracle', 'blind_mapping'):
            with self.assertRaises(ValueError): builder.build(dict(self.case, **{key: 'private'}))

    def test_strict_json_rejects_fences_duplicates_nonfinite(self):
        for raw in ('```json\n{}\n```', '{"x":1,"x":2}', '{"x":NaN}'):
            with self.assertRaises(ValueError): strict_json(raw)

    def test_numeric_schema_equivalence_not_boolean(self):
        self.assertTrue(evaluator.schema_same(3.0, 3, {'type': 'integer'}))
        self.assertFalse(evaluator.schema_same(True, 1, {'type': 'integer'}))

    def test_format_failure_not_semantic_success(self):
        result = evaluator.grade(self.case, self.oracle, '```json\n{"count":3}\n```')
        self.assertFalse(result['json_syntax']); self.assertIsNone(result['semantic_exact'])

    def test_exact_semantics(self):
        self.assertEqual(evaluator.grade(self.case, self.oracle, '{"count":3}')['semantic_exact'], 1)
        self.assertEqual(evaluator.grade(self.case, self.oracle, '{"count":2}')['semantic_exact'], 0)

    def test_ast_synthetic_function(self):
        spec = {'name': 'double', 'args': ['x'], 'cases': [[[2], 4], [[-3], -6]]}
        result = evaluator.evaluate_code('def double(x):\n return x * 2', spec)
        self.assertEqual(result['code_function'], 1)
        bad = evaluator.evaluate_code('def double(x):\n return __import__("os").system("echo unsafe")', spec)
        self.assertFalse(bad['ast_allowed'])

    def test_ast_validator_limit_separate(self):
        result = evaluator.evaluate_code('x' * 4001, {'name': 'double', 'args': ['x'], 'cases': [[[1], 2]]})
        self.assertIsNone(result['ast_allowed']); self.assertEqual(result['ast_failure_class'], 'validator_limit')

    def test_confirmation_required(self):
        with self.assertRaises(ValueError): runner.run(self.payload, self.out, call=self.fake)
        self.assertEqual(self.calls, [])

    def test_runtime_lock_required(self):
        (self.out / 'runtime-lock.json').unlink()
        with self.assertRaises(ValueError): self.run_fake()
        self.assertEqual(self.calls, [])

    def test_preflight_only_no_generation(self):
        state = self.run_fake(preflight_only=True)
        self.assertEqual(len(state['preflight']), 3)
        self.assertNotIn('/v1/chat/completions', self.calls)

    def test_completed_resume_no_duplicate_generation(self):
        state = self.run_fake(); self.assertEqual(len(state['records']), 3)
        self.calls.clear(); self.run_fake()
        self.assertNotIn('/v1/chat/completions', self.calls)

    def test_ambiguous_request_not_replayed(self):
        def fail(endpoint, body=None):
            if endpoint == '/v1/chat/completions': raise TimeoutError('synthetic')
            return self.fake(endpoint, body)
        with self.assertRaises(TimeoutError): self.run_fake(call=fail)
        self.calls.clear()
        with self.assertRaises(ValueError): self.run_fake()
        self.assertNotIn('/v1/chat/completions', self.calls)

    def test_token_mismatch_blocks_generation(self):
        def mismatch(endpoint, body=None):
            return {'input_tokens': 3} if endpoint.endswith('/input_tokens') else self.fake(endpoint, body)
        with self.assertRaises(ValueError): self.run_fake(call=mismatch)
        self.assertNotIn('/v1/chat/completions', self.calls)

    def test_context_overflow_blocks_generation(self):
        def overflow(endpoint, body=None):
            if endpoint == '/tokenize': return {'tokens': [1] * 4096}
            if endpoint.endswith('/input_tokens'): return {'input_tokens': 4096}
            return self.fake(endpoint, body)
        with self.assertRaises(ValueError): self.run_fake(call=overflow)
        self.assertNotIn('/v1/chat/completions', self.calls)

    def test_hash_change_blocks_generation(self):
        self.pack['requests'][0]['request']['temperature'] = 1
        self.payload.write_text(json.dumps(self.pack))
        with self.assertRaises(ValueError): self.run_fake()
        self.assertNotIn('/v1/chat/completions', self.calls)

    def test_lora_blocks_generation(self):
        def adapted(endpoint, body=None):
            return [{'id': 1}] if endpoint == '/lora-adapters' else self.fake(endpoint, body)
        with self.assertRaises(ValueError): self.run_fake(call=adapted)
        self.assertNotIn('/v1/chat/completions', self.calls)

    def test_checkpoint_scoring_and_payload_mismatch(self):
        state = self.run_fake()
        args = (state, self.payload.read_bytes(), {self.case['case_id']: self.case}, {self.case['case_id']: self.oracle})
        self.assertEqual([r['semantic_exact'] for r in score_checkpoint.score(*args)], [1, 1, 1])
        state['payload_sha256'] = '0' * 64
        with self.assertRaises(ValueError): score_checkpoint.score(*args)

    def test_notebooks_unexecuted_and_disabled(self):
        for path in (ROOT / 'notebooks').glob('*.ipynb'):
            notebook = json.loads(path.read_text())
            sources = '\n'.join(''.join(c['source']) for c in notebook['cells'])
            self.assertIn('ALLOW_EXECUTION = False', sources)
            self.assertIn('INCLUDE_EVALUATION=False', sources)
            for cell in notebook['cells']:
                if cell['cell_type'] == 'code':
                    self.assertIsNone(cell['execution_count']); self.assertEqual(cell['outputs'], [])
                    ast.parse(''.join(cell['source']))

    def test_summary_consistency_and_unknown_provenance(self):
        result = json.loads((ROOT / 'experiments/runs/gemma4-baseline-2026-10-04/summary.json').read_text())
        self.assertEqual(result['coverage']['cases'] * result['coverage']['prompt_layouts'], 216)
        self.assertIsNone(result['original_run_commit']); self.assertFalse(result['archive']['verified_locally'])
        self.assertEqual([(m.get('numerator'), m['denominator']) for m in result['metrics'][:3]], [(0, 216), (128, 162), (11, 18)])


if __name__ == '__main__': unittest.main()
