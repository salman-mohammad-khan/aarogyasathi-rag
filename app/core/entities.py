import re
import unicodedata

SYMPTOM_LEXICON = {
    "fever": ["fever", "bukhar", "बुखार", "ज्वर", "high temperature", "tapman"],
    "headache": ["headache", "sar dard", "sir dard", "सिरदर्द", "सिर में दर्द", "head pain", "headake", "hedache", "head ache", "sar dardh"],
    "cough": ["cough", "khansi", "खाँसी", "खांसी"],
    "cold": ["cold", "runny nose", "sardi", "zukam", "जुकाम", "ज़ुकाम", "सर्दी", "naak behna", "नाक बहना"],
    "sore_throat": ["sore throat", "gale me dard", "gale mein dard", "गले में दर्द", "गले में खराश"],
    "body_pain": ["body pain", "body ache", "badan dard", "मांसपेशियों में दर्द", "बदन दर्द", "शरीर में दर्द", "muscle pain"],
    "joint_pain": ["joint pain", "jodo me dard", "जोड़ों में दर्द", "जोड़ों का दर्द"],
    "nausea": ["nausea", "ji michlana", "मतली", "जी मिचलाना", "उबकाई", "feeling sick"],
    "vomiting": ["vomiting", "ulti", "उल्टी", "vomit", "उलटी"],
    "diarrhoea": ["diarrhoea", "diarrhea", "loose motions", "dast", "दस्त", "loose stool", "अतिसार"],
    "abdominal_pain": ["stomach pain", "pet dard", "pet me dard", "पेट दर्द", "पेट में दर्द", "abdominal pain", "stomach ache", "cramps", "marod", "मरोड़", "stoamch", "stomache", "stomuch", "stomch", "pet me dardh", "tummy", "tummy pain", "pet kharab", "पेट खराब", "pet kharaab", "stomach upset", "pet me jalan", "पेट में जलन"],
    "rash": ["rash", "rashes", "chakte", "चकत्ते", "त्वचा पर दाने", "dane", "दाने", "skin rash"],
    "fatigue": ["fatigue", "tired", "thakan", "थकान", "weakness", "kamzori", "कमज़ोरी", "कमजोरी", "sust", "सुस्त"],
    "dizziness": ["dizzy", "chakkar", "चक्कर", "dizziness", "vertigo", "ghoomna"],
    "breathlessness": ["breathless", "saans phoolna", "साँस फूलना", "सांस लेने में दिक्कत", "difficulty breathing", "saanas", "shortness of breath"],
    "chest_pain": ["chest pain", "chhati me dard", "सीने में दर्द", "छाती में दर्द"],
    "eye_pain": ["eye pain", "aankh dard", "आँखों में दर्द", "pain behind eyes", "आँखों के पीछे दर्द"],
    "jaundice_sign": ["yellow eyes", "yellow skin", "peeliya", "पीलिया", "peela", "पीला पेशाब", "dark urine", "गहरे रंग का पेशाब"],
    "weight_loss": ["weight loss", "wajan kam", "वज़न घटना", "वजन कम", "waight loss"],
    "night_sweats": ["night sweats", "raat me pasina", "रात में पसीना"],
    "blood_sputum": ["blood in sputum", "balgam me khoon", "बलगम में खून", "khoon ki khansi"],
    "bleeding": ["bleeding", "khoon behna", "खून बहना", "रक्तस्राव", "nose bleed", "nakseer", "नकसीर"],
    "loss_appetite": ["loss of appetite", "bhookh kam", "bhookh nahi", "भूख न लगना", "भूख कम"],
    "dehydration": ["dehydration", "pani ki kami", "पानी की कमी", "sunken eyes", "dhasi aankhein", "धँसी आँखें"],
    "unconscious": ["unconscious", "behosh", "बेहोश", "faint", "fainted", "collapse"],
    "seizure": ["seizure", "fits", "daure", "दौरे", "दौरा", "convulsion", "jhatke"],
    "swelling": ["swelling", "sujan", "सूजन", "सूजी"],
    "neck_pain": ["neck pain", "neck ache", "neck me dard", "gardan me dard", "गर्दन में दर्द", "neck stiffness", "गर्दन अकड़न"],
    "back_pain": ["back pain", "backache", "kamar dard", "कमर दर्द", "कमर में दर्द", "back me dard"],
    "shoulder_pain": ["shoulder pain", "kandhe me dard", "कंधे में दर्द", "kandha dard"],
    "leg_pain": ["leg pain", "leg me dard", "पैर में दर्द", "pair me dard", "foot pain"],
    "arm_pain": ["arm pain", "hand pain", "haath me dard", "बाँह में दर्द"],
    "knee_pain": ["knee pain", "ghutne me dard", "घुटने में दर्द"],
}

