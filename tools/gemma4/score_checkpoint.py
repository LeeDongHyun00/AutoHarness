"""Offline explicit-input scorer; outputs must remain outside the repository."""
import argparse
import hashlib
import json
from pathlib import Path
from evaluator import grade
from build_payload import ROOT


def score(checkpoint, payload, cases, oracles):
    if checkpoint['payload_sha256'] != hashlib.sha256(payload).hexdigest():
        raise ValueError('Wrong payload version')
    pack = json.loads(payload)
    by_id = {cell['request_id']: cell for cell in pack['requests']}
    if len(by_id) != len(pack['requests']):
        raise ValueError('Duplicate request IDs')
    results = []
    for rid, record in checkpoint['records'].items():
        if rid not in by_id or record['request_sha256'] != by_id[rid]['request_sha256']:
            raise ValueError('Unplanned response')
        cell = by_id[rid]
        cid = cell['case_id']
        results.append({'request_id': rid, **grade(cases[cid], oracles[cid],
                       record.get('raw_text'), record['status'], record.get('finish_reason'))})
    return results


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('checkpoint', 'payload', 'cases', 'oracles', 'out'):
        parser.add_argument('--' + name, required=True, type=Path)
    args = parser.parse_args()
    if args.out.resolve().is_relative_to(ROOT):
        parser.error('Use evaluator-authorized storage outside this repository')
    read = lambda path: json.loads(path.read_text())
    results = score(read(args.checkpoint), args.payload.read_bytes(),
                    read(args.cases), read(args.oracles))
    with args.out.open('x') as output:
        json.dump(results, output, ensure_ascii=False, indent=2)
        output.write('\n')
