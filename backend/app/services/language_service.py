"""Language Service — Schemora Universal Multilingual Layer.

Provides modular, pluggable language detection, script matching, localization,
and internal retrieval translation.

Design Goal:
  Allows adding any supported language (22+ Indic & Global languages) simply by
  registering a new LanguageSpec in the SUPPORTED_LANGUAGES registry without modifying
  the core RAG pipeline, vector search engine, or database models.
"""

import re
import logging
from dataclasses import dataclass
from typing import Dict, Any, Optional, List, Tuple

logger = logging.getLogger("schemora.language_service")


@dataclass
class LanguageSpec:
    code: str                  # ISO 639-1 code (e.g. 'hi', 'gu', 'mr', 'bn', 'ta', 'te')
    name: str                  # English name ('Hindi', 'Gujarati')
    native_name: str           # Native script name ('हिंदी', 'ગુજરાતી')
    script_regex: Optional[str] = None # Regex matching script character range
    greeting_msg: str = ""
    thanks_msg: str = ""
    goodbye_msg: str = "Goodbye! 👋 Have a great day ahead!"
    not_found_msg: str = ""
    out_of_scope_msg: str = ""
    header_intro: str = ""
    apply_label: str = ""
    support_title: str = ""


# ── Pluggable Language Registry ──────────────────────────────────────────────

DEFAULT_EN = LanguageSpec(
    code="en",
    name="English",
    native_name="English",
    script_regex=r"^[A-Za-z0-9\s\.\,\?\!\-\'\"]+$",
    greeting_msg="Hello! 👋 I am your Schemora AI Assistant. Ask me any question regarding central or state government schemes, scholarships, eligibility, or application guidelines!",
    thanks_msg="You're welcome! 😊 Feel free to ask if you have any more questions about government schemes or scholarships.",
    goodbye_msg="Goodbye! 👋 Have a great day ahead. Feel free to ask whenever you need information on government schemes or scholarships!",
    not_found_msg="I couldn't find verified information for this in the current Schemora knowledge base. Please check the official government portal.",
    out_of_scope_msg="I am Schemora's dedicated Government Scheme Assistant. I can only answer questions about central/state government schemes, scholarships, internships, and educational welfare benefits.",
    header_intro="Here are the top verified government schemes matching your request:",
    apply_label="Apply Online",
    support_title="💡 **Related Support Questions (tap to ask)**:",
)

DEFAULT_HI = LanguageSpec(
    code="hi",
    name="Hindi",
    native_name="हिंदी",
    script_regex=r"[\u0900-\u097F]",
    greeting_msg="नमस्ते! 🙏 मैं स्केमोरा AI सहायक हूँ। आप मुझसे केंद्र या राज्य सरकार की योजनाओं, छात्रवृत्ति, पात्रता नियमों या आवेदन प्रक्रिया के बारे में कोई भी प्रश्न पूछ सकते हैं!",
    thanks_msg="आपका स्वागत है! 😊 यदि आपके पास सरकारी योजनाओं या छात्रवृत्ति के बारे में कोई और प्रश्न हैं, तो निसंकोच पूछें।",
    goodbye_msg="अलविदा! 👋 आपका दिन शुभ हो। सरकारी योजनाओं के बारे में जानकारी के लिए कभी भी पूछ सकते हैं!",
    not_found_msg="इस प्रश्न के लिए हमारे वर्तमान ज्ञान आधार में पर्याप्त सत्यापित जानकारी नहीं मिली। कृपया आधिकारिक सरकारी पोर्टल देखें।",
    out_of_scope_msg="मैं स्केमोरा का समर्पित सरकारी योजना सहायक हूँ। मैं केवल केंद्र और राज्य सरकार की योजनाओं, छात्रवृत्ति और शैक्षणिक लाभों से संबंधित प्रश्नों का उत्तर देता हूँ।",
    header_intro="यहाँ आपके अनुरोध से संबंधित शीर्ष सत्यापित सरकारी योजनाएं हैं:",
    apply_label="आवेदन करें",
    support_title="💡 **संबंधित प्रश्न (पूछने के लिए टैप करें)**:",
)

