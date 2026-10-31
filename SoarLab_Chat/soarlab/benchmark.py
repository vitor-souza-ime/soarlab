"""Measured native Soar queries and reproducible plots (no mock results).

Fixed mode: prespecified independently authored intent/topic references.
Session mode: replays the user's recorded questions; labels are parser-derived,
so the agreement metric is NOT an independently established accuracy score.
"""
from __future__ import annotations
import csv
import json
import random
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean, median
from time import perf_counter_ns
from .questions import PARAPHRASE_TESTS, classify
from .native import ROOT

RESULTS = ROOT / 'results'
KINDS=('semantic','procedural','episodic')
LABELS=('Semantic','Procedural','Episodic')

def _percentile(values,p):
    if not values:return None
    ordered=sorted(values);position=(len(ordered)-1)*p
    a=int(position);b=min(a+1,len(ordered)-1)
    return round(ordered[a]+(ordered[b]-ordered[a])*(position-a),5)

def _save_csv(rows,path):
    if not rows:return
    with path.open('w',newline='',encoding='utf-8-sig') as output:
        writer=csv.DictWriter(output,fieldnames=list(rows[0]))
        writer.writeheader();writer.writerows(rows)

def _schedule(engine,mode,seed,repetitions):
    if mode=='fixed':
        questions=[{'question':q,'reference_memory':m,'reference_topic':t,
                    'reference_status':'found'} for q,m,t in PARAPHRASE_TESTS]
    elif mode=='session':
        questions=[{'question':r['question'],'reference_memory':r['memory'],
                    'reference_topic':r['topic'],'reference_status':r['status']}
                   for r in engine.history[-100:]
                   if r['memory'] in KINDS and r.get('question')]
        if not questions:raise ValueError('No session questions yet. Ask the agent a few questions first.')
    else:raise ValueError('Mode must be fixed or session.')
    randomizer=random.Random(int(seed));schedule=[]
    for rep in range(1,repetitions+1):
        shuffled=list(questions);randomizer.shuffle(shuffled)
        for q in shuffled:schedule.append((rep,q))
    return schedule,len(questions)

