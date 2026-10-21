"""Offline menu operations. Deterministic, no fabricated dishes or remote AI claims."""
import re
from collections import Counter
import dining
import store
import agent_contract as contract

WORDS={
'ru':{'list':'Вот позиции из текущего меню:','empty':'Под эти условия в загруженном меню позиций нет. Могу подобрать другой вариант.','cart':'Обновляю заказ по вашей просьбе.','ambiguous':'Уточните название блюда: под это описание подходит несколько позиций.','fish':'Рыба указана отдельно: это не вегетарианское блюдо.','restricted':'Есть ограничения по составу; позиции с известным исключённым ингредиентом нельзя добавить.','offline':'Работаю по загруженному меню.','set':'Предлагаю такой набор.','missing':'Такой позиции в загруженном меню нет. Вот доступные альтернативы:','budget':'Этот вариант превышает бюджет; ниже точный расчёт.','allergy':'Неизвестный аллерген требует уточнения; меню остаётся доступным для просмотра.'},
'en':{'list':'These items are on the current menu:','empty':'No items in the loaded menu match these requirements. I can help adjust the choice.','cart':'Updating the order as you requested.','ambiguous':'Please specify the dish name; several items match that description.','fish':'Fish is listed separately; it is not vegetarian.','restricted':'Known excluded ingredients prevent adding the affected items.','offline':'I am using the loaded menu.','set':'Here is a suggested selection.','missing':'That item is not in the loaded menu. Here are available alternatives:','budget':'This selection exceeds the budget; the exact calculation is shown below.','allergy':'An unknown allergen needs clarification; the menu remains visible.'},
'pl':{'list':'Oto pozycje z aktualnego menu:','empty':'Żadna pozycja w załadowanym menu nie spełnia tych warunków. Możemy zmienić wybór.','cart':'Aktualizuję zamówienie zgodnie z prośbą.','ambiguous':'Podaj nazwę dania; kilka pozycji pasuje do opisu.','fish':'Ryby są pokazane oddzielnie: nie są wegetariańskie.','restricted':'Znane wykluczone składniki blokują dodanie odpowiednich dań.','offline':'Korzystam z załadowanego menu.','set':'Proponuję taki zestaw.','missing':'Tej pozycji nie ma w załadowanym menu. Oto alternatywy:','budget':'Zestaw przekracza budżet; dokładne wyliczenie znajduje się poniżej.','allergy':'Nieznany alergen wymaga wyjaśnienia; menu pozostaje widoczne.'},
'de':{'list':'Diese Gerichte stehen auf der aktuellen Karte:','empty':'Keine Position der geladenen Karte erfüllt diese Anforderungen. Wir können die Auswahl anpassen.','cart':'Ich aktualisiere Ihre Bestellung wie gewünscht.','ambiguous':'Bitte nennen Sie das Gericht; mehrere Positionen passen zu dieser Beschreibung.','fish':'Fisch wird gesondert aufgeführt; er ist nicht vegetarisch.','restricted':'Bekannte ausgeschlossene Zutaten verhindern das Hinzufügen betroffener Gerichte.','offline':'Ich verwende die geladene Speisekarte.','set':'Ich schlage diese Auswahl vor.','missing':'Dieses Gericht steht nicht auf der geladenen Karte. Hier sind Alternativen:','budget':'Diese Auswahl überschreitet das Budget; die genaue Berechnung steht unten.','allergy':'Ein unbekanntes Allergen muss geklärt werden; die Speisekarte bleibt sichtbar.'},
'uk':{'list':'Ось позиції з поточного меню:','empty':'У завантаженому меню немає позицій під ці умови. Можемо змінити вибір.','cart':'Оновлюю замовлення за вашим проханням.','ambiguous':'Уточніть назву страви: під опис підходить кілька позицій.','fish':'Рибу показано окремо: це не вегетаріанська страва.','restricted':'Відомі виключені інгредієнти блокують додавання відповідних страв.','offline':'Працюю із завантаженим меню.','set':'Пропоную такий набір.','missing':'Цієї позиції немає в завантаженому меню. Ось альтернативи:','budget':'Набір перевищує бюджет; точний розрахунок наведено нижче.','allergy':'Невідомий алерген потребує уточнення; меню залишається видимим.'}}

ALIASES={
 r'компот\w*|compote|kompot':r'kompot|compote|компот',
 r'торт\w*|cake|tort':r'tort|cake|торт',
 r'чизкейк|sernik|cheesecake':r'sernik|cheesecake|чизкейк',
 r'журек|żurek|zurek':r'żurek|zurek|журек',
 r'бульон|росол|ros[oó]ł|broth':r'ros[oó]ł|broth|бульон',
 r'пицц\w*|pizza':r'pizza|пицц',
 r'суши|sushi':r'sushi|суши',
 r'кофе|coffee|kawa':r'coffee|kawa|кофе',
 r'чай|tea|herbata':r'tea|herbata|чай'}

