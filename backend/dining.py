"""Deterministic safety, ranking and pairing. No generated prices, stock or margins.
Optional flavor/cost/diet metadata must be entered by the restaurant, never invented.
"""
import itertools
import json
import re
from decimal import Decimal, ROUND_HALF_UP
import store

ALLERGENS={'gluten','pork','lactose','milk','egg','fish','nuts','peanut','soy','sesame','celery','mustard','shellfish','molluscs','sulphites','lupin'}
DIETS={'vegan','vegetarian','pescatarian','halal','kosher'}
TEXT={
'en':{'hello':'Welcome. I can explain the dishes, help you choose and suggest a set. Tell me what you enjoy and any dietary restrictions.','none':'I cannot find a verified dish for these requirements. Please confirm the ingredients with your waiter.','safety':'For an allergy, confirm ingredients and cross-contact with your waiter.','recommend':'Here are my suggestions from the available menu. Would you prefer something light or hearty?','upsell':'Would you like {name} to accompany your choice? It is optional; you can add it or decline.','decline':'Of course. I will not suggest any more extras in this session.','accepted':'I have added your chosen accompaniment to the guest check.','expired':'That suggestion is no longer available. Nothing has been added; please check the menu again.','nooffer':'Your choice is complete. I do not have a suitable accompaniment within the current constraints.','clarify':'Tell me about your appetite, budget or dietary requirements, and I will narrow down the menu.','offtopic':'I can help with this restaurant’s menu, ingredients, pairings and guest check. What would you like to eat?','budget':'I cannot find a complete set within that budget. I can suggest individual dishes instead.','combo':'Here is a balanced set from the available dishes. The current price and discount are shown below.','confirm':'There is no active offer to accept. Please choose a dish or tell me what you would like.','unavailable':'That dish is not available to order. I can help choose an alternative.','culture':'Kartacze are large potato dumplings with a meat filling, similar to Lithuanian cepelinai.'},
'ru':{'hello':'Добро пожаловать. Расскажу о блюдах, помогу выбрать и собрать сет. Подскажите, что любите и есть ли ограничения по питанию.','none':'Не нашёл подтверждённых блюд под эти условия. Уточните состав у официанта — отсутствие отметки не означает безопасность.','safety':'При аллергии подтвердите состав и риск перекрёстного контакта у официанта.','recommend':'Вот варианты из доступного меню. Вам хочется чего-то лёгкого или сытного?','upsell':'К вашему выбору могу предложить {name}. Добавить это дополнение или оставить заказ как есть?','decline':'Конечно, оставим ваш выбор без дополнений. Больше не буду предлагать допродажи в этой сессии.','accepted':'Добавил выбранное дополнение в чек гостя.','expired':'Это предложение уже недоступно. Ничего не добавлено — уточним выбор по актуальному меню.','nooffer':'Подходящего дополнения в рамках ваших ограничений сейчас нет. Оставим выбранный заказ.','clarify':'Подскажите аппетит, бюджет или ограничения по питанию — я сужу выбор до нескольких блюд.','offtopic':'Я помогу с меню этого ресторана, составом, сочетаниями и чеком гостя. Что вам хотелось бы попробовать?','budget':'Полный сет не укладывается в этот бюджет. Могу подобрать отдельные блюда.','combo':'Подобрал сбалансированный сет из доступных блюд. Актуальная цена и скидка указаны ниже.','confirm':'Сейчас нет активного предложения для подтверждения. Выберите блюдо или уточните пожелание.','unavailable':'Эту позицию сейчас нельзя заказать. Помогу выбрать доступную альтернативу.','culture':'Kartacze — крупные картофельные клёцки с мясом, похожие на литовские цеппелины.'},
'pl':{'hello':'Witamy. Wyjaśnię dania i pomogę wybrać zestaw. Co lubisz i czy masz ograniczenia żywieniowe?','none':'Nie znalazłem potwierdzonych dań dla tych wymagań. Potwierdź skład z kelnerem.','safety':'Przy alergii potwierdź skład i ryzyko kontaktu krzyżowego z kelnerem.','recommend':'Oto propozycje z dostępnego menu. Wolisz coś lekkiego czy sycącego?','upsell':'Do Twojego wyboru mogę zaproponować {name}. Dodać czy pozostawić zamówienie bez zmian?','decline':'Oczywiście. Nie będę już proponować dodatków w tej sesji.','accepted':'Dodałem wybrany dodatek do rachunku gościa.','expired':'Ta propozycja jest już niedostępna. Niczego nie dodano. Sprawdźmy aktualne menu.','nooffer':'Nie ma odpowiedniego dodatku spełniającego te wymagania. Pozostawmy obecny wybór.','clarify':'Podaj apetyt, budżet lub ograniczenia żywieniowe, a zawężę wybór.','offtopic':'Pomogę z menu tej restauracji, składnikami i zestawami. Na co masz ochotę?','budget':'Pełny zestaw nie mieści się w budżecie. Mogę polecić pojedyncze dania.','combo':'Oto zbilansowany zestaw z dostępnych dań. Cena i zniżka są poniżej.','confirm':'Nie ma aktywnej propozycji do potwierdzenia. Wybierz danie lub opisz życzenie.','unavailable':'Tego dania nie można teraz zamówić. Pomogę wybrać alternatywę.','culture':'Kartacze to duże kluski ziemniaczane z mięsem, podobne do litewskich cepelinów.'},
'de':{'hello':'Willkommen. Ich erkläre Ihnen die Gerichte und helfe bei der Auswahl. Was mögen Sie, und haben Sie Ernährungseinschränkungen?','none':'Für diese Anforderungen finde ich keine bestätigten Gerichte. Bitte klären Sie die Zutaten mit dem Service.','safety':'Bei Allergien klären Sie Zutaten und mögliche Kreuzkontakte bitte mit dem Service.','recommend':'Hier sind meine Empfehlungen aus der verfügbaren Speisekarte. Möchten Sie etwas Leichtes oder Herzhaftes?','upsell':'Zu Ihrer Auswahl kann ich {name} empfehlen. Möchten Sie die Ergänzung hinzufügen oder lieber darauf verzichten?','decline':'Selbstverständlich. Ich werde in dieser Sitzung keine weiteren Ergänzungen anbieten.','accepted':'Ich habe die gewählte Ergänzung zum Gästebeleg hinzugefügt.','expired':'Dieses Angebot ist nicht mehr verfügbar. Es wurde nichts hinzugefügt. Wir können die aktuelle Karte prüfen.','nooffer':'Unter diesen Voraussetzungen ist keine passende Ergänzung verfügbar. Wir belassen es bei Ihrer Auswahl.','clarify':'Nennen Sie mir Ihren Appetit, Ihr Budget oder Ihre Ernährungseinschränkungen, damit ich die Auswahl eingrenzen kann.','offtopic':'Ich helfe Ihnen mit der Speisekarte dieses Restaurants, Zutaten und passenden Kombinationen. Worauf haben Sie Appetit?','budget':'Ein vollständiges Menü passt nicht in dieses Budget. Ich kann einzelne Gerichte empfehlen.','combo':'Hier ist ein ausgewogenes Menü aus verfügbaren Gerichten. Preis und Rabatt stehen darunter.','confirm':'Es gibt kein aktives Angebot zu bestätigen. Bitte wählen Sie ein Gericht oder nennen Sie Ihren Wunsch.','unavailable':'Dieses Gericht ist derzeit nicht bestellbar. Ich helfe Ihnen, eine Alternative zu finden.','culture':'Kartacze sind große Kartoffelklöße mit Fleischfüllung, ähnlich den litauischen Cepelinai.'},
'fr':{'hello':'Bienvenue. Je peux expliquer les plats et vous aider à choisir. Quels sont vos goûts et vos contraintes alimentaires ?','none':'Je ne trouve aucun plat vérifié pour ces contraintes. Veuillez confirmer les ingrédients avec le serveur.','safety':'En cas d’allergie, confirmez les ingrédients et les contacts croisés avec le serveur.','recommend':'Voici mes suggestions parmi les plats disponibles. Préférez-vous un repas léger ou copieux ?','upsell':'Pour accompagner votre choix, je peux proposer {name}. Voulez-vous cet ajout ou préférez-vous refuser ?','decline':'Bien sûr. Je ne proposerai plus de suppléments pendant cette session.','accepted':'J’ai ajouté l’accompagnement choisi à votre note.','expired':'Cette proposition n’est plus disponible. Rien n’a été ajouté. Vérifions le menu actuel.','nooffer':'Aucun accompagnement adapté ne respecte ces contraintes. Gardons votre choix.','clarify':'Indiquez votre appétit, votre budget ou vos contraintes alimentaires pour affiner le choix.','offtopic':'Je peux vous aider avec le menu de ce restaurant, les ingrédients et les accords. Que souhaitez-vous manger ?','budget':'Un menu complet dépasse ce budget. Je peux proposer des plats individuels.','combo':'Voici un menu équilibré parmi les plats disponibles. Le prix et la remise figurent ci-dessous.','confirm':'Il n’y a aucune proposition active à confirmer. Choisissez un plat ou précisez votre souhait.','unavailable':'Ce plat n’est pas disponible actuellement. Je peux proposer une alternative.','culture':'Les kartacze sont de grosses quenelles de pomme de terre farcies à la viande, proches des cepelinai lituaniens.'},
'es':{'hello':'Bienvenido. Puedo explicar los platos y ayudarle a elegir. ¿Qué le gusta y tiene restricciones alimentarias?','none':'No encuentro platos verificados para estos requisitos. Confirme los ingredientes con el camarero.','safety':'Si tiene alergias, confirme ingredientes y posibles contactos cruzados con el camarero.','recommend':'Estas son mis sugerencias del menú disponible. ¿Prefiere algo ligero o abundante?','upsell':'Para acompañar su elección, puedo ofrecer {name}. ¿Desea añadirlo o prefiere rechazarlo?','decline':'Por supuesto. No ofreceré más extras durante esta sesión.','accepted':'He añadido el acompañamiento elegido a su cuenta.','expired':'Esta propuesta ya no está disponible. No se ha añadido nada. Revisemos el menú actual.','nooffer':'No hay acompañamientos adecuados para estos requisitos. Mantendremos su elección.','clarify':'Dígame su apetito, presupuesto o restricciones alimentarias para reducir la selección.','offtopic':'Puedo ayudarle con el menú de este restaurante, ingredientes y combinaciones. ¿Qué le apetece comer?','budget':'Un menú completo no cabe en ese presupuesto. Puedo sugerir platos individuales.','combo':'Aquí tiene un menú equilibrado con platos disponibles. El precio y descuento están debajo.','confirm':'No hay una propuesta activa para aceptar. Elija un plato o indique su preferencia.','unavailable':'Este plato no está disponible. Puedo ayudarle a elegir otra opción.','culture':'Los kartacze son grandes albóndigas de patata rellenas de carne, similares a los cepelinai lituanos.'},
'it':{'hello':'Benvenuto. Posso spiegare i piatti e aiutare nella scelta. Quali gusti e restrizioni alimentari ha?','none':'Non trovo piatti verificati per queste esigenze. Confermi gli ingredienti con il cameriere.','safety':'In caso di allergie, confermi ingredienti e contatti incrociati con il cameriere.','recommend':'Ecco i suggerimenti dal menu disponibile. Preferisce qualcosa di leggero o sostanzioso?','upsell':'Per accompagnare la sua scelta posso proporre {name}. Vuole aggiungerlo oppure preferisce rifiutare?','decline':'Certamente. Non proporrò altri extra in questa sessione.','accepted':'Ho aggiunto l’accompagnamento scelto al conto.','expired':'La proposta non è più disponibile. Non è stato aggiunto nulla. Controlliamo il menu attuale.','nooffer':'Non ci sono accompagnamenti adatti a questi requisiti. Manteniamo la scelta attuale.','clarify':'Mi indichi appetito, budget o restrizioni alimentari per restringere la scelta.','offtopic':'Posso aiutarla con il menu di questo ristorante, ingredienti e abbinamenti. Che cosa desidera mangiare?','budget':'Un menu completo supera il budget. Posso proporre singoli piatti.','combo':'Ecco un menu equilibrato con piatti disponibili. Prezzo e sconto sono indicati sotto.','confirm':'Non c’è una proposta attiva da confermare. Scelga un piatto o descriva il desiderio.','unavailable':'Questo piatto non è disponibile. Posso aiutarla a scegliere un’alternativa.','culture':'I kartacze sono grandi gnocchi di patate ripieni di carne, simili ai cepelinai lituani.'},
'pt':{'hello':'Bem-vindo. Posso explicar os pratos e ajudar na escolha. Quais são os seus gostos e restrições alimentares?','none':'Não encontro pratos verificados para estes requisitos. Confirme os ingredientes com o empregado.','safety':'Em caso de alergia, confirme ingredientes e contactos cruzados com o empregado.','recommend':'Estas são as minhas sugestões do menu disponível. Prefere algo leve ou mais substancial?','upsell':'Para acompanhar a sua escolha, posso sugerir {name}. Deseja adicionar ou prefere recusar?','decline':'Claro. Não voltarei a propor extras nesta sessão.','accepted':'Adicionei o acompanhamento escolhido à conta.','expired':'Esta proposta já não está disponível. Nada foi adicionado. Vamos verificar o menu atual.','nooffer':'Não há acompanhamentos adequados a estes requisitos. Mantemos a escolha atual.','clarify':'Indique o seu apetite, orçamento ou restrições alimentares para reduzir as opções.','offtopic':'Posso ajudar com o menu deste restaurante, ingredientes e combinações. O que deseja comer?','budget':'Um menu completo ultrapassa o orçamento. Posso sugerir pratos individuais.','combo':'Aqui está um menu equilibrado com pratos disponíveis. O preço e desconto estão abaixo.','confirm':'Não existe proposta ativa para aceitar. Escolha um prato ou diga o que deseja.','unavailable':'Este prato não está disponível. Posso ajudar a escolher uma alternativa.','culture':'Os kartacze são grandes bolinhos de batata recheados com carne, semelhantes aos cepelinai lituanos.'},
'uk':{'hello':'Вітаю. Розповім про страви та допоможу обрати. Що ви любите та які маєте обмеження в харчуванні?','none':'Не знайшов перевірених страв під ці вимоги. Уточніть склад в офіціанта.','safety':'За алергії підтвердьте склад і ризик перехресного контакту в офіціанта.','recommend':'Ось варіанти з доступного меню. Бажаєте легку чи ситну страву?','upsell':'До вашого вибору можу запропонувати {name}. Додати чи залишити замовлення без змін?','decline':'Звісно. Більше не пропонуватиму доповнень у цій сесії.','accepted':'Додав обране доповнення до чека гостя.','expired':'Ця пропозиція вже недоступна. Нічого не додано. Перевірмо актуальне меню.','nooffer':'Відповідного доповнення під ці обмеження немає. Залишимо ваш вибір.','clarify':'Підкажіть апетит, бюджет або обмеження в харчуванні — я звужу вибір.','offtopic':'Я допоможу з меню цього ресторану, складом і поєднаннями. Що бажаєте скуштувати?','budget':'Повний сет не вкладається в бюджет. Можу порадити окремі страви.','combo':'Ось збалансований сет із доступних страв. Актуальна ціна та знижка наведені нижче.','confirm':'Зараз немає активної пропозиції для підтвердження. Оберіть страву або уточніть побажання.','unavailable':'Цю страву зараз не можна замовити. Допоможу обрати альтернативу.','culture':'Kartacze — великі картопляні галушки з м’ясом, схожі на литовські цепеліни.'},
'nl':{'hello':'Welkom. Ik kan gerechten uitleggen en helpen kiezen. Wat vindt u lekker en zijn er dieetbeperkingen?','none':'Ik vind geen gecontroleerde gerechten voor deze voorwaarden. Vraag de bediening naar de ingrediënten.','safety':'Bevestig bij een allergie de ingrediënten en mogelijke kruiscontacten bij de bediening.','recommend':'Dit zijn mijn suggesties uit de beschikbare kaart. Wilt u iets lichts of hartigs?','upsell':'Bij uw keuze kan ik {name} aanbevelen. Wilt u dit toevoegen of liever afwijzen?','decline':'Natuurlijk. Ik zal in deze sessie geen extra’s meer voorstellen.','accepted':'Ik heb de gekozen aanvulling aan uw rekening toegevoegd.','expired':'Dit voorstel is niet meer beschikbaar. Er is niets toegevoegd. Laten we de actuele kaart bekijken.','nooffer':'Er is geen geschikte aanvulling voor deze voorwaarden. We houden uw huidige keuze.','clarify':'Vertel uw eetlust, budget of dieetbeperkingen zodat ik de keuze kan beperken.','offtopic':'Ik help u met de kaart van dit restaurant, ingrediënten en combinaties. Waar heeft u trek in?','budget':'Een volledig menu past niet in dit budget. Ik kan losse gerechten aanbevelen.','combo':'Dit is een evenwichtige combinatie uit de beschikbare gerechten. Prijs en korting staan hieronder.','confirm':'Er is geen actief voorstel om te bevestigen. Kies een gerecht of geef uw voorkeur aan.','unavailable':'Dit gerecht is niet beschikbaar. Ik help u graag met een alternatief.','culture':'Kartacze zijn grote aardappelknoedels met vleesvulling, vergelijkbaar met Litouwse cepelinai.'}
}

