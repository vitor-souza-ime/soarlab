"""Run native Soar memory audit and reproducible English benchmark batches.

No mock agents or Python-answer fallback are allowed. Results are saved even
when an audit case or a benchmark block fails. The initial corpus is verified
at SoarChat startup and then exercised by the full native audit.

Examples:
    python run_all_tests.py --quick
    python run_all_tests.py --full
    python run_all_tests.py --seeds 2026,2027,2028 --repetitions 5
"""
from __future__ import annotations

import argparse
import csv
import importlib.metadata
import json
import platform
import statistics
import sys
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter

from soarlab.benchmark import RESULTS, run
from soarlab.native import SoarChat, NativeError, safe
from soarlab.questions import PROCEDURES, PARAPHRASE_TESTS, classify

COLUMNS = (
    'memory', 'record', 'topic', 'question', 'result', 'expected_status',
    'observed_status', 'expected_text', 'observed_text', 'soar_rule',
    'latency_soar_ms', 'decision_cycles', 'smem_queries_delta',
    'epmem_queries_delta', 'error',
)


def write_csv(path: Path, rows: list[dict], columns=None):
    columns = list(columns or (list(rows[0]) if rows else COLUMNS))
    with path.open('w', newline='', encoding='utf-8-sig') as file:
        writer = csv.DictWriter(file, columns, extrasaction='ignore')
        writer.writeheader()
        writer.writerows(rows)


def write_json(path: Path, data: dict):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, default=str), encoding='utf-8')


def native_audit(engine, destination: Path):
    """Exercise every native procedural production, semantic fact, and episode.

    The 120 seeded episodes are cued with their exact descriptions; this is an
    exact-cue native retrieval test, not an assessment of natural-language
    interpretation for 120 different experiences.
    """
    rows = []
    entries = []
    for item in PROCEDURES:
        entries.append(('procedural', item['topic'], item['question'], item['response'], ''))
    for item in engine.facts:
        entries.append(('semantic', item['topic'], f'What is {item["label"]}?', item['description'], ''))
    for index, item in enumerate(engine.events, 1):
        entries.append(('episodic', item['topic'], f'Exact episode cue #{index}', item['description'], item['description']))

    with engine.lock:
        for index, (memory, topic, question, expected, cue_content) in enumerate(entries, 1):
            row = dict.fromkeys(COLUMNS, '')
            row.update(memory=memory, record=index, topic=topic, question=question,
                       expected_status='found', expected_text=safe(expected, 800), result='FAIL')
            try:
                intent = 'episodic-exact' if memory == 'episodic' else memory
                response = engine._invoke(intent, topic, question, cue_content)
                row.update(
                    observed_status=response.get('status', ''),
                    observed_text=response.get('text', ''),
                    soar_rule=response.get('rule', ''),
                    latency_soar_ms=response.get('latency_ms', ''),
                    decision_cycles=response.get('cycles', ''),
                    smem_queries_delta=response.get('smem_queries_delta'),
                    epmem_queries_delta=response.get('epmem_queries_delta'),
                )
                if memory in ('procedural', 'semantic'):
                    predicted = classify(question, list(engine.fact_index.values()))
                    if (predicted['intent'], predicted['topic']) != (memory, topic):
                        raise RuntimeError('Question parser resolved to '
                                           f'{predicted["intent"]}/{predicted["topic"]}; expected {memory}/{topic}')
                valid = (response.get('native_soar') is True and
                         response.get('kind') == memory and
                         response.get('topic') == topic and
                         response.get('status') == 'found' and
                         response.get('text') == safe(expected, 800))
                if not valid:
                    raise RuntimeError('Native reply does not match expected kind/topic/status/text')
                row['result'] = 'PASS'
            except Exception as exc:
                row['error'] = f'{type(exc).__name__}: {exc}'[:1500]
            rows.append(row)
            if index % 25 == 0:
                write_csv(destination / 'native_memory_audit.csv', rows)
                print(f'Native audit: {index}/{len(entries)}; failed={sum(r["result"] != "PASS" for r in rows)}', flush=True)

    write_csv(destination / 'native_memory_audit.csv', rows)
    summary = {}
    for memory in ('procedural', 'semantic', 'episodic'):
        group = [r for r in rows if r['memory'] == memory]
        passed = sum(r['result'] == 'PASS' for r in group)
        summary[memory] = {'planned': len(group), 'passed': passed, 'failed': len(group) - passed,
                           'pass_rate': round(passed / len(group), 5) if group else None}
    write_json(destination / 'native_memory_audit_summary.json', summary)
    return summary


