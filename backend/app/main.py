import csv
import io
from pathlib import Path
from threading import RLock

import pandas as pd
from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .seed import LABELS, create_seed
from .ml import Classifier
from .service import Repository, STATUSES
from .documents import KINDS, render, docx_bytes, driver_allowed

BASE=Path(__file__).resolve().parents[1]
DATA=BASE/'data'; DATA.mkdir(exist_ok=True)
create_seed(DATA/'training.csv')
repo=Repository(DATA/'incidents.sqlite3')
model=Classifier(DATA/'training.csv',DATA/'classifier.joblib',DATA/'model_meta.json')
lock=RLock()
if model.pipeline is None: model.train()

app=FastAPI(title='Маршрут.Док',version='0.1.0')
app.add_middleware(CORSMiddleware,allow_origins=['http://localhost:5173','http://127.0.0.1:5173'],allow_methods=['*'],allow_headers=['*'])

class IncidentIn(BaseModel):
    description: str = Field(min_length=8, max_length=5000)
    place: str = ''
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    time: str = ''
    routes: str = ''
    duration_minutes: int | None = Field(default=None,ge=1,le=10080)
    details: str = ''
    safety_confirmed: bool = False
    detour_confirmed: bool = False
    stops_known: bool = False
    turnaround_confirmed: bool = False
    reserve_available: bool = False
    release_adjustment_confirmed: bool = False

class DecisionIn(BaseModel):
    action: str
    route: str = ''
    stops: str = ''
    period: str = ''
    responsible: str = ''
    notes: str = ''
    organization: str = ''
    organization_details: str = ''
    carrier: str = ''
    signer_title: str = ''
    signer_name: str = ''
    document_date: str = ''
    document_number: str = ''

class StatusIn(BaseModel):
    status: str

class DocIn(BaseModel):
    body: str

def safe(fn,*args):
    try: return fn(*args)
    except ValueError as exc: raise HTTPException(422,str(exc))

def incident(ident):
    item=repo.get(ident)
    if item is None: raise HTTPException(404,'Происшествие не найдено')
    return item

@app.get('/api/health')
def health(): return {'ok':True,'model_version':model.meta['version']}

@app.get('/api/model')
def model_info(): return model.meta

@app.post('/api/model/train')
def train():
    with lock: return safe(model.train)

@app.post('/api/model/examples')
async def upload_examples(file: UploadFile = File(...)):
    if not file.filename.lower().endswith('.csv'): raise HTTPException(422,'Загрузите CSV')
    raw=await file.read()
    if len(raw)>2_000_000: raise HTTPException(413,'CSV слишком большой')
    try:
        incoming=pd.read_csv(io.BytesIO(raw),encoding='utf-8-sig').fillna('')
        if not {'text','label'}.issubset(incoming): raise ValueError('Нужны столбцы text и label')
        if incoming.empty or len(incoming)>1000: raise ValueError('Нужно от 1 до 1000 строк')
        if not set(incoming.label).issubset(LABELS): raise ValueError('Неизвестная категория')
        if any(incoming.text.astype(str).str.strip().str.len()<8): raise ValueError('Описание должно содержать не менее 8 символов')
        if 'scenario_group' not in incoming: incoming['scenario_group']=['upload-'+str(i) for i in range(len(incoming))]
        if 'source' not in incoming: incoming['source']='Загруженный CSV; происхождение не проверено'
        incoming=incoming[['text','label','scenario_group','source']]
        with lock:
            incoming.to_csv(DATA/'training.csv',mode='a',index=False,header=False,encoding='utf-8')
        return {'added':len(incoming),'message':'Примеры добавлены. Нажмите «Переобучить модель».'}
    except (ValueError,UnicodeDecodeError,pd.errors.ParserError) as exc: raise HTTPException(422,str(exc))

@app.post('/api/analyze')
def analyze(payload: IncidentIn):
    data=payload.model_dump()
    with lock: classification=model.predict(data['description'])
    analogs=repo.analogs(data['description'])
    ranking=repo.rank(data,analogs)
    analysis={'classification':classification,'analogs':analogs,**ranking,'synthetic_warning':'Учебные данные и исторические случаи синтетические. Качество на реальных происшествиях не доказано.'}
    return repo.create(data,analysis)