def say(lang,key,**values):
    if lang not in TEXT:return None
    return TEXT[lang][key].format(**values)

TERMS={
'pork':r'свин\w*|pork|wieprz\w*|schwein\w*|porc\w*|cerdo|maiale|su[ií]n\w*|varken\w*',
'gluten':r'глютен\w*|gluten\w*|celiac\w*|c[oœ]liaque|z[oö]liak\w*|целіак\w*',
'lactose':r'лактоз\w*|lacto[sz]\w*|lakto[sz]\w*',
'milk':r'молок\w*|milk|dairy|mlek\w*|milch\w*|lait|latte|leite|leche|melk',
'egg':r'яиц\w*|яйц\w*|eggs?|jaj\w*|eier|ei\b|[œo]ufs?|uova|huevos?|ovos?|eieren',
'nuts':r'орех\w*|nuts?\b|orzech\w*|n[üu]ss\w*|noix|noc[ie]|frutos secos|noten',
'peanut':r'peanuts?|арахис\w*|erdn[üu]ss\w*|cacahu[eè]t\w*|arachid\w*',
'fish':r'рыб\w*|риб\w*|fish|ryb\w*|fisch|poisson|pesce|peixe|pescado|vis\b',
'shellfish':r'shrimp|prawn|shellfish|кревет\w*|krewet\w*|garnel\w*|crevette|camar[oó]n|camar[aã]o',
'soy':r'soy\w*|soja|со[яю]\b','sesame':r'sesam\w*|sésam\w*|кунжут\w*','mustard':r'mustard|senf|moutarde|горчиц\w*|musztard\w*','celery':r'celery|sellerie|céleri|сельдере\w*|seler\w*'}
EXCLUDE=r'без|не ем|нельзя|аллерг\w*|не перенос\w*|не вжива\w*|алергі\w*|no\b|without|allerg\w*|avoid|free from|bez\b|nie jem|ohne|kein\w*|vertrage.{0,12}nicht|sans\b|sin\b|s[ée]nza|sem\b|intoler\w*|zonder|sauf'

