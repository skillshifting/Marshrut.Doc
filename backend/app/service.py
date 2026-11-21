import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from .seed import HISTORY, LABELS

ACTIONS = ['Ожидание восстановления движения','Укороченные рейсы','Временное изменение маршрута','Использование резервного транспорта','Временная корректировка выпуска']
STATUSES = ['Черновик','На проверке','Утверждено','Готово к доведению']
CHANGE_ACTIONS = {ACTIONS[1], ACTIONS[2]}

def now(): return datetime.now(timezone.utc).isoformat(timespec='seconds')

class Repository:
    def __init__(self, path: Path):
        self.path = path
        with self.db() as db:
            db.executescript('''CREATE TABLE IF NOT EXISTS history (id INTEGER PRIMARY KEY, description TEXT, type TEXT, place TEXT, routes TEXT, duration INTEGER, measure TEXT, outcome TEXT, source TEXT);
            CREATE TABLE IF NOT EXISTS incidents (id INTEGER PRIMARY KEY, payload TEXT NOT NULL, analysis TEXT NOT NULL, decision TEXT NOT NULL DEFAULT '{}', status TEXT NOT NULL DEFAULT 'Черновик', updated_at TEXT);
            CREATE TABLE IF NOT EXISTS events (id INTEGER PRIMARY KEY, incident_id INTEGER, at TEXT, action TEXT, details TEXT);
            CREATE TABLE IF NOT EXISTS documents (incident_id INTEGER, doc_type TEXT, body TEXT, updated_at TEXT, PRIMARY KEY(incident_id, doc_type));''')
            if not db.execute('SELECT 1 FROM history LIMIT 1').fetchone():
                db.executemany('INSERT INTO history(description,type,place,routes,duration,measure,outcome,source) VALUES(?,?,?,?,?,?,?,?)',
                               [(d,LABELS[t],p,r,mins,m,o,'Синтетический учебный случай') for d,t,p,r,mins,m,o in HISTORY])

    def db(self):
        con = sqlite3.connect(self.path)
        con.row_factory = sqlite3.Row
        return con

    def log(self, db, incident, action, details):
        db.execute('INSERT INTO events(incident_id,at,action,details) VALUES(?,?,?,?)', (incident,now(),action,details))

    def analogs(self, description, limit=3):
        with self.db() as db: rows = [dict(r) for r in db.execute('SELECT * FROM history')]
        corpus = [r['description'] for r in rows] + [description]
        mat = TfidfVectorizer(ngram_range=(1,2), analyzer='char', min_df=1).fit_transform(corpus)
        sim = cosine_similarity(mat[-1],mat[:-1]).ravel()
        for row, score in zip(rows,sim): row['similarity'] = float(score)
        return sorted(rows,key=lambda r:r['similarity'],reverse=True)[:limit]

    def rank(self, payload, analogs):
        missing = []
        if not payload.get('place','').strip(): missing.append('Место происшествия')
        if not payload.get('routes','').strip(): missing.append('Затронутые маршруты')
        if not payload.get('duration_minutes'): missing.append('Предполагаемая длительность')
        if not payload.get('safety_confirmed'): missing.append('Подтверждение безопасности исполнения')
        results = []
        for action in ACTIONS:
            evidence = sum(a['similarity'] for a in analogs if a['measure'] == action)
            examples = sum(1 for a in analogs if a['measure'] == action and a['similarity'] >= .12)
            blockers = list(missing)
            if action == ACTIONS[2]:
                if not payload.get('detour_confirmed'): blockers.append('Подтверждённая схема объезда')
                if not payload.get('stops_known'): blockers.append('Известные остановки объезда')
            if action == ACTIONS[1] and not payload.get('turnaround_confirmed'):
                blockers.append('Подтверждённый разворотный пункт')
            if action == ACTIONS[3] and not payload.get('reserve_available'):
                blockers.append('Наличие резервного транспорта')
            if action == ACTIONS[4] and not payload.get('release_adjustment_confirmed'):
                blockers.append('Возможность корректировки выпуска')
            duration = int(payload.get('duration_minutes') or 0)
            # A small deterministic contextual adjustment, documented in README; evidence is still visible.
            context = (.08 if duration >= 90 and action in [ACTIONS[2],ACTIONS[3]] else 0) + (.05 if duration < 45 and action == ACTIONS[0] else 0)
            score = round(evidence + context, 4)
            results.append(dict(action=action, score=score, supporting_cases=examples, eligible=not blockers,
                                blockers=blockers, evidence_weight=round(evidence,4),
                                reason=f'Сумма текстового сходства аналогов с этой мерой: {evidence:.2f}; подходящих аналогов: {examples}. ' +
                                ('Длительное нарушение добавляет небольшой приоритет.' if context and duration >= 90 else 'Краткий сбой добавляет небольшой приоритет ожиданию.' if context else 'Дополнительный приоритет не применён.'),
                                effectiveness_unproven=True))
        results.sort(key=lambda a:(not a['eligible'],-a['score']))
        return dict(actions=results, missing_data=sorted(set(missing)), specialist_required=bool(missing) or not any(a['eligible'] and a['supporting_cases'] >= 2 for a in results),
                    note='Ранжирование основано на сходстве текстов и правилах. Исторические исходы не доказывают эффективность меры. При недостатке независимых аналогов требуется решение специалиста.')

    def create(self,payload,analysis):
        with self.db() as db:
            cur=db.execute('INSERT INTO incidents(payload,analysis,updated_at) VALUES(?,?,?)', (json.dumps(payload,ensure_ascii=False),json.dumps(analysis,ensure_ascii=False),now()))
            ident=cur.lastrowid; self.log(db,ident,'Создан черновик','Проведён локальный ML-анализ')
        return self.get(ident)

    def get(self,ident):
        with self.db() as db:
            row=db.execute('SELECT * FROM incidents WHERE id=?',(ident,)).fetchone()
            if row is None: return None
            item=dict(row)
            for key in ['payload','analysis','decision']: item[key]=json.loads(item[key])
            item['events']=[dict(x) for x in db.execute('SELECT at,action,details FROM events WHERE incident_id=? ORDER BY id DESC',(ident,))]
            return item

    def update_decision(self,ident,decision):
        item=self.get(ident)
        if item is None: raise ValueError('Происшествие не найдено')
        if item['status'] in STATUSES[2:]: raise ValueError('Утверждённое решение нельзя изменить без нового черновика')
        if decision.get('action') not in ACTIONS: raise ValueError('Выберите допустимую меру')
        if decision.get('document_date','').strip():
            from datetime import datetime
            try: datetime.strptime(decision['document_date'].strip(), '%d.%m.%Y')
            except ValueError: raise ValueError('Дата документа должна быть в формате ДД.ММ.ГГГГ')
        with self.db() as db:
            db.execute('UPDATE incidents SET decision=?,updated_at=? WHERE id=?',(json.dumps(decision,ensure_ascii=False),now(),ident))
            self.log(db,ident,'Решение отредактировано',f"Мера: {decision['action']}; ответственный: {decision.get('responsible','не указан')}")
            db.execute('DELETE FROM documents WHERE incident_id=?',(ident,))
        return self.get(ident)

    def transition(self,ident,target):
        item=self.get(ident)
        if item is None: raise ValueError('Происшествие не найдено')
        if target not in STATUSES or STATUSES.index(target) != STATUSES.index(item['status'])+1: raise ValueError('Недопустимый переход статуса')
        d=item['decision']; p=item['payload']; action=d.get('action')
        if not action: raise ValueError('Сначала выберите меру реагирования')
        if target in STATUSES[2:]:
            if not d.get('responsible','').strip(): raise ValueError('Назначьте ответственного')
            if not d.get('period','').strip(): raise ValueError('Укажите срок действия решения')
            if not p.get('place','').strip() or not p.get('routes','').strip(): raise ValueError('Уточните место и маршруты')
            if not p.get('safety_confirmed'): raise ValueError('Безопасность исполнения не подтверждена')
            if action == ACTIONS[2] and not (p.get('detour_confirmed') and p.get('stops_known') and d.get('route','').strip() and d.get('stops','').strip()):
                raise ValueError('Для изменения маршрута подтвердите объезд, трассу и остановки')
            if action == ACTIONS[1] and not (p.get('turnaround_confirmed') and d.get('route','').strip() and d.get('stops','').strip()):
                raise ValueError('Для укороченных рейсов подтвердите разворот, трассу и остановки')
            if action == ACTIONS[3] and not p.get('reserve_available'): raise ValueError('Резервный транспорт не подтверждён')
            if action == ACTIONS[4] and not p.get('release_adjustment_confirmed'): raise ValueError('Корректировка выпуска не подтверждена')
        with self.db() as db:
            db.execute('UPDATE incidents SET status=?,updated_at=? WHERE id=?',(target,now(),ident))
            self.log(db,ident,'Статус изменён',f"{item['status']} → {target}")
        return self.get(ident)

    def save_document(self,ident,kind,body):
        if len(body) > 30000: raise ValueError('Текст документа слишком длинный')
        with self.db() as db:
            db.execute('INSERT INTO documents VALUES(?,?,?,?) ON CONFLICT(incident_id,doc_type) DO UPDATE SET body=excluded.body,updated_at=excluded.updated_at',(ident,kind,body,now()))
            self.log(db,ident,'Документ отредактирован',kind)

    def document_override(self,ident,kind):
        with self.db() as db:
            row=db.execute('SELECT body FROM documents WHERE incident_id=? AND doc_type=?',(ident,kind)).fetchone()
        return row['body'] if row else None

    def reset_document(self, ident, kind):
        with self.db() as db:
            db.execute('DELETE FROM documents WHERE incident_id=? AND doc_type=?', (ident, kind))
            self.log(db, ident, 'Шаблон документа восстановлен', kind)

    def list_incidents(self):
        with self.db() as db: ids=[r['id'] for r in db.execute('SELECT id FROM incidents ORDER BY id DESC')]
        return [self.get(i) for i in ids]