def run(engine,repetitions=3,seed=2026,mode='fixed'):
    repetitions=int(repetitions)
    if not 1<=repetitions<=15:raise ValueError('Repetitions must be between 1 and 15.')
    if mode not in ('fixed','session'):raise ValueError('Mode must be fixed or session.')
    output=RESULTS/('benchmark_'+datetime.now().strftime('%Y%m%d_%H%M%S_%f'))
    output.mkdir(exist_ok=True,parents=True)
    rows=[]
    meta={'run_id':output.name,'status':'running','mode':mode,'repetitions':repetitions,
          'random_seed':int(seed),'timestamp_utc':datetime.now(timezone.utc).isoformat(),
          'platform':'Native Soar 9.6.5 SML; Python intent/slot parser',
          'corpus':{'procedural_productions':engine.startup_checks.get('procedural_productions',0),
                    'semantic_verified':engine.startup_checks['semantic'],
                    'episodic_verified':engine.startup_checks['episodic']},
          'reference_source':('predefined human-authored intent/topic labels' if mode=='fixed'
                              else 'original session predictions, not independent ground truth'),
          'warnings':['Episodic seed events are synthetic pedagogical records, not field observations.',
                      'Paraphrase classification is performed in Python, not Soar.',
                      'SML wrapper and telemetry are included in measured Soar response time.',
                      'Within-process measurements may exhibit activation and caching effects.',
                      'No claim about human learning is supported by this benchmark.'],
          'native_soar':True}
    try:
        with engine.lock:
            schedule,n_questions=_schedule(engine,mode,seed,repetitions)
            meta['questions_per_repetition']=n_questions
            meta['planned_rows']=len(schedule)
            facts=list(engine.fact_index.values())
            for index,(rep,entry) in enumerate(schedule,1):
                question=entry['question']
                t_start=perf_counter_ns()
                p_start=perf_counter_ns()
                parsed=classify(question,facts)
                parse_ms=(perf_counter_ns()-p_start)/1e6
                if parsed['intent']=='unknown':
                    raise RuntimeError('Parser rejected a scheduled question: '+question)
                reply=engine._invoke(parsed['intent'],parsed['topic'],question)
                if parsed['intent']=='semantic' and reply['smem_queries_delta'] is None:
                    raise RuntimeError('SMem telemetry is unavailable for a semantic query.')
                if parsed['intent']=='episodic' and reply['epmem_queries_delta'] is None:
                    raise RuntimeError('EpMem telemetry is unavailable for an episodic query.')
                full_ms=(perf_counter_ns()-t_start)/1e6
                if mode=='fixed':
                    correct=(parsed['intent']==entry['reference_memory'] and
                             parsed['topic']==entry['reference_topic'] and
                             reply['kind']==entry['reference_memory'] and reply['status']=='found')
                else:
                    correct=(parsed['intent']==entry['reference_memory'] and
                             parsed['topic']==entry['reference_topic'] and
                             reply['kind']==entry['reference_memory'] and
                             reply['status']==entry['reference_status'])
                rows.append({'index':index,'repetition':rep,'mode':mode,'question':question,
                    'gold_memory':entry['reference_memory'],'gold_topic':entry['reference_topic'],
                    'reference_status':entry['reference_status'],
                    'pred_memory':parsed['intent'],'pred_topic':parsed['topic'],
                    'match_method':parsed['method'],'match_confidence':parsed['confidence'],
                    'native_status':reply['status'],'correct':int(correct),
                    'latency_soar_ms':reply['latency_ms'],'parse_ms':round(parse_ms,5),
                    'latency_e2e_ms':round(full_ms,5),'decision_cycles':reply['cycles'],
                    'smem_queries_delta':reply['smem_queries_delta'],
                    'epmem_queries_delta':reply['epmem_queries_delta'],
                    'episode_id':reply['episode_id'],'native_soar':reply['native_soar']})
        meta['status']='completed';meta['rows']=len(rows)
        meta['correct']=sum(r['correct'] for r in rows)
        meta['accuracy']=round(meta['correct']/len(rows),5) if rows else None
        meta['score_name']='fixed-set accuracy' if mode=='fixed' else 'session replay agreement'
        meta['summary']={}
        for kind in KINDS:
            group=[r for r in rows if r['gold_memory']==kind]
            latency=[r['latency_soar_ms'] for r in group]
            meta['summary'][kind]={'n':len(group),
                'mean_ms':round(mean(latency),5) if latency else None,
                'median_ms':round(median(latency),5) if latency else None,
                'p95_ms':_percentile(latency,.95),
                'score':round(sum(r['correct'] for r in group)/len(group),5) if group else None}
        meta['graphics']=_graphs(rows,output,mode=mode)
    except Exception as exc:
        meta['status']='failed';meta['error']=f'{type(exc).__name__}: {exc}';meta['rows']=len(rows)
        raise BenchmarkError(f'Benchmark failed after {len(rows)} completed observations: {exc}. '
                             f'Partial records saved in {output}.',output) from exc
    finally:
        _save_csv(rows,output/'raw.csv')
        (output/'metadata.json').write_text(json.dumps(meta,ensure_ascii=False,indent=2),encoding='utf8')
    return {'run_id':output.name,'n':len(rows),'accuracy':meta['accuracy'],
            'mode':mode,'score_name':meta['score_name'],'summary':meta['summary'],
            'files':['raw.csv','metadata.json']+meta['graphics']}

class BenchmarkError(RuntimeError):
    def __init__(self,message,output_dir):
        super().__init__(message);self.output_dir=output_dir