DEFAULT_GU = LanguageSpec(
    code="gu",
    name="Gujarati",
    native_name="ગુજરાતી",
    script_regex=r"[\u0A80-\u0AFF]",
    greeting_msg="નમસ્તે! 🙏 હું તમારો સ્કીમોરા AI સહાયક છું. કેન્દ્ર અથવા રાજ્ય સરકારની યોજનાઓ, શિષ્યવૃત્તિ, પાત્રતા અથવા અરજી પ્રક્રિયા વિશે મને પૂછો!",
    thanks_msg="તમારું સ્વાગત છે! 😊 જો તમારી પાસે સરકારી યોજનાઓ અથવા શિષ્યવૃત્તિ વિશે વધુ પ્રશ્નો હોય, તો નિઃસંકોચ પૂછો.",
    goodbye_msg="આવજો! 👋 તમારો દિવસ શુભ રહે. સરકારી યોજનાઓ વિશે પૂછવા માટે ક્યારેય પણ સંપર્ક કરી શકો છો!",
    not_found_msg="આ પ્રશ્ન માટે વર્તમાન નોલેજ બેઝમાં પૂરતી ખાતરીપૂર્વકની માહિતી મળી નથી. કૃપા કરીને સત્તાવાર સરકારી પોર્ટલ જુઓ.",
    out_of_scope_msg="હું સ્કીમોરાનો સમર્પિત સરકારી યોજના સહાયક છું. હું ફક્ત કેન્દ્ર અને રાજ્ય સરકારની યોજનાઓ, શિષ્યવૃત્તિઓ અને શૈક્ષણિક લાભો વિશે જ પ્રશ્નોના જવાબ આપું છું.",
    header_intro="તમારી વિનંતી સંબંધિત મુખ્ય ખાતરીપૂર્વકની સરકારી યોજનાઓ અહીં છે:",
    apply_label="ઓનલાઈન અરજી કરો",
    support_title="💡 **સંબંધિત પ્રશ્નો (પૂછવા માટે ટેપ કરો)**:",
)

DEFAULT_MR = LanguageSpec(
    code="mr",
    name="Marathi",
    native_name="मराठी",
    script_regex=r"[\u0900-\u097F]", # Shares Devanagari script range
    greeting_msg="नमस्कार! 🙏 मी स्केमोरा AI सहाय्यक आहे. तुम्ही मला केंद्र किंवा राज्य सरकारच्या योजना, शिष्यवृत्ती, पात्रता किंवा अर्ज प्रक्रियेबद्दल कोणताही प्रश्न विचारू शकता!",
    thanks_msg="तुमचे स्वागत आहे! 😊 जर तुम्हाला सरकारी योजनांबद्दल आणखी काही प्रश्न असतील तर नक्की विचारारा.",
    goodbye_msg="फिर भेटू! 👋 तुमचा दिवस आनंदाचा जावो. सरकारी योजनांबद्दल विचारण्यासाठी कधीही संपर्क करा!",
    not_found_msg="या प्रश्नासाठी आमच्या सध्याच्या ज्ञान आधारात पुरेशी सत्यापित माहिती आढळली नाही. कृपया अधिकृत सरकारी पोर्टल पहा.",
    out_of_scope_msg="मी स्केमोराचा शैक्षणिक योजना सहाय्यक आहे. मी फक्त केंद्र आणि राज्य सरकारी योजना, शिष्यवृत्ती आणि शैक्षणिक लाभांशी संबंधित प्रश्नांची उत्तरे देतो.",
    header_intro="तुमच्या विनंतीशी संबंधित शीर्ष अधिकृत सरकारी योजना खालीलप्रमाणे आहेत:",
    apply_label="अर्ज करा",
    support_title="💡 **संबंधित प्रश्न (विचारण्यासाठी टॅप करा)**:",
)

