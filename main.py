import os
import json
import random
import sympy
import logging
import redis
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes

# ================== ۱. تنظیمات اولیه و لاگینگ ==================
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

# ================== ۲. اتصال Redis و متغیرهای محیطی ==================
# متغیرهای محیطی
BOT_TOKEN = os.environ.get("BOT_TOKEN")
USDT_WALLET = os.environ.get("USDT_WALLET")
ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME")
ADMIN_ID = os.environ.get("ADMIN_ID") # شناسه عددی تلگرام ادمین
REDIS_URL = os.environ.get("REDIS_URL")

# تنظیمات ربات
FREE_TRIAL = 5  # تعداد سوالات رایگان برای کاربران عادی

# اتصال Redis
if not REDIS_URL:
    logging.error("REDIS_URL environment variable is not set! Using dummy client for Redis.")
    # کلاس ساختگی برای جلوگیری از خطا در صورت عدم تنظیم متغیر محیطی
    class DummyRedis:
        def exists(self, key): return False
        def get(self, key): return None
        def set(self, key, value): pass
        def keys(self, pattern): return []
    REDIS_CLIENT = DummyRedis()
else:
    try:
        REDIS_CLIENT = redis.from_url(REDIS_URL, decode_responses=True)
        REDIS_CLIENT.ping()
        logging.info("Successfully connected to Redis.")
    except Exception as e:
        # مدیریت خطای اتصال Redis
        logging.critical(f"Failed to connect to Redis at {REDIS_URL}: {e}")
        REDIS_CLIENT = DummyRedis()


# ================== ۳. زبان‌ها و متون (شامل توضیحات مفصل) ==================
LANGUAGES = ["fa","en","es","fr","ar","hi"]

# متون ثابت و پیام‌ها (TEXT)
TEXT = {
    "welcome": {"fa": "به ربات آموزش کسرها خوش آمدید! 👋", "en": "Welcome to Fraction Learning Bot! 👋", "es": "¡Bienvenido al Bot de Fracciones! 👋", "fr": "Bienvenue sur le Bot de Fractions ! 👋", "ar": "مرحباً بك في بوت تعليم الكسور! 👋", "hi": "भिन्न सीखने वाले बॉट में आपका स्वागत है! 👋"},
    "choose_op": {"fa": "یک عملیات را انتخاب کنید:", "en": "Choose an operation:", "es": "Elige una operación:", "fr": "Choisissez une opération :", "ar": "اختر عملية:", "hi": "एक ऑपरेशन चुनें:"},
    "trial_left": {"fa": "سوال رایگان باقی‌مانده", "en": "free questions left", "es": "preguntas gratis restantes", "fr": "questions gratuites restantes", "ar": "الأسئلة المجانية المتبقية", "hi": "बचे हुए मुफ्त प्रश्न"},
    "trial_over": {"fa": "سوالات رایگان شما تمام شد! لطفاً برای ادامه اشتراک بخرید.", "en": "Your free questions are finished! Please buy a subscription to continue.", "es": "¡Se terminaron las preguntas gratis! Compra una suscripción para continuar.", "fr": "Vos questions gratuites sont terminées ! Veuillez acheter un abonnement pour continuer.", "ar": "انتهت أسئلتك المجانية! يرجى شراء الاشتراك للمتابعة.", "hi": "आपके मुफ्त प्रश्न समाप्त हो गए! जारी रखने के लिए कृपया सदस्यता खरीदें।"},
    "send_proof": {"fa": f"💳 **خرید اشتراک VIP**\n\nلطفاً پرداخت را به کیف پول زیر واریز کنید و اسکرین‌شات رسید را به @{ADMIN_USERNAME} بفرستید.\n\n`{USDT_WALLET}`", "en": f"💳 **Buy VIP Subscription**\n\nPlease send the payment to the wallet below and forward the proof (screenshot) to @{ADMIN_USERNAME}.\n\n`{USDT_WALLET}`", "es": f"💳 **Comprar Suscripción VIP**\n\nEnvía el pago a la billetera a continuación y el comprobante (captura de pantalla) a @{ADMIN_USERNAME}.\n\n`{USDT_WALLET}`", "fr": f"💳 **Acheter un Abonnement VIP**\n\nVeuillez envoyer le paiement au portefeuille ci-dessous et la preuve (capture d'écran) à @{ADMIN_USERNAME}.\n\n`{USDT_WALLET}`", "ar": f"💳 **شراء اشتراك VIP**\n\nيرجى إرسال الدفع إلى المحفظة أدناه وإرسال الإثبات (لقطة الشاشة) إلى @{ADMIN_USERNAME}.\n\n`{USDT_WALLET}`", "hi": f"💳 **वीआईपी सदस्यता खरीदें**\n\nकृपया नीचे दिए गए वॉलेट में भुगतान भेजें और प्रमाण (स्क्रीनशॉट) @{ADMIN_USERNAME} को भेजें।\n\n`{USDT_WALLET}`"},
    "correct": {"fa": "✅ پاسخ درست است! آفرین!", "en": "✅ Correct answer! Well done!", "es": "✅ ¡Respuesta correcta! ¡Bien hecho!", "fr": "✅ Bonne réponse ! Bien joué !", "ar": "✅ الإجابة صحيحة! أحسنت!", "hi": "✅ सही उत्तर! शाबाश!"},
    "wrong": {"fa": "❌ پاسخ اشتباه است. جواب درست:", "en": "❌ Wrong answer. Correct answer:", "es": "❌ Respuesta incorrecta. Respuesta correcta:", "fr": "❌ Mauvaise réponse. Réponse correcte :", "ar": "❌ إجابة خاطئة. الإجابة الصحيحة:", "hi": "❌ गलत उत्तर। सही उत्तर:"},
    "next_question": {"fa": "سوال بعدی:", "en": "Next question:", "es": "Siguiente pregunta:", "fr": "Question suivante :", "ar": "السؤال التالي:", "hi": "अगला प्रश्न:"},
    "buy_sub": {"fa": "💳 خرید اشتراک VIP", "en": "💳 Buy VIP Subscription", "es": "💳 Comprar Suscripción VIP", "fr": "💳 Acheter un Abonnement VIP", "ar": "💳 شراء اشتراك VIP", "hi": "💳 वीआईपी सदस्यता खरीदें"},
    "op_menu": {"fa": "بازگشت به عملیات", "en": "Back to Operations Menu", "es": "Volver al Menú de Operaciones", "fr": "Retour au Menu des Opérations", "ar": "العودة إلى قائمة العمليات", "hi": "ऑपरेशन मेनू पर वापस जाएं"}
}

