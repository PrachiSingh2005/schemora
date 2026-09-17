"""Schemora Authoritative Glossary & Concept Knowledge Base.

Contains authoritative conceptual knowledge definitions for core government scheme terms:
  - Government Scheme
  - Central Government Scheme
  - State Government Scheme
  - Eligibility
  - Beneficiary
  - Benefits
  - Documents Required
  - Application Process
  - Subsidy
  - Financial Assistance
  - Scholarship
  - Direct Benefit Transfer (DBT)
  - Income Certificate
  - Caste Certificate
  - Disability Certificate
  - Residence / Domicile Certificate
  - Renewal
  - Common Service Centre (CSC)

Stored in PostgreSQL + pgvector as semantic KnowledgeChunks for definition & concept Q&A.
"""

import logging
from typing import Any, Dict, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.knowledge import KnowledgeDocument, KnowledgeChunk
from app.services.embedding_service import embed_text, embedding_to_json

logger = logging.getLogger(__name__)

GLOSSARY_DOC_ID = "doc-schemora-glossary-v2"
GLOSSARY_SCHEME_ID = "schemora-glossary"

GLOSSARY_CONCEPTS: List[Dict[str, Any]] = [
    {
        "key": "government_scheme",
        "title": "Government Scheme",
        "content": (
            "Concept: Government Scheme (सरकारी योजना / સરકારી યોજના)\n"
            "Definition: A Government Scheme (also known as a Yojana or Welfare Program) is an official policy, program, "
            "or initiative introduced by the Central or State Government to provide financial assistance, social welfare, "
            "subsidies, education support, healthcare, or skill development to eligible citizens.\n"
            "Purpose: To uplift economically weaker sections, empower students, farmers, women, and senior citizens, "
            "reduce inequality, and promote national socio-economic growth.\n"
            "Key Components: Every government scheme has defined eligibility criteria, direct benefits (such as stipends, "
            "subsidies, or cash transfers via DBT), required documents, and a structured application process.\n"
            "Hindi Explanation: सरकारी योजना सरकार (केंद्र या राज्य) द्वारा नागरिकों के सामाजिक एवं आर्थिक कल्याण के लिए "
            "शुरू किया गया एक आधिकारिक कार्यक्रम है। इसके तहत पात्र नागरिकों को वित्तीय सहायता, छात्रवृत्ति, सब्सिडी, स्वास्थ्य सेवाएँ "
            "या रोजगार सहायता प्रदान की जाती है।\n"
            "Gujarati Explanation: સરકારી યોજના એ કેન્દ્ર અથવા રાજ્ય સરકાર દ્વારા નાગરિકોના કલ્યાણ માટે શરૂ કરવામાં આવેલો "
            "એક સત્તાવાર કાર્યક્રમ છે, જેનો હેતુ નાણાકીય સહાય, શિષ્યવૃત્તિ, સબસીડી અથવા રોજગારી પૂરી પાડવાનો છે."
        ),
    },
    {
        "key": "central_government_scheme",
        "title": "Central Government Scheme",
        "content": (
            "Concept: Central Government Scheme (केंद्र सरकार की योजना / કેન્દ્ર સરકારની યોજના)\n"
            "Definition: A Central Government Scheme is a welfare initiative planned, formulated, and funded by the Union Government of India "
            "through Central Ministries (such as Ministry of Education, Ministry of Agriculture, Ministry of Social Justice).\n"
            "Types: 1. Central Sector Schemes — 100% funded and implemented directly by the Central Government (e.g., PM-KISAN, PM Internship Scheme).\n"
            "2. Centrally Sponsored Schemes — Funded jointly by Central and State Governments (e.g., 60:40 or 90:10 ratio) and executed by State authorities.\n"
            "Coverage: Available uniformly across all States and Union Territories in India.\n"
            "Hindi Explanation: केंद्र सरकार की योजनाएं भारत सरकार के केंद्रीय मंत्रालयों द्वारा पूरी तरह या आंशिक रूप से वित्तपोषित "
            "और संचालित होती हैं। ये योजनाएं पूरे देश में समान रूप से लागू होती हैं।\n"
            "Gujarati Explanation: કેન્દ્ર સરકારની યોજનાઓ ભારત સરકારના કેન્દ્રીય મંત્રાલયો દ્વારા ભંડોળ પૂરું પાડવામાં આવે છે "
            "અને સમગ્ર ભારતમાં એકસરખી રીતે લાગુ થાય છે."
        ),
    },
    {
        "key": "state_government_scheme",
        "title": "State Government Scheme",
        "content": (
            "Concept: State Government Scheme (राज्य सरकार की योजना / રાજ્ય સરકારની યોજના)\n"
            "Definition: A State Government Scheme is a localized welfare program created, funded, and administered by a specific State Government "
            "or Union Territory Administration (such as Maharashtra, Gujarat, Uttar Pradesh, Tamil Nadu, etc.).\n"
            "Purpose: Targeted specifically to meet the unique socio-economic, educational, or agricultural needs of state domiciles/residents.\n"
            "Eligibility Rule: Applicants usually must possess a valid Domicile Certificate or Residence Proof of that specific State.\n"
            "Examples: Ladki Bahin Scheme (Maharashtra), MYSY Scheme (Gujarat), Kanya Sumangala Yojana (UP).\n"
            "Hindi Explanation: राज्य सरकार की योजनाएं किसी विशेष राज्य (जैसे महाराष्ट्र, गुजरात, यूपी) द्वारा अपने राज्य के मूल निवासियों के लिए "
            "बनाई और चलाई जाती हैं। इनके लिए संबंधित राज्य का अधिवास (Domicile) प्रमाण पत्र आवश्यक होता है।\n"
            "Gujarati Explanation: રાજ્ય સરકારની યોજનાઓ ચોક્કસ રાજ્યના સ્થાનિક નાગરિકો માટે બનાવવામાં આવે છે. તેના માટે તે રાજ્યનું "
            "રહેવાસી અથવા ડોમિસાઇલ પ્રમાણપત્ર જરૂરી હોય છે."
        ),
    },
    {
        "key": "eligibility",
        "title": "Eligibility Criteria",
        "content": (
            "Concept: Eligibility Criteria (पात्रता मानदंड / પાત્રતા)\n"
            "Definition: Eligibility Criteria is the set of official conditions, qualifications, and requirements that an individual citizen "
            "must satisfy in order to qualify for and receive benefits under a government scheme.\n"
            "Common Eligibility Parameters:\n"
            "1. Domicile / Residency: State of residence or Union Territory.\n"
            "2. Age Limits: Minimum and maximum age requirements.\n"
            "3. Family Annual Income Limit: E.g., annual income below ₹2.5 Lakhs, ₹8 Lakhs, etc.\n"
            "4. Social Category: General, OBC (Other Backward Classes), SC (Scheduled Castes), ST (Scheduled Tribes), EWS (Economically Weaker Section).\n"
            "5. Educational Qualification: Class 10th pass, Class 12th pass, Graduation, Diploma, etc.\n"
            "6. Occupation: Student, Farmer, Small Landholder, Micro-entrepreneur, Woman, Senior Citizen.\n"
            "Hindi Explanation: पात्रता वह आवश्यक शर्तों और नियमों का समूह है जिन्हें पूरा करने पर ही कोई नागरिक योजना का लाभ उठाने के लिए योग्य माना जाता है।\n"
            "Gujarati Explanation: પાત્રતા એ શરતો અને સુવિધાઓનો સમૂહ છે જે નાગરિકે યોજનાનો લાભ મેળવવા માટે પૂરી કરવી પડે છે."
        ),
    },
    {
        "key": "beneficiary",
        "title": "Beneficiary",
        "content": (
            "Concept: Beneficiary (लाभार्थी / લાભાર્થી)\n"
            "Definition: A Beneficiary is an eligible individual, student, farmer, woman, family, or institution selected to receive financial aid, "
            "subsidies, stipends, or services under a government scheme.\n"
            "Identification & Verification: Beneficiaries are identified through authenticated verification of eligibility documents and identity proofs.\n"
            "Direct Benefit Transfer (DBT): Benefits are directly credited to the beneficiary's Aadhaar-linked bank account to ensure zero leakage and full transparency.\n"
            "Hindi Explanation: लाभार्थी वह व्यक्ति, छात्र, किसान या महिला है जो किसी सरकारी योजना के तहत मिलने वाली वित्तीय सहायता या सुविधाओं को प्राप्त करने का पात्र होता है।\n"
            "Gujarati Explanation: લાભાર્થી એ એવી વ્યક્તિ અથવા નાગરિક છે જે સરકારી યોજના હેઠળ મળતા લાભો કે નાણાકીય સહાય મેળવે છે."
        ),
    },
    {
        "key": "benefits",
        "title": "Scheme Benefits",
        "content": (
            "Concept: Scheme Benefits (लाभ / લાભો)\n"
            "Definition: Scheme Benefits represent the specific financial assistance, financial support, material goods, services, or concessions "
            "provided to verified beneficiaries under a government initiative.\n"
            "Types of Benefits:\n"
            "1. Financial Support: Monthly stipends, annual scholarships, direct cash transfers (DBT).\n"
            "2. Subsidies: Price reductions on farming seeds, fertilizers, solar equipment, gas cylinders, interest rate subsidies on loans.\n"
            "3. Fee Waivers: Reimbursement or waiver of tuition, hostel, and examination fees for students.\n"
            "4. Healthcare & Insurance: Free hospital coverage (e.g., Ayushman Bharat ₹5 Lakh health cover), life & disability insurance.\n"
            "5. Skill & Infrastructure Support: Free training certificates, toolkits (PM Vishwakarma), laptop or smartphone distribution.\n"
            "Hindi Explanation: लाभ उन वित्तीय सहायताओं, छात्रवृत्तियों, रियायतों या सेवाओं को कहते हैं जो योजना के तहत योग्य नागरिक को दी जाती हैं।\n"
            "Gujarati Explanation: લાભ એ સરકારી યોજના હેઠળ લાભાર્થીને મળતી નાણાકીય સહાય, સબસીડી અથવા સેવાઓ છે."
        ),
    },
    {
        "key": "documents_required",
        "title": "Documents Required",
        "content": (
            "Concept: Documents Required (आवश्यक दस्तावेज / જરૂરી દસ્તાવેજો)\n"
            "Definition: Documents Required is the official mandatory checklist of identity proofs, certificates, and records that an applicant "
            "must submit alongside their scheme application form to verify their identity and eligibility.\n"
            "Standard Document Checklist:\n"
            "1. Identity Proof: Aadhaar Card, Voter ID, PAN Card, Passport.\n"
            "2. Address / Domicile Proof: Domicile Certificate, Electricity Bill, Ration Card.\n"
            "3. Income Proof: Income Certificate issued by Tehsildar / Revenue Authority.\n"
            "4. Category Certificate: Caste Certificate for OBC, SC, ST, or EWS Certificate.\n"
            "5. Educational Documents: Marksheets, Passing Certificates, Bonafide Student Certificate.\n"
            "6. Bank Account Details: Bank Passbook photocopy (Aadhaar linked for DBT transfer).\n"
            "7. Photographs: Recent Passport size photos.\n"
            "Hindi Explanation: आवश्यक दस्तावेज वे आधिकारिक प्रमाण पत्र और कागजात हैं जिन्हें योजना का लाभ लेने के लिए आवेदन के साथ जमा करना अनिवार्य होता है।\n"
            "Gujarati Explanation: જરૂરી દસ્તાવેજો એવા સત્તાવાર પ્રમાણપત્રો અને પુરાવાઓ છે જે અરજી સાથે રજૂ કરવાના હોય છે."
        ),
    },
    {
        "key": "application_process",
        "title": "Application Process",
        "content": (
            "Concept: Application Process (आवेदन प्रक्रिया / અરજી પ્રક્રિયા)\n"
            "Definition: The Application Process is the official step-by-step procedure an applicant must complete to apply for a government scheme.\n"
            "Channels:\n"
            "1. Online Mode: Registering on official government web portals (e.g., myScheme, NSP, State Scholarship Portals).\n"
            "2. Offline Mode: Submitting physical forms at Common Service Centers (CSC), Tehsil Offices, Block Offices, or District Welfare Departments.\n"
            "Standard Steps:\n"
            "Step 1: Portal Registration using Mobile Number and Aadhaar.\n"
            "Step 2: Fill Personal, Contact, Academic, and Bank Details in the Application Form.\n"
            "Step 3: Upload Scanned copies of Required Documents.\n"
            "Step 4: Review application summary and Submit.\n"
            "Step 5: Download & print Application Ackowledgment for tracking status.\n"
            "Hindi Explanation: आवेदन प्रक्रिया वह चरण-दर-चरण तरीका है जिसके द्वारा पात्र नागरिक योजना के लिए ऑनलाइन या ऑफलाइन फॉर्म भरते हैं और जमा करते हैं।\n"
            "Gujarati Explanation: અરજી પ્રક્રિયા એ યોજનાનો લાભ મેળવવા માટે ઓનલાઈન અથવા ઓફલાઈન ફોર્મ ભરવાની ક્રમશઃ રીત છે."
        ),
    },
    {
        "key": "subsidy",
        "title": "Subsidy",
        "content": (
            "Concept: Subsidy (सब्सिडी / સબસીડી)\n"
            "Definition: A Subsidy is a direct or indirect financial grant, discount, or price concession provided by the Government "
            "to lower the cost of essential commodities, services, loans, agricultural inputs, or equipment for citizens.\n"
            "Types of Subsidies:\n"
            "1. Price Subsidy: Discounted prices on fertilizers, seeds, LPG cooking gas, electricity, and food grains (Ration).\n"
            "2. Capital Subsidy: Financial grant covering 20% to 50% of the equipment or solar pump installation cost (e.g., PM KUSUM).\n"
            "3. Interest Subsidy: Discounted interest rates on education loans, home loans (PMAY), or MSME business loans.\n"
            "Hindi Explanation: सब्सिडी सरकार द्वारा दी जाने वाली वह आर्थिक छूट या वित्तीय मदद है जिससे आवश्यक वस्तुओं, बीजों, खादों, शिक्षा ऋण या गैस सिलेंडर की कीमत आम जनता के लिए कम हो जाती है।\n"
            "Gujarati Explanation: સબસીડી એ સરકાર દ્વારા આપવામાં આવતી નાણાકીય છૂટછાટ છે જેથી મોંઘી વસ્તુઓ કે સેવાઓ સસ્તા દરે ઉપલબ્ધ થાય છે."
        ),
    },
    {
        "key": "financial_assistance",
        "title": "Financial Assistance",
        "content": (
            "Concept: Financial Assistance (वित्तीय सहायता / નાણાકીય સહાય)\n"
            "Definition: Financial Assistance refers to direct monetary aid, scholarships, stipends, or relief funds transferred by the Government "
            "to eligible individuals to cover educational expenses, farming costs, medical treatment, or subsistence.\n"
            "Delivery Mechanism: Disbursed electronically into the beneficiary's Aadhaar-seeded bank account via Direct Benefit Transfer (DBT).\n"
            "Examples: Post-Matric Scholarship funds for students, ₹6,000 yearly income support under PM-KISAN for farmers, ₹5,000 maternity assistance under PMMVY.\n"
            "Hindi Explanation: वित्तीय सहायता सरकार द्वारा छात्रों, किसानों, महिलाओं या गरीब परिवारों को शिक्षा, कृषि या जीवन यापन के लिए दी जाने वाली प्रत्यक्ष नकद या बैंक हस्तांतरण सहायता है।\n"
            "Gujarati Explanation: નાણાકીય સહાય એ સરકાર દ્વારા નાગરિકોને તેમના શિક્ષણ, ખેતી કે આરોગ્યના ખર્ચમાં મદદ માટે બેંકમાં સીધી ટ્રાન્સફર કરાતી રકમ છે."
        ),
    },
    {
        "key": "scholarship",
        "title": "Scholarship",
        "content": (
            "Concept: Scholarship (छात्रवृत्ति / શિષ્યવૃત્તિ)\n"
            "Definition: A Scholarship is a form of financial aid or financial assistance awarded by the Government, "
            "institution, or organization to eligible students to support their education at school, college, or university level. "
            "Scholarships are merit-based, need-based, or both.\n"
            "Types:\n"
            "1. Pre-Matric Scholarships: For students studying in Class 1–10 (below Class 10 board exam).\n"
            "2. Post-Matric Scholarships: For students who have passed Class 10 (matriculation) and are studying in Class 11, 12, Diploma, Graduation, or Post-Graduation.\n"
            "3. Merit-cum-Means Scholarships: Require both good academic merit and financial need.\n"
            "4. Central Government Scholarships: Available via the National Scholarship Portal (NSP) — scholarships.gov.in.\n"
            "5. State Government Scholarships: Available via State scholarship portals (e.g., MahaDBT for Maharashtra, MYSY for Gujarat).\n"
            "Key Examples: Post-Matric Scholarship for OBC, SC, ST students; Central Sector Scholarship; PM YASASVI; PM Vidyalaxmi.\n"
            "Hindi Explanation: छात्रवृत्ति वह वित्तीय सहायता है जो सरकार या संस्था द्वारा योग्य छात्रों को उनकी शिक्षा जारी रखने के लिए दी जाती है। यह मेरिट, आर्थिक जरूरत या दोनों के आधार पर मिलती है।\n"
            "Gujarati Explanation: શિષ્યવૃત્તિ એ સરકાર અથવા સંસ્થા દ્વારા લાયક વિદ્યાર્થીઓને તેમનો અભ્યાસ ચાલુ રાખવા માટે આપવામાં આવતી નાણાકીય સહાય છે."
        ),
    },
    {
        "key": "dbt",
        "title": "Direct Benefit Transfer (DBT)",
        "content": (
            "Concept: Direct Benefit Transfer — DBT (प्रत्यक्ष लाभ अंतरण / ડાયરેક્ટ બેનિફિટ ટ્રાન્સફર)\n"
            "Definition: Direct Benefit Transfer (DBT) is an Indian Government mechanism that electronically transfers "
            "financial benefits, subsidies, scholarships, and welfare payments directly into the verified Aadhaar-linked bank account "
            "of the eligible beneficiary — eliminating middlemen and preventing leakage.\n"
            "How It Works:\n"
            "1. Beneficiary links their Aadhaar number to their bank account (Aadhaar seeding).\n"
            "2. Government verifies eligibility via Aadhaar authentication.\n"
            "3. The entitled scholarship, pension, or subsidy amount is transferred directly to the bank account.\n"
            "Benefits of DBT: Zero leakage, real-time transfers, zero intermediary corruption, instant grievance tracking.\n"
            "Portal: Government manages DBT via https://dbtbharat.gov.in\n"
            "Hindi Explanation: DBT (प्रत्यक्ष लाभ अंतरण) एक प्रणाली है जिसके तहत सरकार छात्रवृत्ति, पेंशन, या सब्सिडी की राशि सीधे लाभार्थी के आधार-लिंक्ड बैंक खाते में जमा करती है।\n"
            "Gujarati Explanation: DBT (ડાયરેક્ટ બેનિફિટ ટ્રાન્સફર) એ એક સરકારી પ્રણાલી છે જે આધાર-જોડાયેલ બેંક ખાતામાં સ્કોલરશીપ, પેન્શન કે સબ્સીડી સીધી ટ્રાન્સફર કરે છે."
        ),
    },
    {
        "key": "income_certificate",
        "title": "Income Certificate",
        "content": (
            "Concept: Income Certificate (आय प्रमाण पत्र / આવક પ્રમાણ પત્ર)\n"
            "Definition: An Income Certificate is an official government document that certifies the annual household income of a family. "
            "It is issued by a Revenue Officer, Tehsildar, or Sub-Divisional Magistrate (SDM) and is required for most means-tested schemes.\n"
            "When It Is Required: Most Central and State schemes that have income eligibility limits require an Income Certificate. "
            "For example, Post-Matric Scholarship requires annual family income below ₹2.5 Lakhs.\n"
            "Issuing Authority: Tehsildar / Sub-Divisional Magistrate (SDM) / Revenue Circle Officer — depending on State.\n"
            "How to Get It:\n"
            "1. Apply at the local Tehsil Office or nearest Common Service Centre (CSC / Jan Seva Kendra).\n"
            "2. Submit ID proof (Aadhaar), address proof, and salary slips or affidavit.\n"
            "3. Revenue officer issues the certificate after verification. Valid for 1 year.\n"
            "Digital Alternative: Many states now issue income certificates via their e-District or Seva Sindhu portals.\n"
            "Hindi Explanation: आय प्रमाण पत्र एक सरकारी दस्तावेज है जो परिवार की वार्षिक आय को प्रमाणित करता है। इसे तहसीलदार या SDM द्वारा जारी किया जाता है और अधिकांश सरकारी योजनाओं में आवेदन के लिए आवश्यक होता है।\n"
            "Gujarati Explanation: આવક પ્રમાણ પત્ર એ સરકારી દસ્તાવેજ છે જે પરિવારની વાર્ષિક આવક સ્ત્યયિત કરે છે. તે મોટાભાગની સ્કોલરશીપ અને કલ્યાણ યોજનાઓ માટે ફરજિયાત છે."
        ),
    },
    {
        "key": "caste_certificate",
        "title": "Caste Certificate (SC / OBC / ST)",
        "content": (
            "Concept: Caste Certificate (जाति प्रमाण पत्र / જ્ઞાતિ પ્રમાણ પત્ર)\n"
            "Definition: A Caste Certificate is an official document issued by the State Government that certifies a person's social category — "
            "Scheduled Caste (SC), Scheduled Tribe (ST), or Other Backward Classes (OBC). It is mandatory for applying to caste-specific reservations in government schemes.\n"
            "Who Needs It: Students or citizens belonging to SC, ST, or OBC categories applying for reserved category schemes or scholarships.\n"
            "Types:\n"
            "1. SC Certificate — Scheduled Castes recognized by the Indian Constitution.\n"
            "2. ST Certificate — Scheduled Tribes recognized by the Indian Constitution.\n"
            "3. OBC Certificate — Other Backward Classes (Non-Creamy Layer check applicable for Central schemes).\n"
            "4. EWS Certificate — Economically Weaker Section (annual income < ₹8 Lakhs for unreserved category).\n"
            "Issuing Authority: Tehsildar / Sub-Divisional Magistrate (SDM) / District Magistrate.\n"
            "Important Note: For Central Government OBC schemes, the OBC-NCL (Non-Creamy Layer) certificate is required — not just any OBC certificate.\n"
            "Hindi Explanation: जाति प्रमाण पत्र एक सरकारी दस्तावेज है जो SC, ST, OBC या EWS श्रेणी में जन्मे व्यक्ति की सामाजिक स्थिति को प्रमाणित करता है।\n"
            "Gujarati Explanation: જ્ઞાતિ પ્રમાણ પત્ર SC, ST, OBC અથવા EWS વ્યક્તિ માટે ઇશ્યુ થતો સત્તાવાર દસ્તાવેજ છે જે આરક્ષણ-આધારિત સ્કોલરશીપ કે સ્કીમ માટે ફરજિયાત છે."
        ),
    },
    {
        "key": "disability_certificate",
        "title": "Disability Certificate (PwD / UDID)",
        "content": (
            "Concept: Disability Certificate — PwD / UDID (दिव्यांगता प्रमाण पत्र / અપંગ પ્રમાણ પત્ર)\n"
            "Definition: A Disability Certificate is an official document that certifies a person's type and percentage of disability. "
            "It is issued by a government medical authority and is required to avail benefits under PwD-specific government schemes.\n"
            "UDID Card: The Government of India issues a Unique Disability ID (UDID) Card — a single digital document for all disability-related schemes. Apply at: https://www.swavlambancard.gov.in\n"
            "Minimum Disability: Most schemes require minimum 40% disability benchmark.\n"
            "Types of Disability Recognized (RPwD Act 2016):\n"
            "Visual Impairment, Hearing Impairment, Locomotor Disability, Intellectual Disability, Mental Illness, "
            "Autism Spectrum Disorder, Cerebral Palsy, Specific Learning Disabilities, Multiple Disabilities, and 14 others.\n"
            "Issuing Authority: Civil Surgeon / District Medical Board in a Government Hospital.\n"
            "Hindi Explanation: दिव्यांगता प्रमाण पत्र एक सरकारी दस्तावेज है जो किसी व्यक्ति की विकलांगता के प्रकार और प्रतिशत को प्रमाणित करता है। UDID कार्ड सभी PwD योजनाओं के लिए एकल डिजिटल पहचान के रूप में कार्य करता है।\n"
            "Gujarati Explanation: અપંગ પ્રમાણ પત્ર (UDID) એ સરકારી દસ્તાવેજ છે જે દિવ્યાંગ વ્યક્તિની વિકલાંગતાના પ્રકાર અને ટકાવારીને પ્રમાણિત કરે છે."
        ),
    },
    {
        "key": "residence_domicile_certificate",
        "title": "Residence / Domicile Certificate",
        "content": (
            "Concept: Domicile Certificate / Residence Certificate (निवास प्रमाण पत्र / રહેઠાણ / ડોમિસાઇલ પ્રમાણ પત્ર)\n"
            "Definition: A Domicile Certificate (also known as Residence Certificate or Bonafide Resident Certificate) is an official document "
            "issued by a State Government that certifies that a person is a permanent or bona fide resident of that specific State or Union Territory.\n"
            "When It Is Required: State Government schemes require applicants to be resident/domicile of that State. "
            "For example, MYSY Gujarat Scholarship requires a Gujarat domicile certificate; "
            "MahaDBT Scholarship requires Maharashtra domicile.\n"
            "Issuing Authority: Tehsildar / Sub-Divisional Magistrate (SDM) / Revenue Department — depending on State.\n"
            "How to Get It:\n"
            "1. Apply at local Tehsil Office or via State's e-District/Digital portal.\n"
            "2. Submit Aadhaar, proof of residency (utility bills, ration card, voter ID), and self-declaration.\n"
            "3. Revenue officer verifies and issues certificate. Valid period varies by State (typically 3–5 years).\n"
            "Hindi Explanation: निवास प्रमाण पत्र एक सरकारी दस्तावेज है जो यह सिद्ध करता है कि व्यक्ति किसी विशेष राज्य का स्थायी निवासी है। राज्य सरकार की योजनाओं के लिए यह अनिवार्य होता है।\n"
            "Gujarati Explanation: ડોમિસાઇલ/રહેઠાણ પ્રમાણ પત્ર એ એક સત્તાવાર દસ્તાવેજ છે જે દર્શાવે છે કે વ્યક્તિ ચોક્કસ રાજ્ય/UT નો કાયમી નિવાસી છે. રાજ્ય સ્કોલરશીપ માટે ફરજિયાત."
        ),
    },
    {
        "key": "renewal",
        "title": "Scheme Renewal",
        "content": (
            "Concept: Renewal (नवीनीकरण / નવીકરણ)\n"
            "Definition: Renewal is the process by which a beneficiary who is already receiving a government scheme benefit — "
            "particularly a scholarship — reapplies each academic year to continue receiving the benefit.\n"
            "When Renewal Applies: Most post-matric and central sector scholarships are disbursed annually and require yearly renewal. "
            "The beneficiary must reapply each year to confirm continuation of eligibility (e.g., maintained minimum marks, same institution, income within limit).\n"
            "Renewal Conditions (typical):\n"
            "1. Minimum attendance requirement met.\n"
            "2. Minimum academic performance (e.g., 50% marks in previous year).\n"
            "3. No change in institution or stream without prior approval.\n"
            "4. Income certificate renewed if required.\n"
            "Renewal Window: Typically opens July–November each year on the National Scholarship Portal (scholarships.gov.in).\n"
            "Steps: Log in to NSP/State Portal → Select Renewal Mode → Verify previous application ID → Update current year details → Upload new certificate if required → Submit.\n"
            "Hindi Explanation: नवीनीकरण वह प्रक्रिया है जिसके द्वारा मौजूदा छात्रवृत्ति लाभार्थी अगले शैक्षणिक वर्ष में भी लाभ जारी रखने के लिए पुनः आवेदन करता है।\n"
            "Gujarati Explanation: નવીકરણ (Renewal) એ પ્રક્રિયા છે જ્યારે સ્કોલરશીપ મેળવનાર વિદ્યાર્થી દર વર્ષે ફરીથી અરજી કરે છે જેથી આગામી વર્ષ પણ સ્કોલરશીપ ચાલુ રહે."
        ),
    },
    {
        "key": "common_service_centre",
        "title": "Common Service Centre (CSC)",
        "content": (
            "Concept: Common Service Centre — CSC (कॉमन सर्विस सेंटर / કૉમન સર્વિસ સેન્ટર)\n"
            "Definition: A Common Service Centre (CSC) is a Government of India ICT-enabled citizen service point established under the "
            "Digital India initiative. It acts as a one-stop shop where rural and semi-urban citizens can access government services, "
            "apply for schemes, and complete digital transactions without needing internet access at home.\n"
            "Services Available at CSC:\n"
            "1. Applying for government scholarships and scheme benefits.\n"
            "2. Printing and submitting applications for certificates (Income, Caste, Domicile).\n"
            "3. Aadhaar enrolment and updation.\n"
            "4. Passport, PAN card, and NREGA job card applications.\n"
            "5. Banking, insurance, and pension services.\n"
            "How to Find Nearest CSC: Visit https://locator.csccloud.in or call the CSC helpline 1800-121-3468 (Toll Free).\n"
            "Also Known As: Jan Seva Kendra, e-Mitra (Rajasthan), Meeseva (AP/Telangana), Aaple Sarkar (Maharashtra), UMANG Centre.\n"
            "Hindi Explanation: CSC (कॉमन सर्विस सेंटर) एक सरकारी डिजिटल सेवा केंद्र है जहाँ नागरिक ग्रामीण क्षेत्रों में भी सरकारी योजनाओं के लिए आवेदन, प्रमाण पत्र प्राप्त और डिजिटल सेवाएं ले सकते हैं।\n"
            "Gujarati Explanation: CSC (કૉમન સર્વિસ સેન્ટર) એ ગ્રામ/અર્ધ-શહેરી વિસ્તારોમાં ઇ-ગ્વર્નન્સ સેવાઓ, સ્કોલરશીપ અરજી, પ્રમાણ પત્ર, આધાર અને ડિજિટલ પેમેન્ટ ઉપલબ્ધ કરાવતું સરકારી કેન્દ્ર છે."
        ),
    }
]