DEFAULT_BN = LanguageSpec(
    code="bn",
    name="Bengali",
    native_name="বাংলা",
    script_regex=r"[\u0980-\u09FF]",
    greeting_msg="নমস্কার! 🙏 আমি স্কেমোরা AI সহকারী। আপনি আমাকে সরকারি প্রকল্প, স্কলারশিপ, যোগ্যতা বা আবেদন প্রক্রিয়া সম্পর্কে যেকোনো প্রশ্ন জিজ্ঞাসা করতে পারেন!",
    thanks_msg="আপনাকে স্বাগতম! 😊 সরকারি প্রকল্প বা স্কলারশিপ সম্পর্কে আরও কোনো প্রশ্ন থাকলে নির্দ্বিধায় জিজ্ঞাসা করুন।",
    goodbye_msg="বিদায়! 👋 আপনার দিনটি ভালো কাটুক। সরকারি প্রকল্প সম্পর্কে জানতে যেকোনো সময় জিজ্ঞাসা করতে পারেন!",
    not_found_msg="এই প্রশ্নের জন্য আমাদের বর্তমান জ্ঞান ভাণ্ডারে যথেষ্ট তথ্য পাওয়া যায়নি। অনুগ্রহ করে অফিসিয়াল সরকারি পোর্টাল দেখুন।",
    out_of_scope_msg="আমি স্কেমোরার সরকারি প্রকল্প সহকারী। আমি কেবল সরকারি প্রকল্প, স্কলারশিপ এবং শিক্ষাগত সুবিধা সম্পর্কিত প্রশ্নের উত্তর দিতে পারি।",
    header_intro="এখানে আপনার অনুরোধের সাথে সম্পর্কিত শীর্ষ সরকারি প্রকল্পগুলি রয়েছে:",
    apply_label="অনলাইনে আবেদন করুন",
    support_title="💡 **সম্পর্কিত প্রশ্ন (জিজ্ঞাসা করতে ট্যাপ করুন)**:",
)

DEFAULT_TA = LanguageSpec(
    code="ta",
    name="Tamil",
    native_name="தமிழ்",
    script_regex=r"[\u0B80-\u0BFF]",
    greeting_msg="வணக்கம்! 🙏 நான் ஸ்கீமோரா AI உதவியாளர். அரசு திட்டங்கள், உதவித்தொகை, தகுதி பற்றி என்னிடம் கேளுங்கள்!",
    thanks_msg="உங்களை வரவேற்கிறோம்! 😊 அரசு திட்டங்கள் பற்றி ஏதேனும் கேள்விகள் இருந்தால் தாராளமாகக் கேட்கலாம்.",
    goodbye_msg="விடைபெறுகிறேன்! 👋 இனிய நாளாக அமையட்டும்!",
    not_found_msg="இந்தக் கேள்விக்கு போதுமான தகவல் கிடைக்கவில்லை. அரசு இணையதளத்தைப் பார்க்கவும்.",
    out_of_scope_msg="நான் அரசு திட்டங்கள் பற்றிய கேள்விகளுக்கு மட்டுமே பதிலளிப்பேன்.",
    header_intro="உங்கள் கோரிக்கைக்கு இணையான சிறந்த அரசு திட்டங்கள் இதோ:",
    apply_label="விண்ணப்பிக்கவும்",
    support_title="💡 **தொடர்புடைய கேள்விகள் (கேட்க தட்டவும்)**:",
)

DEFAULT_TE = LanguageSpec(
    code="te",
    name="Telugu",
    native_name="తెలుగు",
    script_regex=r"[\u0C00-\u0C7F]",
    greeting_msg="నమస్కారం! 🙏 నేను స్కీమోరా AI సహాయకుడిని. ప్రభుత్వ పథకాలు, స్కాలర్‌షిప్‌లు, అర్హత గురించి నన్ను ఏమైనా అడగండి!",
    thanks_msg="మీకు స్వాగతం! 😊 ప్రభుత్వ పథకాల గురించి మరిన్ని ప్రశ్నలు ఉంటే నిరభ్యంతరంగా అడగండి.",
    goodbye_msg="సెలవు! 👋 ఈ రోజు మీకు శుభప్రదంగా ఉండాలని కోరుకుంటున్నాము!",
    not_found_msg="ఈ ప్రశ్నకు సంబంధించిన సమాచారం కనుగొనబడలేదు. దయచేసి అధికారిక ప్రభుత్వ పోర్టల్ చూడండి.",
    out_of_scope_msg="నేను ప్రభుత్వ పథకాల గురించి మాత్రమే సమాచారం ఇస్తాను.",
    header_intro="మీ అభ్యర్థనకు సంబంధించిన అగ్ర ప్రభుత్వ పథకాలు ఇక్కడ ఉన్నాయి:",
    apply_label="దరఖాస్తు చేయండి",
    support_title="💡 **సంబంధిత ప్రశ్నలు (అడగడానికి నొక్కండి)**:",
)