RED_FLAG_LEXICON = {
    "chest_pain": ["chest pain", "heart attack", "sine me dard", "सीने में दर्द", "chhati me dard", "dil ka daura", "दिल का दौरा"],
    "breathing": ["cannot breathe", "can't breathe", "difficulty breathing", "saans nahi aa rahi", "साँस नहीं आ रही", "सांस लेने में तकलीफ", "dum ghut raha hai", "दम घुट रहा है"],
    "unconscious": ["unconscious", "behosh", "बेहोश", "not responding", "unresponsive", "fainted", "collapse"],
    "seizure": ["seizure", "fits", "daure", "दौरे", "convulsions"],
    "bleeding": ["heavy bleeding", "khoon beh raha", "खून बह रहा", "severe bleeding", "profuse bleeding"],
    "snake_bite": ["snake bite", "snakebite", "saap ne kaat", "साँप ने काट", "saanp kaata", "सर्पदंश"],
    "rabid_animal": ["dog bite", "kutta kaat", "कुत्ते ने काट", "monkey bite", "bandar ne kaat", "बंदर ने काट"],
    "poison": ["poison", "zahar", "ज़हर", "जहर", "consumed poison", "jahar kha liya"],
    "stroke": ["stroke", "paralysis", "lakwa", "लकवा", "face drooping", "slurred speech"],
    "suicide": [
        "suicide", "khudkushi", "आत्महत्या", "self harm", "self-harm", "kill myself", "jeena nahi",
        "end my life", "ending my life", "end it all", "want to die", "wanna die", "take my own life",
        "don't want to live", "dont want to live", "no reason to live",
        "marna chahta", "marna chahti", "mar jana chahta", "mar jaana chahta", "mar jana chahti",
        "jeene ka mann nahi", "jine ka mann nahi", "zindagi khatam",
        "मरना चाहता", "मरना चाहती", "जीने का मन नहीं", "जिंदगी खत्म", "ज़िंदगी खत्म",
    ],
    "pregnancy_bleed": ["pregnancy bleeding", "garbhavati ko khoon", "गर्भावस्था में खून"],
    "severe_burn": ["severe burn", "burned badly", "jala hua", "जल गया"],
}

# Natural phrasings that a fixed phrase list cannot cover ("a snake just bit my brother", "seene mein dard ho raha
# hai"). Each pattern joins two cue words with at most three other words and no sentence punctuation between them, so
# "is that snake poisonous" and "snake sightings in my village" stay information questions. Plain regex, no model.
_GAP = r"(?:\s+[^\s.,;:!?]+){0,3}?"
_BITE = (
    r"(?:bit|bite|bites|biting|bitten|kaat|kaata|kaati|kaatna|kaatne|kata|dasa|daas|daans|dans|"
    r"काट|काटा|काटी|डस|डसा|डसी)"
)
_SNAKE = r"(?:snakes?|cobra|viper|krait|saap|saanp|sanp|sap|साँप|सांप|सर्प)"
_ANIMAL = r"(?:dogs?|puppy|monkeys?|kutta|kutte|bandar|कुत्ता|कुत्ते|बंदर)"
_CHEST = r"(?:chest|seene|seena|sine|sina|chhati|chhaati|chati|chaati|सीने|सीना|छाती)"
_CHEST_SYMPTOM = (
    r"(?:pains?|hurt|hurts|hurting|ache|aching|tight|tightness|heavy|heaviness|pressure|crushing|burning|squeez\w*|"
    r"dard|dardh|dabav|bhaari|bhari|jalan|jakdan|दर्द|जलन|भारीपन|दबाव|जकड़न)"
)
_ASCII_WORD = r"(?<![a-z0-9])"  # left edge: do not start in the middle of an ASCII word
_ASCII_END = r"(?![a-z0-9])"

RED_FLAG_PATTERNS = {
    "snake_bite": [
        re.compile(rf"{_ASCII_WORD}{_SNAKE}{_GAP}\s+{_BITE}{_ASCII_END}"),
        re.compile(rf"{_ASCII_WORD}{_BITE}{_GAP}\s+{_SNAKE}{_ASCII_END}"),
    ],
    "rabid_animal": [
        re.compile(rf"{_ASCII_WORD}{_ANIMAL}{_GAP}\s+(?:bit|bites|bitten|kaat|kaata|kaati|काट|काटा|काटी){_ASCII_END}"),
        re.compile(rf"{_ASCII_WORD}(?:bit|bitten){_GAP}\s+(?:by\s+)?(?:an?\s+|the\s+)?{_ANIMAL}{_ASCII_END}"),
    ],
    "chest_pain": [
        re.compile(rf"{_ASCII_WORD}{_CHEST}{_GAP}\s+{_CHEST_SYMPTOM}{_ASCII_END}"),
        re.compile(rf"{_ASCII_WORD}{_CHEST_SYMPTOM}\s+(?:in|on|around)\s+(?:my\s+|his\s+|her\s+|the\s+)?chest{_ASCII_END}"),
    ],
}

