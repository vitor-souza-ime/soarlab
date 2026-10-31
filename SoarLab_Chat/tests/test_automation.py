"""Checks for automation and CSV aggregation using a TEST DOUBLE, not Soar data.

These tests certify orchestration only. Native Soar must be tested on Windows.
"""
import csv
import json
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

import run_all_tests as auto
from soarlab.questions import PROCEDURES
from soarlab.native import ROOT, safe


class FakeEngine:
    def __init__(self):
        self.lock = threading.RLock()
        self.facts = json.loads((ROOT/'data/semantic_seed.json').read_text(encoding='utf-8'))
        self.events = json.loads((ROOT/'data/episodic_seed.json').read_text(encoding='utf-8'))
        self.fact_index = {x['topic']: x for x in self.facts}
        self.procedures = {x['topic']: x for x in PROCEDURES}
        self.bad = False

    def _invoke(self, intent, topic, question, content=''):
        if intent == 'procedural':
            text = self.procedures[topic]['response']; kind = 'procedural'
        elif intent == 'semantic':
            text = self.fact_index[topic]['description']; kind = 'semantic'
        else:
            text = content; kind = 'episodic'
        if self.bad and topic == 'low-battery':
            text = 'WRONG'
        return {'kind': kind, 'topic': topic, 'status': 'found', 'text': safe(text, 800),
                'native_soar': True, 'latency_ms': 1, 'cycles': 3, 'rule': 'fake-unit-test',
                'smem_queries_delta': int(intent == 'semantic'),
                'epmem_queries_delta': int(intent == 'episodic-exact')}


class AutomationTests(unittest.TestCase):
    def test_audit_all_352_records_with_test_double(self):
        fake = FakeEngine()
        with tempfile.TemporaryDirectory() as tmp:
            summaries = auto.native_audit(fake, Path(tmp))
            self.assertEqual([summaries[k]['planned'] for k in ('procedural','semantic','episodic')],
                             [108, 124, 120])
            self.assertEqual(sum(s['failed'] for s in summaries.values()), 0)
            with open(Path(tmp)/'native_memory_audit.csv', newline='', encoding='utf-8-sig') as handle:
                rows = list(csv.DictReader(handle))
            self.assertEqual(len(rows), 352)
            self.assertTrue(all(r['result'] == 'PASS' for r in rows))

    def test_audit_failure_is_retained(self):
        fake = FakeEngine(); fake.bad = True
        with tempfile.TemporaryDirectory() as tmp:
            summaries = auto.native_audit(fake, Path(tmp))
            self.assertEqual(summaries['procedural']['failed'], 1)
            with open(Path(tmp)/'native_memory_audit.csv', newline='', encoding='utf-8-sig') as handle:
                failures = [r for r in csv.DictReader(handle) if r['result'] == 'FAIL']
            self.assertEqual(len(failures), 1)

    def test_aggregate_from_completed_runs_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            run_dir = base/'benchmark_example'; run_dir.mkdir()
            records=[dict(gold_memory=k,correct='1',latency_soar_ms='1.5',
                          decision_cycles='2', index=str(i))
                     for i,k in enumerate(('semantic','procedural','episodic'),1)]
            auto.write_csv(run_dir/'raw.csv',records)
            with patch.object(auto,'RESULTS',base):
                summary = auto.collect_runs(base,[
                    dict(seed=2026,status='completed',run_id='benchmark_example',
                         partial_dir='',observations=3,score=1,warmup_queries=48,error=''),
                    dict(seed=2027,status='failed',run_id='',partial_dir='',
                         observations=0,score='',warmup_queries=0,error='failed')],{})
            self.assertEqual(summary['total_observations'],3)
            self.assertEqual(summary['completed_runs'],1)
            self.assertEqual(len(summary['summary_by_memory']),3)
            self.assertTrue((base/'summary_by_memory.csv').exists())


if __name__ == '__main__':
    unittest.main()