DEFAULT_KN = LanguageSpec(
    code="kn",
    name="Kannada",
    native_name="ಕನ್ನಡ",
    script_regex=r"[\u0C80-\u0CFF]",
    greeting_msg="ನಮಸ್ಕಾರ! 🙏 ನಾನು ಸ್ಕೀಮೋರಾ AI ಸಹಾಯಕ. ಸರ್ಕಾರಿ ಯೋಜನೆಗಳು, ವಿದ್ಯಾರ್ಥಿವೇತನ, ಅರ್ಹತೆ ಕುರಿತು ನನ್ನನ್ನು ಕೇಳಿ!",
    thanks_msg="ನಿಮಗೆ ಸ್ವಾಗತ! 😊 ಸರ್ಕಾರಿ ಯೋಜನೆಗಳ ಕುರಿತು ಯಾವುದೇ ಹೆಚ್ಚಿನ ಪ್ರಶ್ನೆಗಳಿದ್ದರೆ ಉಚಿತವಾಗಿ ಕೇಳಿ.",
    goodbye_msg="ನಿರ್ಗಮನ! 👋 ನಿಮ್ಮ ದಿನ ಶುಭವಾಗಿರಲಿ!",
    not_found_msg="ಈ ಪ್ರಶ್ನೆಗೆ ಸಂಬಂಧಿಸಿದ ಮಾಹಿತಿ ಲಭ್ಯವಿಲ್ಲ. ದಯವಿಟ್ಟು ಅಧಿಕೃತ ಸರ್ಕಾರಿ ಪೋರ್ಟಲ್ ನೋಡಿ.",
    out_of_scope_msg="ನಾನು ಸರ್ಕಾರಿ ಯೋಜನೆಗಳ ಬಗ್ಗೆ ಮಾತ್ರ ಮಾಹಿತಿ ನೀಡಬಲ್ಲೆ.",
    header_intro="ನಿಮ್ಮ ವಿನಂತಿಗೆ ಸಂಬಂಧಿಸಿದ ಉನ್ನತ ಸರ್ಕಾರಿ ಯೋಜನೆಗಳು ಇಲ್ಲಿವೆ:",
    apply_label="ಅರ್ಜಿ ಸಲ್ಲಿಸಿ",
    support_title="💡 **ಸಂಬಂಧಿತ ಪ್ರಶ್ನೆಗಳು (ಕೇಳಲು ಟ್ಯಾಪ್ ಮಾಡಿ)**:",
)

DEFAULT_ML = LanguageSpec(
    code="ml",
    name="Malayalam",
    native_name="മലയാളം",
    script_regex=r"[\u0D00-\u0D7F]",
    greeting_msg="നമസ്കാരം! 🙏 ഞാൻ സ്കീമോറ AI സഹായകനാണ്. സർക്കാർ പദ്ധതികൾ, സ്കോളർഷിപ്പ്, അർഹത എന്നിവയെക്കുറിച്ച് എന്നോട് ചോദിക്കൂ!",
    thanks_msg="തീർച്ചയായും സ്വാഗതം! 😊 സർക്കാർ പദ്ധതികളെക്കുറിച്ചോ കൂടുതൽ ചോദ്യങ്ങളുണ്ടെങ്കിൽ ചോദിക്കാവുന്നതാണ്.",
    goodbye_msg="വിട! 👋 നല്ലൊരു ദിവസം ആശംസിക്കുന്നു!",
    not_found_msg="ഈ ചോദ്യത്തിന് ആവശ്യമായ വിവരങ്ങൾ കണ്ടെത്തിയില്ല. ഔദ്യോഗിക സർക്കാർ പോർട്ടൽ പരിശോധിക്കൂ.",
    out_of_scope_msg="ഞാൻ സർക്കാർ പദ്ധതികളെ കുറിച്ചുള്ള ചോദ്യങ്ങൾക്ക് മാത്രം ഉത്തരം നൽകുന്നു.",
    header_intro="നിങ്ങളുടെ ആവശ്യത്തിന് അനുയോജ്യമായ പ്രധാന സർക്കാർ പദ്ധതികൾ താഴെ നൽകുന്നു:",
    apply_label="അപേക്ഷിക്കൂ",
    support_title="💡 **ബന്ധപ്പെട്ട ചോദ്യങ്ങൾ (ചോദിക്കാൻ ടാപ്പ് ചെയ്യുക)**:",
)