def parse_base(text):
    # Stop an exclusion clause at an explicit positive preference.
    low=re.sub(r'\b(?:а?\s*хочу|але хочу|but i want|and i want|aber ich möchte|chcę za to)\b',';',text.casefold());ex=set()
    for code,pattern in TERMS.items():
        if re.search(r'(?:'+EXCLUDE+r')[^;.!?]{0,90}(?:'+pattern+r')',low) or re.search(r'(?:'+pattern+r')[- ]?(?:free|frei)\b',low):ex.add(code)
    if 'milk' in ex:ex.add('lactose')
    diets={d for d,p in {'vegan':r'веган|vegan|v[ée]g[ée]talien','vegetarian':r'вегетариан|vegetarian|wegetarian|vegetarisch|v[ée]g[ée]tarien','halal':r'halal|халяль|حلال','kosher':r'kosher|кошер|casher'}.items() if re.search(p,low)}
    budget=re.search(r'(?:до\b|under\b|below\b|do\b|budget\b|бюджет\w*|bis\b|unter\b|maximal\b|maximum\b|moins de|hasta\b|fino a|at[ée]\b|tot\b)\s*(\d+(?:[.,]\d{1,2})?)',low)
    flags={'excludes':ex,'diets':diets,'budget':float(budget.group(1).replace(',','.')) if budget else None,'combo':bool(re.search(r'комбо|combo|сет\b|zestaw|set men[uü]|men[üu] completo|formule',low)),'hearty':bool(re.search(r'сыт|hearty|syc|hungry|herzhaft|s[aä]ttig|copieux|abbondante',low)),'light':bool(re.search(r'л[её]гк|light|lekk|leicht|l[ée]ger|ligero|leggero',low))}
    flags['risk_mentioned']=bool(re.search(r'allerg|аллерг|алергі|celiac|z[oö]liak|intoler',low))
    return flags

