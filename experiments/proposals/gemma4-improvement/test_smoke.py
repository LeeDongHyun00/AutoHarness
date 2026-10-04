import copy
import json
from pathlib import Path
import socket
import tempfile
import unittest
from unittest.mock import patch
import smoke


class SmokeTests(unittest.TestCase):
    def setUp(self):
        self.guard = patch.object(socket, 'socket', side_effect=AssertionError('Network forbidden'))
        self.guard.start(); self.addCleanup(self.guard.stop)
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.example = json.loads((smoke.HERE / 'synthetic-smoke.json').read_text())
        self.arm = smoke.DESIGN['arms'][-1]
        self.good = json.dumps(self.example['public_good_response'])

    def test_eight_factorial_arms_not_run(self):
        arms = smoke.DESIGN['arms']
        self.assertEqual(len({(a['json_schema'], a['file_id_validation'], a['bounded_repair']) for a in arms}), 8)
        self.assertEqual(smoke.DESIGN['status'], 'NOT_RUN'); self.assertIsNone(smoke.DESIGN['results'])

    def test_requests_preserve_task_model_budget(self):
        for arm in smoke.DESIGN['arms']:
            req = smoke.request(self.example, arm)
            self.assertEqual(req['max_tokens'], 384); self.assertEqual(req['temperature'], 0)
            self.assertEqual(json.loads(req['messages'][1]['content'])['task'], self.example['task'])
            self.assertEqual('response_format' in req, arm['json_schema'])
            if arm['json_schema']:
                field = req['response_format']['json_schema']['schema']['properties']['plan']['items']['properties']['file_id']
                self.assertEqual('enum' in field, arm['file_id_validation'])

    def test_good_public_plan(self):
        self.assertEqual(smoke.inspect(self.good, self.example, self.root), [])

    def test_raw_fence_is_failure(self):
        self.assertEqual(smoke.inspect('```json\n' + self.good + '\n```', self.example, self.root), ['invalid_json'])

    def test_unknown_id(self):
        raw = json.dumps({'plan': [{'file_id': 'INVENTED', 'action': 'read'}]})
        self.assertEqual(smoke.inspect(raw, self.example, self.root), ['unknown_file_id'])

    def test_absolute_traversal_and_windows_path(self):
        for value in ('/etc/passwd', '../escape', 'docs/../../escape', 'C:\\secret', '.'):
            with self.assertRaises(ValueError): smoke.resolve_file('DOC', {'DOC': value}, self.root)

    def test_symlink_escape(self):
        (self.root / 'escape').symlink_to(self.root.parent, target_is_directory=True)
        with self.assertRaises(ValueError): smoke.resolve_file('DOC', {'DOC': 'escape/secret'}, self.root)

    def test_max_one_repair(self):
        self.assertTrue(smoke.permit_repair(self.arm, ['invalid_json'], 1, 384, 100, 150, 1))
        self.assertFalse(smoke.permit_repair(self.arm, ['invalid_json'], 2, 400, 100, 150, 2))

    def test_budget_and_ambiguous_stop(self):
        base = dict(arm=self.arm, errors=['invalid_json'], calls=1, output_tokens=384, input_tokens=100, next_input_tokens=150, elapsed=1)
        for change in ({'output_tokens': 385}, {'next_input_tokens': 4096}, {'input_tokens': 6656}, {'elapsed': 120}, {'ambiguous': True}):
            self.assertFalse(smoke.permit_repair(**dict(base, **change)))
        for change in ({'input_tokens': None}, {'next_input_tokens': True}, {'elapsed': float('nan')}):
            with self.assertRaises(ValueError): smoke.permit_repair(**dict(base, **change))

    def test_no_repair_when_pass_or_disabled(self):
        self.assertFalse(smoke.permit_repair(self.arm, [], 1, 20, 100, 150, 1))
        arm = dict(self.arm, bounded_repair=False)
        self.assertFalse(smoke.permit_repair(arm, ['invalid_json'], 1, 20, 100, 150, 1))
        with self.assertRaises(ValueError): smoke.request(self.example, arm, 'bad', ['invalid_json'])

    def test_feedback_contains_only_public_codes(self):
        req = smoke.request(self.example, self.arm, 'bad', ['invalid_json'])
        self.assertIn('invalid_json', req['messages'][-1]['content'])
        with self.assertRaises(ValueError): smoke.request(self.example, self.arm, 'bad', ['secret expected value'])

    def test_file_feedback_factor_is_separate(self):
        arm = dict(self.arm, file_id_validation=False)
        self.assertFalse(smoke.permit_repair(arm, ['unknown_file_id'], 1, 20, 100, 150, 1))
        self.assertTrue(smoke.permit_repair(arm, ['invalid_json'], 1, 20, 100, 150, 1))

    def test_synthetic_repair_sequence_without_model(self):
        errors = smoke.inspect('bad', self.example, self.root)
        self.assertTrue(smoke.permit_repair(self.arm, errors, 1, 20, 100, 150, 1))
        req = smoke.request(self.example, self.arm, 'bad', errors)
        self.assertEqual(len(req['messages']), 4)
        self.assertEqual(smoke.inspect(self.good, self.example, self.root), [])
        # These are supplied synthetic strings, not generated or measured results.
        template = json.loads((smoke.HERE / 'result.template.json').read_text())
        self.assertEqual(template['status'], 'NOT_RUN'); self.assertEqual(template['attempts'], [])


if __name__ == '__main__': unittest.main()
