'use strict';
const {esc:E,icon:I}=K;
const $=s=>document.querySelector(s);
const L={
 ru:{menu:'Меню',count:'позиций',categories:['Все','Супы','Горячее','Напитки и десерты','Закуски','Другое'],filters:['Хиты кухни','Без глютена','Без свинины'],empty:'Нет подходящих блюд. Уберите фильтр или спросите официанта.',add:'Добавить в заказ',stopped:'Временно нет',unknown:'Состав уточняется',photo:'Иллюстрация подачи',chat:'Ваш проводник по меню',greet:'Добро пожаловать. Помогу выбрать блюда и собрать заказ.',cool:' В прохладную погоду приятно начать с горячего Rosół.',quick:['Без свинины','Сытно до 100 PLN','Комбо со скидкой'],input:'Спросите про блюда или комбо…',cart:'Ваш заказ',show:'Показать официанту',total:'Итого',clear:'Очистить',checkout:'Сформировать чек',notice:'Заказ ожидает подтверждения персоналом; после подтверждения появится в работе кухни.',receipt:'Чек гостя',combo:'Комбо',set:'Добавить сет',saving:'Выгода',checking:'Проверяем цены и доступность…',reset:'Сбросить',diet:'Исключения',thinking:'Подбираю блюда…',voice:'Голосовой ввод недоступен. Используйте текст.',error:'Не удалось получить ответ. Попробуйте ещё раз.',retry:'Повторить',load:'Не удалось загрузить меню.',emptyCart:'В корзине пока нет блюд.',remove:'Удалить',rules:'Локальный помощник',gemini:'ИИ-сомелье',allergens:{gluten:'глютен',pork:'свинина',lactose:'лактоза',milk:'молоко',egg:'яйцо',fish:'рыба',nuts:'орехи'}},
 en:{menu:'Menu',count:'dishes',categories:['All','Soups','Mains','Drinks & desserts','Starters','Other'],filters:['Kitchen hits','Gluten-free','No pork'],empty:'No matching dishes. Remove a filter or ask your waiter.',add:'Add to order',stopped:'Unavailable',unknown:'Confirm ingredients',photo:'Serving illustration',chat:'Your guide to the menu',greet:'Welcome. I can explain dishes and help build your order.',cool:' A hot Rosół is a lovely start in cool weather.',quick:['No pork','Hearty under 100 PLN','Combo deal'],input:'Ask about dishes or combos…',cart:'Your order',show:'Show to waiter',total:'Total',clear:'Clear',checkout:'Create guest check',notice:'Your order awaits staff approval before kitchen preparation.',receipt:'Guest check',combo:'Combo',set:'Add set',saving:'Saving',checking:'Checking prices and availability…',reset:'Reset',diet:'Exclusions',thinking:'Finding dishes…',voice:'Voice input unavailable. Please type.',error:'Could not get a response. Please retry.',retry:'Retry',load:'Could not load menu.',emptyCart:'Your cart is empty.',remove:'Remove',rules:'Local assistant',gemini:'AI sommelier',allergens:{gluten:'gluten',pork:'pork',lactose:'lactose',milk:'milk',egg:'egg',fish:'fish',nuts:'nuts'}},
 pl:{menu:'Menu',count:'pozycji',categories:['Wszystko','Zupy','Dania główne','Napoje i desery','Przystawki','Inne'],filters:['Hity kuchni','Bez glutenu','Bez wieprzowiny'],empty:'Brak pasujących dań. Zmień filtr lub zapytaj kelnera.',add:'Dodaj do zamówienia',stopped:'Niedostępne',unknown:'Potwierdź skład',photo:'Przykładowe podanie',chat:'Twój przewodnik po menu',greet:'Witamy. Pomogę wybrać dania i złożyć zamówienie.',cool:' W chłodną pogodę warto zacząć od gorącego rosołu.',quick:['Bez wieprzowiny','Sycąco do 100 PLN','Combo ze zniżką'],input:'Zapytaj o dania lub combo…',cart:'Twoje zamówienie',show:'Pokaż kelnerowi',total:'Razem',clear:'Wyczyść',checkout:'Utwórz rachunek',notice:'Zamówienie czeka na potwierdzenie przez obsługę przed realizacją w kuchni.',receipt:'Rachunek gościa',combo:'Combo',set:'Dodaj zestaw',saving:'Oszczędność',checking:'Sprawdzamy ceny i dostępność…',reset:'Resetuj',diet:'Wykluczenia',thinking:'Wybieram dania…',voice:'Wpisz wiadomość — głos niedostępny.',error:'Nie udało się uzyskać odpowiedzi. Spróbuj ponownie.',retry:'Ponów',load:'Nie udało się załadować menu.',emptyCart:'Koszyk jest pusty.',remove:'Usuń',rules:'Lokalny pomocnik',gemini:'AI sommelier',allergens:{gluten:'gluten',pork:'wieprzowina',lactose:'laktoza',milk:'mleko',egg:'jajko',fish:'ryba',nuts:'orzechy'}}
};
Object.assign(L.ru,{staff:'Ограничение нужно уточнить у официанта'});Object.assign(L.en,{staff:'A dietary restriction needs staff confirmation'});Object.assign(L.pl,{staff:'Ograniczenie wymaga potwierdzenia przez kelnera'});
const S={lang:['ru','en','pl'].includes(K.read('konomi-lang','ru'))?K.read('konomi-lang','ru'):'ru',menu:[],cat:'all',filters:new Set(),lines:[],history:[],excludes:[],diets:[],quote:null,busy:false,opened:false,venue:'',currency:'PLN',idempotency:null,session:null,chatLang:null,needsStaff:false,applied:[],upsellsDeclined:false};
const t=k=>L[S.lang][k];
const money=v=>new Intl.NumberFormat(S.lang==='ru'?'ru-RU':S.lang==='en'?'en-GB':'pl-PL',{minimumFractionDigits:2,maximumFractionDigits:2}).format(v)+' '+S.currency;
const categories=['all','soup','main','beverage','starter','other'];
let quoteController,quoteTimer,lastWeather=null;
const tableParam=new URLSearchParams(location.search).get('table');
const TABLE=tableParam&&/^[1-9]\d{0,3}$/.test(tableParam)?Number(tableParam):null;
const CART_KEY='konomi-cart-v4:'+(TABLE??'no-table');
const SESSION_KEY='konomi-session-v4:'+(TABLE??'no-table');
try{S.session=sessionStorage.getItem(SESSION_KEY)||null;}catch{}
const turns=[];let processing=false,deciding=false,cartRevision=0,offerTimer=null,autoOpened=false,manualSheet=false;
const HISTORY_KEY='konomi-history-v6:'+(TABLE??'no-table');
try{const h=JSON.parse(sessionStorage.getItem(HISTORY_KEY)||'[]');if(Array.isArray(h))S.history=h.filter(m=>['user','assistant'].includes(m.role)&&typeof m.content==='string').slice(-8);}catch{}
function persistHistory(){try{sessionStorage.setItem(HISTORY_KEY,JSON.stringify(S.history));}catch{}}
const OFFER_TEXT={ru:['Добавить','Без дополнений'],en:['Add accompaniment','No extras'],pl:['Dodaj','Bez dodatków'],de:['Hinzufügen','Keine Extras'],fr:['Ajouter','Sans supplément'],es:['Añadir','Sin extras'],it:['Aggiungi','Nessun extra'],pt:['Adicionar','Sem extras'],uk:['Додати','Без доповнень'],nl:['Toevoegen','Geen extra’s']};
function setSession(value){S.session=value;try{if(value)sessionStorage.setItem(SESSION_KEY,value);else sessionStorage.removeItem(SESSION_KEY);}catch{}}