def eligible(excludes=(),diets=()):
    # This is the POST-generation/order effect validator, NOT the LLM context builder.
    # Unknown verification never makes a known dish disappear; do not claim allergy safety.
    result=[]
    for d in store.dishes():
        if d.get('available') is False or d.get('status','published')!='published':continue
        if set(excludes)&set(d.get('allergens',[])):continue
        if any(not diet_matches(d,diet) for diet in diets):continue
        result.append(d)
    return result

def cents(value):return int((Decimal(str(value))*100).quantize(Decimal('1'),rounding=ROUND_HALF_UP))
def weight(d):
    m=re.search(r'(\d+(?:[.,]\d+)?)\s*(kg|g|gr)',d.get('weight','').lower())
    return float(m.group(1).replace(',','.'))*(1000 if m.group(2)=='kg' else 1) if m else 0

def score(d,prefs,weather,base=None):
    scores=[];tags=set(d.get('tags',[]));f=d.get('flavor') or {}
    context=1.0 if (weather.get('temp') is not None and weather['temp']<12 and ('warming' in tags or d['category']=='soup')) else .25
    scores.append((.30,context))
    taste=1 if (prefs.get('light') and ('light' in tags)) or (prefs.get('hearty') and ('heavy' in tags or weight(d)>600)) else .4
    scores.append((.25,taste))
    if d.get('cost') is not None and d['price']>0:
        scores.append((.20,max(0,(d['price']-d['cost'])/d['price'])))
    if base:
        bf=base.get('flavor') or {};lipid=bf.get('lipid_density')
        sour=f.get('sourness')
        if lipid is not None and sour is not None:scores.append((.25,lipid*sour))
        elif 'heavy' in base.get('tags',[]) and ('refreshing' in tags or 'sour' in tags or 'palate-cleanser' in tags):scores.append((.25,1))
    value=sum(w*s for w,s in scores)/sum(w for w,s in scores)
    return value*d.get('kitchen_priority',1)