def warm_up(engine, seed=1000):
    """Run 48 native queries once without including them in measured CSVs."""
    from soarlab.benchmark import _schedule
    schedule, _ = _schedule(engine, 'fixed', seed, 1)
    with engine.lock:
        for _, entry in schedule:
            parsed = classify(entry['question'], list(engine.fact_index.values()))
            if (parsed['intent'], parsed['topic']) != (entry['reference_memory'], entry['reference_topic']):
                raise RuntimeError('Warm-up parser failed: ' + entry['question'])
            result = engine._invoke(parsed['intent'], parsed['topic'], entry['question'])
            if result.get('status') != 'found' or result.get('kind') != entry['reference_memory']:
                raise RuntimeError('Warm-up native retrieval failed: ' + entry['question'])
    return len(schedule)


def collect_runs(dirpath: Path, runs: list[dict], corpus: dict):
    combined = []
    for result in runs:
        if result['status'] != 'completed' or not result.get('run_id'):
            continue
        raw_path = RESULTS / result['run_id'] / 'raw.csv'
        if not raw_path.exists():
            continue
        with raw_path.open('r', newline='', encoding='utf-8-sig') as file:
            for row in csv.DictReader(file):
                combined.append({'run_id': result['run_id'], 'seed': result['seed'], **row})
    if combined:
        write_csv(dirpath / 'combined_raw.csv', combined)

    by_kind = []
    for memory in ('procedural', 'semantic', 'episodic'):
        sample = [r for r in combined if r.get('gold_memory') == memory]
        if not sample:
            by_kind.append({'memory': memory, 'n': 0, 'correct': 0,
                            'accuracy': '', 'median_ms': '', 'p95_ms': '',
                            'mean_ms': '', 'mean_cycles': ''})
            continue
        latencies = sorted(float(r['latency_soar_ms']) for r in sample)
        position = (len(latencies) - 1) * .95
        lower = int(position)
        upper = min(lower + 1, len(latencies) - 1)
        p95 = latencies[lower] + (latencies[upper] - latencies[lower]) * (position - lower)
        ncorrect = sum(int(r['correct']) for r in sample)
        by_kind.append({'memory': memory, 'n': len(sample), 'correct': ncorrect,
                        'accuracy': round(ncorrect / len(sample), 5),
                        'median_ms': round(statistics.median(latencies), 5),
                        'p95_ms': round(p95, 5),
                        'mean_ms': round(statistics.mean(latencies), 5),
                        'mean_cycles': round(statistics.mean(float(r['decision_cycles']) for r in sample), 5)})
    write_csv(dirpath / 'summary_by_memory.csv', by_kind)
    write_csv(dirpath / 'run_index.csv', runs, columns=['seed', 'status', 'run_id', 'partial_dir', 'observations', 'score', 'warmup_queries', 'error'])
    return {'completed_runs': sum(r['status'] == 'completed' for r in runs),
            'total_observations': len(combined), 'summary_by_memory': by_kind}