function saveCart(changed=true){if(changed){cartRevision++;S.idempotency=null;}K.save(CART_KEY,{lines:S.lines,excludes:S.excludes,diets:S.diets,needsStaff:S.needsStaff,applied:S.applied,idempotency:S.idempotency});}
function restoreCart(){const old=K.read(CART_KEY,{});S.lines=Array.isArray(old.lines)?old.lines.filter(l=>Array.isArray(l.ids)&&l.ids.length>0&&l.ids.length<=3&&l.ids.every(i=>typeof i==='string')&&Number.isInteger(l.qty)&&l.qty>0&&l.qty<=30).slice(0,200).map(l=>({ids:l.ids,qty:l.qty,combo:!!l.combo})):[];S.excludes=Array.isArray(old.excludes)?old.excludes.filter(x=>typeof x==='string').slice(0,200):[];S.diets=Array.isArray(old.diets)?old.diets:[];S.needsStaff=!!old.needsStaff;S.applied=Array.isArray(old.applied)?old.applied.slice(-50):[];S.idempotency=typeof old.idempotency==='string'?old.idempotency:null;}
function applyLanguage(){
 document.documentElement.lang=S.lang; document.title=`Konomi AI — ${S.venue}`;
 $('#menuTitle').textContent=t('menu');$('#messageInput').placeholder=t('input');$('#cartCta').textContent=t('show');$('#cartTitle').textContent=t('cart');$('#totalLabel').textContent=t('total');$('#checkout').textContent=t('checkout');$('#clearCart').textContent=t('clear');$('#checkNotice').textContent=t('notice');$('#receiptTitle').textContent=t('receipt');$('#clearDiet').textContent=t('reset');$('#engineLabel').textContent=t('chat');
 document.querySelectorAll('[data-lang]').forEach(b=>{b.classList.toggle('active',b.dataset.lang===S.lang);b.setAttribute('aria-pressed',b.dataset.lang===S.lang);});
 $('#tabs').innerHTML=categories.map((c,i)=>`<button data-cat="${c}" class="${S.cat===c?'active':''}" aria-pressed="${S.cat===c}">${E(t('categories')[i])}</button>`).join('');
 $('#filters').innerHTML=['hit','gluten','pork'].map((f,i)=>`<button data-filter="${f}" class="${S.filters.has(f)?'active':''}" aria-pressed="${S.filters.has(f)}">${I(['star','grain-off','pork-off'][i])}${E(t('filters')[i])}</button>`).join('');
 $('#quick').innerHTML=t('quick').map((q,i)=>`<button data-quick="${i}">${E(q)}</button>`).join('');
 renderDiet();renderMenu();renderCart();
}
function renderDiet(){
 $('#dietBar').classList.toggle('hidden',S.excludes.length===0&&S.diets.length===0&&!S.needsStaff);
 $('#dietText').textContent=t('diet')+': '+[...S.excludes.map(a=>t('allergens')[a]||a),...S.diets,...(S.needsStaff?[t('staff')]:[])].join(', ');
}
function renderMenu(){
 const visible=S.menu.filter(d=>{
  if(S.cat!=='all'&&(S.cat==='beverage'?!['beverage','dessert'].includes(d.category):d.category!==S.cat))return false;
  if(S.filters.has('hit')&&!d.tags.includes('hit'))return false;
  for(const a of ['gluten','pork'])if(S.filters.has(a)&&d.allergens.includes(a))return false;
  return true;
 });
 $('#dishCount').textContent=`${visible.length} ${t('count')}`;$('#empty').classList.toggle('hidden',visible.length>0);$('#empty').textContent=t('empty');
 $('#menuGrid').innerHTML=visible.map((d,i)=>`<article class="dish" data-dish="${E(d.id)}" style="animation-delay:${Math.min(i,8)*35}ms">
 <div class="photo">${I('leaf',28)}${d.image?`<img src="${E(d.image)}" alt="${E(d.name)}" loading="lazy" referrerpolicy="no-referrer"><span class="photo-label">${E(t('photo'))}</span>`:''}</div>
 <div class="dish-body"><div class="dish-top"><h2>${E(d.name)}</h2><span class="weight">${E(d.weight)}</span></div><p class="description">${E(d.desc?.[S.lang]||d.desc?.pl||d.desc?.en||d.desc?.ru||'')}</p><div class="badges">${d.tags.includes('hit')?`<span class="badge hit">${I('star',10)} ${E(t('filters')[0])}</span>`:''}${d.allergens.map(a=>`<span class="badge">${E(t('allergens')[a]||a)}</span>`).join('')}${!d.allergens_verified?`<span class="badge warn">${E(t('unknown'))}</span>`:''}</div>
 <div class="dish-bottom"><span class="price">${new Intl.NumberFormat(S.lang).format(d.price)} <small>${E(S.currency)}</small></span><button class="add" data-add="${E(d.id)}" aria-label="${E(t('add')+': '+d.name)}" ${!d.available?'disabled':''}>${I(d.available?'plus':'ban',18)}</button></div>${!d.available?`<span class="small subtle">${E(t('stopped'))}</span>`:''}</div></article>`).join('');
 $('#menuGrid').querySelectorAll('img').forEach(img=>img.addEventListener('error',()=>{img.nextElementSibling?.remove();img.remove();},{once:true}));
}
function openChat(open=true){S.opened=open;$('#sheet').classList.toggle('open',open);$('#sheet').setAttribute('aria-hidden',String(!open));$('#sheet').inert=!open;$('#toggleChat').setAttribute('aria-expanded',String(open));$('#toggleChat').style.transform=open?'rotate(180deg)':'';if(open)$('#messages').scrollTop=$('#messages').scrollHeight;}
function addLine(ids,combo=false,automaticOffer=true){
 const same=S.lines.find(l=>l.combo===combo&&l.ids.join('|')===ids.join('|'));
 if(same&&same.qty>=30){K.toast('Максимум 30 порций в строке',true);return;}
 if(same)same.qty++;else if(S.lines.length<200)S.lines.push({ids,qty:1,combo});else{K.toast('Максимум 200 строк в чеке',true);return;}
 saveCart();renderCart();requestQuote();K.toast(t('add'));
 window.konomiTrack?.('cart_add',{dish_id:ids[0]});
 if(automaticOffer&&!combo&&ids.length===1){const d=S.menu.find(x=>x.id===ids[0]);if(d?.category==='main'&&!S.upsellsDeclined)scheduleUpsell(d.id);}
 return true;
}
function renderCart(){
 const count=S.lines.reduce((s,l)=>s+l.qty*l.ids.length,0);
 $('#cartOpen').classList.toggle('hidden',count===0);$('#cartCount').textContent=count;$('#checkout').disabled=!count||!S.quote;
 $('#cartTotal').textContent=S.quote?money(S.quote.total):'— '+S.currency;$('#dialogTotal').textContent=S.quote?money(S.quote.total):'—';
 $('#cartSaving').classList.toggle('hidden',!S.quote?.saving);$('#cartSaving').textContent=S.quote?.saving?`−${money(S.quote.saving)}`:'';
 $('#cartItems').innerHTML=S.lines.length?S.lines.map((l,i)=>{const server=S.quote?.lines[i];const names=server?.names||l.ids.map(id=>S.menu.find(d=>d.id===id)?.name||id);return `<div class="cart-line"><div class="cart-line-head"><div>${l.combo?`<span class="badge hit">${E(t('combo'))}</span><br>`:''}${names.map(E).join('<br>')}</div><span>${server?E(money(server.total)):'—'}</span></div><div class="qty-row"><button class="icon-btn" data-qty="${i}" data-delta="-1" aria-label="Уменьшить">${I('minus',13)}</button><span class="mono">${l.qty}</span><button class="icon-btn" data-qty="${i}" data-delta="1" aria-label="Увеличить" ${l.qty>=30?'disabled':''}>${I('plus',13)}</button><button class="text-btn small" data-remove="${i}">${E(t('remove'))}</button></div></div>`;}).join(''):`<p class="empty">${E(t('emptyCart'))}</p>`;
}
function requestQuote(){
 clearTimeout(quoteTimer);quoteController?.abort();S.quote=null;$('#cartStatus').textContent=S.lines.length?t('checking'):'';$('#cartStatus').className='inline-status';renderCart();
 if(!S.lines.length)return;
 const signature=JSON.stringify({lines:S.lines,excludes:S.excludes,diets:S.diets,session_id:S.session});
 quoteTimer=setTimeout(async()=>{quoteController=new AbortController();try{const result=await K.api('/api/order/quote',{method:'POST',body:JSON.parse(signature),signal:quoteController.signal});if(signature!==JSON.stringify({lines:S.lines,excludes:S.excludes,diets:S.diets,session_id:S.session}))return;S.quote=result;$('#cartStatus').textContent='';renderCart();}catch(e){if(e.name==='AbortError'||signature!==JSON.stringify({lines:S.lines,excludes:S.excludes,diets:S.diets,session_id:S.session}))return;$('#cartStatus').textContent=e.message;$('#cartStatus').className='inline-status error';$('#cartTotal').textContent='—';$('#checkout').disabled=true;}},120);
}
function message(role,text){const el=document.createElement('div');el.className='message '+(role==='user'?'user':'');const p=document.createElement('p');p.textContent=text;el.append(p);$('#messages').append(el);$('#messages').scrollTop=$('#messages').scrollHeight;return el;}
function replyCards(el,result){
 const list=document.createElement('div');list.className='chat-picks';
 list.innerHTML=(result.dishes||[]).map(id=>S.menu.find(d=>d.id===id)).filter(Boolean).map(d=>`<div class="chat-pick"><button class="text-btn" data-focus="${E(d.id)}">${E(d.name)}</button>${result.dish_annotations?.[d.id]?.diet_class==='fish'?`<span class="badge">${E(t('allergens').fish)}</span>`:''}<span>${E(money(d.price))}</span><button class="icon-btn" data-add="${E(d.id)}" aria-label="${E(t('add'))}">${I('plus',13)}</button></div>`).join('');el.append(list);
 if(result.combo){const c=result.combo;const box=document.createElement('div');box.className='combo';box.innerHTML=`<div class="combo-head">${E(t('combo'))}<span>−${c.discount}%</span></div><ul>${c.ids.map(id=>S.menu.find(d=>d.id===id)).filter(Boolean).map(d=>`<li>${E(d.name)}</li>`).join('')}</ul><div class="combo-total"><span>${E(money(c.total))}</span><del>${E(money(c.subtotal))}</del></div><button class="primary lime" data-combo="${E(c.ids.join('|'))}">${I('plus')}${E(t('set'))}</button>`;el.append(box);}
 $('#messages').scrollTop=$('#messages').scrollHeight;
}
function offerButtons(el,offer,lang){
 if(!offer||!S.lines.some(l=>l.ids.includes(offer.trigger_id)))return;
 const text=OFFER_TEXT[lang]||OFFER_TEXT.en;
 const actions=document.createElement('div');actions.className='offer-actions';
 actions.innerHTML=`<button class="primary lime" data-offer="${E(offer.id)}" data-decision="accept">${E(text[0])}</button><button class="secondary" data-offer="${E(offer.id)}" data-decision="decline">${E(text[1])}</button>`;
 el.append(actions);
}
function displayResult(r,expectedCart=null){
 if(r.session_id)setSession(r.session_id);if(r.lang)S.chatLang=r.lang;
 S.excludes=r.excludes||S.excludes;S.diets=r.diets||S.diets;if(typeof r.needs_staff==='boolean')S.needsStaff=r.needs_staff;saveCart(false);renderDiet();requestQuote();
 if(r.suppressed||!r.reply)return;
 if(r.cart_action&&!S.applied.includes(r.cart_action.id)){
  if(S.lines.length>=200){K.toast(t('error'),true);return;}
  // One persistent save contains both the added line and the applied action ID.
  r.cart_action.add.forEach(id=>{const old=S.lines.find(l=>!l.combo&&l.ids.length===1&&l.ids[0]===id);if(old)old.qty++;else S.lines.push({ids:[id],qty:1,combo:false});});
  S.applied.push(r.cart_action.id);S.applied=S.applied.slice(-1000);saveCart();requestQuote();
 }
 if(r.cart_actions?.length&&r.cart_after&&!S.applied.includes(r.cart_action_id)){
  const current=JSON.stringify(S.lines);
  if(expectedCart!==null&&current!==expectedCart){
   const text={ru:'Корзина изменилась, пока готовился ответ. Повторите команду — я не буду перезаписывать ваш выбор.',en:'Your cart changed while I was replying. Please repeat the action; your selection was not overwritten.',pl:'Koszyk zmienił się podczas odpowiedzi. Powtórz polecenie; Twój wybór nie został nadpisany.'};
   r={...r,reply:text[S.lang],cart_actions:[]};
  }else{
   S.lines=structuredClone(r.cart_after);S.applied.push(r.cart_action_id);S.applied=S.applied.slice(-1000);
   saveCart();renderCart();requestQuote();K.toast({ru:'Корзина обновлена',en:'Cart updated',pl:'Koszyk zaktualizowany'}[S.lang]);
   r.cart_actions.filter(a=>a.action==='add').forEach(a=>window.konomiTrack?.('cart_add',{dish_id:a.id}));
  }
 }
 if(r.filters?.category){S.cat=r.filters.category;document.querySelectorAll('[data-cat]').forEach(b=>{b.classList.toggle('active',b.dataset.cat===S.cat);b.setAttribute('aria-pressed',String(b.dataset.cat===S.cat));});renderMenu();}
 if(Array.isArray(r.filters?.excludes)){S.filters=new Set(r.filters.excludes.filter(a=>['pork','gluten'].includes(a)));renderMenu();}
 const el=message('assistant',r.reply);el.lang=r.lang||'und';
 if(!S.history.some(m=>m.request_id===r.request_id&&m.role==='assistant')){S.history.push({role:'assistant',content:r.reply,dishes:r.dishes||[],request_id:r.request_id});S.history=S.history.slice(-8);persistHistory();}
 if(r.plan){
  const box=document.createElement('div');box.className='agent-plan';
  const title={ru:'Расчёт набора',en:'Selection calculation',pl:'Wyliczenie zestawu'}[S.lang];
  const warning=r.plan.over_budget?{ru:'Выше указанного бюджета',en:'Above your stated budget',pl:'Powyżej budżetu'}[S.lang]:'';
  box.innerHTML=`<strong>${E(title)} · ${E(money(r.plan.total))}</strong>${r.plan.lines.map(l=>`<div>${l.qty} × ${E(S.menu.find(d=>d.id===l.id)?.name||l.id)} <span>${E(money(l.total))}</span></div>`).join('')}<p>${Math.round(r.plan.known_food_grams)} g${r.plan.people?' / '+r.plan.people+' guests':''}${r.plan.unknown_weights.length?' · '+E(t('unknown')):''}</p>${warning?`<p class="plan-warning">${E(warning)}</p>`:''}`;
  if(r.plan.grams_per_person>1000){const note=document.createElement('p');note.className='plan-warning';note.textContent={ru:'Более 1 кг указанной еды на гостя: возможно, стоит уменьшить порции.',en:'Over 1 kg of listed food per guest: consider fewer portions.',pl:'Ponad 1 kg jedzenia na osobę: rozważ mniejsze porcje.'}[S.lang];box.append(note);}
  el.append(box);
 }
 const origin=document.createElement('span');origin.className='origin';origin.textContent='Konomi AI';el.prepend(origin);
 // An upsell can only be accepted through the explicit offer action, never a generic +.
 replyCards(el,{...r,dishes:r.offer?[]:r.dishes});
 if(r.offer){openChat(true);const names=r.offer.item_ids.map(id=>S.menu.find(d=>d.id===id)).filter(Boolean);const info=document.createElement('div');info.className='chat-picks';info.innerHTML=names.map(d=>`<div class="chat-pick"><span>${E(d.name)}</span><span>${E(money(d.price))}</span></div>`).join('');el.append(info);offerButtons(el,r.offer,r.lang);}
 $('#engineLabel').textContent=r.engine==='gemini'?t('gemini'):r.engine==='openai'?t('gemini'):t('rules');$('#messages').scrollTop=$('#messages').scrollHeight;
}
function enqueue(job){turns.push(job);pump();}
async function pump(){
 if(processing||deciding)return;processing=true;S.busy=true;$('#messages').setAttribute('aria-busy','true');
 try{while(turns.length){const job=turns.shift();if(job.event==='cart_added'&&(S.upsellsDeclined||!S.lines.some(l=>l.ids.includes(job.trigger))))continue;
   const revision=cartRevision;const typing=message('assistant',t('thinking'));typing.classList.add('typing');
   try{
    if(!job.payload)job.payload={message:job.text||'',event:job.event||'message',trigger_id:job.trigger||null,session_id:S.session,request_id:job.id||uniqueKey(),history:(job.history||S.history).slice(-8).map(({role,content,dishes})=>({role,content,dishes:dishes||[]})),cart:structuredClone(S.lines),excludes:[...S.excludes],diets:[...S.diets],table:TABLE,visitor_language:S.chatLang||navigator.language||'en'};
    let r;
    try{r=await K.api('/api/chat',{method:'POST',body:job.payload});}
    catch(error){if(error.message==='GUEST_SESSION_EXPIRED'){setSession(null);job.payload.session_id=null;job.payload.request_id=uniqueKey();r=await K.api('/api/chat',{method:'POST',body:job.payload});}else throw error;}
    typing.remove();if(r.session_id)setSession(r.session_id);
    if(job.event==='cart_added'&&revision!==cartRevision)continue;
    displayResult(r,JSON.stringify(job.payload.cart));
   }catch(error){typing.remove();if(job.event==='cart_added')continue;const box=message('system',t('error'));box.classList.add('system');const retry=document.createElement('button');retry.className='text-btn';retry.style.color='var(--lime)';retry.textContent=t('retry');retry.onclick=()=>{retry.disabled=true;enqueue(job);};box.append(retry);}
 } }finally{processing=false;S.busy=false;$('#messages').setAttribute('aria-busy','false');}
}
function send(text){
 if(!text.trim())return;if(turns.filter(j=>j.event==='message').length>=3){K.toast(t('thinking'));return;}
 text=text.trim().slice(0,2000);$('#messageInput').value='';clearTimeout(offerTimer);openChat();manualSheet=true;
 const history=structuredClone(S.history);S.history.push({role:'user',content:text,dishes:[]});S.history=S.history.slice(-8);persistHistory();
 message('user',text);enqueue({event:'message',text,id:uniqueKey(),history});
}
function scheduleUpsell(id){
 clearTimeout(offerTimer);offerTimer=setTimeout(()=>enqueue({event:'cart_added',trigger:id,id:uniqueKey()}),600);
}
async function decideOffer(button){
 if(processing||deciding){K.toast(t('thinking'));return;}deciding=true;S.busy=true;const wrap=button.closest('.offer-actions');wrap.querySelectorAll('button').forEach(b=>b.disabled=true);
 if(button.dataset.decision==='decline')S.upsellsDeclined=true;
 try{const r=await K.api('/api/chat/offer',{method:'POST',body:{session_id:S.session,offer_id:button.dataset.offer,decision:button.dataset.decision,cart:S.lines}});displayResult(r);button.innerHTML=I('check')+' '+E(button.textContent);}
 catch(e){K.toast(t('error'),true);wrap.querySelectorAll('button').forEach(b=>b.disabled=false);}
 finally{deciding=false;S.busy=false;pump();}
}
async function loadMenu(){
 $('#loadStatus').hidden=false;$('#loadStatus').textContent='…';
 try{const data=await K.api('/api/menu');S.menu=data.dishes;S.venue=data.venue;S.city=data.city;S.currency=data.currency||'PLN';$('#venue').textContent=data.venue;$('#loadStatus').hidden=true;applyLanguage();requestQuote();}
 catch(e){$('#loadStatus').innerHTML=`${E(t('load'))} <button class="text-btn" id="reloadMenu">${E(t('retry'))}</button>`;$('#reloadMenu').onclick=loadMenu;}
}
function greet(){
 if($('#messages').children.length)return;const box=message('system',({ru:(S.venue?'Добро пожаловать в '+S.venue+'. ':'Добро пожаловать. ')+'Помогу с меню, составом и вашим заказом.',en:(S.venue?'Welcome to '+S.venue+'. ':'Welcome. ')+'I can help with the menu, ingredients and your order.',pl:(S.venue?'Witamy w '+S.venue+'. ':'Witamy. ')+'Pomogę z menu, składnikami i zamówieniem.'}[S.lang]));box.classList.add('system');
}
function voice(){
 const Recognition=window.SpeechRecognition||window.webkitSpeechRecognition;
 if(!Recognition){K.toast(t('voice'));return;}
 const rec=new Recognition();rec.lang=S.chatLang||navigator.language||'en-US';let ended=false;$('#mic').disabled=true;$('#mic').classList.add('live');
 const reset=()=>{if(ended)return;ended=true;$('#mic').disabled=false;$('#mic').classList.remove('live');};rec.onresult=e=>{reset();send(e.results[0][0].transcript);};rec.onerror=()=>{reset();K.toast(t('voice'),true);};rec.onend=reset;try{rec.start();}catch{reset();K.toast(t('voice'),true);}
}
function uniqueKey(){return globalThis.crypto?.randomUUID?.()||Date.now().toString(36)+'-'+Math.random().toString(36).slice(2);}

