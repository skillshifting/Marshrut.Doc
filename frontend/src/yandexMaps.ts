/** Minimal types for the Yandex Maps JavaScript API 2.1 used by the picker. */
export type Coordinates=[number,number]; // Yandex uses [latitude, longitude].

export interface YandexPlacemark {
 geometry:{setCoordinates:(coordinates:Coordinates)=>void};
}

export interface YandexMap {
 events:{add:(name:string,handler:(event:{get:(key:string)=>Coordinates})=>void)=>void};
 geoObjects:{add:(object:YandexPlacemark)=>void};
 container:{fitToViewport:()=>void};
 setCenter:(coordinates:Coordinates,zoom?:number)=>void;
 destroy:()=>void;
}

export interface YandexGeoResult {
 geoObjects:{get:(index:number)=>({geometry:{getCoordinates:()=>Coordinates};getAddressLine:()=>string})|undefined};
}

export interface YandexMaps {
 ready:(success:()=>void,error:(reason:unknown)=>void)=>void;
 Map:new (element:HTMLElement,state:{center:Coordinates;zoom:number;controls:string[]})=>YandexMap;
 Placemark:new (coordinates:Coordinates,properties?:Record<string,unknown>,options?:Record<string,unknown>)=>YandexPlacemark;
 geocode:(query:string|Coordinates,options?:Record<string,unknown>)=>PromiseLike<YandexGeoResult>;
}

declare global { interface Window { ymaps?:YandexMaps; MARSHRUT_DOC_YANDEX_KEY?:string } }

let activeKey:string|null=null;
let loading:Promise<YandexMaps>|null=null;

export function loadYandexMaps(key:string):Promise<YandexMaps>{
 if(loading){
  if(activeKey!==key)return Promise.reject(new Error('Ключ сохранён. Обновите страницу, чтобы подключить карту с новым ключом.'));
  return loading;
 }
 activeKey=key;
 loading=new Promise<YandexMaps>((resolve,reject)=>{
  const script=document.createElement('script');
  let finished=false;
  const timeout=window.setTimeout(()=>fail('Не удалось загрузить Яндекс Карты. Проверьте интернет и ключ.'),15000);
  function fail(message:string){
   if(finished)return;
   finished=true;window.clearTimeout(timeout);script.remove();
   loading=null;activeKey=null;
   reject(new Error(message));
  }
  script.async=true;
  script.src=`https://api-maps.yandex.ru/2.1/?apikey=${encodeURIComponent(key)}&lang=ru_RU`;
  script.onerror=()=>fail('Не удалось загрузить Яндекс Карты. Проверьте интернет, ключ и ограничения по домену.');
  script.onload=()=>{
   const api=window.ymaps;
   if(!api){fail('Яндекс Карты не ответили. Проверьте ключ и обновите страницу.');return}
   api.ready(()=>{
    if(finished)return;
    finished=true;window.clearTimeout(timeout);resolve(api);
   },()=>fail('Не удалось запустить Яндекс Карты. Проверьте ключ и ограничения по домену.'));
  };
  document.head.append(script);
 });
 return loading;
}