def rank(items,prefs,weather,base=None):return sorted(items,key=lambda d:(-score(d,prefs,weather,base),d['price'],d['id']))

def best_combo(items,prefs,weather,discount):
    groups=[[d for d in items if d['category'] in cats] for cats in [('soup','starter'),('main',),('beverage',)]]
    if any(not g for g in groups):return []
    # Bound search by ranking rather than first-match: <= 30^3 candidates.
    groups=[rank(g,prefs,weather)[:30] for g in groups]
    best=None
    for ds in itertools.product(*groups):
        subtotal=sum(cents(d['price']) for d in ds);saving=int((Decimal(subtotal)*discount/100).quantize(Decimal('1'),rounding=ROUND_HALF_UP))
        if prefs.get('budget') is not None and subtotal-saving>cents(prefs['budget']):continue
        if sum(weight(d) for d in ds if d['category']!='beverage')>prefs.get('max_grams',1700):continue
        objective=sum(score(d,prefs,weather) for d in ds)
        # Margin is a real contribution only when ALL three costs are known.
        if all(d.get('cost') is not None for d in ds):objective+=(subtotal-saving-sum(cents(d['cost']) for d in ds))/max(subtotal,1)
        candidate=(objective,-(subtotal-saving),[d['id'] for d in ds])
        if best is None or candidate[:2]>best[:2]:best=candidate
    return best[2] if best else []