restoreCart();applyLanguage();openChat(false);greet();
if(TABLE){$('#tableContext').textContent='Table '+TABLE;$('#tableContext').classList.remove('hidden');}
setTimeout(()=>{if(!manualSheet&&!document.querySelector('dialog[open]')){autoOpened=true;openChat(true);}},500);
let dwelled=false;const dwellStart=Date.now();window.addEventListener('scroll',()=>{if(!dwelled&&Date.now()-dwellStart>45000&&!S.lines.length&&!S.busy){dwelled=true;const el=message('system',t('quick')[1]+'?');el.classList.add('system');openChat();}},{passive:true});
new ResizeObserver(entries=>document.documentElement.style.setProperty('--dock-h',entries[0].target.getBoundingClientRect().height+'px')).observe($('#dock'));
// Keep controls above the software keyboard, including Safari visualViewport resizing.
function keyboard(){const v=window.visualViewport;const offset=v?Math.max(0,innerHeight-v.height-v.offsetTop):0;document.documentElement.style.setProperty('--keyboard',offset+'px');}
window.visualViewport?.addEventListener('resize',keyboard);window.visualViewport?.addEventListener('scroll',keyboard);
$('#toggleChat').onclick=()=>{manualSheet=true;openChat(!S.opened);};$('#closeChat').onclick=()=>{manualSheet=true;openChat(false);};$('#grab').onclick=()=>{manualSheet=true;openChat(false);};
let startY=0;$('#grab').addEventListener('pointerdown',e=>{startY=e.clientY;$('#grab').setPointerCapture(e.pointerId);});$('#grab').addEventListener('pointerup',e=>{if(e.clientY-startY>35)openChat(false);});
$('#messageInput').addEventListener('focus',()=>openChat());$('#composer').onsubmit=e=>{e.preventDefault();send($('#messageInput').value);};$('#mic').onclick=voice;
$('#cartOpen').onclick=()=>{$('#cartDialog').showModal();requestQuote();};
document.querySelectorAll('[data-close]').forEach(b=>b.onclick=()=>$('#'+b.dataset.close).close());
$('#clearCart').onclick=()=>{S.lines=[];saveCart();requestQuote();};$('#clearDiet').onclick=async()=>{if(processing||deciding){K.toast(t('thinking'));return;}try{if(S.session)await K.api('/api/chat/reset-constraints',{method:'POST',body:{session_id:S.session}});S.excludes=[];S.diets=[];S.needsStaff=false;saveCart();renderDiet();requestQuote();}catch(e){K.toast(t('error'),true);}};
document.addEventListener('click',e=>{
 const decision=e.target.closest('[data-offer]');if(decision){decideOffer(decision);return;}
 const add=e.target.closest('[data-add]');if(add){addLine([add.dataset.add]);return;}
 const combo=e.target.closest('[data-combo]');if(combo){addLine(combo.dataset.combo.split('|'),true);combo.disabled=true;combo.innerHTML=I('check')+' '+E(t('add'));return;}
 const cat=e.target.closest('[data-cat]');if(cat){S.cat=cat.dataset.cat;applyLanguage();return;}
 const filter=e.target.closest('[data-filter]');if(filter){const f=filter.dataset.filter;S.filters.has(f)?S.filters.delete(f):S.filters.add(f);applyLanguage();return;}
 const focus=e.target.closest('[data-focus]');if(focus){openChat(false);S.cat='all';S.filters.clear();applyLanguage();const card=[...document.querySelectorAll('[data-dish]')].find(x=>x.dataset.dish===focus.dataset.focus);if(card){card.classList.add('highlight');card.scrollIntoView({behavior:'smooth',block:'center'});}return;}
 const quick=e.target.closest('[data-quick]');if(quick){send(t('quick')[Number(quick.dataset.quick)]);return;}
 const lang=e.target.closest('[data-lang]');if(lang){S.lang=lang.dataset.lang;K.save('konomi-lang',S.lang);applyLanguage();return;}
 const qty=e.target.closest('[data-qty]');if(qty){const i=Number(qty.dataset.qty);S.lines[i].qty+=Number(qty.dataset.delta);S.lines=S.lines.filter(l=>l.qty>0);saveCart();requestQuote();return;}
 const remove=e.target.closest('[data-remove]');if(remove){S.lines.splice(Number(remove.dataset.remove),1);saveCart();requestQuote();}
});
$('#checkout').onclick=async()=>{
 if(!S.quote)return;$('#checkout').disabled=true;S.idempotency ||= uniqueKey();saveCart(false);
 try{const r=await K.api('/api/orders',{method:'POST',body:{lines:S.lines,excludes:S.excludes,diets:S.diets,idempotency_key:S.idempotency,session_id:S.session,table:TABLE}});$('#receipt').innerHTML=`<p class="small subtle">${E(S.venue)} · ${E(new Date(r.created_at).toLocaleString(S.lang))}${r.table?' · Table '+r.table:''}</p>${r.lines.map(l=>`<div class="cart-line-head"><span>${l.qty} × ${l.names.map(E).join(' + ')}</span><span>${E(money(l.total))}</span></div>`).join('')}<div class="total-row"><span>${E(t('total'))}</span><span>${E(money(r.total))}</span></div>${r.saving?`<p class="small subtle">${E(t('saving'))}: ${E(money(r.saving))}</p>`:''}<div class="checkout-code"><span class="small">${E(t('show'))}</span><strong>${E(r.code)}</strong></div><p class="small subtle">${E(t('notice'))}</p>`;$('#cartDialog').close();$('#receiptDialog').showModal();window.konomiReceipt?.(r);}catch(e){K.toast(e.message,true);}finally{$('#checkout').disabled=!S.quote;}
};
(async()=>{await loadMenu();try{lastWeather=await K.api('/api/weather');$('#weather').innerHTML=I(lastWeather.condition==='clear'?'sun':['rain','drizzle'].includes(lastWeather.condition)?'rain':'cloud')+E(lastWeather.temp===null?lastWeather.city:`${lastWeather.city} ${lastWeather.temp}°C`);if(lastWeather.stale)$('#weather').title='Weather data unavailable or stale';}catch{$('#weather').textContent=S.city||'';}greet();})();