# متون دکمه‌های عملیات
OP_BUTTONS = {
    "fa": ["جمع", "تفریق", "ضرب", "تقسیم"],
    "en": ["Add", "Subtract", "Multiply", "Divide"],
    "es": ["Sumar", "Restar", "Multiplicar", "Dividir"],
    "fr": ["Addition", "Soustraction", "Multiplication", "Division"],
    "ar": ["جمع", "طرح", "ضرب", "قسمة"],
    "hi": ["जोड़", "घटाव", "गुणा", "भाग"]
}

# متون توضیحات گام به گام (EXPLANATIONS) - با جزئیات کامل آموزشی
EXPLANATIONS = {
    "problem_intro": {"fa": "📚 **حل گام به گام برای: {f1} {op_symbol} {f2}**", "en": "📚 **Step-by-step solution for: {f1} {op_symbol} {f2}**", "es": "📚 **Solución paso a paso para: {f1} {op_symbol} {f2}**", "fr": "📚 **Solution étape par étape pour: {f1} {op_symbol} {f2}**", "ar": "📚 **الحل خطوة بخطوة لـ: {f1} {op_symbol} {f2}**", "hi": "📚 **के लिए चरण-दर-चरण समाधान: {f1} {op_symbol} {f2}**"},
    "lcm_step": {
        "fa": "مرحله {step}: یافتن **مخرج مشترک** (ک.م.م) بین {q1} و {q2} → **{lcm}**\n\n*📌 چرا؟ برای جمع یا تفریق کسرها، مخرج‌ها باید یکسان باشند. کوچک‌ترین عددی که هر دو مخرج ( {q1} و {q2} ) بر آن بخش‌پذیر باشند، ک.م.م است که عملیات را ساده‌تر می‌کند.*",
        "en": "Step {step}: Find the **Lowest Common Multiple (LCM)** of {q1} and {q2} → **{lcm}**\n\n*📌 Why? To add or subtract fractions, they must have a common denominator. The LCM is the smallest number both denominators ( {q1} and {q2} ) can divide into, simplifying the process.*",
        "es": "Paso {step}: Encuentra el **Mínimo Común Múltiplo (MCM)** de {q1} y {q2} → **{lcm}**\n\n*📌 ¿Por qué? Para sumar o restar, deben tener un denominador común. El MCM es el número más pequeño que ambos ( {q1} y {q2} ) pueden dividir, simplificando el proceso.*",
        "fr": "Étape {step}: Trouvez le **Plus Petit Commun Multiple (PPCM)** de {q1} et {q2} → **{lcm}**\n\n*📌 Pourquoi ? Pour l'addition/soustraction, les fractions doivent avoir un dénominateur commun. Le PPCM est le plus petit nombre divisible par les deux ( {q1} et {q2} ), simplifiant le calcul.*",
        "ar": "الخطوة {step}: إيجاد **المضاعف المشترك الأصغر (LCM)** للمقامات {q1} و {q2} → **{lcm}**\n\n*📌 لماذا؟ لجمع أو طرح الكسور، يجب توحيد المقامات. المضاعف المشترك الأصغر هو أصغر عدد يقبل القسمة على كلا المقامين ( {q1} و {q2} )، مما يسهل العملية.*",
        "hi": "चरण {step}: {q1} और {q2} का **लघुत्तम समापवर्त्य (LCM)** ज्ञात करें → **{lcm}**\n\n*📌 क्यों? भिन्नों को जोड़ने या घटाने के लिए, उनका भाजक समान होना चाहिए। LCM वह सबसे छोटी संख्या है जिससे दोनों भाजक ( {q1} और {q2} ) विभाजित हो सकते हैं, जिससे प्रक्रिया सरल हो जाती है।*",
    },
    "convert_step": {
        "fa": "مرحله {step}: **تبدیل کسرها** به مخرج مشترک **{lcm}**:\n  {f1} → **{f1_new}** (صورت و مخرج در **{factor1}** ضرب شدند)\n  {f2} → **{f2_new}** (صورت و مخرج در **{factor2}** ضرب شدند)\n\n*💡 نکته: برای حفظ ارزش کسر، هر عملی که روی مخرج انجام می‌دهید، باید روی صورت هم انجام دهید.*",
        "en": "Step {step}: **Convert fractions** to the common denominator **{lcm}**:\n  {f1} → **{f1_new}** (Numerator and denominator multiplied by **{factor1}**)\n  {f2} → **{f2_new}** (Numerator and denominator multiplied by **{factor2}**)\n\n*💡 Tip: To maintain the value of the fraction, whatever you do to the denominator, you must also do to the numerator.*",
        "es": "Paso {step}: **Convertir fracciones** al denominador común **{lcm}**:\n  {f1} → **{f1_new}** (Numerador y denominador multiplicados por **{factor1}**)\n  {f2} → **{f2_new}** (Numerador y denominador multiplicados por **{factor2}**)\n\n*💡 Consejo: Para mantener el valor de la fracción, lo que hagas al denominador, también debes hacerlo al numerador.*",
        "fr": "Étape {step}: **Convertissez les fractions** au dénominateur commun **{lcm}**:\n  {f1} → **{f1_new}** (Numérateur et dénominateur multipliés par **{factor1}**)\n  {f2} → **{f2_new}** (Numérateur et dénominateur multipliés par **{factor2}**)\n\n*💡 Astuce: Pour conserver la valeur, toute opération effectuée sur le dénominateur doit également l'être sur le numérateur.*",
        "ar": "الخطوة {step}: **تحويل الكسور** إلى المقام المشترك **{lcm}**:\n  {f1} → **{f1_new}** (تم ضرب البسط والمقام في **{factor1}**)\n  {f2} → **{f2_new}** (تم ضرب البسط والمقام في **{factor2}**)\n\n*💡 تلميح: للحفاظ على قيمة الكسر، يجب أن تقوم بنفس العملية على كل من البسط والمقام.*",
        "hi": "चरण {step}: भिन्नों को सामान्य भाजक **{lcm}** में **बदलें**:\n  {f1} → **{f1_new}** (अंश और भाजक को **{factor1}** से गुणा किया गया)\n  {f2} → **{f2_new}** (अंश और भाजक को **{factor2}** से गुणा किया गया)\n\n*💡 सुझाव: भिन्न का मान बनाए रखने के लिए, भाजक के साथ जो भी करें, वह अंश के साथ भी करना होगा।*",
    },
    "operation_step": {
        "fa": "مرحله {step}: انجام عملیات ({f1_new} {op_symbol} {f2_new}) بر روی **صورت‌ها**: نتیجه = **{res}**\n\n*✅ قاعده: مخرج مشترک ( {lcm} ) حفظ می‌شود، و فقط صورت‌ها ( {f1_new} و {f2_new} ) با هم جمع یا تفریق می‌شوند.*",
        "en": "Step {step}: Perform the operation ({f1_new} {op_symbol} {f2_new}) on the **numerators**: Result = **{res}**\n\n*✅ Rule: The common denominator ( {lcm} ) is kept, and only the numerators ( {f1_new} and {f2_new} ) are added or subtracted.*",
        "es": "Paso {step}: Realice la operación ({f1_new} {op_symbol} {f2_new}) en los **numeradores**: Resultado = **{res}**\n\n*✅ Regla: El denominador común ( {lcm} ) se mantiene, y solo se suman o restan los numeradores ( {f1_new} y {f2_new} ).*",
        "fr": "Étape {step}: Effectuez l'opération ({f1_new} {op_symbol} {f2_new}) sur les **numérateurs**: Résultat = **{res}**\n\n*✅ Règle: Le dénominateur commun ( {lcm} ) est conservé, et seuls les numérateurs ( {f1_new} et {f2_new} ) sont additionnés ou soustraits.*",
        "ar": "الخطوة {step}: إجراء العملية ({f1_new} {op_symbol} {f2_new}) على **البسط**: النتيجة = **{res}**\n\n*✅ القاعدة: يتم الاحتفاظ بالمقام المشترك ( {lcm} )، ويتم فقط جمع أو طرح البسطين ( {f1_new} و {f2_new} ).*",
        "hi": "चरण {step}: **अंशों** पर ऑपरेशन ({f1_new} {op_symbol} {f2_new}) करें: परिणाम = **{res}**\n\n*✅ नियम: सामान्य भाजक ( {lcm} ) को रखा जाता है, और केवल अंशों ( {f1_new} और {f2_new} ) को जोड़ा या घटाया जाता है।*",
    },
    "mult_step": {
        "fa": "مرحله {step}: **ضرب کسرها**:\n  {f1} × {f2} = **{res}**\n\n*💡 روش: صورت‌ها ( {n1} و {n2} ) را در هم ضرب کنید و مخرج‌ها ( {q1} و {q2} ) را نیز در هم ضرب کنید. ( {n1}×{n2} / {q1}×{q2} )*",
        "en": "Step {step}: **Multiply the fractions**:\n  {f1} × {f2} = **{res}**\n\n*💡 Method: Multiply the numerators ( {n1} and {n2} ) together and the denominators ( {q1} and {q2} ) together. ( {n1}×{n2} / {q1}×{q2} )*",
        "es": "Paso {step}: **Multiplicar las fracciones**:\n  {f1} × {f2} = **{res}**\n\n*💡 Método: Multiplica los numeradores ( {n1} y {n2} ) entre sí y los denominadores ( {q1} y {q2} ) entre sí. ( {n1}×{n2} / {q1}×{q2} )*",
        "fr": "Étape {step}: **Multipliez les fractions**:\n  {f1} × {f2} = **{res}**\n\n*💡 Méthode: Multipliez les numérateurs ( {n1} et {n2} ) ensemble et les dénominateurs ( {q1} et {q2} ) ensemble. ( {n1}×{n2} / {q1}×{q2} )*",
        "ar": "الخطوة {step}: **ضرب الكسور**:\n  {f1} × {f2} = **{res}**\n\n*💡 الطريقة: اضرب البسط ( {n1} و {n2} ) معًا والمقامات ( {q1} و {q2} ) معًا. ( {n1}×{n2} / {q1}×{q2} )*",
        "hi": "चरण {step}: **भिन्नों को गुणा करें**:\n  {f1} × {f2} = **{res}**\n\n*💡 विधि: अंशों ( {n1} और {n2} ) को एक साथ और भाजकों ( {q1} और {q2} ) को एक साथ गुणा करें। ( {n1}×{n2} / {q1}×{q2} )*",
    },
    "div_step1": {
        "fa": "مرحله {step}: تبدیل تقسیم به **ضرب معکوس**:\n  {f1} ÷ {f2} = {f1} × **{f2_reciprocal}**\n\n*💡 قاعده: برای تقسیم بر کسر، کافی است کسر اول را در **معکوس** کسر دوم ضرب کنید. (معکوس کردن یعنی جابجایی صورت و مخرج کسر دوم)*",
        "en": "Step {step}: Convert division to **multiplication by the reciprocal**:\n  {f1} ÷ {f2} = {f1} × **{f2_reciprocal}**\n\n*💡 Rule: To divide by a fraction, simply multiply the first fraction by the **reciprocal** of the second fraction. (Reciprocal means flipping the numerator and denominator)*",
        "es": "Paso {step}: Convertir la división en **multiplicación por el recíproco**:\n  {f1} ÷ {f2} = {f1} × **{f2_reciprocal}**\n\n*💡 Regla: Para dividir, simplemente multiplica la primera fracción por el **recíproco** de la segunda. (Recíproco significa invertir el numerador y el denominador)*",
        "fr": "Étape {step}: Convertir la division en **multiplication par l'inverse**:\n  {f1} ÷ {f2} = {f1} × **{f2_reciprocal}**\n\n*💡 Règle: Pour diviser, il suffit de multiplier la première fraction par l'**inverse** de la seconde. (L'inverse signifie intervertir le numérateur et le dénominateur)*",
        "ar": "الخطوة {step}: تحويل القسمة إلى **ضرب في المقلوب**:\n  {f1} ÷ {f2} = {f1} × **{f2_reciprocal}**\n\n*💡 القاعدة: للقسمة على كسر، قم بضرب الكسر الأول في **مقلوب** الكسر الثاني. (المقلوب يعني قلب البسط والمقام)*",
        "hi": "चरण {step}: भाग को **व्युत्क्रम द्वारा गुणन** में बदलें:\n  {f1} ÷ {f2} = {f1} × **{f2_reciprocal}**\n\n*💡 नियम: किसी भिन्न से भाग देने के लिए, पहले भिन्न को दूसरे भिन्न के **व्युत्क्रम** से गुणा करें। (व्युत्क्रम का अर्थ है अंश और भाजक को उलटना)*",
    },
    "div_step2": {
        "fa": "مرحله {step}: انجام عملیات ضرب:\n  {f1} × {f2_reciprocal} = **{res}**\n\n*💡 نکته: این مرحله طبق قوانین ضرب کسرها انجام می‌شود (صورت در صورت و مخرج در مخرج).*",
        "en": "Step {step}: Perform the multiplication:\n  {f1} × {f2_reciprocal} = **{res}**\n\n*💡 Tip: This step is done according to the rules of fraction multiplication (numerator times numerator, denominator times denominator).*",
        "es": "Paso {step}: Realizar la multiplicación:\n  {f1} × {f2_reciprocal} = **{res}**\n\n*💡 Consejo: Este paso se realiza según las reglas de la multiplicación de fracciones (numerador por numerador, denominador por denominador).*",
        "fr": "Étape {step}: Effectuez la multiplication:\n  {f1} × {f2_reciprocal} = **{res}**\n\n*💡 Astuce: Cette étape est effectuée selon les règles de la multiplication des fractions (numérateur fois numérateur, dénominateur fois dénominateur).*",
        "ar": "الخطوة {step}: إجراء عملية الضرب:\n  {f1} × {f2_reciprocal} = **{res}**\n\n*💡 تلميح: يتم تنفيذ هذه الخطوة وفقًا لقواعد ضرب الكسور (البسط في البسط والمقام في المقام).*",
        "hi": "चरण {step}: गुणन करें:\n  {f1} × {f2_reciprocal} = **{res}**\n\n*💡 सुझाव: यह चरण भिन्न गुणन के नियमों के अनुसार किया जाता है (अंश गुणा अंश, भाजक गुणा भाजक)।*",
    },
    "final_step_simple": {
        "fa": "مرحله {step}: **پاسخ نهایی** (ساده شده) = **{res}**\n\n*✨ نهایی: کسر به ساده‌ترین شکل خود تبدیل شد.*",
        "en": "Step {step}: **Final Answer** (simplified) = **{res}**\n\n*✨ Final: The fraction has been reduced to its simplest form.*",
        "es": "Paso {step}: **Respuesta Final** (simplificada) = **{res}**\n\n*✨ Final: La fracción ha sido reducida a su forma más simple.*",
        "fr": "Étape {step}: **Réponse Finale** (simplifiée) = **{res}**\n\n*✨ Final: La fraction a été réduite à sa forme la plus simple.*",
        "ar": "الخطوة {step}: **الإجابة النهائية** (المبسطة) = **{res}**\n\n*✨ النهائي: تم اختزال الكسر إلى أبسط صورة له.*",
        "hi": "चरण {step}: **अंतिम उत्तर** (सरलीकृत) = **{res}**\n\n*✨ अंतिम: भिन्न को उसके सरलतम रूप में कम कर दिया गया है।*",
    },
    "final_step_mixed": {
        "fa": "مرحله {step}: تبدیل به **عدد مخلوط** → **{whole}** و **{remainder}**\n\n*💡 چرا؟ صورت ( {numerator} ) از مخرج ( {denominator} ) بزرگتر است، بنابراین به عدد مخلوط تبدیل شد تا فهم بهتری از مقدار آن داشته باشیم.*",
        "en": "Step {step}: Convert to a **mixed number** → **{whole}** and **{remainder}**\n\n*💡 Why? The numerator ( {numerator} ) is greater than the denominator ( {denominator} ), so it was converted to a mixed number for a better understanding of its value.*",
        "es": "Paso {step}: Convertir a un **número mixto** → **{whole}** y **{remainder}**\n\n*💡 ¿Por qué? El numerador ( {numerator} ) es mayor que el denominador ( {denominator} ), por lo que se convirtió en un número mixto para comprender mejor su valor.*",
        "fr": "Étape {step}: Convertir en **nombre fractionnaire** → **{whole}** و **{remainder}**\n\n*💡 Pourquoi ? Le numérateur ( {numerator} ) est supérieur au dénominateur ( {denominator} ), il a donc été converti en nombre fractionnaire pour mieux comprendre sa valeur.*",
        "ar": "الخطوة {step}: التحويل إلى **عدد كسري** → **{whole}** و **{remainder}**\n\n*💡 لماذا؟ البسط ( {numerator} ) أكبر من المقام ( {denominator} )، لذلك تم تحويله إلى عدد كسري لفهم أفضل لقيمته.*",
        "hi": "चरण {step}: **मिश्रित संख्या** में बदलें → **{whole}** और **{remainder}**\n\n*💡 क्यों? अंश ( {numerator} ) भाजक ( {denominator} ) से बड़ा है, इसलिए इसे मिश्रित संख्या में बदल दिया गया ताकि इसके मान को बेहतर ढंग से समझा जा सके।*",
    }
}


