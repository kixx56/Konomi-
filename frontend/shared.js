/* Shared UI: escaped strings, one thin-stroke icon set, typed API errors. */
window.K = {
  esc(value){return String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));},
  icon(name,size=16){const paths={
    qr:'<path d="M3 3h6v6H3zM15 3h6v6h-6zM3 15h6v6H3zM15 15h3v3h3v3h-6zM21 12v3M12 3v9M3 12h9M12 15v6"/>',
    plus:'<path d="M12 5v14M5 12h14"/>',minus:'<path d="M5 12h14"/>',close:'<path d="m6 6 12 12M18 6 6 18"/>',
    arrow:'<path d="M5 12h14m-6-6 6 6-6 6"/>',chevron:'<path d="m6 14 6-6 6 6"/>',
    bag:'<path d="M5 7h14l1 14H4L5 7Z"/><path d="M8 8V6a4 4 0 0 1 8 0v2"/>',
    mic:'<rect x="9" y="2" width="6" height="13" rx="3"/><path d="M5 10v2a7 7 0 0 0 14 0v-2M12 19v3"/>',
    star:'<path d="m12 3 2.8 5.7 6.2.9-4.5 4.4 1.1 6.2-5.6-3-5.6 3 1.1-6.2L3 9.6l6.2-.9L12 3Z"/>',
    'pork-off':'<path d="M5 9a7 7 0 0 1 3-3V3l4 3a9 9 0 0 1 6 4h3v6h-3l-1 4h-3v-3H9v3H6l-1-4a5 5 0 0 1-2-4V9Z"/><path d="M2 4 22 22" stroke="var(--icon-bg,#f9f8f6)" stroke-width="4"/><path d="M2 4 22 22"/><circle cx="15.5" cy="9" r=".65" fill="currentColor" stroke="none"/>',
    'grain-off':'<path d="M12 20V4m0 4C8 8 6 6 6 4c4 0 6 2 6 4Zm0 0c4 0 6-2 6-4-4 0-6 2-6 4Zm0 6c-4 0-6-2-6-4 4 0 6 2 6 4Zm0 0c4 0 6-2 6-4-4 0-6 2-6 4Z"/><path d="m3 3 18 18" stroke="var(--icon-bg,#f9f8f6)" stroke-width="4"/><path d="m3 3 18 18"/>',
    settings:'<path d="M4 7h16M4 17h16"/><circle cx="8" cy="7" r="3" fill="var(--icon-bg,#f9f8f6)"/><circle cx="16" cy="17" r="3" fill="var(--icon-bg,#f9f8f6)"/>',
    shield:'<path d="m12 3 8 3v6c0 5-8 9-8 9s-8-4-8-9V6l8-3Z"/><path d="m8 12 3 3 5-6"/>',
    ban:'<circle cx="12" cy="12" r="9"/><path d="m6 6 12 12"/>',
    rain:'<path d="M6 15a4 4 0 0 1 0-8 6 6 0 0 1 11-1 4.5 4.5 0 1 1 1 9H6ZM8 18l-1 3m7-3-1 3"/>',
    cloud:'<path d="M6 17a5 5 0 0 1 0-10 6 6 0 0 1 11-1 5.5 5.5 0 1 1 1 11H6Z"/>',
    sun:'<circle cx="12" cy="12" r="4"/><path d="M12 2v2m0 16v2M2 12h2m16 0h2M5 5l2 2m10 10 2 2M5 19l2-2M17 7l2-2"/>',
    check:'<path d="m5 12 4 4L19 6"/>',key:'<circle cx="8" cy="8" r="5"/><path d="m12 12 9 9m-3-6-3 3m0-6-3 3"/>',
    upload:'<path d="M12 16V3m-5 5 5-5 5 5M4 15v6h16v-6"/>',download:'<path d="M12 3v13m-5-5 5 5 5-5M4 17v4h16v-4"/>',
    edit:'<path d="m14 4 6 6M4 20l5-1L21 7l-4-4L5 15l-1 5Z"/>',menu:'<path d="M5 5h14M5 12h14M5 19h14"/>',
    search:'<circle cx="10" cy="10" r="6"/><path d="m15 15 6 6"/>',info:'<circle cx="12" cy="12" r="9"/><path d="M12 11v6M12 7v.5"/>',
    logout:'<path d="M10 4H4v16h6m3-8h9m-4-4 4 4-4 4"/>',clock:'<circle cx="12" cy="12" r="9"/><path d="M12 6v6l4 2"/>',
    leaf:'<path d="M5 19C0 9 11 3 21 3c0 10-6 21-16 16Zm0 0L17 7"/>',trash:'<path d="M3 6h18M9 6V3h6v3M6 6l1 15h10l1-15M10 10v7m4-7v7"/>'
  };return `<svg data-symbol="${name}" width="${size}" height="${size}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${paths[name]||paths.info}</svg>`;},
  async api(path,{method='GET',body,signal}={}){
    const options={method,credentials:'same-origin',signal,headers:{'X-Konomi-Admin':'1'}};
    if(body instanceof FormData)options.body=body;
    else if(body!==undefined){options.body=JSON.stringify(body);options.headers['Content-Type']='application/json';}
    let r;try{r=await fetch(path,options);}catch(e){if(e.name==='AbortError')throw e;throw new Error('Нет связи с сервером. Проверьте подключение.');}
    const data=await r.json().catch(()=>({}));
    if(!r.ok){const detail=typeof data.detail==='string'?data.detail:Array.isArray(data.detail)?data.detail.map(d=>`${d.loc?.slice(-1)[0]}: ${d.msg}`).join('; '):'Ошибка сервера';const e=new Error(detail);e.status=r.status;throw e;}
    return data;
  },
  toast(text,error=false){let box=document.querySelector('#toast');if(!box){box=document.createElement('div');box.id='toast';box.role='status';document.body.append(box);}box.textContent=text;box.className=error?'visible error':'visible';clearTimeout(this.toastTimer);this.toastTimer=setTimeout(()=>box.className='',4500);},
  read(key,fallback){try{return JSON.parse(localStorage.getItem(key))??fallback;}catch{return fallback;}},
  save(key,value){try{localStorage.setItem(key,JSON.stringify(value));}catch{}}
};
document.querySelectorAll('[data-icon]').forEach(e=>e.innerHTML=K.icon(e.dataset.icon));