def execute(args, factory=SoarChat, benchmark=run):
    if args.quick:
        seeds = [2026]
        repetitions = 1
    elif args.full:
        seeds = [2026, 2027, 2028, 2029, 2030]
        repetitions = 15
    else:
        seeds = [int(part.strip()) for part in args.seeds.split(',') if part.strip()]
        repetitions = args.repetitions
    if not seeds or len(set(seeds)) != len(seeds):
        raise ValueError('Provide at least one unique seed.')
    if not 1 <= repetitions <= 15:
        raise ValueError('Repetitions must be from 1 to 15.')

    outdir = RESULTS / ('auto_'+datetime.now().strftime('%Y%m%d_%H%M%S_%f'))
    outdir.mkdir(parents=True, exist_ok=False)
    try:
        pkg_version = importlib.metadata.version('soar-sml')
    except importlib.metadata.PackageNotFoundError:
        pkg_version = 'not installed'
    metadata = {
        'status': 'running',
        'time_utc': datetime.now(timezone.utc).isoformat(),
        'platform': platform.platform(), 'python': sys.version,
        'soar_sml_distribution': pkg_version,
        'mode': 'fixed', 'seeds': seeds, 'repetitions': repetitions,
        'target_benchmark_observations': len(seeds) * len(PARAPHRASE_TESTS) * repetitions,
        'native_only': True,
        'startup_corpus_validation': {}, 'audit': {}, 'runs': [],
        'notes': [
            'Every seed is measured in a new SoarChat/native kernel instance.',
            'Each seed uses the same current JSON seed corpus and learned journals.',
            'One 48-query warm-up block is excluded from measured rows for each seed.',
            'Paraphrase interpretation is Python-based; cognitive replies come from native Soar.',
            'Native episodic audit is exact-cue verification, not 120 natural language queries.',
            'No human learning outcomes are measured.',
        ],
    }
    write_json(outdir / 'automation_manifest.json', metadata)
    failed = False
    # Audit: a separate kernel, and all 352 records are tested at native level.
    engine = None
    try:
        print('Loading native Soar to verify 124 SMem facts and 120 EpMem episodes...', flush=True)
        engine = factory()
        state = engine.state()
        metadata['startup_corpus_validation'] = state.get('native_verifications', {})
        metadata['audit'] = native_audit(engine, outdir)
        failed = any(row['failed'] for row in metadata['audit'].values())
    except Exception as exc:
        metadata['audit_error'] = f'{type(exc).__name__}: {exc}'
        failed = True
        print('Native memory audit failed:', exc, flush=True)
    finally:
        if engine is not None:
            engine.close()
        write_json(outdir / 'automation_manifest.json', metadata)

    for seed in seeds:
        record = {'seed': seed, 'status': 'failed', 'run_id': '', 'partial_dir': '', 'observations': 0,
                  'score': '', 'warmup_queries': 0, 'error': ''}
        instance = None
        try:
            print(f'Benchmark seed={seed}: initializing fresh native kernel...', flush=True)
            instance = factory()
            record['warmup_queries'] = warm_up(instance)
            response = benchmark(instance, repetitions=repetitions, seed=seed, mode='fixed')
            record.update(status='completed', run_id=response['run_id'],
                          observations=response['n'], score=response['accuracy'])
            print(f'Benchmark seed={seed}: {record["observations"]} native observations saved.', flush=True)
        except Exception as exc:
            failed = True
            record['error'] = f'{type(exc).__name__}: {exc}'[:3000]
            if getattr(exc, 'output_dir', None):
                record['partial_dir'] = str(exc.output_dir)
            print(f'Benchmark seed={seed}: FAILED — {exc}', flush=True)
        finally:
            if instance is not None:
                instance.close()
            metadata['runs'].append(record)
            write_json(outdir / 'automation_manifest.json', metadata)

    totals = collect_runs(outdir, metadata['runs'], metadata['startup_corpus_validation'])
    metadata.update(totals)
    metadata['status'] = ('failed' if failed else 'completed')
    write_json(outdir / 'automation_manifest.json', metadata)
    print('\nResults:', outdir)
    print('Native memory audit:', outdir / 'native_memory_audit.csv')
    print('Run index:', outdir / 'run_index.csv')
    print('Combined observations:', totals['total_observations'])
    print('Overall status:', metadata['status'].upper())
    return 1 if failed else 0


def main():
    parser = argparse.ArgumentParser(description='Automated native SoarLab memory tests and reproducible English benchmarks')
    selection = parser.add_mutually_exclusive_group()
    selection.add_argument('--quick', action='store_true', help='One seed, one repetition (48 prompts), full 352-record audit')
    selection.add_argument('--full', action='store_true', help='Five seeds with 15 repetitions each (3,600 measured queries)')
    parser.add_argument('--seeds', default='2026,2027,2028', help='Comma-separated integer seeds in custom mode')
    parser.add_argument('--repetitions', type=int, default=3, help='Queries per prompt in custom mode, range 1..15')
    return execute(parser.parse_args())


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (ValueError, NativeError) as exc:
        print('ERROR:', exc, file=sys.stderr)
        raise SystemExit(2)