# --- Wider coverage: English, Hindi and Hinglish only --------------------------------------------------------
# Added after an audit found that most real emergency and self-harm wordings were missed (6 of 17 emergencies,
# 0 of 5 self-harm messages). These rules cannot understand a message; they only match wordings listed here.
# Tamil, Bengali, Marathi and the other listed languages are NOT covered. When in doubt a rule fires: a false alarm
# shows a helpline, a miss can cost a life. Tests are in tests/test_emergency_coverage.py.
_MORE_RED_FLAGS = {
    "chest_pain": [
        "cardiac arrest", "crushing chest", "dil ki dhadkan ruk", "haath sunn", "hath sunn", "arm numb",
        "left arm pain", "हाथ सुन्न",
    ],
    "breathing": [
        "not breathing", "stopped breathing", "stops breathing", "struggling to breathe", "unable to breathe",
        "not able to breathe", "trouble breathing", "gasping", "turning blue", "blue lips",
        "saans nahi le", "sans nahi le", "saans nahi aa", "sans nahi aa", "saans lene me dikkat",
        "sans lene me dikkat", "saans lene mein dikkat", "sans lene mein dikkat", "saans ruk",
        "struggling for air", "gasping for air", "hawa nahi", "asthma attack", "inhaler is not working", "inhaler not working", "dama ka daura", "दमे का दौरा",
        "सांस नहीं ले", "साँस नहीं ले", "सांस नहीं आ", "सांस लेने में दिक्कत", "साँस लेने में दिक्कत", "दम घुट",
    ],
    "injury": [
        "head injury", "road accident", "accident ho gaya", "accident hua", "accident ho gayi", "stabbed", "gunshot",
        "shot in", "sir me chot", "sar me chot", "सिर में चोट", "एक्सीडेंट", "दुर्घटना",
    ],
    "choking": [
        "choking", "choked", "swallowed a coin", "swallowed a button", "swallowed a battery",
        "nigal li", "nigal liya", "निगल लिया", "निगल ली", "something stuck in throat", "gale me atak", "गले में अटक",
    ],
    "unconscious": [
        "not waking up", "won't wake up", "wont wake up", "not responding", "passed out", "not conscious",
        "hosh nahi", "hosh me nahi", "went limp", "eyes rolled back", "eyes rolling back", "no pulse", "no heartbeat", "pulse nahi", "slumped",
        "बोल नहीं रहे", "बोल नहीं रही", "बोल नहीं रहा", "won't respond", "wont respond", "doesn't respond", "does not respond", "uth nahi", "utth nahi",
        "hil nahi raha", "hil nahi rahi", "hil nahi rahe", "aankhein ulat", "ankhein ulat", "उठ नहीं", "हिल नहीं",
        "आँखें उलट", "आंखें उलट", "होश नहीं",
    ],
    "seizure": [
        "foaming at the mouth", "foaming at mouth", "mooh se jhaag", "munh se jhaag", "jhaag aa", "body akad",
        "मुँह से झाग", "मुंह से झाग", "झाग",
        "convulsing", "having a fit", "having fits", "jhatke aa", "daura pad", "daura pada", "mirgi ka daura",
        "मिर्गी", "दौरा पड़", "दौरा पड",
    ],
    "bleeding": [
        "bleeding heavily", "bleeding badly", "bleeding a lot", "bleeding profusely", "bleeding non stop",
        "bleeding nonstop", "won't stop bleeding", "wont stop bleeding", "vomiting blood", "vomit blood",
        "vomited blood", "coughing blood", "coughing up blood", "cough up blood", "blood in vomit",
        "blood in the vomit", "khoon nikal", "khoon beh", "khoon bah", "khoon aa raha", "ulti me khoon",
        "ulti mein khoon", "khoon ki ulti", "huge amount of blood", "huge amounts of blood", "so much blood",
        "blood everywhere", "blood all over", "ब्लीडिंग हो", "बहुत ब्लीडिंग", "bleeding ho raha", "bleeding ho rahi", "losing blood", "lost a lot of blood", "losing a lot of blood",
        "bleeding from the head", "bleeding from his head", "bleeding from her head", "bleeding from my head", "खून निकल", "खून बह", "खून आ रहा", "उल्टी में खून", "खून की उल्टी",
    ],
    "stroke": [
        "face droop", "face is drooping", "drooping face", "mouth drooping", "mouth is twisted", "muh tedha",
        "munh tedha", "mooh tedha", "मुँह टेढ़ा", "मुंह टेढ़ा", "चेहरा टेढ़ा", "bol nahi pa", "bol nahi sakta",
        "bol nahi sakti", "बोल नहीं पा", "बोल नहीं सक", "cannot speak", "can't speak", "unable to speak",
        "weakness on one side", "one sided weakness", "lakwa maar", "aadha sharir", "आधा शरीर", "लकवा मार",
    ],
    "poison": ["zeher", "poisoned", "zeher de", "जहर दे", "ज़हर दे", "overdose", "over dose", "too many pills", "too many tablets", "कीटनाशक पी"],
    "electric_shock": [
        "electric shock", "electrocuted", "electrocution", "got a shock", "bijli ka jhatka", "current laga",
        "current lag", "करंट लग", "बिजली का झटका",
    ],
    "severe_burn": [
        "gas cylinder phat", "cylinder blast", "cylinder phat", "सिलेंडर फट", "जल गई", "जल गयी",
        "burned badly", "burnt badly", "burns badly", "burned severely", "burnt severely", "skin peeling",
        "skin is peeling", "skin coming off", "skin came off", "scalded", "bahut jal gaya", "jhulas", "झुलस",
    ],
    "drowning": ["drowning", "drowned", "pani me dub", "paani me dub", "पानी में डूब"],
    "scorpion_sting": ["scorpion sting", "scorpion stung", "bichhu ne", "bichhu kaat", "बिच्छू ने", "बिच्छू काट"],
    "suicide": [
        "disappear forever", "want to disappear", "phansi laga", "fansi laga", "फांसी लग", "फाँसी लग",
        "done with life", "done with my life", "tired of life", "tired of my life", "sick of living",
        "can't go on", "cant go on", "cannot go on", "suicide note", "goodbye note", "no one would miss me",
        "nobody would miss me", "world is better without me", "naso kaat", "nason kaat", "nas kaat",
        "cut my wrist", "cut my wrists", "cut my veins", "नस काट", "jeena hi nahi", "jina hi nahi",
        "जीना ही नहीं", "जी नहीं सकता", "जी नहीं सकती",
        "killing myself", "going to kill myself", "ending it all", "end everything", "end this life",
        "not worth living", "no point in living", "no point living", "better off dead", "better off without me",
        "cutting myself", "hurting myself", "harming myself", "hang myself", "slit my wrist", "slit my wrists",
        "wish i was dead", "wish i were dead", "wish i could die", "thinking of dying",
        "mar jaun", "mar jau", "mar jaaun", "mar jana chahiye", "mar jaana chahiye", "mar jane ka mann",
        "jaan de dunga", "jaan de dungi", "jaan dena chahta", "jaan dena chahti", "apni jaan de", "apni jaan le",
        "khud ko khatam", "khudko khatam", "khud ko maar", "jeene ka koi fayda nahi", "jeene ka koi matlab nahi",
        "jeene ki ichha nahi", "jine ka koi fayda nahi", "zindagi se thak",
        "मर जाऊं", "मर जाऊँ", "मर जाना चाहिए", "जान दे दूँ", "जान देना चाहता", "जान लेना चाहता",
        "अपनी जान", "खुद को खत्म", "खुद को मार", "जीने का कोई फायदा नहीं", "जीने का कोई मतलब नहीं",
        "जीना नहीं चाहता", "जीना नहीं चाहती",
    ],
}