@app.put('/api/incidents/{ident}/payload')
def correct_payload(ident:int,payload:IncidentIn):
    item=incident(ident)
    if item['status'] in STATUSES[2:]: raise HTTPException(422,'Утверждённый случай нельзя исправить')
    data=payload.model_dump()
    with lock: classification=model.predict(data['description'])
    analogs=repo.analogs(data['description'])
    analysis={'classification':classification,'analogs':analogs,**repo.rank(data,analogs),
              'synthetic_warning':'Учебные данные и исторические случаи синтетические. Качество на реальных происшествиях не доказано.'}
    import json
    from .service import now
    with repo.db() as db:
        db.execute('UPDATE incidents SET payload=?,analysis=?,updated_at=? WHERE id=?',(json.dumps(data,ensure_ascii=False),json.dumps(analysis,ensure_ascii=False),now(),ident))
        db.execute('DELETE FROM documents WHERE incident_id=?',(ident,))
        repo.log(db,ident,'Сведения исправлены','Анализ и рекомендации пересчитаны')
    return incident(ident)

@app.get('/api/incidents')
def incidents(): return repo.list_incidents()

@app.get('/api/incidents/{ident}')
def get_incident(ident:int): return incident(ident)

@app.put('/api/incidents/{ident}/decision')
def update_decision(ident:int,body:DecisionIn):
    incident(ident)
    return safe(repo.update_decision,ident,body.model_dump())

@app.post('/api/incidents/{ident}/status')
def status(ident:int,body:StatusIn):
    incident(ident)
    return safe(repo.transition,ident,body.status)

@app.get('/api/incidents/{ident}/documents')
def documents(ident:int):
    item=incident(ident)
    result=[]
    for kind,title in KINDS.items():
        allowed=kind!='driver' or driver_allowed(item)
        result.append({'kind':kind,'title':title,'available':allowed,'body':(repo.document_override(ident,kind) or render(item,kind)) if allowed else None})
    return result

@app.put('/api/incidents/{ident}/documents/{kind}')
def update_doc(ident:int,kind:str,body:DocIn):
    item=incident(ident)
    if kind not in KINDS: raise HTTPException(404,'Документ не найден')
    if kind=='driver' and not driver_allowed(item): raise HTTPException(422,'Трасса и остановки не подтверждены')
    safe(repo.save_document,ident,kind,body.body)
    return {'saved':True}

@app.delete('/api/incidents/{ident}/documents/{kind}')
def reset_doc(ident:int,kind:str):
    incident(ident)
    if kind not in KINDS: raise HTTPException(404,'Документ не найден')
    repo.reset_document(ident,kind)
    return {'reset':True}

@app.get('/api/incidents/{ident}/documents/{kind}/download')
def download(ident:int,kind:str):
    item=incident(ident)
    body=safe(render,item,kind)
    body=repo.document_override(ident,kind) or body
    filename=f'marshrut-doc-{ident}-{kind}.docx'
    return Response(docx_bytes(body,kind),media_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document',headers={'Content-Disposition':f'attachment; filename="{filename}"'})

@app.post('/api/incidents/{ident}/simulate-delivery')
def simulate(ident:int):
    item=incident(ident)
    if item['status']!='Готово к доведению': raise HTTPException(422,'Сначала доведите статус до «Готово к доведению»')
    with repo.db() as db: repo.log(db,ident,'Локальная симуляция отправки','Внешняя отправка не выполнялась')
    return {'message':'Локальная симуляция завершена. Документы никуда не отправлены.'}

# The distributable includes the Vite build. FastAPI serves it on the same
# origin as /api, so an operator can run the packaged application without Node.
FRONTEND_DIST=BASE.parent/'frontend'/'dist'
if (FRONTEND_DIST/'index.html').is_file():
    app.mount('/', StaticFiles(directory=FRONTEND_DIST, html=True), name='frontend')