def named_matches(message,items):
    low=message.casefold();matches=[]
    for d in items:
        name=d['name'].casefold()
        if name in low or re.search(r'(?<!\w)'+re.escape(d['id'].casefold())+r'(?!\w)',low):matches.append(d);continue
        if any(re.search(query,low) and re.search(target,name) for query,target in ALIASES.items()):matches.append(d)
    return matches

def requested_count(message):
    if re.search(r'\b(?:один|одну|одно|one|a single|jedn[ąoa]|ein(?:e|en)?)\b',message,re.I):return 1
    m=re.search(r'(?:покажи|предложи|посоветуй|show|recommend|poleć|zeige)\s+(\d+)\b',message,re.I)
    return int(m.group(1)) if m else None

def select(message,items,prefs):
    low=message.casefold();topics=set(prefs.get('topics',[]))
    if prefs.get('diets'):
        return [d for d in items if all(dining.diet_matches(d,diet) for diet in prefs['diets'])]
    named=named_matches(message,items)
    if named:return named
    if 'SOUP' in topics:return [d for d in items if d['category']=='soup']
    if 'DESSERT' in topics:return [d for d in items if d['category']=='dessert']
    if 'DRINK' in topics:return [d for d in items if d['category']=='beverage']
    if re.search(r'закуск\w*|starter|appetizer|przystawk|vorspeis',low):return [d for d in items if d['category']=='starter']
    if topics & {'DUCK','GOOSE','POULTRY','MEAT','PORK','DUMPLINGS','FISH','LIGHT'}:return dining.select(items,prefs,{})
    return list(items)


def group_plan(message,items,prefs):
    low=message.casefold();people=prefs.get('people',1)
    m=re.search(r'(?:на|for|für|dla)\s+(\d+)\s*(?:человек|гост|person|people|os[oó]b|g[aä]ste)',low)
    if m:people=max(1,min(30,int(m.group(1))))
    if re.search(r'на троих|for three|für drei|dla trzech',low):people=3
    if re.search(r'на четверых|for four|für vier|dla czterech',low):people=4
    specs=[('soup',r'(\d+)\s*(?:первых|первое|суп\w*|soups?|zup\w*|suppen?)'),('main',r'(\d+)\s*(?:вторых|горячих|основных|mains?|dania główne|hauptgerichte?)'),('beverage',r'(\d+)\s*(?:напитк\w*|drinks?|napoj\w*|getränke?)'),('starter',r'(\d+)[- ]?(?:е\s*)?\s*(?:закуск\w*|starters?|appetizers?|przystawk\w*|vorspeisen?)')]
    counts={cat:int(m.group(1)) for cat,pat in specs if (m:=re.search(pat,low))}
    explicit_counts=bool(counts)
    if not counts and (prefs.get('combo') or re.search(r'сет|набор|собери|собрать|rebuild|build|meal|set|zestaw',low)):counts={'soup':people,'main':people,'beverage':people}
    if not counts:return [],people
    plan=[]
    for category,count in counts.items():
        options=[d for d in items if d['category']==category]
        if prefs.get('budget') is not None:options.sort(key=lambda d:d['price'])
        if not options:continue
        grouped=Counter(options[i%len(options)]['id'] for i in range(min(30,count)))
        plan.extend({'id':ident,'qty':qty} for ident,qty in grouped.items())
    if not explicit_counts and prefs.get('budget') is not None:
        by={d['id']:d for d in items}
        while len(plan)>1 and sum(dining.cents(by[x['id']]['price'])*x['qty'] for x in plan)>dining.cents(prefs['budget']):plan.pop()
    return plan,people


def quantity_near(message,dish):
    low=message.casefold();positions=[]
    for query,target in ALIASES.items():
        if re.search(target,dish['name'],re.I):positions.extend(m.start() for m in re.finditer(query,low))
    pos=low.find(dish['name'].casefold())
    if pos>=0:positions.append(pos)
    number=r'(\d+|два|две|один|одну|три|четыре|two|three|four|one|dwa|dwie|trzy|cztery|zwei|drei|vier)\s*$'
    mapping={'два':2,'две':2,'один':1,'одну':1,'три':3,'четыре':4,'two':2,'three':3,'four':4,'one':1,'dwa':2,'dwie':2,'trzy':3,'cztery':4,'zwei':2,'drei':3,'vier':4}
    for pos in positions:
        match=re.search(number,low[max(0,pos-18):pos])
        if match:return mapping.get(match.group(1),int(match.group(1)) if match.group(1).isdigit() else 1)
    match=re.search(r'(?:количество|qty|quantity|set|поставь|сделай|ustaw)\D{0,10}(\d+)',low)
    return int(match.group(1)) if match else 1