_POISON_NOUN = (
    r"(?:kerosene|phenyl|phenol|pesticides?|insecticides?|rat\s+poison|rat\s+killer|bleach|acid|harpic|petrol|diesel|"
    r"mitti\s+ka\s+tel|matti\s+ka\s+tel|zeher|zehar|zahar|jahar|ज़हर|जहर|कीटनाशक|फिनाइल|मिट्टी\s+का\s+तेल|तेजाब)"
)
_INGEST = (
    r"(?:drank|drink|drunk|swallow(?:ed)?|ate|eaten|consum(?:e|ed)|took|taken|"
    r"pi\s+liya|pee\s+liya|pi\s+li|pi\s+gaya|kha\s+liya|kha\s+li|khaya|piya|"
    r"पी\s+लिया|पी\s+ली|खा\s+लिया|खा\s+ली|पिया|खाया)"
)
_MANY_PILLS = (
    r"(?:too\s+many|a\s+lot\s+of|handful\s+of|whole\s+(?:strip|bottle)\s+of|bottle\s+of|strip\s+of|\d{2,}|"
    r"zyada|bahut\s+saari|saari|bahut\s+sari)\s+(?:\w+\s+){0,3}?"
    r"(?:pills?|tablets?|tabs?|capsules?|goliyan|goli|dawai|medicine)"
)
_BLEED = r"(?:bleed\w*|khoon|खून|blood|रक्त)"
_PREGNANT = r"(?:pregnan\w*|garbh\w*|गर्भ\w*|expecting)"
_SCORPION = r"(?:scorpions?|bichhu|bichchu|bichu|बिच्छू)"
_POISON_MORE = (
    r"(?:cleaning|cleaner|chemical|detergent|naphthalene|mothballs?|weed\s*killer|ant\s+killer|"
    r"keede\s+(?:maarne\s+)?ki\s+dawai|chuhe\s+(?:maarne\s+)?ki\s+dawai|कीड़े\s+मारने\s+की\s+दवा|"
    r"चूहे\s+(?:मारने\s+)?की\s+दवा|कीड़ेमार)"
)
_STING = r"(?:stung|sting|stings|bit|bite|kaat\w*|dank|डंक|काट\w*)"

