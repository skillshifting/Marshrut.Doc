import {useEffect,useId,useRef,useState,type FormEvent} from 'react';
import * as Dialog from '@radix-ui/react-dialog';
import {MapPin,Search,X} from 'lucide-react';
import {loadYandexMaps,type Coordinates,type YandexMap,type YandexMaps,type YandexPlacemark} from '../yandexMaps';
import {Button,Input} from './ui';

type Point={lat:number;lon:number};
const apiKey=(window.MARSHRUT_DOC_YANDEX_KEY||'').trim();
const coords=(point:Point):Coordinates=>[point.lat,point.lon];
const fallback=(point:Point)=>`Координаты: ${point.lat.toFixed(5)}, ${point.lon.toFixed(5)}`;

export function LocationField({address,latitude,longitude,onChange}:{address:string;latitude?:number|null;longitude?:number|null;onChange:(address:string,point?:Point|null)=>void}){
 const id=useId();
 const [open,setOpen]=useState(false);
 const [point,setPoint]=useState<Point|null>(null);
 const [draft,setDraft]=useState('');
 const [city,setCity]=useState('');
 const [notice,setNotice]=useState('');
 const [mapError,setMapError]=useState('');
 const [ready,setReady]=useState(false);
 const [lookingUp,setLookingUp]=useState(false);
 const [searching,setSearching]=useState(false);
 const [mapNode,setMapNode]=useState<HTMLDivElement|null>(null);
 const map=useRef<YandexMap|null>(null);
 const api=useRef<YandexMaps|null>(null);
 const pin=useRef<YandexPlacemark|null>(null);
 const timer=useRef<ReturnType<typeof setTimeout>|null>(null);
 const requestNumber=useRef(0);

 function openMap(){
  setDraft(address);
  setPoint(latitude != null && longitude != null?{lat:latitude,lon:longitude}:null);
  setCity('');setNotice('');setMapError('');setReady(false);setLookingUp(false);setSearching(false);
  setOpen(true);
 }

 useEffect(()=>{
  if(!open||!apiKey||mapNode)return;
  const timeout=window.setTimeout(()=>setMapError('Не удалось подготовить окно карты. Закройте его и откройте снова.'),5000);
  return ()=>window.clearTimeout(timeout);
 },[open,mapNode]);

 useEffect(()=>{
  if(!open||!apiKey||!mapNode)return;
  let cancelled=false;
  const initial=latitude != null && longitude != null?{lat:latitude,lon:longitude}:null;
  setReady(false);setMapError('');
  loadYandexMaps(apiKey).then(ymaps=>{
   if(cancelled)return;
   api.current=ymaps;
   const instance=new ymaps.Map(mapNode,{
    center:initial?coords(initial):[59.9386,30.3141],zoom:initial?16:11,controls:['zoomControl']
   });
   map.current=instance;
   const drawPin=(selected:Point)=>{
    if(pin.current)pin.current.geometry.setCoordinates(coords(selected));
    else{
     pin.current=new ymaps.Placemark(coords(selected),{}, {preset:'islands#darkBlueDotIcon'});
     instance.geoObjects.add(pin.current);
    }
   };
   if(initial)drawPin(initial);
   instance.events.add('click',event=>{
    const [lat,lon]=event.get('coords');
    const selected={lat,lon};
    drawPin(selected);setPoint(selected);setDraft('');setNotice('');setLookingUp(true);
    if(timer.current)clearTimeout(timer.current);
    const current=++requestNumber.current;
    timer.current=setTimeout(()=>{
     Promise.resolve(ymaps.geocode(coords(selected),{results:1})).then(result=>{
      if(cancelled||current!==requestNumber.current)return;
      const found=result.geoObjects.get(0)?.getAddressLine()?.replace(/^Россия,\s*/,'')||'';
      setDraft(found||fallback(selected));
      if(!found)setNotice('Адрес не найден. Впишите место вручную.');
     }).catch(()=>{
      if(cancelled||current!==requestNumber.current)return;
      setDraft(fallback(selected));
      setNotice('Не удалось определить адрес. Впишите место вручную.');
     }).finally(()=>{if(!cancelled&&current===requestNumber.current)setLookingUp(false)});
    },300);
   });
   setReady(true);
   window.setTimeout(()=>{if(!cancelled)instance.container.fitToViewport()},230);
  }).catch(error=>{if(!cancelled)setMapError((error as Error).message)});
  return ()=>{
   cancelled=true;
   if(timer.current)clearTimeout(timer.current);
   requestNumber.current++;
   map.current?.destroy();map.current=null;api.current=null;pin.current=null;
  };
 },[open,mapNode]);

 async function findCity(event:FormEvent){
  event.preventDefault();
  if(city.trim().length<2||!api.current||!map.current)return;
  setSearching(true);setNotice('');
  const current=requestNumber.current;
  try{
   const result=await api.current.geocode(city.trim(),{results:1});
   if(current!==requestNumber.current)return;
   const found=result.geoObjects.get(0);
   if(!found){setNotice('Место не найдено. Уточните город или район.');return}
   map.current?.setCenter(found.geometry.getCoordinates(),14);
   setNotice('Карта перемещена. Нажмите на точку происшествия.');
  }catch{if(current===requestNumber.current)setNotice('Не удалось найти место. Попробуйте ещё раз или переместите карту вручную.')}
  finally{setSearching(false)}
 }

 function apply(){if(point&&draft.trim()){onChange(draft.trim(),point);setOpen(false)}}

 return <div className="field">
  <label htmlFor={id}>Где?</label>
  <div className="location-input-row">
   <Input id={id} placeholder="Улица, остановка или перекрёсток" value={address} onChange={e=>onChange(e.target.value)}/>
   <Button type="button" variant="outline" onClick={openMap}><MapPin size={15}/>На карте</Button>
  </div>
  {latitude != null && longitude != null&&<span className="location-hint">Точка выбрана · адрес можно исправить вручную <button type="button" onClick={()=>onChange(address,null)}>Убрать точку</button></span>}
  <Dialog.Root open={open} onOpenChange={setOpen}>
   <Dialog.Portal>
    <Dialog.Overlay className="location-overlay"/>
    <Dialog.Content className="location-dialog" aria-describedby="location-instructions">
     <div className="location-dialog-heading">
      <div><span className="eyebrow">МЕСТО ПРОИСШЕСТВИЯ / ЯНДЕКС КАРТЫ</span><Dialog.Title>Укажите точку на карте</Dialog.Title><Dialog.Description id="location-instructions">Найдите город и нажмите на нужное место. Полученный адрес можно поправить перед сохранением.</Dialog.Description></div>
      <Dialog.Close className="location-close" aria-label="Закрыть карту"><X size={19}/></Dialog.Close>
     </div>
     {apiKey&&<form onSubmit={findCity} className="location-search">
      <Input aria-label="Город или район" placeholder="Город или район, например: Казань" value={city} onChange={e=>setCity(e.target.value)} maxLength={120}/>
      <Button type="submit" variant="outline" disabled={!ready||searching||city.trim().length<2}><Search size={15}/>{searching?'Ищем…':'Найти'}</Button>
     </form>}
     {apiKey?<div className="location-map-wrap"><div className="location-map" ref={setMapNode} aria-label="Яндекс Карта для выбора места происшествия"/>{(!ready||mapError)&&<div className="location-map-status">{mapError||'Загружаем Яндекс Карты…'}</div>}</div>:<div className="location-map-empty"><MapPin size={30}/><strong>Ключ карты не задан</strong><span>Укажите ключ JavaScript API в файле map-config.js проекта.</span></div>}
     {apiKey&&<div className="location-dialog-bottom">
      <label className="field"><span>Адрес точки</span><Input placeholder={point?'Укажите адрес вручную':'Сначала выберите точку на карте'} value={draft} onChange={e=>setDraft(e.target.value)} disabled={!point||lookingUp}/></label>
      <div className="location-footer"><div className="location-meta">{lookingUp?'Определяем адрес…':notice||(!point?'Нажмите на карту, чтобы поставить точку.':`${point.lat.toFixed(5)}, ${point.lon.toFixed(5)} · проверьте адрес`)}</div><Button type="button" onClick={apply} disabled={!point||!draft.trim()||lookingUp}>Использовать адрес</Button></div>
     </div>}
    </Dialog.Content>
   </Dialog.Portal>
  </Dialog.Root>
 </div>;
}
