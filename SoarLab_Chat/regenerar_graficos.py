"""Regenerate eight figures from an existing, COMPLETE native benchmark CSV.

Examples:
    python regenerar_graficos.py
    python regenerar_graficos.py "C:\\path\\to\\results\\benchmark_YYYYMMDD_HHMMSS"
The original raw.csv remains unchanged. No native Soar queries are performed.
"""
from __future__ import annotations
import argparse
import csv
import json
import shutil
from pathlib import Path
from soarlab.benchmark import _graphs

ROOT=Path(__file__).resolve().parent
INT_FIELDS=('correct','decision_cycles','index','repetition','smem_queries_delta','epmem_queries_delta')
FLOAT_FIELDS=('latency_soar_ms','latency_e2e_ms','parse_ms')

def regenerate(directory:Path)->list[str]:
    directory=Path(directory).resolve()
    csv_path=directory/'raw.csv';meta_path=directory/'metadata.json'
    if not csv_path.is_file() or not meta_path.is_file():
        raise FileNotFoundError('Both raw.csv and metadata.json are required in the specified folder.')
    meta=json.loads(meta_path.read_text(encoding='utf8'))
    with csv_path.open('r',newline='',encoding='utf-8-sig') as handle:
        rows=list(csv.DictReader(handle))
    expected=int(meta['repetitions'])*int(meta['questions_per_repetition'])
    if not rows or len(rows)!=expected:
        raise ValueError(f'Incomplete benchmark: saved {len(rows)}, expected {expected}. '
                         'Partial results are not accepted as a complete experimental run.')
    if any(str(row.get('native_soar','')).strip().lower() not in ('true','1') for row in rows):
        raise ValueError('At least one row is missing a native Soar confirmation.')
    for row in rows:
        for field in INT_FIELDS:
            value=row.get(field,'');row[field]=None if value in ('',None) else int(value)
        for field in FLOAT_FIELDS:
            value=row.get(field,'');row[field]=None if value in ('',None) else float(value)
    figures=_graphs(rows,directory,mode=meta.get('mode','fixed'))
    if len(figures)!=8 or any(not (directory/f).is_file() for f in figures):
        raise RuntimeError('Failed to regenerate all eight graphs.')
    backup=directory/'metadata_before_regeneration.json'
    if not backup.exists():shutil.copy2(meta_path,backup)
    prior_error=str(meta.get('error',''))
    if "Axes.boxplot() got an unexpected keyword argument 'tick_labels'" in prior_error:
        meta['status']='completed';meta['original_graph_error']=meta.pop('error')
    meta['graphics']=figures
    meta['graphics_regenerated_from_raw_csv']=True
    meta['note_regeneration']='Original CSV preserved; graph generation did not rerun Soar.'
    meta_path.write_text(json.dumps(meta,ensure_ascii=False,indent=2),encoding='utf8')
    return figures

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory',nargs='?',type=Path,help='Directory with raw.csv and metadata.json')
    options=parser.parse_args()
    if options.directory is None:
        folders=[d for d in sorted((ROOT/'results').glob('benchmark_*'),reverse=True)
                 if (d/'raw.csv').exists()]
        if not folders:parser.error('No benchmark was found. Specify a result directory.')
        directory=folders[0]
    else:directory=options.directory
    for name in regenerate(directory):print('Generated:',name)
    print('Original raw.csv was not modified.')

if __name__=='__main__':main()