_MORE_PATTERNS = {
    "stroke": [
        re.compile(r"(?<![a-z0-9])(?:can't|cant|cannot|unable\s+to)\s+(?:move|lift|feel)\s+(?:\w+\s+){0,2}(?:side|arm|leg|face|hand)"),
        re.compile(r"(?<![a-z0-9])(?:one|left|right)\s+side\s+(?:\w+\s+){0,2}(?:weak|numb|paraly\w+|not\s+working)"),
    ],
    "choking": [
        re.compile(r"(?<![a-z0-9])swallow(?:ed)?\s+(?:a\s+|an\s+|the\s+)?(?:\w+\s+){0,2}(?:coin|button|battery|batteries|magnet|needle|pin|marble|bead)"),
    ],
    "chest_pain": [
        re.compile(r"(?<![a-z0-9])dard\s+(?:\w+\s+){0,3}(?:seene|seena|sine|chhati|chhaati)\s*(?:me|mein|main)?"),
        re.compile(r"दर्द\s+(?:\S+\s+){0,3}(?:सीने|छाती)"),
    ],
    "injury": [
        re.compile(r"(?<![a-z0-9])fell\s+(?:down\s+)?from\s+(?:the\s+|a\s+)?(?:roof|terrace|height|tree|stairs|building|bike|truck)"),
    ],
    "breathing": [
        re.compile(r"(?<![a-z0-9])(?:can't|cant|cannot|can\s+not|couldn't|unable\s+to|not\s+able\s+to)\s+breathe"),
        re.compile(r"(?<![a-z0-9])(?:saans|sans|saas)\s+lene\s+(?:me|mein|main)?\s*(?:\w+\s+){0,2}(?:dikkat|takleef|taklif|mushkil)"),
        re.compile(r"(?:सांस|साँस)\s+लेने\s+में\s+(?:\S+\s+){0,2}(?:दिक्कत|तकलीफ|परेशानी|मुश्किल)"),
    ],
    "bleeding": [
        re.compile(r"(?<![a-z0-9])(?:a\s+lot\s+of|too\s+much|lots\s+of)\s+blood"),
        re.compile(r"(?<![a-z0-9])blood\s+(?:won't|will\s+not|is\s+not|isn't|not)\s+(?:stop|stopping|clot)"),
        re.compile(r"(?<![a-z0-9])bahut\s+(?:sara\s+|zyada\s+)?khoon\s+(?:beh|bah|nikal|aa|gir)"),
        re.compile(r"(?<![a-z0-9])khoon\s+(?:ruk|rukk)"),
        re.compile(r"खून\s+(?:बहुत|रुक)"),
        re.compile(r"बहुत\s+(?:सारा\s+)?खून"),
    ],
    "poison": [
        re.compile(rf"{_ASCII_WORD}{_INGEST}{_GAP}\s+{_POISON_MORE}"),
        re.compile(rf"{_POISON_MORE}{_GAP}\s+{_INGEST}"),
        re.compile(rf"{_ASCII_WORD}{_INGEST}{_GAP}\s+{_POISON_NOUN}"),
        re.compile(rf"{_ASCII_WORD}{_POISON_NOUN}{_GAP}\s+{_INGEST}"),
        re.compile(rf"{_ASCII_WORD}{_INGEST}\s+(?:\w+\s+){{0,2}}{_MANY_PILLS}"),
        re.compile(rf"{_ASCII_WORD}{_MANY_PILLS}"),
    ],
    "unconscious": [
        re.compile(r"(?<![a-z0-9])not\s+moving(?![^.!?]*(?:\bmuch\b|\bsleeping\b|breathing\s+fine|\bfine\b|\bok\b|\bokay\b))"),
    ],
    "severe_burn": [
        re.compile(r"(?<![a-z0-9])(?:ladki|ladka|bacha|bachha|bachcha|bachchi|woh|wo|usko|use|papa|mummy|maa|beta|beti|patni|pati|bhai|behen)\s+(?:\w+\s+){0,2}jal\s+(?:gaya|gayi|gaye)"),
        re.compile(r"(?<![a-z0-9])(?:burn(?:ed|t|s)?|scald(?:ed)?)\s*(?:\w+\s+){0,2}(?:badly|severely|seriously)"),
        re.compile(r"(?<![a-z0-9])(?:boiling|hot)\s+(?:water|oil|milk|tea)\s+(?:fell|spilled|poured|splashed)"),
    ],
    "scorpion_sting": [
        re.compile(rf"{_ASCII_WORD}{_SCORPION}{_GAP}\s+{_STING}"),
        re.compile(rf"{_ASCII_WORD}{_STING}{_GAP}\s+{_SCORPION}"),
    ],
    "pregnancy_bleed": [
        re.compile(rf"{_ASCII_WORD}{_PREGNANT}{_GAP}\s+{_BLEED}"),
        re.compile(rf"{_ASCII_WORD}{_BLEED}{_GAP}\s+{_PREGNANT}"),
    ],
    "suicide": [
        re.compile(r"(?<![a-z0-9])(?:don't|dont|no|any)\s+(?:see\s+)?(?:any\s+)?reason\s+to\s+(?:keep\s+going|live|go\s+on|continue)"),
        re.compile(r"(?<![a-z0-9])(?:pills?|tablets?|medicine|dawai|goliyan|goli)\s+(?:\w+\s+){0,3}(?:on\s+purpose|deliberately|jaan\s+bujh\s+kar)"),
        re.compile(r"(?<![a-z0-9])(?:jump|jumping|jumped)\s+(?:off|from|in\s+front\s+of)\s+(?:the\s+|a\s+)?(?:bridge|roof|building|terrace|cliff|balcony|train|bus)"),
        re.compile(r"(?<![a-z0-9])better\s+off\s+if\s+i\s+(?:die|was\s+dead|were\s+dead|weren't\s+here|wasn't\s+here)"),
        re.compile(r"(?<![a-z0-9])(?:cut|cutting)\s+my\s+(?:arms?|wrists?|veins?|legs?|thighs?)"),
        re.compile(r"(?<![a-z0-9])(?:done\s+with|tired\s+of|sick\s+of)\s+(?:my\s+)?(?:life|living)"),
        re.compile(r"(?<![a-z0-9])(?:will|going\s+to|gonna)\s+end\s+it"),
        re.compile(r"(?<![a-z0-9])(?:jeena|jina|jeene)\s+(?:hi\s+|bhi\s+)?(?:nahi|nhi)\s+(?:hai|chahta|chahti|chahiye)"),
        re.compile(r"(?<![a-z0-9])(?:sab|sabkuch|sab\s+kuch)\s+khatam\s+kar"),
        re.compile(r"(?<![a-z0-9])khatam\s+kar\s+(?:\w+\s+){0,4}(?:zindagi|jindagi|jaan|life)"),
        re.compile(r"(?<![a-z0-9])(?:marna|mar\s+jana|mar\s+jaana|mar\s+jaun)\s+(?:hi\s+)?(?:theek|thik|behtar|accha|achha)"),
        re.compile(r"नहीं\s+जी\s+सक"),
        re.compile(r"सब\s+खत्म\s+कर"),
        re.compile(r"(?<![a-z0-9])(?:kill|killing|hurting|harming|hanging)\s+my\s*self"),
        re.compile(r"(?<![a-z0-9])(?:want|going|plan|planning|trying|try|wish|wanna|will)\s+(?:\w+\s+){0,2}(?:hurt|harm|cut|kill)\s+myself"),
        re.compile(r"(?<![a-z0-9])(?:want|wanna|wish|going|thinking|trying)\s+(?:\w+\s+){0,3}(?:die|dead)(?![a-z])"),
        re.compile(r"(?<![a-z0-9])end\s+(?:it\s+all|everything|my\s+life|this\s+life)"),
        re.compile(r"(?<![a-z0-9])better\s+off\s+(?:dead|without\s+me)"),
        re.compile(r"(?<![a-z0-9])(?:don't|dont|do\s+not|no\s+longer)\s+want\s+to\s+(?:be\s+alive|live|exist)"),
        re.compile(r"(?<![a-z0-9])(?:life|living)\s+(?:is\s+)?(?:not|isn't|no)\s+(?:worth|point)"),
        re.compile(r"(?<![a-z0-9])(?:mar|maar)\s+(?:jau|jaun|jaaun|jaoon|jaunga|jaungi|jana\s+chahiye|jaana\s+chahiye)"),
        re.compile(r"(?<![a-z0-9])(?:apni|apna)\s+(?:jaan|jan)\s+(?:de|dena|lena|le)"),
        re.compile(r"(?<![a-z0-9])(?:jaan|jan)\s+(?:de|dena|lena|le)\s*(?:dunga|dungi|du|lunga|lungi|chahta|chahti|chahiye)"),
        re.compile(r"(?<![a-z0-9])khud\s*ko\s+(?:khatam|maar|nuksan|nuksaan)"),
        re.compile(r"(?<![a-z0-9])(?:jeene|jine|jeena|jina)\s+(?:ka|ki)\s+(?:koi\s+)?(?:fayda|matlab|mann|man|ichha|iccha)\s+(?:nahi|nhi|nahin)"),
        re.compile(r"मर\s*जा(?:ऊं|ऊँ|उँगा|ऊंगा|ऊंगी|ना\s+चाहिए|ने\s+का)"),
        re.compile(r"जान\s+(?:दे|देना|लेना|ले)"),
        re.compile(r"खुद\s*को\s+(?:खत्म|मार|नुकसान)"),
        re.compile(r"जीने\s+का\s+(?:कोई\s+)?(?:फायदा|मतलब|मन)\s+नहीं"),
    ],
}