async def ensure_glossary_indexed(db: AsyncSession) -> int:
    """Ensure Schemora authoritative glossary concepts are indexed into PostgreSQL + pgvector.

    Returns count of indexed concept chunks.
    """
    try:
        existing_doc_res = await db.execute(
            select(KnowledgeDocument).where(KnowledgeDocument.id == GLOSSARY_DOC_ID)
        )
        existing_doc = existing_doc_res.scalar_one_or_none()

        if not existing_doc:
            doc = KnowledgeDocument(
                id=GLOSSARY_DOC_ID,
                scheme_id=None,
                title="Schemora Authoritative Glossary & Concept Knowledge Base",
                source_url="https://www.myscheme.gov.in",
                doc_type="Glossary",
                file_hash="glossary_v3_hash",
            )
            db.add(doc)
            await db.flush()
        else:
            doc = existing_doc

        indexed_count = 0
        for idx, concept in enumerate(GLOSSARY_CONCEPTS):
            chunk_id = f"chunk-glossary-{concept['key']}"

            existing_chunk_res = await db.execute(
                select(KnowledgeChunk).where(KnowledgeChunk.id == chunk_id)
            )
            existing_chunk = existing_chunk_res.scalar_one_or_none()

            content = concept["content"]
            embedding, is_semantic = await embed_text(content)

            if not existing_chunk:
                chunk_obj = KnowledgeChunk(
                    id=chunk_id,
                    document_id=doc.id,
                    scheme_id=GLOSSARY_SCHEME_ID,
                    chunk_index=idx,
                    content=content,
                    section="concept",
                    scheme_name="Schemora Knowledge Glossary",
                    jurisdiction="Central / All States",
                    state=None,
                    category="Glossary",
                    source_id=concept["key"],
                    official_info_url="https://www.myscheme.gov.in",
                    official_app_url="https://www.myscheme.gov.in",
                    last_verified_at="2026-09-16",
                    scheme_version="v1",
                    embedding_json=embedding_to_json(embedding),
                    embedding_vec=embedding if (is_semantic and isinstance(embedding, list)) else None,
                    metadata_json=f'{{"concept_key": "{concept["key"]}", "title": "{concept["title"]}"}}',
                    is_indexed=is_semantic,
                    page_number=1,
                )
                db.add(chunk_obj)
                indexed_count += 1
            else:
                existing_chunk.content = content
                existing_chunk.section = "concept"
                existing_chunk.category = "Glossary"
                existing_chunk.scheme_name = "Schemora Knowledge Glossary"
                existing_chunk.embedding_json = embedding_to_json(embedding)
                if is_semantic and isinstance(embedding, list):
                    existing_chunk.embedding_vec = embedding
                    existing_chunk.is_indexed = True
                indexed_count += 1

        await db.commit()
        logger.info(f"Schemora Glossary: {indexed_count} authoritative concept chunks indexed into Knowledge Base.")
        return indexed_count
    except Exception as e:
        logger.error(f"Failed to index Schemora Glossary: {e}")
        await db.rollback()
        return 0