DEFAULT_PA = LanguageSpec(
    code="pa",
    name="Punjabi",
    native_name="ਪੰਜਾਬੀ",
    script_regex=r"[\u0A00-\u0A7F]",
    greeting_msg="ਸਤਿ ਸ੍ਰੀ ਅਕਾਲ! 🙏 ਮੈਂ ਸਕੀਮੋਰਾ AI ਸਹਾਇਕ ਹਾਂ। ਕੇਂਦਰ ਜਾਂ ਰਾਜ ਸਰਕਾਰ ਦੀਆਂ ਯੋਜਨਾਵਾਂ, ਸਕਾਲਰਸ਼ਿਪ, ਯੋਗਤਾ ਬਾਰੇ ਮੈਨੂੰ ਪੁੱਛੋ!",
    thanks_msg="ਤੁਹਾਡਾ ਸੁਆਗਤ ਹੈ! 😊 ਜੇਕਰ ਤੁਹਾਡੇ ਕੋਲ ਸਰਕਾਰੀ ਯੋਜਨਾਵਾਂ ਬਾਰੇ ਹੋਰ ਸਵਾਲ ਹਨ, ਤਾਂ ਬੇਝਿਜਕ ਪੁੱਛੋ।",
    goodbye_msg="ਅਲਵਿਦਾ! 👋 ਤੁਹਾਡਾ ਦਿਨ ਵਧੀਆ ਰਹੇ!",
    not_found_msg="ਇਸ ਸਵਾਲ ਲਈ ਕਾਫ਼ੀ ਜਾਣਕਾਰੀ ਨਹੀਂ ਮਿਲੀ। ਕਿਰਪਾ ਕਰਕੇ ਸਰਕਾਰੀ ਪੋਰਟਲ ਵੇਖੋ।",
    out_of_scope_msg="ਮੈਂ ਸਿਰਫ਼ ਸਰਕਾਰੀ ਯੋਜਨਾਵਾਂ ਬਾਰੇ ਸਵਾਲਾਂ ਦੇ ਜਵਾਬ ਦਿੰਦਾ ਹਾਂ।",
    header_intro="ਤੁਹਾਡੀ ਬੇਨਤੀ ਨਾਲ ਸਬੰਧਤ ਮੁੱਖ ਸਰਕਾਰੀ ਯੋਜਨਾਵਾਂ ਹੇਠਾਂ ਦਿੱਤੀਆਂ ਗਈਆਂ ਹਨ:",
    apply_label="ਅਰਜ਼ੀ ਕਰੋ",
    support_title="💡 **ਸਬੰਧਤ ਸਵਾਲ (ਪੁੱਛਣ ਲਈ ਟੈਪ ਕਰੋ)**:",
)