def accompaniment(base,items,cart_ids,prefs,weather,cart_total):
    allowed=base.get('pairing_ids') or []
    if allowed:candidates=[d for d in items if d['id'] in allowed]
    else:
        # Restaurant tags express side/sauce compatibility; no made-up burger/fries.
        wanted={'beverage','dessert','starter'}
        candidates=[d for d in items if d['category'] in wanted]
        if 'burger' in base.get('tags',[]):
            sides=[d for d in candidates if {'side','sauce','fries'}.intersection(d.get('tags',[]))]
            if sides:candidates=sides
        if 'heavy' in base.get('tags',[]):
            candidates=[d for d in candidates if d['category']!='starter' or 'light' in d.get('tags',[])]
    candidates=[d for d in candidates if d['id'] not in cart_ids and d['id']!=base['id']]
    if prefs.get('budget') is not None:candidates=[d for d in candidates if cents(cart_total)+cents(d['price'])<=cents(prefs['budget'])]
    return next(iter(rank(candidates,prefs,weather,base)),None)


# Intent matching is a hard filter BEFORE price/margin ranking, never an LLM hint.
SYNONYMS={
'SOUP':['суп','супа','супом','супчик','супчика','супы','бульон','журек','росол','квасница','борщ','первое','похлебка','похлёбка','жидкое','крем-суп','soup','soups','broth','zupa','zupy','zupę','zupe','żurek','zurek','rosół','rosol','kwaśnica','kwasnica','krem','suppe','suppen','юшка','бульйон'],
'DUCK':['утка','утку','утиное','качка','качку','duck','kaczka','kaczkę','ente','entenbrust'],
'GOOSE':['гусь','гуся','гусиная','гусиную','гусак','гусятина','goose','gęś','gesi','gęsia','gęsiny','gans','gänse'],
'POULTRY':['птица','птицу','курица','курицу','птиця','курка','poultry','chicken','drób','kurczak','geflügel','hähnchen'],
'MEAT':['мясо','мясное','мяса','мясу','м’ясо',"м'ясо",'meat','mięso','mieso','fleisch'],
'PORK':['свинина','свинину','рулька','рульку','свиняче','pork','golonka','wieprzowina','wieprzowiny','schwein','schweinefleisch','schweinshaxe'],
'DUMPLINGS':['картачи','картаче','картач','клёцки','клецки','картофель','картошку','вареники','картопля','галушки','dumpling','dumplings','potato','potatoes','kartacze','ziemniaki','kluski','kartoffel','kartoffeln','knödel'],
'FISH':['рыба','рыбу','рыбы','форель','рибa','риба','рибу','fish','trout','ryba','rybę','pstrąg','pstrag','fisch','forelle'],
'LIGHT':['салат','салаты','легкое','лёгкое','легкий','лёгкий','лёгкого','легкого','легка','легке','salad','light','sałatka','salatka','lekko','lekkie','salat','leicht','leichtes'],
'DESSERT':['десерт','десерты','сладкое','торт','чизкейк','солодке','dessert','desserts','cake','cheesecake','deser','ciasto','sernik','nachtisch','kuchen'],
'DRINK':['напиток','напитки','пить','попить','компот','морс','напій','напої','drink','drinks','beverage','juice','kompot','napój','napoje','getränk','getränke','trinken'],
'WARMING':['согреться','горячее','горячий','замерз','замёрз','тепле','зігрітися','warming','warm','hot','rozgrzewające','ciepłe','gorące','wärmend','heiß'],
'COLD':['холодное','холодный','прохладное','холодне','cold','chilled','zimne','chłodne','kalt','gekühlt'],
'BUDGET':['бюджет','злотых','злотих','pln','zł','budget','under','bis','euro','на двоих','на двох','for two','für zwei','dla dwóch'],
'UNAVAILABLE_FOOD':['суши','пицца','пиццу','роллы','роллов','кебаб','піца','піцу','роли','sushi','pizza','rolls','kebab','döner'],
'PROMPT_INJECTION':['забудь инструкции','игнорируй инструкции','скидку 100','скидка 100','промокод admin','ignore instructions','ignore previous','system prompt','discount 100','forget instructions','admin promo','ignoruj instrukcje','rabatu 100','ignoriere anweisungen','rabatt 100','забудь інструкції']}

