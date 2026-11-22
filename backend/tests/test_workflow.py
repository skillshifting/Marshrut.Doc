import csv
import re
import tempfile
import unittest
from pathlib import Path
from zipfile import ZipFile
from io import BytesIO
from docx import Document

from fastapi.testclient import TestClient
from app import main
from app.ml import Classifier, _groups
from app.service import Repository
from app.seed import LABELS


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.original_repo=main.repo
        main.repo=Repository(Path(self.temp.name)/'test.sqlite3')
        self.client=TestClient(main.app)

    def tearDown(self):
        main.repo=self.original_repo
        self.client.close()
        self.temp.cleanup()

    def payload(self,**updates):
        p=dict(description='На новой улице столкнулись два автомобиля, автобусы объезжают по одной полосе',place='Улица Новая',time='2026-11-22T10:20',routes='12, 18',duration_minutes=120,details='',safety_confirmed=True,detour_confirmed=False,stops_known=False,turnaround_confirmed=False,reserve_available=False,release_adjustment_confirmed=False)
        p.update(updates); return p

    def test_classifier_analogues_and_recommendations_change(self):
        for description,label in [
            ('У автобуса отказал мотор на остановке, рейс прерван','Поломка транспортного средства'),
            ('После отключения питания светофор не переключает фазы','Сбой светофорного регулирования'),
            ('Весь участок улицы перекрыт полицией, проезд закрыт','Полное перекрытие улицы')]:
            self.assertEqual(main.model.predict(description)['label'],label)
        created=self.client.post('/api/analyze',json=self.payload()).json()
        self.assertEqual(len(created['analysis']['analogs']),3)
        scores=[a['similarity'] for a in created['analysis']['analogs']]
        self.assertEqual(scores,sorted(scores,reverse=True))
        detour=next(x for x in created['analysis']['actions'] if x['action']=='Временное изменение маршрута')
        self.assertFalse(detour['eligible'])
        updated=self.client.put(f'/api/incidents/{created["id"]}/payload',json=self.payload(detour_confirmed=True,stops_known=True)).json()
        detour_after=next(x for x in updated['analysis']['actions'] if x['action']=='Временное изменение маршрута')
        self.assertTrue(detour_after['eligible'])
        self.assertTrue(any(e['action']=='Сведения исправлены' for e in updated['events']))

    def test_packaged_frontend_served_by_fastapi(self):
        response=self.client.get('/')
        self.assertEqual(response.status_code,200)
        self.assertIn('Маршрут.Док',response.text)
        asset=re.search(r'src="([^"]+\.js)"',response.text)
        self.assertIsNotNone(asset)
        self.assertEqual(self.client.get(asset.group(1)).status_code,200)
        self.assertIn('/map-config.js',response.text)
        self.assertEqual(self.client.get('/map-config.js').status_code,200)
        self.assertEqual(self.client.get('/api/health').status_code,200)
        self.assertEqual(self.client.get('/training-example.csv').status_code,200)

    def test_map_address_and_point_survive_save_and_manual_correction(self):
        created=self.client.post('/api/analyze',json=self.payload(place='Невский проспект 12, Санкт-Петербург',latitude=59.93,longitude=30.34)).json()
        self.assertEqual(created['payload']['latitude'],59.93)
        corrected=self.client.put(f'/api/incidents/{created["id"]}/payload',json=self.payload(place='Невский проспект, у остановки',latitude=59.93,longitude=30.34)).json()
        self.assertEqual(corrected['payload']['place'],'Невский проспект, у остановки')
        self.assertEqual(corrected['payload']['longitude'],30.34)

    def test_manual_approval_and_real_docx(self):
        created=self.client.post('/api/analyze',json=self.payload()).json(); ident=created['id']
        url=f'/api/incidents/{ident}'
        d=dict(action='Временное изменение маршрута',route='Улица Новая — Проспект Мира',stops='Новая, Мира',period='10:30–12:00',responsible='Диспетчер Иванов',notes='Проверено')
        self.assertEqual(self.client.put(url+'/decision',json=d).status_code,200)
        documents=self.client.get(url+'/documents').json()
        self.assertEqual(len(documents),4)
        self.assertFalse(next(x for x in documents if x['kind']=='driver')['available'])
        self.assertEqual(self.client.get(url+'/documents/driver/download').status_code,422)
        self.assertEqual(self.client.post(url+'/status',json={'status':'На проверке'}).status_code,200)
        self.assertEqual(self.client.post(url+'/status',json={'status':'Утверждено'}).status_code,422)
        self.assertEqual(self.client.post(url+'/simulate-delivery').status_code,422)
        self.client.put(url+'/payload',json=self.payload(detour_confirmed=True,stops_known=True))
        approved=self.client.post(url+'/status',json={'status':'Утверждено'}).json()
        self.assertEqual(approved['status'],'Утверждено')
        for kind in ['operator','order','carrier','driver']:
            response=self.client.get(url+f'/documents/{kind}/download')
            self.assertEqual(response.status_code,200)
            with ZipFile(BytesIO(response.content)) as zipfile:
                self.assertIn('word/document.xml',zipfile.namelist())
        self.client.put(url+'/documents/driver',json={'body':'Отредактированная инструкция'})
        response=self.client.get(url+'/documents/driver/download')
        with ZipFile(BytesIO(response.content)) as zipfile:
            self.assertIn('Отредактированная инструкция',zipfile.read('word/document.xml').decode())
        self.assertEqual(self.client.post(url+'/status',json={'status':'Готово к доведению'}).status_code,200)
        self.assertIn('Локальная симуляция',self.client.post(url+'/simulate-delivery').json()['message'])

    def test_document_requisites_layout_and_reset(self):
        ident=self.client.post('/api/analyze',json=self.payload()).json()['id']
        url=f'/api/incidents/{ident}'
        decision=dict(action='Ожидание восстановления движения',route='',stops='',period='22.11.2026 10:30–12:00',
                      responsible='Диспетчер Иванов И.И.',notes='',organization='Городская диспетчерская служба',
                      organization_details='ул. Примерная, 1; +7 000 000-00-00',carrier='Перевозчик А',
                      signer_title='Руководитель службы',signer_name='Петров П.П.',document_date='22.11.2026',document_number='18/6')
        self.assertEqual(self.client.put(url+'/decision',json=decision).status_code,200)
        docs=self.client.get(url+'/documents').json()
        texts={x['kind']:x['body'] for x in docs}
        self.assertIn('СЛУЖЕБНАЯ ЗАПИСКА',texts['operator'])
        self.assertIn('1. Сохранить',texts['order'])
        self.assertIn('Кому: Перевозчик А',texts['carrier'])
        self.assertNotIn('СЛУЖЕБНАЯ ЗАПИСКА',texts['driver'])
        self.assertIn('ПРОЕКТ — НЕ ПОДПИСАНО',texts['order'])
        self.assertNotIn('[дата подписания]',texts['order'])
        reply=self.client.get(url+'/documents/order/download')
        document=Document(BytesIO(reply.content))
        self.assertAlmostEqual(document.sections[0].left_margin.cm,3,places=1)
        self.assertAlmostEqual(document.sections[0].right_margin.cm,1.5,places=1)
        self.assertAlmostEqual(document.sections[0].page_width.cm,21,places=1)
        self.assertEqual(document.styles['Normal'].font.size.pt,12)
        self.assertEqual(document.styles['Normal'].font.name,'Times New Roman')
        self.client.put(url+'/documents/operator',json={'body':'Исправленный текст'})
        self.assertEqual(self.client.get(url+'/documents').json()[0]['body'],'Исправленный текст')
        self.client.delete(url+'/documents/operator')
        self.assertIn('СЛУЖЕБНАЯ ЗАПИСКА',self.client.get(url+'/documents').json()[0]['body'])
        decision['document_date']='2026-11-22'
        self.assertEqual(self.client.put(url+'/decision',json=decision).status_code,422)

    def test_retrain_file_reload_and_group_split(self):
        base=Path(self.temp.name)
        data=base/'training.csv'
        data.write_bytes(main.model.data.read_bytes())
        classifier=Classifier(data,base/'classifier.joblib',base/'metadata.json')
        first=classifier.train()
        self.assertEqual(first['count'],120)
        self.assertEqual(first['train_count']+first['test_count'],first['count'])
        import pandas as pd
        frame=pd.read_csv(data,encoding='utf-8-sig').fillna('')
        groups=_groups(frame)
        self.assertEqual(len(groups),120)
        with data.open('a',encoding='utf-8',newline='') as f:
            csv.writer(f).writerow(['В ином районе автобус заглох из-за аккумулятора','Поломка транспортного средства','new-independent-incident','Тестовый CSV'])
        second=classifier.train()
        self.assertEqual(second['count'],121)
        self.assertEqual(Classifier(data,base/'classifier.joblib',base/'metadata.json').meta['count'],121)

    def test_csv_upload_and_retrain_endpoint(self):
        base=Path(self.temp.name)
        data=base/'training.csv'; data.write_bytes(main.model.data.read_bytes())
        original_model,original_data=main.model,main.DATA
        main.model=Classifier(data,base/'classifier.joblib',base/'metadata.json')
        main.DATA=base
        try:
            raw='text,label,scenario_group,source\n"Автобус потерял питание в ином районе и остановился",Поломка транспортного средства,uploaded-1,Тестовый файл\n'
            uploaded=self.client.post('/api/model/examples',files={'file':('new.csv',raw.encode('utf-8'),'text/csv')})
            self.assertEqual(uploaded.status_code,200)
            self.assertEqual(uploaded.json()['added'],1)
            retrained=self.client.post('/api/model/train')
            self.assertEqual(retrained.status_code,200)
            self.assertEqual(retrained.json()['count'],121)
            self.assertEqual(self.client.get('/api/model').json()['count'],121)
        finally:
            main.model,main.DATA=original_model,original_data

if __name__=='__main__': unittest.main()
