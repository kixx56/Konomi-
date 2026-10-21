'use strict';
// Same-origin staff-only tools. No order tokens, PINs or API keys are written to browser storage.
(()=>{
 const q=s=>document.querySelector(s),e=K.esc;
 let currency='PLN';
 const money=(n,unit=currency)=>new Intl.NumberFormat('ru-RU',{minimumFractionDigits:2,maximumFractionDigits:2}).format(n)+' '+unit;
 const labels={created:'Ожидает',confirmed:'На кухне',ready:'Готово к подаче',completed:'Выдано / оплачено',cancelled:'Отклонён'};
 let active='',timer=null,running=false,seen=null,sound=null,page=0,lastReport=null,filterKey='',exporting=false;
 const call=(url,opts)=>K.api(url,opts);
 function notify(){if(!sound)return;try{const o=sound.createOscillator(),g=sound.createGain();o.connect(g);g.connect(sound.destination);o.frequency.value=740;g.gain.setValueAtTime(.13,sound.currentTime);g.gain.exponentialRampToValueAtTime(.001,sound.currentTime+.35);o.start();o.stop(sound.currentTime+.35);}catch{}}
 function table(rows,headers){return `<table class="table"><thead><tr>${headers.map(x=>`<th>${e(x)}</th>`).join('')}</tr></thead><tbody>${rows.length?rows.map(r=>`<tr>${r.map(v=>`<td>${v}</td>`).join('')}</tr>`).join(''):`<tr><td colspan="${headers.length}">Пока нет данных</td></tr>`}</tbody></table>`;}
 async function board(){
  const data=await call('/api/admin/board');currency=data.orders[0]?.currency||currency;
  const next=new Set(data.orders.filter(o=>o.status==='created').map(o=>o.code));
  if(seen&&[...next].some(code=>!seen.has(code)))notify();seen=next;
  q('#boardHealth').textContent='На связи · '+new Date().toLocaleTimeString('ru-RU')+(data.truncated?' · Достигнут лимит 500 активных заказов!':'');q('#boardHealth').className='connected';
  const html=data.orders.map(o=>{
   const age=Math.max(0,Math.floor((data.server_time-o.at)/60));
   const acts=o.status==='created'?[['confirmed','Принять на кухню']]:o.status==='confirmed'?[['ready','Готово к подаче']]:[['completed','Выдано / оплачено']];
   return `<article class="order-ticket order-${e(o.status)}"><header><span>Столик #${e(o.table??'—')}</span><strong>${e(o.code)}</strong></header><div class="ticket-meta"><span>${e(labels[o.status])}</span><span>${age} мин · ${money(o.total,o.currency||currency)}</span></div>${age>=15?'<span class="wait-alert">Длительное ожидание</span>':''}<ul>${o.lines.map(l=>`<li><strong>${l.qty} ×</strong> ${l.names.map(e).join(' + ')}${l.combo?' <span class="badge">Комбо</span>':''}</li>`).join('')}</ul>${o.excludes?.length?`<div class="allergy-alert">ИСКЛЮЧЕНИЯ: ${o.excludes.map(e).join(', ')}<br>Проверить состав и перекрёстные контакты!</div>`:''}${o.diets?.length?`<div class="allergy-alert">Диета: ${o.diets.map(e).join(', ')}</div>`:''}<footer>${acts.map(([st,label])=>`<button class="primary" data-status="${st}" data-code="${e(o.code)}" data-version="${o.version}">${label}</button>`).join('')}<button class="text-btn danger" data-status="cancelled" data-code="${e(o.code)}" data-version="${o.version}">Отклонить / спам</button></footer></article>`;
  }).join('')||'<div class="board-empty">Нет активных заказов. Новые чеки появятся здесь автоматически.</div>';
  // Do not replace focused controls during staff interaction.
  if(!q('#serviceBoard').contains(document.activeElement))q('#serviceBoard').innerHTML=html;
 }
 function filters(){const p=new URLSearchParams();for(const [id,key] of [['salesSince','since'],['salesUntil','until'],['salesTable','table']]){const v=q('#'+id).value;if(v)p.set(key,v);}return p;}
 async function analytics(){
  const params=filters(),sig=params.toString()+q('#salesStatus').value;if(filterKey!==sig){page=0;filterKey=sig;}
  const [r,h]=await Promise.all([call('/api/admin/analytics?'+params),history()]);lastReport=r;currency=r.currency||currency;
  const f=r.finance;
  q('#salesStats').innerHTML=[['Подтверждено (не факт оплаты)',money(f.confirmed_revenue)],['Завершено персоналом',money(f.completed_revenue)],['Ожидает подтверждения',money(f.pending_value)],['Средний чек · с ИИ',f.average_ai===null?'Нет данных':money(f.average_ai)],['Средний чек · без ИИ',f.average_no_ai===null?'Нет данных':money(f.average_no_ai)],['Комбо / допродажи',f.combo_units+' / '+f.upsell_units]].map(([k,v])=>`<div class="stat"><span>${e(k)}</span><strong>${e(v)}</strong></div>`).join('');
  const names={views:'Открытия меню',unique_visitors:'Уникальные посетители',ai_chats:'Сессии диалога',cart_adds:'Сессии с корзиной',checks_created:'Созданные чеки',confirmed_sales:'Подтверждённые'};
  q('#salesFunnel').innerHTML=Object.entries(r.funnel).map(([k,v])=>`<div><strong>${v}</strong><span>${e(names[k])}</span></div>`).join('');
  q('#tableStats').innerHTML=table(r.tables.map(x=>[e(x.table),x.views,x.confirmed_sales,money(x.revenue)]),['Стол','Открытия','Продажи','Сумма']);
  const max=Math.max(1,...r.hours.map(x=>x.views));q('#hourStats').innerHTML=r.hours.map(x=>`<div title="${x.hour}:00 — ${x.views}"><span class="hour-bar" style="height:${Math.max(2,90*x.views/max)}px"></span><small>${x.hour}</small></div>`).join('');
  q('#dishStats').innerHTML=table(r.top_dishes.map(x=>[e(x.name),x.qty]),['Блюдо','Порций']);
  const counts=obj=>Object.entries(obj).map(([k,v])=>`<div class="audit-line"><span>${e(k)}</span><strong>${v}</strong></div>`).join('')||'<p>Пока нет данных</p>';
  q('#demandStats').innerHTML='<h3>Именные запросы блюд</h3>'+table(r.requested_dishes.map(x=>[e(x.name),x.requests]),['Блюдо','Запросов'])+'<h3>Запросы категорий (не продажи)</h3>'+counts(r.requested_topics)+'<h3>Фильтры / ограничения чата</h3>'+counts(r.allergen_filters);
  q('#analyticsHealth').textContent='Обновлено '+new Date().toLocaleTimeString('ru-RU')+' · Открытие страницы не доказывает физическое сканирование QR.';
 }
 async function history(){const params=filters();params.set('status',q('#salesStatus').value);params.set('offset',String(page*50));params.set('limit','50');const r=await call('/api/admin/sales?'+params);q('#salesHistory').innerHTML=table(r.orders.map(o=>[e(o.code),e(o.table??'—'),e(labels[o.status]||o.status),money(o.total,o.currency||currency),e(new Date(o.at*1000).toLocaleString('ru-RU')),o.ai_assisted?'Да':'Нет',o.lines.map(l=>e(l.qty+' × '+l.names.join(' + '))).join('<br>')]),['Чек','Стол','Статус','Сумма','Создан','ИИ','Состав']);q('#salesPage').textContent=`${page*50+Math.min(1,r.total)}–${Math.min((page+1)*50,r.total)} из ${r.total}`;q('#salesPrev').disabled=page===0;q('#salesNext').disabled=(page+1)*50>=r.total;return r;}
 async function tick(){if(running||!['service','analytics'].includes(active)||document.hidden)return;running=true;try{if(active==='service')await board();else await analytics();}catch(err){const el=q(active==='service'?'#boardHealth':'#analyticsHealth');el.textContent='Нет актуальных данных: '+err.message+' · повторяем подключение';el.className='error';}finally{running=false;}}
 window.serviceNavigate=async tab=>{active=tab;clearInterval(timer);if(tab==='service'){try{const r=await call('/api/admin/hall-pin');q('#hallPinStatus').textContent=r.configured?'PIN настроен; значение не раскрывается.':'PIN не настроен. Подтверждение через табло уже доступно.';}catch{}}if(['service','analytics'].includes(tab)){tick();timer=setInterval(tick,tab==='service'?2000:10000);}};
 q('#boardSound').onclick=async()=>{try{sound ||=new(window.AudioContext||window.webkitAudioContext)();await sound.resume();q('#boardSound').textContent='Звук включён';notify();}catch{K.toast('Браузер не разрешил звук',true);}};
 q('#serviceBoard').onclick=async ev=>{const b=ev.target.closest('[data-status]');if(!b)return;b.disabled=true;try{await call('/api/admin/orders/'+encodeURIComponent(b.dataset.code)+'/status',{method:'POST',body:{status:b.dataset.status,version:Number(b.dataset.version)}});b.blur();await board();}catch(err){K.toast(err.message,true);}finally{b.disabled=false;}};
 q('#hallPinForm').onsubmit=async ev=>{ev.preventDefault();const b=ev.submitter;b.disabled=true;try{await call('/api/admin/hall-pin',{method:'PUT',body:{pin:q('#hallPin').value}});q('#hallPin').value='';q('#hallPinStatus').textContent='PIN обновлён. Сообщите его только сотрудникам.';}catch(err){K.toast(err.message,true);}finally{b.disabled=false;}};
 q('#salesFilters').onsubmit=ev=>{ev.preventDefault();page=0;tick();};q('#salesPrev').onclick=()=>{page--;tick();};q('#salesNext').onclick=()=>{page++;tick();};
 q('#salesCSV').onclick=async()=>{if(exporting)return;exporting=true;try{let rows=[],offset=0;const p=filters();p.set('status',q('#salesStatus').value);p.set('limit','200');for(;;){p.set('offset',offset);const r=await call('/api/admin/sales?'+p);rows.push(...r.orders);offset+=r.orders.length;if(offset>=r.total||!r.orders.length)break;}const cell=v=>'"'+String(v??'').replace(/^[=+@\-]/,"'$&").replaceAll('"','""')+'"';const data='\ufeff'+[['code','table','status','total','created_at','ai_assisted'],...rows.map(o=>[o.code,o.table,o.status,o.total,o.created_at,o.ai_assisted])].map(row=>row.map(cell).join(',')).join('\r\n');const url=URL.createObjectURL(new Blob([data],{type:'text/csv;charset=utf-8'}));const a=document.createElement('a');a.href=url;a.download='konomi-sales.csv';a.click();setTimeout(()=>URL.revokeObjectURL(url),2000);}catch(err){K.toast(err.message,true);}finally{exporting=false;}};
 document.addEventListener('visibilitychange',()=>{if(!document.hidden)tick();});
})();
