import {useEffect,useState} from 'react';
import {Button,Card,CardContent,CardHeader,Input,Textarea,Badge} from './ui';
import {IncidentFields} from './IncidentFields';
import type {Incident,Decision,Payload} from '../types';
import {api} from '../api';
const statuses=['Черновик','На проверке','Утверждено','Готово к доведению'];
export function DecisionPanel({item,onUpdate,notify,onDocuments}:{item:Incident;onUpdate:(i:Incident)=>void;notify:(s:string)=>void;onDocuments:()=>void}){
 const [decision,setDecision]=useState<Decision>(item.decision);const [payload,setPayload]=useState<Payload>(item.payload);const [busy,setBusy]=useState(false);
 useEffect(()=>{setDecision(item.decision);setPayload(item.payload)},[item.id,item.updated_at]);
 const set=(key:keyof Decision,value:string)=>setDecision({...decision,[key]:value});
 const selected=item.analysis.actions.find(x=>x.action===decision.action);
 const changeRoute=['Временное изменение маршрута','Укороченные рейсы'].includes(decision.action);
 const locked=statuses.indexOf(item.status)>=2;
 async function persist(){
  if(!decision.action)throw new Error('Выберите меру');
  if(JSON.stringify(payload)!==JSON.stringify(item.payload))await api.correct(item.id,payload);
  const updated=await api.decision(item.id,decision);onUpdate(updated);return updated;
 }
 async function act(target?:string){setBusy(true);try{
  if(locked&&target){onUpdate(await api.status(item.id,target));notify('Статус изменён');return}
  const saved=await persist();
  if(target){onUpdate(await api.status(saved.id,target));notify(`Решение передано: ${target}`)}
  else notify('Решение и сведения сохранены');
 }catch(e){notify((e as Error).message)}finally{setBusy(false)}}
 return <div className="space-y-4">
  <div className="notice"><b>Решение принимает человек.</b> Проверьте условия, затем передайте вариант на проверку. До утверждения ничего не меняется на линии.</div>
  <Card><CardHeader><h2 className="section-title">Выбранная мера</h2></CardHeader><CardContent className="space-y-4">
   <label className="field"><span>Что сделать?</span><select disabled={locked} className="select" value={decision.action||''} onChange={e=>set('action',e.target.value)}><option value="">Выберите меру</option>{item.analysis.actions.map(x=><option key={x.action} value={x.action}>{x.action}</option>)}</select></label>
   {selected&&!selected.eligible&&<div className="rounded-sm border border-amber-300 bg-amber-50 px-4 py-3 text-sm">Перед утверждением уточните: {selected.blockers.join(', ')}.</div>}
   <div className="grid gap-4 sm:grid-cols-2"><label className="field"><span>Срок действия решения</span><Input disabled={locked} value={decision.period||''} onChange={e=>set('period',e.target.value)} placeholder="Например: 22.11, 10:30–12:00"/></label><label className="field"><span>Ответственный</span><Input disabled={locked} value={decision.responsible||''} onChange={e=>set('responsible',e.target.value)} placeholder="Должность и Ф.И.О."/></label></div>
   {changeRoute&&<div className="grid gap-4 sm:grid-cols-2"><label className="field"><span>Подтверждённая трасса</span><Input disabled={locked} value={decision.route||''} onChange={e=>set('route',e.target.value)} placeholder="Улицы и направление"/></label><label className="field"><span>Остановки и разворот</span><Input disabled={locked} value={decision.stops||''} onChange={e=>set('stops',e.target.value)} placeholder="Список остановок по порядку"/></label></div>}
   <label className="flex items-center gap-3 rounded border border-line p-3 text-sm cursor-pointer"><input type="checkbox" disabled={locked} checked={payload.safety_confirmed} onChange={e=>setPayload({...payload,safety_confirmed:e.target.checked})}/>Подтверждаю, что меру можно выполнить безопасно</label>
   {decision.action==='Временное изменение маршрута'&&<div className="flex flex-wrap gap-4 text-sm"><label className="flex gap-2 items-center"><input type="checkbox" disabled={locked} checked={payload.detour_confirmed} onChange={e=>setPayload({...payload,detour_confirmed:e.target.checked})}/>Схема объезда подтверждена</label><label className="flex gap-2 items-center"><input type="checkbox" disabled={locked} checked={payload.stops_known} onChange={e=>setPayload({...payload,stops_known:e.target.checked})}/>Остановки известны</label></div>}
   {decision.action==='Укороченные рейсы'&&<div className="flex flex-wrap gap-4 text-sm"><label className="flex gap-2 items-center"><input type="checkbox" disabled={locked} checked={payload.turnaround_confirmed} onChange={e=>setPayload({...payload,turnaround_confirmed:e.target.checked})}/>Разворот подтверждён</label><label className="flex gap-2 items-center"><input type="checkbox" disabled={locked} checked={payload.stops_known} onChange={e=>setPayload({...payload,stops_known:e.target.checked})}/>Остановки известны</label></div>}
   {decision.action==='Использование резервного транспорта'&&<label className="flex gap-2 items-center text-sm"><input type="checkbox" disabled={locked} checked={payload.reserve_available} onChange={e=>setPayload({...payload,reserve_available:e.target.checked})}/>Резервная машина доступна</label>}
   {decision.action==='Временная корректировка выпуска'&&<label className="flex gap-2 items-center text-sm"><input type="checkbox" disabled={locked} checked={payload.release_adjustment_confirmed} onChange={e=>setPayload({...payload,release_adjustment_confirmed:e.target.checked})}/>Корректировка выпуска подтверждена</label>}
   <label className="field"><span>Комментарий специалиста</span><Textarea disabled={locked} rows={2} value={decision.notes||''} onChange={e=>set('notes',e.target.value)} placeholder="Только если есть важные уточнения"/></label>
  </CardContent></Card>
  {!locked&&<details className="disclosure bg-white"><summary>Реквизиты для документов</summary><div className="p-5 pt-2"><p className="text-sm text-muted">Заполните официальные данные. Пока они неизвестны, в документах будут видимые поля для заполнения.</p><div className="grid gap-4 sm:grid-cols-2">{([['organization','Организация'],['organization_details','Адрес и контакты отправителя письма'],['carrier','Перевозчик'],['signer_title','Должность подписанта'],['signer_name','Ф.И.О. подписанта'],['document_date','Дата подписания'],['document_number','Регистрационный номер']] as [keyof Decision,string][]).map(([key,label])=><label className="field" key={key}><span>{label}</span><Input value={decision[key]||''} onChange={e=>set(key,e.target.value)}/></label>)}</div></div></details>}
  {!locked&&<details className="disclosure bg-white"><summary>Исправить сообщение или подтверждённые условия</summary><div className="p-5 pt-2"><IncidentFields value={payload} onChange={setPayload} showChecks/><p className="text-xs text-muted mt-3">Сведения и ML-анализ обновятся при сохранении решения.</p></div></details>}
  <Card><CardHeader><h2 className="section-title">Согласование</h2></CardHeader><CardContent><div className="flex flex-wrap items-center gap-2 mb-4">{statuses.map((x,i)=><div key={x} className="flex items-center gap-2"><Badge tone={i<statuses.indexOf(item.status)?'green':i===statuses.indexOf(item.status)?'amber':'neutral'}>{x}</Badge>{i<3&&<span className="text-muted">›</span>}</div>)}</div>
   {item.status==='Черновик'&&<div className="flex gap-2 flex-wrap"><Button disabled={busy||!decision.action} onClick={()=>act('На проверке')}>Сохранить и передать на проверку</Button><Button variant="outline" disabled={busy||!decision.action} onClick={()=>act()}>Сохранить черновик</Button></div>}
   {item.status==='На проверке'&&<div className="flex gap-2 flex-wrap"><Button disabled={busy||!decision.action} onClick={()=>act('Утверждено')}>Подтвердить решение</Button><Button variant="outline" disabled={busy||!decision.action} onClick={()=>act()}>Сохранить правки</Button></div>}
   {item.status==='Утверждено'&&<Button onClick={()=>act('Готово к доведению')} disabled={busy}>Готово к доведению</Button>}
   {item.status==='Готово к доведению'&&<Button variant="outline" disabled={busy} onClick={async()=>{try{const x=await api.simulate(item.id);notify(x.message);onUpdate(await api.get(item.id))}catch(e){notify((e as Error).message)}}}>Симулировать отправку локально</Button>}
   <div className="mt-5"><Button variant="ghost" onClick={onDocuments}>Посмотреть документы</Button></div>
  </CardContent></Card>
  <details className="disclosure bg-white"><summary>История изменений</summary><div className="p-5 pt-2 border-l border-line ml-5">{item.events.map((e,i)=><div key={i} className="pl-3 pb-3 text-sm"><b>{e.action}</b><span className="font-mono text-[10px] text-muted ml-2">{new Date(e.at).toLocaleString('ru-RU')}</span><p className="text-muted mb-0">{e.details}</p></div>)}</div></details>
 </div>
}
