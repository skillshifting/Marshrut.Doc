import {Input,Textarea} from './ui';
import type {Payload} from '../types';
const checks:[keyof Payload,string][]=[
 ['safety_confirmed','Действие можно выполнить безопасно'],
 ['detour_confirmed','Схема объезда согласована'],
 ['stops_known','Остановки на новой трассе известны'],
 ['turnaround_confirmed','Место разворота подтверждено'],
 ['reserve_available','Резервный автобус доступен'],
 ['release_adjustment_confirmed','Выпуск можно изменить']
];
export function IncidentFields({value,onChange,showChecks=false}:{value:Payload;onChange:(v:Payload)=>void;showChecks?:boolean}){
 const set=(key:keyof Payload,v:string|number|boolean|null)=>onChange({...value,[key]:v});
 return <div className="space-y-4">
  <label className="field"><span>Что произошло? <b className="text-red-700">*</b></span><Textarea rows={4} required minLength={8} placeholder="Например: на перекрёстке столкнулись автомобили, автобусам трудно проехать" value={value.description} onChange={e=>set('description',e.target.value)}/></label>
  <div className="grid gap-4 sm:grid-cols-2"><label className="field"><span>Где?</span><Input placeholder="Улица, остановка или перекрёсток" value={value.place} onChange={e=>set('place',e.target.value)}/></label><label className="field"><span>Какие маршруты?</span><Input placeholder="Например: 12, 18" value={value.routes} onChange={e=>set('routes',e.target.value)}/></label><label className="field"><span>Сколько продлится? Примерно, минут</span><Input type="number" min={1} max={10080} placeholder="Например: 90" value={value.duration_minutes??''} onChange={e=>set('duration_minutes',e.target.value?Number(e.target.value):null)}/></label><label className="field"><span>Когда произошло?</span><Input type="datetime-local" value={value.time} onChange={e=>set('time',e.target.value)}/></label></div>
  <details className="disclosure"><summary>Дополнительные сведения</summary><div className="pt-3"><Textarea rows={2} placeholder="Источник сообщения, известные ограничения…" value={value.details} onChange={e=>set('details',e.target.value)}/></div></details>
  {showChecks&&<div className="rounded-sm border border-line bg-slate-50 p-4"><h3 className="font-semibold text-sm mb-1">Что уже подтверждено?</h3><p className="text-xs text-muted mb-3">Отметьте только проверенные сведения. Эти условия влияют на допустимость мер.</p><div className="grid gap-2 sm:grid-cols-2">{checks.map(([key,label])=><label key={key} className="flex items-start gap-2 text-sm cursor-pointer py-1"><input type="checkbox" className="mt-0.5 accent-[#143d65]" checked={Boolean(value[key])} onChange={e=>set(key,e.target.checked)}/>{label}</label>)}</div></div>}
 </div>
}
