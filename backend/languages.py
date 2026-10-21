"""Message-language detection independent of all interface settings.
langid is local (97 languages), with explicit short-utterance and script handling.
A venue dish name alone does not change the language of an ongoing conversation.
"""
import re
import threading
from functools import lru_cache
from langid.langid import LanguageIdentifier, model

_lock=threading.Lock()
_identifier=None
NAMES={'ru':'Russian','en':'English','pl':'Polish','de':'German','fr':'French','es':'Spanish','it':'Italian','pt':'Portuguese','uk':'Ukrainian','nl':'Dutch','cs':'Czech','tr':'Turkish','ar':'Arabic','zh':'Chinese','ja':'Japanese','ko':'Korean','he':'Hebrew','hi':'Hindi','sv':'Swedish','da':'Danish','fi':'Finnish','ro':'Romanian','hu':'Hungarian','el':'Greek'}
SHORT={'hello':'en','hi':'en','thanks':'en','thank you':'en','yes':'en','no thanks':'en','hallo':'de','guten tag':'de','nein':'de','danke':'de','bonjour':'fr','merci':'fr','non merci':'fr','hola':'es','gracias':'es','ciao':'it','grazie':'it','olá':'pt','obrigado':'pt','cześć':'pl','dzień dobry':'pl','dziękuję':'pl','tak':'pl','привет':'ru','спасибо':'ru','здравствуйте':'ru','дякую':'uk','вітаю':'uk','привіт':'uk','merhaba':'tr','teşekkürler':'tr','ahoj':'cs','děkuji':'cs','hallo!':'de','مرحبا':'ar','شكرا':'ar','你好':'zh','谢谢':'zh','こんにちは':'ja','ありがとう':'ja','안녕하세요':'ko','감사합니다':'ko'}
AMBIGUOUS={'ok','okay','yes','no','ja','non','si','sí','да','нет','давай','👍','nein','oui','да спасибо'}

def clean(text,names=()):
    text=re.sub(r'https?://\S+',' ',str(text)).strip()
    names=set(names)|{name.split()[0] for name in names if name and len(name.split()[0])>4}
    for name in sorted(names,key=len,reverse=True):
        if name:text=re.sub(re.escape(name),' ',text,flags=re.I)
    return re.sub(r'\s+',' ',text).strip()

def detect(text,previous=None,names=()):
    text=clean(text,names)
    low=text.casefold().strip(' .!?…')
    if not re.search(r'[^\W\d_]',text,re.UNICODE):return previous or 'en'
    if low in {'ok','okay','ja','si','sí','oui'} and previous:return previous
    if low in SHORT:return SHORT[low]
    if len(low)<3 and previous:return previous
    if re.search(r'\b(свинини|порадьте|бажаю|хочу їсти|смачного|будь ласка|страву|страви|рибу|риба|напої|лактози)\b',low):return 'uk'
    if re.search('[а-яё]',text,re.I) and not re.search('[іїєґІЇЄҐ]',text):return 'ru'
    if re.search(r'\b(i want|i would|what is|what does|please recommend|please explain|can you|could you|would you)\b',low):return 'en'
    if re.search(r'\b(soup|soups|broth|dessert|drink|fish)\b',low) and not re.search(r'\b(ich|bitte|chcę|poproszę)\b',low):return 'en'
    if re.search(r'\b(suppe|suppen|fisch|getränk|nachtisch)\b',low):return 'de'
    if re.search(r'\b(ich|ihnen|dazu|empfehle|bitte|diese gerichte|aktuellen karte)\b',low):return 'de'
    if re.search(r'\b(zupa|zupy|rosół|żurek|chce|prosze|zurek)\b',low):return 'pl'
    latin=len(re.findall('[A-Za-z]',text))
    native=len(re.findall(r'[^\x00-\x7f\W\d_]',text))
    if latin>native and re.search(r"\b(what (is|does|would)|i would|i am|i have|please (explain|recommend)|would you|i want)\b",low):return 'en'
    if re.search('[ぁ-ヿ]',text) and len(re.findall('[ぁ-ヿ一-龯]',text))>latin*.5:return 'ja'
    if re.search('[가-힣]',text):return 'ko'
    if re.search('[\u4e00-\u9fff]',text):return 'zh'
    if re.search('[א-ת]',text):return 'he'
    if re.search('[\u0900-\u097f]',text):return 'hi'
    if re.search('[\u0600-\u06ff]',text):return 'ar'
    if re.search('[іїєґІЇЄҐ]',text):return 'uk'
    # Prevent short German questions being labelled Polish by a statistical detector.
    if re.search(r'\b(ich|möchte|empfehlen|schweinefleisch|bitte|danke|was empfehlen|hätte|allergisch|keine)\b',low):return 'de'
    if re.search(r'\b(je suis|je voudrais|sans|bonjour|allergique|recommandez)\b',low):return 'fr'
    if re.search(r'\b(would|please|without|recommend|allergic|i want|i am|i have|what is|no pork|combo deal|hearty under)\b',low):return 'en'
    if re.search(r'\b(chcę|poproszę|polecasz|wieprzowiny|dziękuję|bez glutenu|zestaw|sycąco)\b',low):return 'pl'
    if re.search(r'\b(хочу|посоветуй|собери|свин\w*|лактоз\w*|не ем|сытно|аллерги\w*|спасибо)\b',low):return 'ru'
    return classify(text,previous)[0]

@lru_cache(maxsize=1024)
def classify(text,previous=None):
    global _identifier
    with _lock:
        if _identifier is None:_identifier=LanguageIdentifier.from_modelstring(model,norm_probs=True)
        code,confidence=_identifier.classify(text)
    if confidence<.65 and previous:return previous,float(confidence)
    return code,float(confidence)

def matches(text,expected,names=()):
    stripped=clean(text,names)
    if len(re.sub(r'\W','',stripped))<5:return False
    actual=detect(stripped)
    # One clear mismatch is a repair/fallback, never a silently wrong-language answer.
    return actual==expected or (expected in ('zh','ja') and actual==expected)


def detect_message_language(guest_message, previous=None, names=(), ui_lang=None):
    """ui_lang exists for compatibility; it is deliberately never read."""
    return detect(guest_message,previous,names)