# ================== ۴. کیبوردها و توابع کمکی ==================
def t(lang, key, **kwargs):
    """دسترسی به متون چندزبانه."""
    return TEXT[key].get(lang, TEXT[key]["en"]).format(**kwargs)

def op_keyboard(lang="en"):
    """کیبورد عملیات اصلی را بر اساس زبان تولید می‌کند."""
    labels = OP_BUTTONS.get(lang, OP_BUTTONS["en"])
    keyboard = [
        [InlineKeyboardButton(f"➕ {labels[0]}", callback_data='+'),
         InlineKeyboardButton(f"➖ {labels[1]}", callback_data='-')],
        [InlineKeyboardButton(f"✖️ {labels[2]}", callback_data='*'),
         InlineKeyboardButton(f"➗ {labels[3]}", callback_data='/')],
        # دکمه /Status باید همیشه آخرین آیتم باشد تا با edit_message_text تداخل نداشته باشد
        [InlineKeyboardButton(f"📊 /Status", callback_data='status_check')] 
    ]
    return InlineKeyboardMarkup(keyboard)

def status_keyboard(lang):
    """کیبورد پنل وضعیت را تولید می‌کند."""
    keyboard = [
        [InlineKeyboardButton(TEXT['buy_sub'].get(lang, TEXT['buy_sub']['en']), callback_data='buy_vip')],
        [InlineKeyboardButton(TEXT['op_menu'].get(lang, TEXT['op_menu']['en']), callback_data='op_menu')]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_user(user_id):
    """دریافت اطلاعات کاربر از Redis."""
    try:
        user_data = REDIS_CLIENT.get(f"user:{user_id}")
        if user_data:
            # مطمئن می‌شویم که داده‌ها قبل از بارگذاری JSON خالی نیستند
            return json.loads(user_data)
    except Exception as e:
        logging.error(f"Redis get error for user {user_id}: {e}")
    # مقادیر پیش‌فرض
    return {"lang":"fa","trial":FREE_TRIAL,"is_vip":False,"total":0,"correct":0,"topic":"+","expected_answer":None,"f1_tuple":(1,2),"f2_tuple":(1,3)}

def save_user(user_id, data):
    """ذخیره اطلاعات کاربر در Redis."""
    try:
        REDIS_CLIENT.set(f"user:{user_id}", json.dumps(data))
    except Exception as e:
        logging.error(f"Redis save error for user {user_id}: {e}")

def normalize(ans):
    """نرمال‌سازی پاسخ کاربر به کسر ساده شده (پشتیبانی از عدد مخلوط '1 1/2' یا '1+1/2')."""
    ans = ans.strip().replace(" ","")
    try: 
        # پشتیبانی از عدد مخلوط با فضای خالی یا + (مثلا: "1+1/2" یا "1 1/2" که قبلاً با replace حذف شده)
        if '+' in ans:
            parts = ans.split('+')
            res = sum(sympy.Rational(p) for p in parts)
            return str(res)
        
        # اگر کاربر عدد مخلوط را به صورت "11/2" (بدون فاصله) وارد کرده باشد (که معمولاً به صورت 11/2 تفسیر می‌شود)
        # فرض می‌کنیم ورودی تنها یک کسر است مگر اینکه با "+" جدا شده باشد.
        return str(sympy.Rational(ans))
    except: 
        return ans.strip()

def is_admin(user_id):
    """بررسی می‌کند که آیا کاربر ادمین است."""
    # مطمئن شوید که ADMIN_ID تنظیم شده و قابل مقایسه است
    return str(user_id) == str(ADMIN_ID) if ADMIN_ID else False

# ================== ۵. تولید سوال و توضیح گام‌به‌گام ==================
def generate_problem(op, vip=False):
    """تولید تصادفی مسئله کسرها."""
    max_num = 30 if vip else 15
    max_den = 20 if vip else 12
    
    # تولید تصادفی
    n1, n2 = random.randint(1,max_num), random.randint(1,max_num)
    d1, d2 = random.randint(2,max_den), random.randint(2,max_den)
    
    f1, f2 = sympy.Rational(n1,d1), sympy.Rational(n2,d2)
    
    if op == '+':
        res = f1+f2
        text = f"{f1} + {f2}"
    elif op=='-':
        if f1<f2: f1,f2=f2,f1 # جلوگیری از پاسخ منفی در سطح مقدماتی (اگرچه sympy منفی را مدیریت می‌کند)
        res = f1-f2
        text = f"{f1} − {f2}"
    elif op=='*':
        res=f1*f2
        text=f"{f1} × {f2}"
    else: # op == '/'
        if f2==0: f2=sympy.Rational(1,2) # اطمینان از عدم تقسیم بر صفر
        res=f1/f2
        text=f"{f1} ÷ {f2}"
        
    return text,str(res),(f1.p,f1.q),(f2.p,f2.q)

def explain(f1_tuple, f2_tuple, op, lang):
    """تولید توضیح گام به گام چندزبانه با جزئیات کامل."""
    f1 = sympy.Rational(f1_tuple[0], f1_tuple[1])
    f2 = sympy.Rational(f2_tuple[0], f2_tuple[1])
    
    op_symbols = {'+': '+', '-': '−', '*': '×', '/': '÷'}
    explanation = EXPLANATIONS["problem_intro"].get(lang, EXPLANATIONS["problem_intro"]["en"]).format(f1=f1, op_symbol=op_symbols[op], f2=f2)
    step = 1
    
    explanation += "\n\n"

    # ---------- عملیات جمع و تفریق ----------
    if op in ['+', '-']:
        q1, q2 = f1.q, f2.q
        lcm = sympy.lcm(q1, q2)
        
        # گام ۱: یافتن مخرج مشترک (LCM)
        explanation += f"\n{EXPLANATIONS['lcm_step'].get(lang, EXPLANATIONS['lcm_step']['en']).format(step=step, q1=q1, q2=q2, lcm=lcm)}"
        step += 1
        
        # گام ۲: تبدیل کسرها (با محاسبه فاکتورها)
        factor1 = lcm // q1
        factor2 = lcm // q2
        f1_new = sympy.Rational(f1.p * factor1, lcm)
        f2_new = sympy.Rational(f2.p * factor2, lcm)
        explanation += f"\n{EXPLANATIONS['convert_step'].get(lang, EXPLANATIONS['convert_step']['en']).format(step=step, f1=f1, f1_new=f1_new, f2=f2, f2_new=f2_new, factor1=factor1, factor2=factor2, lcm=lcm)}"
        step += 1
        
        # گام ۳: انجام عملیات روی صورت‌ها
        res = f1_new + f2_new if op == '+' else f1_new - f2_new
        explanation += f"\n{EXPLANATIONS['operation_step'].get(lang, EXPLANATIONS['operation_step']['en']).format(step=step, f1_new=f1_new.p, op_symbol=op_symbols[op], f2_new=f2_new.p, res=f1_new.p + (f2_new.p if op == '+' else -f2_new.p), lcm=lcm)}"
        step += 1
        
    # ---------- عملیات ضرب ----------
    elif op == '*':
        # گام ۱: انجام ضرب (با ارسال صورت‌ها و مخرج‌ها)
        res = f1 * f2
        explanation += f"\n{EXPLANATIONS['mult_step'].get(lang, EXPLANATIONS['mult_step']['en']).format(step=step, f1=f1, f2=f2, res=res, n1=f1.p, n2=f2.p, q1=f1.q, q2=f2.q)}"
        step += 1
        
    # ---------- عملیات تقسیم ----------
    else:  # op == '/'
        f2_reciprocal = sympy.Rational(f2.q, f2.p)
        
        # گام ۱: تبدیل به ضرب معکوس
        explanation += f"\n{EXPLANATIONS['div_step1'].get(lang, EXPLANATIONS['div_step1']['en']).format(step=step, f1=f1, f2=f2, f2_reciprocal=f2_reciprocal)}"
        step += 1
        
        # گام ۲: انجام ضرب
        res = f1 * f2_reciprocal
        explanation += f"\n{EXPLANATIONS['div_step2'].get(lang, EXPLANATIONS['div_step2']['en']).format(step=step, f1=f1, f2_reciprocal=f2_reciprocal, res=res)}"
        step += 1
        
    # ---------- گام نهایی: ساده‌سازی / عدد مخلوط ----------
    # محاسبه نهایی (ساده شده)
    final_result = f1 + f2 if op == '+' else (f1 - f2 if op == '-' else (f1 * f2 if op == '*' else f1 / f2))

    if final_result.q == 1:
        explanation += f"\n{EXPLANATIONS['final_step_simple'].get(lang, EXPLANATIONS['final_step_simple']['en']).format(step=step, res=final_result)}"
    elif abs(final_result) > 1:
        whole = abs(final_result.p) // final_result.q
        remainder = abs(final_result) - whole
        sign = "-" if final_result < 0 else ""
        explanation += f"\n{EXPLANATIONS['final_step_mixed'].get(lang, EXPLANATIONS['final_step_mixed']['en']).format(step=step, whole=sign+str(whole), remainder=remainder, numerator=abs(final_result.p), denominator=final_result.q)}"
    else:
        explanation += f"\n{EXPLANATIONS['final_step_simple'].get(lang, EXPLANATIONS['final_step_simple']['en']).format(step=step, res=final_result)}"
        
    return explanation

# ================== ۶. هندلرهای ربات (دستورات کاربر) ==================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """هندلر دستور /start."""
    user_id = update.effective_user.id
    user = get_user(user_id)
    save_user(user_id,user)
    
    # منوی انتخاب زبان
    await update.message.reply_text("انتخاب زبان / Choose language:",reply_markup=InlineKeyboardMarkup([
        [InlineKeyboardButton("FA 🇮🇷",callback_data="lang_fa"),
         InlineKeyboardButton("EN 🇬🇧",callback_data="lang_en"),
         InlineKeyboardButton("ES 🇪🇸",callback_data="lang_es")],
        [InlineKeyboardButton("FR 🇫🇷",callback_data="lang_fr"),
         InlineKeyboardButton("AR 🇸🇦",callback_data="lang_ar"),
         InlineKeyboardButton("HI 🇮🇳",callback_data="lang_hi")]
    ]))

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """هندلر دستور /status برای نمایش وضعیت و آمار کاربر."""
    user_id = update.effective_user.id
    user = get_user(user_id)
    lang = user['lang']
    
    accuracy = (user['correct']/user['total']*100) if user['total'] > 0 else 0
    
    stats_text = {
        "fa": f"📊 **وضعیت و آمار شما** 📊\n\n🧑‍💻 **شناسه کاربری:** `{user_id}`\n🌐 **زبان:** {lang.upper()}\n✨ **وضعیت اشتراک:** {'✅ VIP (نامحدود)' if user['is_vip'] else '❌ عادی'}\n\n⏳ **سوالات رایگان باقی‌مانده:** {user['trial']}\n\n💯 **تعداد کل سوالات حل شده:** {user['total']}\n✅ **پاسخ‌های صحیح:** {user['correct']}\n🎯 **دقت کلی:** {accuracy:.2f}%",
        "en": f"📊 **Your Status & Stats** 📊\n\n🧑‍💻 **User ID:** `{user_id}`\n🌐 **Language:** {lang.upper()}\n✨ **Subscription Status:** {'✅ VIP (Unlimited)' if user['is_vip'] else '❌ Standard'}\n\n⏳ **Free questions left:** {user['trial']}\n\n💯 **Total Questions Solved:** {user['total']}\n✅ **Correct Answers:** {user['correct']}\n🎯 **Overall Accuracy:** {accuracy:.2f}%",
    }.get(lang, f"📊 Your Status & Stats 📊\nUser ID: `{user_id}`\nTotal: {user['total']} | Correct: {user['correct']}")
    
    await update.message.reply_text(stats_text, parse_mode='Markdown', reply_markup=status_keyboard(lang))

async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """هندلر برای دکمه‌های اینلاین."""
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    user = get_user(user_id)
    
    # ۱. مدیریت تغییر زبان
    if query.data.startswith("lang_"):
        user['lang']=query.data.split("_")[1]
        save_user(user_id,user)
        await query.edit_message_text(t(user['lang'],"welcome")+"\n\n"+t(user['lang'],"choose_op"),reply_markup=op_keyboard(user['lang']))
        return
    
    # ۲. مدیریت دکمه‌های UX
    if query.data == 'op_menu' or query.data == 'status_check':
        # اگر از داخل منوی status_check (دکمه "بازگشت به عملیات") یا دکمه op_menu کلیک شد
        await query.edit_message_text(t(user['lang'],"choose_op"),reply_markup=op_keyboard(user['lang']))
        return

    if query.data == 'buy_vip':
        await query.edit_message_text(t(user['lang'],'send_proof'), parse_mode='Markdown')
        return

    # ۳. مدیریت شروع عملیات (تولید سوال)
    op=query.data
    
    # بررسی محدودیت سوال رایگان
    if not user['is_vip'] and user['trial']<=0:
        await query.edit_message_text(t(user['lang'],'trial_over')+"\n\n"+t(user['lang'],'send_proof'), parse_mode='Markdown')
        return
    
    # تولید مسئله
    problem,answer,f1_tuple,f2_tuple=generate_problem(op,vip=user['is_vip'])
    user.update({"expected_answer":answer,"topic":op,"problem_text":problem,"f1_tuple":f1_tuple,"f2_tuple":f2_tuple})
    
    # کاهش سوال رایگان
    if not user['is_vip']:
        user['trial']-=1
        
    save_user(user_id,user)
    
    # ارسال سوال
    await query.edit_message_text(
        f"**{problem} = ?**\n\n"
        f"*{t(user['lang'],'trial_left')}: {user['trial']}*\n\n"
        f"لطفاً پاسخ نهایی را به صورت کسر ساده شده یا عدد مخلوط (مثلاً '3/2' یا '1 1/2') وارد کنید:",
        parse_mode='Markdown'
    )

async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """هندلر برای دریافت پاسخ‌های متنی کاربر."""
    user_id = update.effective_user.id
    text = update.message.text.strip()
    user = get_user(user_id)
    
    if not user.get("expected_answer"):
        # اگر کاربر قبل از انتخاب عملیات پیام فرستاد
        await update.message.reply_text("لطفاً ابتدا /start را بزنید یا یک عملیات را از منو انتخاب کنید.", reply_markup=op_keyboard(user['lang']))
        return
        
    user['total']+=1
    
    # بررسی پاسخ
    if normalize(text)==user['expected_answer']:
        user['correct']+=1
        feedback = t(user['lang'],'correct')
    else:
        # نمایش پاسخ صحیح و توضیح گام به گام
        explanation_text = explain(user['f1_tuple'],user['f2_tuple'],user['topic'],user['lang'])
        feedback = f"{t(user['lang'],'wrong')} **{user['expected_answer']}**\n\n{explanation_text}"
        
    save_user(user_id,user)
    
    # ارسال بازخورد و کیبورد عملیات بعدی
    await update.message.reply_text(feedback+"\n\n"+t(user['lang'],'next_question'), 
                                    parse_mode='Markdown',
                                    reply_markup=op_keyboard(user['lang']))

# ================== ۷. هندلرهای مدیریت ادمین ==================
async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """هندلر دستور /admin."""
    user_id = update.effective_user.id
    if not is_admin(user_id):
        await update.message.reply_text("⛔️ دسترسی محدود شده است.")
        return
        
    await update.message.reply_text(
        "**پنل ادمین (Admin Panel)**\n\n"
        "برای اعطای اشتراک VIP (نامحدود)، از دستور زیر استفاده کنید:\n"
        "`/setvip [USER_ID]`\n"
        "مثال: `/setvip 123456789`",
        parse_mode='Markdown'
    )

async def set_vip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """هندلر دستور /setvip [ID] برای اعطای VIP."""
    user_id = update.effective_user.id
    if not is_admin(user_id):
        await update.message.reply_text("⛔️ دسترسی محدود شده است.")
        return
        
    try:
        if not context.args or not context.args[0].isdigit():
            await update.message.reply_text("❌ فرمت دستور اشتباه است. باید: `/setvip [USER_ID]`", parse_mode='Markdown')
            return
            
        target_id = int(context.args[0])
        
        # به‌روزرسانی وضعیت در Redis
        target_user = get_user(target_id)
        target_user['is_vip'] = True
        target_user['trial'] = 99999 # سوالات رایگان نامحدود برای VIP
        save_user(target_id, target_user)
        
        await update.message.reply_text(f"✅ کاربر با شناسه **{target_id}** با موفقیت به وضعیت VIP ارتقا یافت.", parse_mode='Markdown')
        
        # اطلاع‌رسانی به کاربر هدف (اختیاری)
        try:
             await context.bot.send_message(target_id, "تبریک! اشتراک VIP شما توسط ادمین فعال شد. اکنون می‌توانید به طور نامحدود سوال حل کنید. /status")
        except Exception as e:
             logging.error(f"Could not send VIP notification to user {target_id}: {e}")
             await update.message.reply_text("⚠️ نتوانستم به کاربر مورد نظر پیام ارسال کنم.")

    except Exception as e:
        await update.message.reply_text(f"❌ خطا در به‌روزرسانی کاربر: {e}")

# ================== ۸. اجرای برنامه ==================
def main():
    """شروع به کار ربات."""
    if not BOT_TOKEN:
        logging.critical("BOT_TOKEN environment variable is not set! Exiting.")
        return
        
    app = Application.builder().token(BOT_TOKEN).build()
    
    # هندلرهای دستورات
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("status", status))
    
    # هندلرهای ادمین
    app.add_handler(CommandHandler("admin", admin_panel))
    app.add_handler(CommandHandler("setvip", set_vip))

    # هندلر دکمه‌های اینلاین و پیام‌های متنی
    app.add_handler(CallbackQueryHandler(callback_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))
    
    logging.info("Fraction Bot started! Polling...")
    app.run_polling()

if __name__=="__main__":
    main()