for _flag, _aliases in _MORE_RED_FLAGS.items():
    RED_FLAG_LEXICON.setdefault(_flag, []).extend(_aliases)
for _flag, _patterns in _MORE_PATTERNS.items():
    RED_FLAG_PATTERNS.setdefault(_flag, []).extend(_patterns)

DISEASE_ALIASES = {
    "dengue": ["dengue", "डेंगू", "dengu", "breakbone fever"],
    "malaria": ["malaria", "मलेरिया", "maleriya"],
    "typhoid": ["typhoid", "टाइफाइड", "enteric fever", "miyadi bukhar", "मियादी बुखार"],
    "cholera": ["cholera", "हैज़ा", "haiza", "हैजा"],
    "diarrhoea": ["diarrhoea", "diarrhea", "dast", "दस्त", "loose motion", "अतिसार"],
    "tuberculosis": ["tuberculosis", "tb", "टीबी", "क्षय रोग", "tapedik", "तपेदिक"],
    "hepatitis": ["hepatitis", "हेपेटाइटिस", "jaundice", "पीलिया", "peeliya"],
    "covid19": ["covid", "covid19", "covid-19", "कोविड", "corona", "कोरोना", "coronavirus"],
    "influenza": ["influenza", "flu", "फ्लू", "इन्फ्लूएंजा", "seasonal flu", "mausami bukhar"],
    "pneumonia": ["pneumonia", "निमोनिया", "nimonia"],
    "measles": ["measles", "खसरा", "khasra", "चेचक"],
    "rabies": ["rabies", "रेबीज़", "dog bite disease", "rabis"],
    "heatstroke": ["heatstroke", "heat stroke", "लू", "loo", "loot", "sun stroke", "हीट स्ट्रोक"],
    "anaemia": ["anaemia", "anemia", "एनीमिया", "khoon ki kami", "खून की कमी", "low hemoglobin", "low hb"],
}

VACCINE_ALIASES = {
    "bcg": ["bcg", "बीसीजी"],
    "hepb": ["hepatitis b", "hepatitis-b", "hep b", "हेपेटाइटिस बी"],
    "opv": ["polio", "polio drops", "polio ki boond", "opv", "पोलियो", "पोलियो ड्रॉप"],
    "pentavalent": ["pentavalent", "5 in 1", "पेंटावेलेंट", "dpt", "डीपीटी"],
    "rotavirus": ["rotavirus", "रोटावायरस", "rotavac"],
    "pcv": ["pcv", "pneumococcal", "nimonia ka tika", "pneumonia vaccine", "न्यूमोकोकल"],
    "ipv": ["ipv", "injectable polio", "आईपीवी"],
    "mr": ["mr vaccine", "mr ka tika", "measles vaccine", "khasra rubella", "rubella", "खसरा टीका", "measles rubella", "एमआर टीका", "खसरा रूबेला"],
    "je": ["je vaccine", "japanese encephalitis", "dimagi bukhar", "जापानी इंसेफेलाइटिस", "दिमागी बुखार"],
    "dpt_booster": ["dpt booster", "booster", "बूस्टर", "डीपीटी बूस्टर"],
    "td": ["td vaccine", "tetanus", "टिटनेस", "tt injection", "टीटी इंजेक्शन"],
    "covid_vaccine": ["covid vaccine", "corona vaccine", "covid ka tika", "corona ka tika", "corona tika", "covid tika", "कोविड टीका", "कोरोना टीका", "covidshield", "covaxin", "कोवैक्सिन"],
    "influenza_vaccine": ["flu vaccine", "influenza vaccine", "flu ka tika", "फ्लू टीका"],
}

# Words that show a message is about a vaccine. A vaccine name or a baby's age alone is not enough to answer with a
# vaccine card ("first symptoms of pregnancy" must not return the tetanus card).
VACCINE_WORD_RE = re.compile(
    r"\b(vaccin\w*|immuni[sz]\w*|tika\w*|teeka\w*|tike|injection|injectable|booster|drops?|boond\w*|jab|shots?)\b"
)
VACCINE_WORDS_DEVANAGARI = ("टीका", "टीके", "टीकाकरण", "इंजेक्शन", "बूस्टर", "ड्रॉप", "बूँद", "बूंद")


def has_vaccine_word(text):
    lower = text.lower()
    return bool(VACCINE_WORD_RE.search(lower)) or any(w in lower for w in VACCINE_WORDS_DEVANAGARI)


NEGATION_WORDS = ["no", "not", "nahi", "nhi", "nahin", "कोई नहीं", "नहीं", "without", "koi nahi", "nahi hai"]


