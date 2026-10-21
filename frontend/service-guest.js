'use strict';
// A receipt code is not a password. Public polling requires a high-entropy capability.
(()=>{
 const q=s=>document.querySelector(s),e=K.esc;
 const words={ru:{waiting:'Заказ ожидает подтверждения официантом',confirmed:'Заказ принят и передан на кухню!',ready:'Готово к подаче',completed:'Заказ выдан / закрыт персоналом',cancelled:'Заказ отменён персоналом',staff:'Подтвердить официантом',pin:'PIN зала — только для персонала',send:'Подтвердить',offline:'Нет связи. Статус не обновлён.'},pl:{waiting:'Zamówienie czeka na potwierdzenie kelnera',confirmed:'Zamówienie przyjęte do kuchni!',ready:'Gotowe do podania',completed:'Zamówienie zamknięte przez obsługę',cancelled:'Zamówienie anulowane',staff:'Potwierdzenie przez kelnera',pin:'PIN sali — tylko dla obsługi',send:'Potwierdź',offline:'Brak połączenia. Status nie został odświeżony.'},en:{waiting:'Your order awaits staff approval',confirmed:'Order accepted and sent to the kitchen!',ready:'Ready to serve',completed:'Order closed by staff',cancelled:'Order cancelled by staff',staff:'Confirm as waiter',pin:'Hall PIN — staff only',send:'Confirm',offline:'Offline. Order status has not been refreshed.'}};
 const locale=()=>words[document.documentElement.lang]||words.en;
 const uuid=()=>globalThis.crypto?.randomUUID?.()||Date.now().toString(36)+Math.random().toString(36).slice(2);
 const n=new URLSearchParams(location.search).get('table');const table=n&&/^[1-9]\d{0,3}$/.test(n)?Number(n):null;
 const visit=K.api('/api/visit',{method:'POST',body:{table,view_id:uuid()}}).catch(()=>null);
 window.konomiTrack=async(kind,detail)=>{await visit;try{await K.api('/api/events',{method:'POST',body:{kind,...detail,table,event_id:uuid()}});}catch{ /* telemetry cannot block a real guest action */ }};
 document.addEventListener('click',ev=>{const b=ev.target.closest('[data-filter]');if(b&&b.getAttribute('aria-pressed')==='true')window.konomiTrack('filter',{filter:b.dataset.filter});});
 let current=null,poller=null,polling=false;
 const storage='konomi-live-receipt-v5:'+(table??'none');
 function persist(){try{sessionStorage.setItem(storage,JSON.stringify(current));}catch{}}
 function update(r){
  const el=q('#staffStatus');if(!el)return;
  const w=locale();el.textContent=w[r.status==='created'?'waiting':r.status]||r.status;el.className='receipt-status '+(r.status==='created'?'pending':r.status==='cancelled'?'cancelled':'accepted');
  q('#staffConfirmForm')?.classList.toggle('hidden',r.status!=='created');
  current={...current,...r};persist();
  if(['cancelled','completed'].includes(r.status))clearInterval(poller);
 }
 async function poll(){if(!current||polling||document.hidden)return;polling=true;try{const r=await fetch('/api/orders/'+encodeURIComponent(current.code),{credentials:'same-origin',headers:{'X-Order-Token':current.access_token}});if(!r.ok)throw Error('unavailable');update(await r.json());}catch{const el=q('#staffStatus');if(el)el.textContent=locale().offline;}finally{polling=false;}}
 function controls(r){
  current=r;persist();q('#staffReceiptControls')?.remove();
  const w=locale(),box=document.createElement('div');box.id='staffReceiptControls';box.innerHTML=`<p id="staffStatus" role="status" aria-live="polite"></p><form id="staffConfirmForm"><button class="secondary" type="button" id="showStaffPIN">${e(w.staff)}</button><div id="staffPINFields" class="hidden"><label class="field">${e(w.pin)}<input id="staffPIN" type="password" inputmode="numeric" pattern="[0-9]{4,8}" minlength="4" maxlength="8" autocomplete="off" required></label><button class="primary" type="submit">${e(w.send)}</button><p class="inline-status" id="staffPINError" role="alert"></p></div></form>`;
  q('#receipt').append(box);update(r);
  q('#showStaffPIN').onclick=()=>{q('#staffPINFields').classList.toggle('hidden');};
  q('#staffConfirmForm').onsubmit=async ev=>{ev.preventDefault();const b=ev.submitter;b.disabled=true;q('#staffPINError').textContent='';try{const data=await K.api('/api/orders/'+encodeURIComponent(current.code)+'/confirm',{method:'POST',body:{pin:q('#staffPIN').value,access_token:current.access_token}});q('#staffPIN').value='';update(data);}catch(err){q('#staffPINError').textContent=err.message;q('#staffPIN').value='';}finally{b.disabled=false;}};
  clearInterval(poller);if(!['cancelled','completed'].includes(r.status))poller=setInterval(poll,2500);
 }
 window.konomiReceipt=controls;
 // A reload keeps the capability in sessionStorage, never in the URL/referrer or analytics.
 try{const r=JSON.parse(sessionStorage.getItem(storage)||'null');if(r?.access_token&&r?.code){current=r;const b=document.createElement('button');b.className='secondary receipt-restore';b.textContent=r.code+' · '+locale().waiting;b.onclick=()=>{q('#receipt').innerHTML=`<h3>${e(r.code)} · Table ${e(r.table??'—')}</h3>${r.lines.map(l=>`<p>${l.qty} × ${l.names.map(e).join(' + ')}</p>`).join('')}<strong>${Number(r.total).toFixed(2)} ${e(r.currency||'PLN')}</strong>`;controls(r);q('#receiptDialog').showModal();poll();};q('#menuTitle').parentElement.append(b);}}catch{}
 document.addEventListener('visibilitychange',()=>{if(!document.hidden)poll();});
})();
