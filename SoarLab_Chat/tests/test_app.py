"""Static/parser/plot tests. These are NOT a substitute for the native Soar diagnostic."""
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from soarlab.questions import PARAPHRASE_TESTS,EXAMPLES,PROCEDURES,fold,topic_key,classify
from soarlab.benchmark import _graphs,_percentile,_schedule
from soarlab.native import safe

FACTS=json.loads((ROOT/'data/semantic_seed.json').read_text(encoding='utf8'))
EVENTS=json.loads((ROOT/'data/episodic_seed.json').read_text(encoding='utf8'))

class CorpusTests(unittest.TestCase):
    def test_at_least_100_per_memory(self):
        self.assertGreaterEqual(len(FACTS),100)
        self.assertGreaterEqual(len(EVENTS),100)
        self.assertGreaterEqual(len(PROCEDURES),100)
    def test_semantic_unique_keys(self):
        self.assertEqual(len(FACTS),len({x['topic'] for x in FACTS}))
    def test_episodic_distinct_events(self):
        self.assertEqual(len(EVENTS),len({x['description'] for x in EVENTS}))
        self.assertTrue(all(x['source']=='synthetic-pedagogical' for x in EVENTS))
        self.assertEqual(set(x['topic'] for x in EVENTS),
                         {'battery','obstacle','sensor','navigation','vision','actuator'})
    def test_rule_catalog_unique_keys(self):
        self.assertEqual(len(PROCEDURES),len({x['topic'] for x in PROCEDURES}))
    def test_native_soar_has_compiled_rule_for_each_procedure(self):
        rules=(ROOT/'agents/chat.soar').read_text(encoding='utf8')
        for p in PROCEDURES:
            self.assertIn(f'sp {{chat*procedural*{p["topic"]}',rules)
            self.assertIn(f'^topic {p["topic"]}',rules)
        self.assertEqual(rules.count('sp {'),len(PROCEDURES)+12)
    def test_native_memory_rules_exist(self):
        rules=(ROOT/'agents/chat.soar').read_text(encoding='utf8')
        for key in ('^store-new','^smem.command','^epmem.command','^retrieved','^reply'):
            self.assertIn(key,rules)
    def test_no_runtime_fallback(self):
        native=(ROOT/'soarlab/native.py').read_text(encoding='utf8')
        self.assertIn('import soar_sml as sml',native)
        self.assertIn('read-after-write',native)
    def test_english_ui_and_mobile(self):
        html=(ROOT/'templates/index.html').read_text(encoding='utf8')
        css=(ROOT/'static/style.css').read_text(encoding='utf8')
        self.assertIn('lang="en"',html)
        self.assertIn('name="viewport"',html)
        self.assertIn('@media(max-width:710px)',css)
    def test_questions_and_aliases_all_parse(self):
        failures=[]
        for q,m,t in PARAPHRASE_TESTS:
            p=classify(q,FACTS)
            if (p['intent'],p['topic'])!=(m,t):failures.append((q,p,m,t))
        self.assertFalse(failures,failures)
    def test_all_procedural_questions_parse(self):
        for p in PROCEDURES:
            result=classify(p['question'],FACTS)
            self.assertEqual((result['intent'],result['topic']),('procedural',p['topic']))
    def test_english_unknown_concept(self):
        result=classify('What is a tactile sensor array?',FACTS)
        self.assertEqual((result['intent'],result['topic']),('semantic','tactile-sensor-array'))
    def test_case_folding(self):
        self.assertEqual(fold('NAO ROBOT!'),'nao robot')
        self.assertEqual(topic_key('Tactile Sensor Array'),'tactile-sensor-array')
    def test_fixed_schedule(self):
        class E:history=[]
        schedule,n=_schedule(E(),'fixed',2026,3)
        self.assertEqual((len(schedule),n),(len(PARAPHRASE_TESTS)*3,len(PARAPHRASE_TESTS)))
    def test_session_schedule(self):
        class E:history=[{'question':'What is SLAM?','memory':'semantic','topic':'slam','status':'found'}]
        schedule,n=_schedule(E(),'session',2026,2)
        self.assertEqual((len(schedule),n),(2,1))
        self.assertEqual(schedule[0][1]['reference_status'],'found')
    def test_examples(self):self.assertGreaterEqual(len(EXAMPLES),10)
    def test_safe(self):self.assertEqual(safe('a|b'), 'a b')
    def test_percentile(self):self.assertEqual(_percentile([1,2,3],.5),2)
    def test_eight_graphs_full_and_session_single_memory(self):
        try:import matplotlib
        except ImportError:self.skipTest('Matplotlib is not available.')
        rows=[]
        for i,kind in enumerate(('semantic','procedural','episodic')):
            for j in range(2):
                rows.append({'gold_memory':kind,'latency_soar_ms':.3+i+j,
                    'latency_e2e_ms':.5+i+j,'correct':int(j==0),
                    'match_method':'semantic-alias','index':i*2+j,
                    'decision_cycles':j+1,'smem_queries_delta':int(kind=='semantic'),
                    'epmem_queries_delta':int(kind=='episodic')})
        with tempfile.TemporaryDirectory() as directory:
            names=_graphs(rows,Path(directory),'fixed')
            self.assertEqual(len(names),8)
            self.assertTrue(all((Path(directory)/x).stat().st_size>1000 for x in names))
        with tempfile.TemporaryDirectory() as directory:
            names=_graphs(rows[:2],Path(directory),'session')
            self.assertEqual(len(names),8)
            self.assertTrue(all((Path(directory)/x).stat().st_size>1000 for x in names))
    def test_graphs_compatible_with_matplotlib38(self):
        try:
            from matplotlib.axes import Axes
        except ImportError:self.skipTest('Matplotlib is not available.')
        original=Axes.boxplot
        def old_compat(self,*args,**kwargs):
            if 'tick_labels' in kwargs:
                raise TypeError("Axes.boxplot() got an unexpected keyword argument 'tick_labels'")
            return original(self,*args,**kwargs)
        rows=[]
        for i,kind in enumerate(('semantic','procedural','episodic')):
            rows.append({'gold_memory':kind,'latency_soar_ms':1+i,'latency_e2e_ms':2+i,
                        'correct':1,'match_method':'alias','index':i+1,
                        'decision_cycles':2,'smem_queries_delta':int(kind=='semantic'),
                        'epmem_queries_delta':int(kind=='episodic')})
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(Axes,'boxplot',old_compat):
                names=_graphs(rows,Path(directory),'fixed')
            self.assertEqual(len(names),8)

if __name__=='__main__':unittest.main()