# Phrases that contain a red-flag word but are information topics, not emergencies.
RED_FLAG_CONTEXT_STRIPS = ("food poisoning",)

_SUFFIX_RE = re.compile(r"(?:s|es|ed|d|ing)(?![a-z0-9])")


def _ascii_alnum(ch):
    return ch.isascii() and ch.isalnum()


def _letter_like(ch):
    return unicodedata.category(ch)[0] in ("L", "M", "N")


def find_alias(text_lower, alias):
    """Return the index of `alias` in `text_lower` as a standalone term, or -1.

    English and Hinglish (ASCII) aliases must not touch an ASCII letter or digit, so "tb" does not match
    inside "outbreak", "fits" not inside "benefits" and "flu" not inside "influence". Aliases of five or more
    letters may take a plural or verb ending ("headaches", "coughing"). Very short non-ASCII aliases must not
    touch any letter or combining mark. Longer non-ASCII aliases keep plain substring matching, because
    Devanagari word forms are inflected and Python's word-boundary rules do not handle vowel marks.
    """
    ascii_alias = alias.isascii()
    if not ascii_alias and len(alias) > 3:
        return text_lower.find(alias)
    touches = _ascii_alnum if ascii_alias else _letter_like
    pos = text_lower.find(alias)
    while pos != -1:
        before = text_lower[pos - 1] if pos > 0 else ""
        rest = text_lower[pos + len(alias):]
        after = rest[:1]
        left_ok = not (before and touches(before))
        right_ok = not (after and touches(after))
        if not right_ok and ascii_alias and len(alias) >= 5 and _SUFFIX_RE.match(rest):
            right_ok = True
        if left_ok and right_ok:
            return pos
        pos = text_lower.find(alias, pos + 1)
    return -1


def contains_alias(text_lower, alias):
    return find_alias(text_lower, alias) != -1


# A question about how much or how often to take a medicine needs both a medicine word and a dose cue.
# Naming only a medicine ("is paracetamol used for dengue?") is not a dose question.
MEDICINE_TERMS = [
    "paracetamol", "acetaminophen", "crocin", "dolo", "calpol", "ibuprofen", "brufen", "aspirin", "disprin",
    "combiflam", "diclofenac", "antibiotic", "amoxicillin", "azithromycin", "cetirizine",
    "tablet", "pill", "capsule", "syrup", "medicine", "medication",
    "dawa", "dawai", "goli",
    "पैरासिटामोल", "दवा", "दवाई", "गोली", "टैबलेट", "सिरप",
]
DOSE_CUES = [
    "dose", "dosage", "overdose", "how many", "how much", "how often", "times a day", "times per day",
    "per day", "a day", "daily", "maximum", "max", "mg",
    "kitni baar", "kitna", "kitne", "kitni", "khurak", "din mein", "din me",
    "खुराक", "मात्रा", "कितनी", "कितना", "कितने", "दिन में", "बार",
]


def is_dose_question(text):
    text_lower = text.lower()
    return any(contains_alias(text_lower, m) for m in MEDICINE_TERMS) and any(
        contains_alias(text_lower, c) for c in DOSE_CUES
    )


def _is_negated(text_lower, pos):
    prefix = text_lower[max(0, pos - 30) : pos]
    words = prefix.replace(",", " ").replace(".", " ").split()
    return any(w in NEGATION_WORDS for w in words[-4:])


def find_symptoms(text):
    text_lower = text.lower()
    found = []
    for symptom, aliases in SYMPTOM_LEXICON.items():
        for alias in aliases:
            pos = find_alias(text_lower, alias)
            if pos != -1 and not _is_negated(text_lower, pos):
                found.append(symptom)
                break
    return found


# A denial right next to the symptom ("no chest pain", "not having chest pain", "chest pain nahi hai"). Only this
# tight form counts. A loose negation anywhere earlier in the sentence ("she is not well and bleeding heavily") must
# not hide an emergency, so it is not used.
_DENIED_BEFORE = re.compile(
    r"(?:\bno|\bnot(?:\s+(?:having|facing|feeling|got|any))?|\bwithout|\bdon'?t\s+have|\bdoesn'?t\s+have|"
    r"\bnever\s+had|\bnahi\s+hai)\s*$"
)
_DENIED_AFTER = re.compile(r"^\s*(?:nahi|nahin|nhi|नहीं)\b")