def term_hit(text,term):
    return bool(re.search(r'(?<!\w)'+re.escape(term)+r'(?!\w)',text,re.I))

def parse(text):
    flags=parse_base(text);low=text.casefold()
    found={key for key,terms in SYNONYMS.items() if any(term_hit(low,t) for t in terms)}
    # Exclusion mentions must NOT be turned into positive meat/fish category intent.
    if 'pork' in flags['excludes']:found.discard('PORK')
    if 'fish' in flags['excludes']:found.discard('FISH')
    for topic in list(found):
        if topic in ('PROMPT_INJECTION','UNAVAILABLE_FOOD','BUDGET'):continue
        terms=SYNONYMS[topic]
        negative=r'(?:не хочу|не надо|не люблю|без|не|no|not|without|keine?|ohne|nie chcę|bez)\s+(?:'+ '|'.join(re.escape(t) for t in terms)+r')(?!\w)'
        positive_terms=[t for t in terms if term_hit(low,t)]
        if positive_terms and all(re.search(r'(?:не хочу|не надо|не люблю|без|не|no|not|without|keine?|ohne|nie chcę|bez)\s+'+re.escape(t)+r'(?!\w)',low) for t in positive_terms):found.discard(topic)
    flags['topics']=sorted(found)
    flags['light']|='LIGHT' in found
    if flags['budget'] is None:
        budget=re.search(r'(\d+(?:[.,]\d{1,2})?)\s*(?:pln|zł|злот\w*)',low)
        if budget:flags['budget']=float(budget.group(1).replace(',','.'))
    flags['people']=2 if re.search(r'на двоих|на двох|for two|für zwei|dla dw[oó]ch|2\s*(?:person|osob|челов|людин)',low) else 1
    if re.search(r'(?:per person|на человека|pro person|na osobę)',low):flags['people']=1
    return flags

def select(items,prefs,weather):
    topics=set(prefs.get('topics',[]));pool=list(items)
    if 'SOUP' in topics:pool=[d for d in pool if d['category']=='soup']
    elif 'DESSERT' in topics:pool=[d for d in pool if d['category']=='dessert']
    elif 'DRINK' in topics:pool=[d for d in pool if d['category']=='beverage']
    elif topics & {'DUCK','GOOSE','POULTRY','MEAT','PORK','DUMPLINGS','FISH','LIGHT'}:
        pool=[d for d in pool if d['category'] in ('main','starter')]
    elif 'WARMING' in topics:pool=[d for d in pool if d['category'] in ('soup','main')]
    elif not prefs.get('combo') and not prefs.get('diets'):pool=[d for d in pool if d['category'] in ('soup','main','starter')]
    patterns={'DUCK':r'kaczk|duck|утк|качк|ente','GOOSE':r'gę[sś]|gesi|goose|гус|gans|gäns','POULTRY':r'kaczk|gę[sś]|kurcz|duck|goose|chicken|птиц|кур|geflügel','PORK':r'golonka|wieprz|pork|свин|schwein','DUMPLINGS':r'kartacz|ziemnia|potato|клец|клёц|карто|dumpling|knödel','FISH':r'pstr[aą]g|fish|trout|форел|рыб|риб|fisch|forelle'}
    for topic,pattern in patterns.items():
        if topic in topics:
            pool=[d for d in pool if re.search(pattern,d['name']+' '+d.get('ingredients',''),re.I)]
    if 'MEAT' in topics and not topics & {'DUCK','GOOSE','POULTRY','PORK','DUMPLINGS'}:
        pool=[d for d in pool if d['category']=='main' and re.search(r'mięs|meat|golonka|kaczk|gę[sś]|pork|duck|goose',d['name']+' '+d.get('ingredients',''),re.I)]
    if 'LIGHT' in topics:pool=[d for d in pool if 'light' in d.get('tags',[]) or re.search(r'sałat|salad|pstr[aą]g',d['name'],re.I)]
    if 'COLD' in topics:pool=[d for d in pool if d['category'] in ('beverage','dessert') and not set(d.get('tags',[])) & {'hot','warming'}]
    if prefs.get('budget') is not None:
        max_unit=cents(prefs['budget'])//prefs.get('people',1)
        pool=[d for d in pool if cents(d['price'])<=max_unit]
    return rank(pool,prefs,weather)


