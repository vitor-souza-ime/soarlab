"""Native Soar SML 9.6.5 driver. No Python cognitive decision fallback.

All facts are considered learned only after a native SMem read-after-write check.
Each educational event is verified through native EpMem exact cue retrieval.
"""
from __future__ import annotations
import json
import re
import threading
from pathlib import Path
from time import perf_counter_ns
from .questions import classify, topic_key, PROCEDURES

ROOT=Path(__file__).resolve().parents[1]
SEMANTIC_SEED=ROOT/'data'/'semantic_seed.json'
EPISODIC_SEED=ROOT/'data'/'episodic_seed.json'
FACT_JOURNAL=ROOT/'data'/'learned_facts.jsonl'
EVENT_JOURNAL=ROOT/'data'/'learned_experiences.jsonl'
RULES=ROOT/'agents'/'chat.soar'

class NativeError(RuntimeError):
    pass

def safe(text,limit=700):
    return ' '.join(str(text).replace('\x00',' ').replace('|',' ').split())[:limit]

def counter_num(raw):
    match=re.search(r'(-?\d+)\s*$',str(raw).strip())
    return int(match.group(1)) if match else None

def difference(before,after,key):
    a,b=before.get(key),after.get(key)
    return b-a if a is not None and b is not None else None

def journal_rows(path):
    if not path.exists(): return []
    return [json.loads(line) for line in path.read_text(encoding='utf8').splitlines() if line.strip()]

def append_journal(path,row):
    path.parent.mkdir(exist_ok=True,parents=True)
    with path.open('a',encoding='utf8') as f:
        f.write(json.dumps(row,ensure_ascii=False)+'\n')

