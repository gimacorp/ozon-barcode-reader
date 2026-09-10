"""Короткая приёмка кода, Jupyter Notebook и структуры PDF с журналом версии."""
from pathlib import Path
import sys,json,time,subprocess,hashlib,os,collections
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
os.environ.setdefault('MPLCONFIGDIR',str(ROOT/'.cache/matplotlib'));os.environ['MPLBACKEND']='Agg'

def run():
    start=time.perf_counter()
    result=subprocess.run([sys.executable,'-m','pytest','-q'],cwd=ROOT,capture_output=True,text=True,check=True)
    print(result.stdout)
    collect=subprocess.run([sys.executable,'-m','pytest','--collect-only','-q'],cwd=ROOT,capture_output=True,text=True,check=True)
    groups=collections.Counter(line.split('::')[0] for line in collect.stdout.splitlines() if '::' in line)
    from barcode_reader.replay import run_replay
    replay=run_replay();assert all(b['exact_set'] for b in replay['boxes'])
    assert all(b['message']['capture_complete'] for b in replay['boxes'])
    notebook=json.loads((ROOT/'notebooks/demo_ru.ipynb').read_text());scope={'__name__':'__main__'};count=0
    for c in notebook['cells']:
        if c['cell_type']=='code':
            exec(compile(''.join(c['source']),'demo_ru.ipynb','exec'),scope);count+=1
    from pypdf import PdfReader
    pdf=PdfReader(ROOT/'output/pdf/ozon_cv2_report_ru.pdf')
    assert len(pdf.pages)==21 and len(pdf.outline)==21
    assert len(pdf.pages[1].get('/Annots',[]))>=19
    for page in pdf.pages:assert len(page.extract_text())>300
    sha={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest()
         for folder in ('barcode_reader','scripts','configs') for p in sorted((ROOT/folder).glob('*')) if p.suffix in ('.py','.json')}
    out={'release_tag':'submission-v2','cpu':'Apple M5','python':sys.version,'test_result':result.stdout.strip(),
         'groups':dict(groups),'jupyter_code_cells_executed':count,'replay_exact_boxes':2,
         'pdf_pages':len(pdf.pages),'pdf_bookmarks':len(pdf.outline),'elapsed_s':time.perf_counter()-start,
         'source_sha256':sha,'scope':'Короткая программная проверка; визуальная проверка PDF выполняется по рендерам отдельно.'}
    (ROOT/'results/verification.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n')
    print('Верификация завершена:',out['elapsed_s'])
if __name__=='__main__':run()