class LanguageRegistry:
    """Central registry of supported languages for Schemora."""

    def __init__(self):
        self._languages: Dict[str, LanguageSpec] = {}
        # Register default languages
        for spec in [
            DEFAULT_EN, DEFAULT_HI, DEFAULT_GU, DEFAULT_MR, DEFAULT_BN,
            DEFAULT_TA, DEFAULT_TE, DEFAULT_KN, DEFAULT_ML, DEFAULT_PA
        ]:
            self.register_language(spec)

    def register_language(self, spec: LanguageSpec) -> None:
        """Register or override a LanguageSpec dynamically."""
        self._languages[spec.code.lower()] = spec
        logger.info(f"LanguageRegistry: Registered '{spec.code}' ({spec.name} / {spec.native_name})")

    def get_spec(self, code: str) -> LanguageSpec:
        """Fetch LanguageSpec by code, defaulting to English."""
        return self._languages.get(code.lower(), DEFAULT_EN)

    def detect_language(self, text: str, hint_code: Optional[str] = None) -> LanguageSpec:
        """Detect language by script inspection of text string."""
        if not text or not isinstance(text, str):
            return self.get_spec(hint_code or "en")

        text_stripped = text.strip()
        hint = (hint_code or "").lower()

        # 1. Check specific Indic/Non-English script ranges first
        for code, spec in self._languages.items():
            if spec.script_regex and spec.code != "en":
                if re.search(spec.script_regex, text_stripped):
                    # Devanagari is shared by Hindi and Marathi — use Marathi-only words, then the hint
                    if spec.code in ("hi", "mr"):
                        if hint == "mr" or self._has_marker(text_stripped, self.MARATHI_MARKERS):
                            return self.get_spec("mr")
                        return self.get_spec("hi")
                    return spec

        # 2. Romanized Indic (e.g. Hinglish) — honour the user's chosen language when the
        #    text carries clear markers of it; otherwise Latin text is English.
        if hint in self.ROMANIZED_MARKERS and self._has_marker(text_stripped.lower(), self.ROMANIZED_MARKERS[hint]):
            return self.get_spec(hint)

        latin_char_count = len(re.findall(r"[A-Za-z]", text_stripped))
        if latin_char_count >= 3 or not text_stripped:
            return DEFAULT_EN

        # 3. Fallback to hint_code if non-English
        if hint_code and hint_code.lower() in self._languages:
            return self.get_spec(hint_code)

        return DEFAULT_EN

    # Words common in Marathi but not used in Hindi.
    MARATHI_MARKERS = {
        "आहे", "आहेत", "नाही", "मला", "तुम्ही", "आम्ही", "कसा", "कसे", "कशी",
        "काय", "साठी", "मिळेल", "पाहिजे", "कोणती", "कोणत्या", "सांगा", "योजनेची", "योजनेचे",
    }

    # Romanized words that only appear when someone writes that language in Latin script.
    ROMANIZED_MARKERS = {
        "hi": {"hai", "hain", "kya", "kaise", "kaun", "kitna", "kitni", "liye", "mujhe",
               "chahiye", "milega", "bataiye", "batao", "ke", "ki", "nahi", "kab"},
        "gu": {"che", "chhe", "shu", "kem", "mate", "mane", "joie", "joiye", "kevi",
               "rite", "karvi", "maate", "kyare", "nathi"},
        "mr": {"aahe", "ahe", "kasa", "kase", "mala", "sathi", "pahije", "kay",
               "sanga", "milel", "nahi", "konti"},
    }

    @staticmethod
    def _has_marker(text: str, markers: set) -> bool:
        # Explicit Indic range: Python's \w does not match vowel signs (matras)
        tokens = re.findall(r"[\wऀ-ൿ]+", text)
        return any(t in markers for t in tokens)

    INDIC_KEYWORD_MAP = {
        # Hindi
        "योजना": "scheme yojana",
        "योजनाएं": "schemes yojana",
        "छात्रवृत्ति": "scholarship student education",
        "किसान": "farmer kisan agriculture crop",
        "महिला": "women female girl mahila",
        "गरीब": "poor low income ews bpl welfare",
        "दस्तावेज": "documents papers certificate proof",
        "पात्रता": "eligibility criteria qualification",
        "आवेदन": "application apply process portal",
        "लाभ": "benefits amount financial assistance",
        # Gujarati
        "યોજના": "scheme yojana",
        "યોજનાઓ": "schemes yojana",
        "સરકારી": "government official",
        "વિદ્યાર્થીઓ": "students education scholarship",
        "ખેડૂતો": "farmers agriculture kisan crop",
        "મહિલાઓ": "women female girl mahila",
        "ગરીબ": "poor low income ews bpl welfare",
        "દસ્તાવેજો": "documents papers certificate proof",
        "પાત્રતા": "eligibility criteria qualification",
        "અરજી": "application apply process portal",
        "લાભ": "benefits amount financial assistance",
        # Marathi (Hindi entries above already cover shared words like किसान, पात्रता, लाभ)
        "योजने": "scheme yojana",
        "शिष्यवृत्ती": "scholarship student education",
        "शेतकरी": "farmer kisan agriculture crop",
        "महिलां": "women female girl mahila",
        "कागदपत्र": "documents papers certificate proof",
        "अर्ज": "application apply process portal",
        "विद्यार्थी": "students education scholarship",
        # Bengali
        "প্রকল্প": "scheme yojana",
        "বৃত্তি": "scholarship student education",
        "কৃষক": "farmer kisan agriculture crop",
        "মহিলা": "women female girl mahila",
        "নথি": "documents papers certificate proof",
        "যোগ্যতা": "eligibility criteria qualification",
        "আবেদন": "application apply process portal",
        # Tamil
        "திட்ட": "scheme yojana",
        "உதவித்தொகை": "scholarship student education",
        "விவசாய": "farmer kisan agriculture crop",
        "பெண்": "women female girl mahila",
        "ஆவண": "documents papers certificate proof",
        "தகுதி": "eligibility criteria qualification",
        "விண்ணப்ப": "application apply process portal",
        # Telugu
        "పథక": "scheme yojana",
        "ఉపకార వేతన": "scholarship student education",
        "రైతు": "farmer kisan agriculture crop",
        "మహిళ": "women female girl mahila",
        "పత్రాలు": "documents papers certificate proof",
        "అర్హత": "eligibility criteria qualification",
        "దరఖాస్తు": "application apply process portal",
        # Kannada
        "ಯೋಜನೆ": "scheme yojana",
        "ವಿದ್ಯಾರ್ಥಿವೇತನ": "scholarship student education",
        "ರೈತ": "farmer kisan agriculture crop",
        "ಮಹಿಳ": "women female girl mahila",
        "ದಾಖಲೆ": "documents papers certificate proof",
        "ಅರ್ಹತೆ": "eligibility criteria qualification",
        "ಅರ್ಜಿ": "application apply process portal",
        # Malayalam
        "പദ്ധതി": "scheme yojana",
        "സ്കോളർഷിപ്പ്": "scholarship student education",
        "കർഷക": "farmer kisan agriculture crop",
        "സ്ത്രീ": "women female girl mahila",
        "രേഖ": "documents papers certificate proof",
        "യോഗ്യത": "eligibility criteria qualification",
        "അപേക്ഷ": "application apply process portal",
        # Punjabi
        "ਯੋਜਨਾ": "scheme yojana",
        "ਵਜ਼ੀਫ਼ਾ": "scholarship student education",
        "ਕਿਸਾਨ": "farmer kisan agriculture crop",
        "ਔਰਤ": "women female girl mahila",
        "ਦਸਤਾਵੇਜ਼": "documents papers certificate proof",
        "ਯੋਗਤਾ": "eligibility criteria qualification",
        "ਅਰਜ਼ੀ": "application apply process portal",
        # Romanized Hindi / Gujarati / Marathi
        "chhatravritti": "scholarship student education",
        "shishyavrutti": "scholarship student education",
        "kheti": "farmer agriculture crop",
        "khedut": "farmer agriculture crop",
        "shetkari": "farmer agriculture crop",
        "dastavej": "documents papers certificate proof",
        "kagadpatra": "documents papers certificate proof",
        "patrata": "eligibility criteria qualification",
        "aavedan": "application apply process portal",
        "arji": "application apply process portal",
    }

    def translate_query_for_retrieval(self, query: str, detected_spec: LanguageSpec) -> str:
        """Prepare query for high-recall vector search.

        Translates Indic keywords (Hindi, Gujarati, Marathi, etc.) to English domain concepts
        to maximize hybrid semantic & TF-IDF recall while retaining original query terms.
        """
        translated_tokens = []
        q_lower = query.lower()
        for word, expansion in self.INDIC_KEYWORD_MAP.items():
            if word in q_lower:
                translated_tokens.append(expansion)

        extra = " " + " ".join(translated_tokens) if translated_tokens else ""
        if detected_spec.code == "en":
            return f"{query}{extra}".strip()

        # Append universal retrieval keywords in English to boost vector/keyword recall
        retrieval_enhancer = f"{extra} scheme scholarship eligibility criteria documents application guidelines portal"
        return f"{query} {retrieval_enhancer}".strip()


# Global Singleton Instance
language_registry = LanguageRegistry()
