import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


def _load_env():
    env_file = BASE_DIR / ".env"
    if not env_file.exists():
        return
    for line in env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if value and not os.environ.get(key):
            os.environ[key] = value


_load_env()
DATA_DIR = BASE_DIR / "data"
KB_DIR = DATA_DIR / "kb"
MODEL_DIR = DATA_DIR / "models"
WEB_DIR = BASE_DIR / "web"

LANG_DETECT_MODEL = "lid.176.bin"

# Second safety layer: when the word rules find no emergency, a short Gemma call on Amazon Bedrock reads the message and
# may still raise the emergency or self-harm reply. It only ever ADDS an alarm and runs only when AWS credentials exist
# (the server's AWS_BEARER_TOKEN_BEDROCK in .env, or an AWS login). Set to false to switch it off.
SAFETY_LLM_CHECK = os.environ.get("SAFETY_LLM_CHECK", "true").lower() in ("1", "true", "yes")
SAFETY_LLM_TIMEOUT_S = float(os.environ.get("SAFETY_LLM_TIMEOUT_S", "2.5"))
SAFETY_LLM_MAX_TOKENS = int(os.environ.get("SAFETY_LLM_MAX_TOKENS", "40"))
# Bedrock model for the check (default Gemma 3 27B).
SAFETY_LLM_MODEL_ID = os.environ.get("SAFETY_LLM_MODEL_ID", "") or "google.gemma-3-27b-it"

SUPPORTED_LANGUAGES = ["en", "hi", "bn", "ta", "te", "mr", "gu", "kn", "ml", "pa", "or", "ur"]
LANG_NAMES = {
    "en": "English",
    "hi": "Hindi",
    "bn": "Bengali",
    "ta": "Tamil",
    "te": "Telugu",
    "mr": "Marathi",
    "gu": "Gujarati",
    "kn": "Kannada",
    "ml": "Malayalam",
    "pa": "Punjabi",
    "or": "Odia",
    "ur": "Urdu",
}

HELPLINES = {
    "en": "National Health Helpline: 108 (Ambulance), 112 (Emergency), 104 (Health Advice).",
    "hi": "राष्ट्रीय स्वास्थ्य हेल्पलाइन: 108 (एम्बुलेंस), 112 (आपातकाल), 104 (स्वास्थ्य सलाह)।",
    "bn": "জাতীয় স্বাস্থ্য হেল্পলাইন: 108 (অ্যাম্বুলেন্স), 112 (জরুরি), 104 (স্বাস্থ্য পরামর্শ)।",
    "ta": "தேசிய சுகாதார உதவி எண்: 108 (ஆம்புலன்ஸ்), 112 (அவசரம்), 104 (சுகாதார ஆலோசனை).",
    "te": "జాతీయ ఆరోగ్య హెల్ప్‌లైన్: 108 (అంబులెన్స్), 112 (అత్యవసరం), 104 (ఆరోగ్య సలహా).",
    "mr": "राष्ट्रीय आरोग्य हेल्पलाइन: 108 (रुग्णवाहिका), 112 (आणीबाणी), 104 (आरोग्य सल्ला).",
    "gu": "રાષ્ટ્રીય આરોગ્ય હેલ્પલાઇન: 108 (એમ્બ્યુલન્સ), 112 (કટોકટી), 104 (આરોગ્ય સલાહ).",
    "kn": "ರಾಷ್ಟ್ರೀಯ ಆರೋಗ್ಯ ಸಹಾಯವಾಣಿ: 108 (ಆಂಬುಲೆನ್ಸ್), 112 (ತುರ್ತು), 104 (ಆರೋಗ್ಯ ಸಲಹೆ).",
    "ml": "ദേശീയ ആരോഗ്യ ഹെൽപ്പ്‌ലൈൻ: 108 (ആംബുലൻസ്), 112 (അടിയന്തരം), 104 (ആരോഗ്യ ഉപദേശം).",
    "pa": "ਰਾਸ਼ਟਰੀ ਸਿਹਤ ਹੈਲਪਲਾਈਨ: 108 (ਐਂਬੂਲੈਂਸ), 112 (ਐਮਰਜੈਂਸੀ), 104 (ਸਿਹਤ ਸਲਾਹ).",
    "or": "ଜାତୀୟ ସ୍ୱାସ୍ଥ୍ୟ ହେଲ୍ପଲାଇନ: 108 (ଆମ୍ବୁଲାନ୍ସ), 112 (ଜରୁରୀ), 104 (ସ୍ୱାସ୍ଥ୍ୟ ପରାମର୍ଶ).",
    "ur": "قومی صحت ہیلپ لائن: 108 (ایمبولینس)، 112 (ہنگامی)، 104 (صحت مشورہ).",
}


# WhatsApp Business Cloud API Configuration
# WhatsApp (Meta Cloud API) is optional. The webhook routes exist only when this is true.
WHATSAPP_ENABLED = os.environ.get("WHATSAPP_ENABLED", "false").lower() in ("1", "true", "yes")

WHATSAPP_TOKEN = os.environ.get("WHATSAPP_TOKEN", "")
WHATSAPP_PHONE_ID = os.environ.get("WHATSAPP_PHONE_ID", "")
WHATSAPP_VERIFY_TOKEN = os.environ.get("WHATSAPP_VERIFY_TOKEN", "")  # no default: set it in .env
WHATSAPP_API_VERSION = os.environ.get("WHATSAPP_API_VERSION", "v25.0")
WHATSAPP_APP_SECRET = os.environ.get("WHATSAPP_APP_SECRET", "")

# Secret for the WhatsApp test route (/webhook/whatsapp/simulate). Unset means that route is disabled.
ADMIN_TOKEN = os.environ.get("ADMIN_TOKEN", "")

# Browsers may call the API only from these origins (the page is served from the same origin, so this is a safety net).
CORS_ORIGINS = [
    o.strip()
    for o in os.environ.get(
        "CORS_ORIGINS", "https://aarogyasathi.nova-care.xyz,http://localhost:8000,http://127.0.0.1:8000"
    ).split(",")
    if o.strip()
]
# Messages one client address may send to /api/chat per minute (0 switches the limit off).
RATE_LIMIT_PER_MIN = int(os.environ.get("RATE_LIMIT_PER_MIN", "30"))