def local_reply(lang,key,items,state=None):
    state=state or {};names=' / '.join(d['name'] for d in items)
    if key in ('recommend','unavailable') and names:
        introductions={
        'ru':('Начнём с','Этого блюда нет в нашем меню. Вместо него рекомендую'),
        'pl':('Polecam','Tego dania nie ma w naszym menu. Zamiast niego polecam'),
        'en':('Let me recommend','That dish is not on our menu. Instead, I recommend'),
        'de':('Ich empfehle Ihnen','Dieses Gericht steht nicht auf unserer Karte. Stattdessen empfehle ich'),
        'uk':('Рекомендую','Цієї страви немає в нашому меню. Натомість рекомендую')}
        if lang in introductions:
            reply=introductions[lang][key=='unavailable']+' '+names+'.'
            # Use authored restaurant descriptions, never invent sensory/ingredient facts.
            desc=items[0].get('desc',{}).get(lang,'')
            if desc:reply+=' '+desc[:500]
            return reply
    return say(lang,key,**({'name':items[0]['name']} if key=='upsell' and items else {}))


def upsell_line(lang,name):
    return {'ru':f'К этому выбору предложу {name}; добавить его можно отдельно, по желанию.',
    'pl':f'Do tego wyboru proponuję {name}; dodatek jest opcjonalny.',
    'en':f'To accompany your choice, I suggest {name}; adding it is optional.',
    'de':f'Dazu empfehle ich {name}; die Ergänzung ist freiwillig.',
    'uk':f'До цього вибору пропоную {name}; доповнення за бажанням.'}.get(lang,'')


MEAT_PATTERN=r'\b(?:meat|pork|beef|veal|chicken|duck|goose|lamb|bacon|ham|sausage|gelatin|gelatine|mięso|mięsem|wieprz\w*|wołow\w*|cielę\w*|kurcz\w*|kaczk\w*|gę[sś]\w*|golonka|wędzon\w*|kiełbas\w*|boczek|szynk\w*|свин\w*|говя\w*|телят\w*|мяс\w*|куриц\w*|утк\w*|гус\w*|бекон|желатин|fleisch|schwein\w*|rind\w*|ente|gans|hähnchen)\b'
FISH_PATTERN=r'\b(?:fish|trout|salmon|tuna|herring|shrimp|prawn|seafood|pstr[aą]g|śledź|śledzie|losos|łosoś|tuńczyk|krewet\w*|ryb\w*|рыб\w*|риб\w*|форел\w*|сельд\w*|лосос\w*|кревет\w*|fisch|forelle|lachs)\b'
VEG_PATTERN=r'\b(?:pierogi z kapustą|kapust\w*|grzyb\w*|szpinak\w*|moskole|salad|sałat\w*|warzyw\w*|vegetable|mushroom|spinach|tofu|авокадо|овощ\w*|гриб\w*|шпинат\w*|салат\w*)\b'

def recipe_text(d):
    desc=d.get('desc',{})
    desc=' '.join(desc.values()) if isinstance(desc,dict) else str(desc)
    text=' '.join([d.get('name',''),d.get('ingredients',''),d.get('details',''),desc]).casefold()
    text=re.sub(r'(?:после|к|after|with|accompan(?:y|ies)|do)\s+(?:(?:сытного|rich|roasted)\s+)?(?:мяса|meat|mięsa)','',text)
    return re.sub(r'без мяса|без свинины|no meat|meat[- ]free|without meat|bez mięsa|ohne fleisch','',text)

def diet_class(d):
    facts=recipe_text(d);labels=set(d.get('diets',[]))|set(d.get('tags',[]));allergens=set(d.get('allergens',[]))
    if 'pork' in allergens or re.search(MEAT_PATTERN,facts):return 'meat'
    if allergens & {'fish','shellfish','molluscs'} or re.search(FISH_PATTERN,facts):return 'fish'
    if 'vegan' in labels:return 'vegan'
    if 'vegetarian' in labels or re.search(VEG_PATTERN,facts):return 'vegetarian'
    if d.get('category') in ('beverage','dessert'):return 'non_meat'
    return 'unknown'

def diet_matches(d,diet):
    kind=diet_class(d);labels=set(d.get('diets',[]))|set(d.get('tags',[]));allergens=set(d.get('allergens',[]))
    if diet=='pescatarian':return kind in ('fish','vegetarian','vegan','non_meat')
    if diet=='vegetarian':return kind in ('vegetarian','vegan','non_meat')
    if diet=='vegan':return kind=='vegan' and not allergens & {'milk','lactose','egg','fish','shellfish','molluscs','pork'}
    return diet in labels

def guest_preferences(text):
    prefs=parse(text)
    low=text.casefold()
    if re.search(r'без мяс\w*|не ем мяс\w*|without meat|no meat|meat[- ]free|bez mi[eę]sa|ohne fleisch|без м.яс',low) and not prefs['diets'] & {'vegetarian','vegan'}:prefs['diets'].add('pescatarian')
    return prefs