def _graphs(rows,out,mode='fixed'):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import numpy as np
    out=Path(out);out.mkdir(parents=True,exist_ok=True)
    buckets={k:[r for r in rows if r['gold_memory']==k] for k in KINDS}
    saved=[]
    def graph(filename,title,callback):
        fig,ax=plt.subplots(figsize=(8,4.8))
        callback(ax)
        ax.set_title(title);fig.tight_layout()
        fig.savefig(out/filename,dpi=160,bbox_inches='tight')
        plt.close(fig);saved.append(filename)
    def boxplot(ax,field,ylabel):
        observed=[(label,[r[field] for r in buckets[k]]) for k,label in zip(KINDS,LABELS) if buckets[k]]
        if observed:
            ax.boxplot([v for _,v in observed]) # Works with matplotlib 3.8.x and newer
            ax.set_xticks(range(1,len(observed)+1),[name for name,_ in observed])
        ax.set_ylabel(ylabel);ax.grid(axis='y',alpha=.20)
    graph('01_latency_distribution.png','Soar response latency distribution',
          lambda ax:boxplot(ax,'latency_soar_ms','Native Soar response time (ms)'))
    def medians(ax):
        selected=[(k,label) for k,label in zip(KINDS,LABELS) if buckets[k]]
        x=np.arange(len(selected));width=.36
        ax.bar(x-width/2,[median([r['latency_soar_ms'] for r in buckets[k]]) for k,_ in selected],width=width,label='Median')
        ax.bar(x+width/2,[_percentile([r['latency_soar_ms'] for r in buckets[k]],.95) for k,_ in selected],width=width,label='95th percentile')
        ax.set_xticks(x,[label for _,label in selected]);ax.set_ylabel('Time (ms)');ax.legend()
    graph('02_median_p95.png','Median and P95 Soar response latency',medians)
    def accuracy(ax):
        selected=[(k,label) for k,label in zip(KINDS,LABELS) if buckets[k]]
        vals=[100*mean([r['correct'] for r in buckets[k]]) for k,_ in selected]
        ax.bar([label for _,label in selected],vals);ax.set_ylim(0,110)
        ax.set_ylabel('Accuracy (%)' if mode=='fixed' else 'Replay agreement (%)')
        for i,v in enumerate(vals):ax.text(i,v+2,f'{v:.1f}%',ha='center')
    graph('03_accuracy_or_agreement.png',
          'Fixed benchmark accuracy' if mode=='fixed' else 'Session replay agreement (non-independent labels)',accuracy)
    def scatter(ax):
        for k,label in zip(KINDS,LABELS):
            group=buckets[k]
            if group:ax.scatter([r['index'] for r in group],[r['latency_soar_ms'] for r in group],s=16,label=label)
        ax.set_xlabel('Query sequence index');ax.set_ylabel('Latency (ms)')
        if any(buckets.values()):ax.legend()
    graph('04_latency_over_queries.png','Soar latency over successive queries',scatter)
    def counters(ax):
        x=np.arange(len(KINDS));width=.36
        sm=[mean([r['smem_queries_delta'] or 0 for r in buckets[k]]) if buckets[k] else 0 for k in KINDS]
        ep=[mean([r['epmem_queries_delta'] or 0 for r in buckets[k]]) if buckets[k] else 0 for k in KINDS]
        ax.bar(x-width/2,sm,width,label='SMem queries');ax.bar(x+width/2,ep,width,label='EpMem queries')
        ax.set_xticks(x,LABELS);ax.set_ylabel('Native query-counter increments / request');ax.legend()
    graph('05_native_memory_queries.png','Native memory query counter changes',counters)
    def paraphrases(ax):
        groups=sorted(set(r['match_method'] for r in rows))
        val=[100*mean([r['correct'] for r in rows if r['match_method']==method]) for method in groups]
        ax.barh(groups,val);ax.set_xlim(0,110)
        ax.set_xlabel('Accuracy (%)' if mode=='fixed' else 'Replay agreement (%)')
    graph('06_paraphrase_accuracy.png','Controlled parser method performance',paraphrases)
    graph('07_soar_decision_cycles.png','Soar decision cycles to reply',
          lambda ax:boxplot(ax,'decision_cycles','Decision cycles per query'))
    def time(ax):
        selected=[(k,label) for k,label in zip(KINDS,LABELS) if buckets[k]]
        vals=[mean([r['latency_e2e_ms'] for r in buckets[k]]) for k,_ in selected]
        internal=[mean([r['latency_soar_ms'] for r in buckets[k]]) for k,_ in selected]
        x=np.arange(len(selected));width=.36
        ax.bar(x-width/2,vals,width,label='Python + SML end to end')
        ax.bar(x+width/2,internal,width,label='SML/Soar call')
        ax.set_xticks(x,[v for _,v in selected]);ax.set_ylabel('Mean latency (ms)');ax.legend()
    graph('08_e2e_vs_soar.png','End-to-end versus SML/Soar latency',time)
    return saved