class SoarChat:
    def __init__(self):
        self.lock=threading.RLock()
        self.kernel=None
        self.agent=None
        self.request_wme=None
        self.sequence=0
        self.history=[]
        self.facts=json.loads(SEMANTIC_SEED.read_text(encoding='utf8'))
        self.events=json.loads(EPISODIC_SEED.read_text(encoding='utf8'))
        self.user_facts=journal_rows(FACT_JOURNAL)
        self.user_events=journal_rows(EVENT_JOURNAL)
        self.fact_index={x['topic']:x for x in self.facts}
        self.startup_checks={'semantic':0,'episodic':0,'procedural_productions':len(PROCEDURES)}
        try:
            try:
                import soar_sml as sml
            except (OSError,ImportError) as exc:
                raise NativeError('Failed to import soar_sml. Check: '
                    'python -m pip show soar-sml; Python version and architecture. '
                    f'Details: {exc}') from exc
            self.kernel=sml.Kernel.CreateKernelInNewThread()
            if not self.kernel or self.kernel.HadError():
                raise NativeError('Failed to initialize native Soar kernel.')
            self.agent=self.kernel.CreateAgent('soarlab_chat_v2')
            if not self.agent or self.agent.HadError():
                raise NativeError('Failed to create Soar agent.')
            for command in ('smem --enable','epmem --enable','epmem --set learning on',
                            'epmem --set trigger dc'):
                self.cli(command)
            if not self.agent.LoadProductions(str(RULES)) or self.agent.HadError():
                raise NativeError('Failed to load agents/chat.soar: '
                        +str(self.agent.GetLastErrorDescription()))
            self.input_link=self.agent.GetInputLink()
            if not self.input_link: raise NativeError('SML input link is unavailable.')
            for index,item in enumerate(self.facts+self.user_facts,1):
                self._install_fact(item)
                if index % 25 == 0: print(f'Native SMem read-back: {index} concepts verified',flush=True)
                self.fact_index[item['topic']]=item
            for index,item in enumerate(self.events+self.user_events,1):
                self._install_event(item)
                if index % 25 == 0: print(f'Native EpMem read-back: {index} episodes verified',flush=True)
        except Exception:
            self.close()
            raise

    def cli(self,cmd):
        raw=str(self.agent.ExecuteCommandLine(cmd))
        if self.agent.HadError() or re.search(r'(?im)^\s*(?:error:|unknown command|invalid command|syntax error)',raw):
            raise NativeError(f'Soar command {cmd!r} failed: {raw[:600]} '
                              +str(self.agent.GetLastErrorDescription()))
        return raw

    def _stat(self,cmd):
        try: return counter_num(self.cli(cmd))
        except Exception: return None

    def stats(self):
        return {'smem_queries':self._stat('smem --stats queries'),
                'smem_stores':self._stat('smem --stats stores'),
                'epmem_queries':self._stat('epmem --stats queries'),
                'episode_id':self._stat('epmem --stats time')}

    def _invoke(self,intent,topic,question,content='',cycles=50):
        """Write input WMEs, RunSelf, read ^reply from native Soar output-link only."""
        if self.request_wme is not None:
            self.agent.DestroyWME(self.request_wme)
            if self.agent.HadError(): raise NativeError('Failed to remove the preceding input request.')
            self.request_wme=None
        self.sequence+=1
        seq=self.sequence
        req=self.agent.CreateIdWME(self.input_link,'request')
        if not req: raise NativeError('CreateIdWME ^request failed.')
        self.request_wme=req
        fields=[('seq',seq),('intent',intent),('topic',topic),('question',safe(question,350)),
                ('content',safe(content,800))]
        for name,value in fields:
            wme=(self.agent.CreateIntWME(req,name,value) if name=='seq'
                 else self.agent.CreateStringWME(req,name,value))
            if wme is None: raise NativeError(f'CreateWME failed: {name}')
        self.agent.Commit()
        self.agent.ClearOutputLinkChanges()
        prior=self.stats()
        t0=perf_counter_ns()
        command=None
        executed=0
        for executed in range(1,cycles+1):
            self.agent.RunSelf(1)
            if self.agent.HadError():
                raise NativeError('RunSelf(1) failed: '+str(self.agent.GetLastErrorDescription()))
            for j in range(self.agent.GetNumberCommands()):
                cmd=self.agent.GetCommand(j)
                if cmd.GetCommandName()=='reply' and cmd.GetParameterValue('seq')==str(seq):
                    command=cmd
                    break
            if command is not None: break
        elapsed=(perf_counter_ns()-t0)/1e6
        after=self.stats()
        if command is None:
            diagnostics=[]
            for cli in ('print --depth 6 s1','production firing-counts','smem --stats','epmem --stats'):
                try: diagnostics.append('['+cli+']\n'+self.cli(cli)[:2500])
                except Exception as exc: diagnostics.append('['+cli+'] '+str(exc))
            raise NativeError(f'Soar agent produced no ^reply for seq={seq} intent={intent} topic={topic} '
                    f'within {cycles} decision cycles.\n'+ '\n'.join(diagnostics))
        result={k:str(command.GetParameterValue(k) or '') for k in
                ('kind','status','topic','text','rule')}
        command.AddStatusComplete()
        if result['topic']!=topic:
            raise NativeError(f'Unexpected Soar reply: requested {topic}, received {result["topic"]}')
        result.update({'seq':seq,'latency_ms':round(elapsed,5),'cycles':executed,
                       'smem_queries_delta':difference(prior,after,'smem_queries'),
                       'epmem_queries_delta':difference(prior,after,'epmem_queries'),
                       'episode_id':after['episode_id'],'native_soar':True})
        if intent=='semantic' and result['status'] in ('found','unknown'):
            n=result['smem_queries_delta']
            if n is not None and n<1: raise NativeError('Soar replied but SMem did not register a new query.')
        if intent in ('episodic','episodic-exact'):
            n=result['epmem_queries_delta']
            if n is not None and n<1: raise NativeError('Soar replied but EpMem did not register a new query.')
        return result

    def _install_fact(self,item):
        topic=item['topic']; desc=safe(item['description'],800)
        r=self._invoke('teach',topic,'seed-or-learn',desc)
        if r['status']!='stored':
            raise NativeError(f'SMem store was not confirmed for topic={topic}: {r}')
        verified=self._invoke('semantic',topic,'read-after-write')
        if verified['status']!='found' or verified['text']!=desc:
            raise NativeError(f'SMem read-after-write failed for {topic}: '
                f'status={verified["status"]}; returned_text={verified["text"][:120]!r}. '
                'Not marked as learned. Inspect productions and SMem state.')
        self.startup_checks['semantic']+=1
        return verified

    def _install_event(self,item):
        topic=item['topic']; desc=safe(item['description'],800)
        r=self._invoke('experience',topic,'episode-seeding',desc)
        if r['status']!='presented':
            raise NativeError(f'The agent did not receive an EpMem event: {topic} {r}')
        # EpMem records during cognitive cycles rather than HTTP reception.
        self.agent.RunSelf(3)
        checked=self._invoke('episodic-exact',topic,'episode-read-after-write',desc)
        if checked['status']!='found' or checked['text']!=desc:
            raise NativeError(f'Native EpMem read-after-write failed for episode {topic!r} na EpMem: '
                              f'status={checked["status"]} text={checked["text"][:140]!r}')
        self.startup_checks['episodic']+=1
        return checked

    def ask(self,question):
        question=safe(question,350)
        if not 2<=len(question)<=350: raise ValueError('Question length must be 2 to 350 characters.')
        with self.lock:
            interpretation=classify(question,list(self.fact_index.values()))
            if interpretation['intent']=='unknown':
                return {'kind':'interpretation','status':'unknown','text':'I could not parse this question. Please rephrase or choose an example.',
                        'topic':'','method':'unresolved','confidence':0.0,'native_soar':False}
            result=self._invoke(interpretation['intent'],interpretation['topic'],question)
            result.update({'interpretation_method':interpretation['method'],
                           'interpretation_confidence':interpretation['confidence'],
                           'original_question':question})
            self.history.append({'question':question,'memory':result['kind'],
                'topic':result['topic'],'status':result['status'], 'latency_ms':result['latency_ms'],
                'text':result['text'],'method':interpretation['method']})
            self.history=self.history[-500:]
            return result

    def teach(self,label,description,aliases=None):
        label=safe(label,85); description=safe(description,700)
        if not 2<=len(label)<=85 or not 10<=len(description)<=700:
            raise ValueError('Provide a concept (2–85 characters) and an explanation (10–700 characters).')
        aliases=aliases or []
        if not isinstance(aliases,list): raise ValueError('Aliases must be provided as a list of phrases.')
        aliases=[safe(a,80) for a in aliases if len(safe(a))>1][:8]
        key=topic_key(label)
        if not key: raise ValueError('Invalid concept name.')
        item={'topic':key,'label':label,'description':description,'aliases':aliases}
        with self.lock:
            self._install_fact(item)
            # Backup journal is written only AFTER successful native retrieval.
            append_journal(FACT_JOURNAL,item)
            self.user_facts.append(item)
            self.fact_index[key]=item
            return {'native_soar':True,'status':'verified','topic':key,
                    'text':'Learned and successfully retrieved the new definition from native SMem.',
                    'read_after_write':True}

    def experience(self,topic,description):
        topic=topic_key(topic)
        description=safe(description,700)
        if topic not in ('battery','obstacle','sensor','navigation','vision','actuator'):
            raise ValueError('Episode topic must be obstacle, battery, sensor, navigation, vision, or actuator.')
        if not 10<=len(description)<=700: raise ValueError('Episode description must be 10 to 700 characters.')
        item={'topic':topic,'description':description}
        with self.lock:
            result=self._install_event(item)
            append_journal(EVENT_JOURNAL,item)
            self.user_events.append(item)
            return {'native_soar':True,'status':'verified','topic':topic,
                    'text':'Experience recorded and retrieved from native EpMem.',
                    'read_after_write':True,'episode_id':result['episode_id']}

    def inspect(self,memory):
        with self.lock:
            if memory=='procedural': return self.cli('production firing-counts')
            if memory=='semantic':
                return self.cli('print @')[:18000]+'\n\nSMEM STATS\n'+self.cli('smem --stats')
            if memory=='episodic':
                n=self.stats()['episode_id']
                fragment=''
                if n and n>=2:
                    try: fragment=self.cli('epmem --print '+str(n-1))[:8000]
                    except Exception: pass
                return 'MOST RECENT EPISODE\n'+fragment+'\n\nEPMEM STATS\n'+self.cli('epmem --stats')
            raise ValueError('Unsupported memory type.')

    def state(self):
        with self.lock:
            return {'native_soar':True,'version':'3.0','concepts':len(self.fact_index),
                    'seed_concepts':len(self.facts),'user_concepts':len(self.user_facts),
                    'seed_experiences':len(self.events),'user_experiences':len(self.user_events),
                    'procedural_productions':len(PROCEDURES),'verified_episodes':self.startup_checks['episodic'],
                    'native_verifications':self.startup_checks,'stats':self.stats(),
                    'questions':len(self.history)}

    def close(self):
        if self.kernel:
            try:
                if self.agent: self.kernel.DestroyAgent(self.agent)
                self.kernel.Shutdown()
            except Exception: pass
            self.kernel=None;self.agent=None