def respond(message,items,state,lang):
    prefs=dining.guest_preferences(message);prefs['diets']=set(state['diets']);prefs['budget']=state['budget']
    if lang not in WORDS and lang not in dining.TEXT:
        from fastapi import HTTPException
        raise HTTPException(503,'AI_PROVIDER_REQUIRED_FOR_LANGUAGE:'+lang)
    words=WORDS.get(lang,WORDS['en']);low=message.casefold()
    selected=select(message,items,prefs);limit=requested_count(message)
    if limit is not None:selected=selected[:limit] # Explicit guest count, never an arbitrary card cap.
    out={'reply':words['list'] if selected else words['empty'],'dishes':[d['id'] for d in selected],'cart_actions':[],'combo':None,'plan':[],'engine':'rules'}
    if selected and len(selected)<=12:out['reply']+=' '+ '; '.join(d['name'] for d in selected)+'.'
    elif selected:out['reply']+=' '+str(len(selected))+'.'
    if any(dining.diet_class(d)=='fish' for d in selected) and prefs['diets']:out['reply']+=' '+words['fish']
    if set(prefs.get('topics',[]))&{'PROMPT_INJECTION'}:
        out.update(reply=dining.say(lang,'offtopic') or words['offline'],dishes=[]);return out
    # Unsupported foods are not universally forbidden: match the actual uploaded catalogue.
    missing=any(re.search(q,low) and not any(re.search(t,d['name'],re.I) for d in items) for q,t in ALIASES.items())
    if missing and not named_matches(message,items):out['reply']=words['missing']+' '+ '; '.join(d['name'] for d in selected)+'.'
    plan,people=group_plan(message,items,prefs)
    if plan:out.update(reply=words['set'],plan=plan,dishes=list(dict.fromkeys(row['id'] for row in plan)),people=people)
    if prefs.get('combo') and people==1:
        ids=dining.best_combo(items,prefs,{},store.settings()['combo_discount'])
        if ids:
            out['combo']={'ids':ids};out['plan']=[];out['dishes']=ids
    if re.search(r'ещ[её].{0,6}(?:4|четв[её]рт)|fourth|next dish|another dish|jeszcze.*danie|weiteres gericht',low):
        previous={ident for m in state['history'] if m['role']=='assistant' for ident in m.get('dishes',[])}
        extra=next((d for d in items if d['id'] not in previous),None)
        if extra:out.update(dishes=[extra['id']],reply=words['list']+' '+extra['name']+'.')
    permissions=contract.authorized_actions(message)
    if permissions:
        actions=[]
        if 'clear' in permissions:actions.append({'action':'clear'})
        named=named_matches(message,items)
        if not named and re.search(r'этот|эту|его|that|this|diese|ten|tę',low):
            last=next((m.get('dishes',[]) for m in reversed(state['history']) if m['role']=='assistant' and m.get('dishes')),[])
            resolved=[d for d in items if d['id'] in last]
            if 'SOUP' in prefs.get('topics',[]):resolved=[d for d in resolved if d['category']=='soup']
            if len(resolved)==1:named=resolved
        if re.search(r'этот суп|эту зупу|this soup|that soup|diese suppe',low):
            last=next((m.get('dishes',[]) for m in reversed(state['history']) if m['role']=='assistant' and m.get('dishes')),[])
            soups=[d for d in items if d['id'] in last and d['category']=='soup']
            if len(soups)==1:named=list({d['id']:d for d in named+soups}.values())
            else:out['cart_actions']=[];out['reply']=words['ambiguous'];return out
        if 'add' in permissions and plan:actions.extend({'action':'add',**row} for row in plan)
        elif 'add' in permissions:
            targets=named or selected
            if not named and len(targets)>1:out['reply']=words['ambiguous']
            else:actions.extend({'action':'add','id':d['id'],'qty':quantity_near(message,d)} for d in targets)
        if 'remove' in permissions:actions.extend({'action':'remove','id':d['id']} for d in named)
        if 'set_qty' in permissions:actions.extend({'action':'set_qty','id':d['id'],'qty':quantity_near(message,d)} for d in named)
        # Do not empty a cart on an ambiguous compound rebuild command.
        if len(permissions)>1 and actions==[{'action':'clear'}]:actions=[];out['reply']=words['ambiguous']
        out['cart_actions']=actions
        if actions:out['reply']=words['cart']
    return out
