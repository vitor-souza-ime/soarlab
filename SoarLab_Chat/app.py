"""SoarLab Chat v3: English web interface backed exclusively by native Soar SML."""
from __future__ import annotations
import argparse
import os
import threading
import traceback
from pathlib import Path
from flask import Flask, jsonify, request, render_template, send_from_directory
from soarlab.native import SoarChat, NativeError
from soarlab.benchmark import run, BenchmarkError
from soarlab.questions import EXAMPLES, PARAPHRASE_TESTS

ROOT=Path(__file__).resolve().parent
app=Flask(__name__)
app.json.ensure_ascii=False
engine=None
engine_lock=threading.RLock()

def get_engine():
    global engine
    with engine_lock:
        if engine is None:engine=SoarChat()
        return engine

@app.errorhandler(Exception)
def errors(exc):
    code=400 if isinstance(exc,ValueError) else 503 if isinstance(exc,(NativeError,BenchmarkError)) else 500
    if code==500:app.logger.error(traceback.format_exc())
    return jsonify({'ok':False,'error':str(exc),'exception':type(exc).__name__}),code

@app.get('/')
def index():return render_template('index.html',examples=EXAMPLES)

@app.get('/api/status')
def status():return jsonify({'ok':True,'state':get_engine().state()})

@app.post('/api/ask')
def ask():
    payload=request.get_json(silent=True) or {}
    return jsonify({'ok':True,'result':get_engine().ask(payload.get('question',''))})

@app.post('/api/teach')
def teach():
    payload=request.get_json(silent=True) or {}
    aliases=[x.strip() for x in str(payload.get('aliases','')).split(';') if x.strip()]
    r=get_engine().teach(payload.get('topic',''),payload.get('description',''),aliases)
    return jsonify({'ok':True,'result':r})

@app.post('/api/experience')
def experience():
    data=request.get_json(silent=True) or {}
    r=get_engine().experience(data.get('topic',''),data.get('description',''))
    return jsonify({'ok':True,'result':r})

@app.get('/api/inspect/<memory>')
def inspect(memory):return jsonify({'ok':True,'raw':get_engine().inspect(memory)})

@app.get('/api/history')
def history():
    e=get_engine()
    with e.lock:return jsonify({'ok':True,'history':e.history[-100:]})

@app.get('/api/questions')
def questions():
    return jsonify({'ok':True,'questions':[{'question':q,'memory':m,'topic':t} for q,m,t in PARAPHRASE_TESTS]})

@app.post('/api/benchmark')
def benchmark():
    data=request.get_json(silent=True) or {}
    answer=run(get_engine(),int(data.get('repetitions',3)),int(data.get('seed',2026)),str(data.get('mode','fixed')))
    return jsonify({'ok':True,'results':answer})

@app.get('/results/<run_id>/<filename>')
def get_result(run_id,filename):
    # Flask send_from_directory rejects directory traversal and only serves existing files.
    if not run_id.startswith('benchmark_') or '/' in run_id or '\\' in run_id:
        raise ValueError('Invalid benchmark identifier.')
    return send_from_directory(ROOT/'results'/run_id,filename,
            as_attachment=filename.endswith(('.csv','.json')))

if __name__=='__main__':
    p=argparse.ArgumentParser(description='SoarLab Chat Flask (native Soar SML)')
    p.add_argument('--lan',action='store_true',help='Serve on the local network for phones. No authentication; do not expose to the internet.')
    p.add_argument('--port',type=int,default=5000)
    args=p.parse_args()
    print('Starting Soar SML 9.6.5 and verifying the initial memory corpus...')
    state=get_engine().state() # native memory initialization must complete before serving HTTP
    print('Soar ready. Procedural rules:',state['procedural_productions'],'semantic concepts:',state['concepts'],'verified experiences:',state['verified_episodes'])
    host='0.0.0.0' if args.lan else '127.0.0.1'
    print('Open http://127.0.0.1:'+str(args.port))
    if args.lan:print('Smartphone: http://YOUR_PC_IP:'+str(args.port)+' (same Wi-Fi). Do not expose to the internet.')
    app.run(host=host,port=args.port,use_reloader=False,debug=False,threaded=True)