# Wording of a question ABOUT a topic ("how to prevent a heart attack", "stroke kya hota hai"), not a report.
_INFO_CUE = re.compile(
    r"(?:\bhow\s+(?:to|can\s+i|do\s+i|can\s+we|do\s+we)\s+(?:prevent|avoid|reduce|lower)|\bways\s+to\s+(?:prevent|avoid)|"
    r"\btips\s+(?:to|for)|\bprevention|\bpreventing|\bavoid(?:ing)?\b|\bwhat\s+(?:is|are|causes?|does)\b|"
    r"\b(?:symptoms|signs|causes|risk\s+factors|treatment)\s+of\b|\bdifference\s+between|\btell\s+me\s+about|"
    r"\bexplain\b|\binformation\s+(?:on|about)|\bmeaning\s+of|\bdiet\b|\bexercise|\bwhich\s+vaccine|\bvaccin|"
    r"\bhelpline|\bis\s+[\w\s]{1,25}?\s+(?:common|dangerous|serious|contagious)\b|\bwhy\s+(?:does|do)\b|"
    r"\bwarning\s+signs|\bhow\s+(?:does|is|are|common|many|often)\b|"
    r"\bhow\s+do\s+(?:doctors|people|they|you|we)\b|\bcan\s+(?:children|kids|people|women|men|babies|adults)\s+(?:get|have|catch)\b|"
    r"\bdoes\s+\w+\s+(?:cause|increase|raise|lead\s+to|affect)\b|\b(?:risk|chances?)\s+of\b|"
    r"lagte\s+hain|lagta\s+hai|lagti\s+hai|\bkaun\s+(?:kaun\s+)?(?:se|sa|si)\b|"
    r"\bcan\s+(?:a\s+|an\s+)?\w+\s+be\s+(?:cured|treated|prevented|avoided)|"
    r"\bis\s+[\w\s]{1,30}?\s+(?:treatable|curable|preventable|fatal)\b|"
    r"\bkya\s+[\w\s]{0,40}?(?:hota|hoti|hote|aata|aati|aate|sakta|sakti|hai)\b|"
    r"kya\s+hota\s+hai|kya\s+hai\b|kya\s+hote|kaise\s+bach|bachne\s+ke|bachav|bachaav|ke\s+lakshan|lakshan|karan\b|"
    r"ke\s+baad\s+kya|kya\s+khana|kab\s+lagta|teeka|\btika\b|\bbatao\b|\bbataiye\b|jaankari|"
    r"क्या\s+होता|क्या\s+है|कैसे\s+बच|बचाव|बचने|के\s+लक्षण|लक्षण|कारण|के\s+बाद\s+क्या|क्या\s+खाना|टीका|जानकारी|"
    r"बताइए|बताओ)"
)
# Something that is happening now or just happened. Any of these keeps the emergency reply.
_NOW_CUE = re.compile(
    r"(?:\bjust\b|\bnow\b|\bright\s+now|\babhi\b|\bturant\b|\bjaldi\b|please\s+help|help\s+me|\bhelp!|\burgent|"
    r"\bemergency\b|\basap\b|\bis\s+(?:not|n't)\b|\bisn't\b|\bnot\s+(?:moving|responding|breathing|waking|talking|speaking)|"
    r"\bstill\b|ho\s+raha|ho\s+rahi|ho\s+rahe|ho\s+gaya|ho\s+gayi|aa\s+raha|aa\s+rahi|nahi\s+(?:aa|le|ho)|"
    r"हो\s+रहा|हो\s+रही|हो\s+गया|हो\s+गई|हो\s+गयी|अभी|तुरंत|जल्दी|बचाओ|मदद|\bbachao\b|\bmadad\b)"
)
# The message is about someone in particular. Used with a past cue below.
_PERSON_CUE = re.compile(
    r"(?:\bmy\b|\bhe\b|\bshe\b|\bhis\b|\bher\b|\bhim\b|\bthey\b|\bbaby\b|\bchild\b|\bson\b|\bdaughter\b|\bwife\b|"
    r"\bhusband\b|\bfather\b|\bmother\b|\bdad\b|\bmom\b|\bbrother\b|\bsister\b|\bfriend\b|\bpapa\b|\bmaa\b|"
    r"\bmummy\b|\bbhai\b|\bbehen\b|\bbachcha\b|\bbachche\b|\bbacche\b|\bmujhe\b|\bmere\b|\bmeri\b|\bmera\b|"
    r"\bunko\b|\busko\b|\buski\b|मुझे|मेरे|मेरी|उन्हें|पापा|माँ|बच्चा|बच्चे)"
)
_PAST_CUE = re.compile(
    r"(?:\bago\b|last\s+(?:year|month|summer|winter|week)|\bin\s+the\s+past|\bpreviously|\bhad\s+an?\b|"
    r"saal\s+pehle|pichle\s+saal|साल\s+पहले|पिछले\s+साल)"
)


def _is_information_question(text_lower):
    """True for a question about a topic (no emergency reply), False for a report of something happening.

    Fails safe: an information wording only wins when nothing says it is happening now, and when the message names a
    person ("my father") it needs a past cue as well ("two years ago").
    """
    if not _INFO_CUE.search(text_lower) or _NOW_CUE.search(text_lower):
        return False
    return bool(_PAST_CUE.search(text_lower)) or not _PERSON_CUE.search(text_lower)


def _first_match(text_lower, flag):
    """Position (start, end) of the first non-denied match for `flag`, or None."""
    spans = []
    for alias in RED_FLAG_LEXICON[flag]:
        pos = find_alias(text_lower, alias)
        if pos != -1:
            spans.append((pos, pos + len(alias)))
    for pattern in RED_FLAG_PATTERNS.get(flag, ()):
        match = pattern.search(text_lower)
        if match:
            spans.append((match.start(), match.end()))
    for start, end in sorted(spans):
        if _DENIED_BEFORE.search(text_lower[:start]) or _DENIED_AFTER.match(text_lower[end:]):
            continue
        return start, end
    return None


def find_red_flags(text):
    text_lower = text.lower().replace("’", "'").replace("‘", "'")
    for phrase in RED_FLAG_CONTEXT_STRIPS:
        text_lower = text_lower.replace(phrase, " ")
    flags = [flag for flag in RED_FLAG_LEXICON if _first_match(text_lower, flag)]
    # Self-harm is never treated as an information question: the helpline is the right reply either way.
    if flags and "suicide" not in flags and _is_information_question(text_lower):
        return []
    return flags


def find_disease(text):
    text_lower = text.lower()
    for disease, aliases in DISEASE_ALIASES.items():
        for alias in aliases:
            if contains_alias(text_lower, alias):
                return disease
    return None


def find_vaccine(text):
    """The vaccine whose longest alias appears in the text ("dpt booster" beats "dpt")."""
    text_lower = text.lower()
    best, best_len = None, 0
    for vaccine, aliases in VACCINE_ALIASES.items():
        for alias in aliases:
            if len(alias) > best_len and contains_alias(text_lower, alias):
                best, best_len = vaccine, len(alias)
    return best
