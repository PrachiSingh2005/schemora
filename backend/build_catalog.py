import json
from pathlib import Path

# Target output dataset path
DATASET_PATH = Path(r"d:\Schemora\data\schemes\schemes.v1.json")

schemes_catalog = [
    {
        "scheme_id": "sch-central-csss-001",
        "scheme_name": "Central Sector Scheme of Scholarship for College and University Students",
        "scheme_version": "2026-08-07-v1",
        "short_description": "Central scholarship support for eligible college and university students across India.",
        "description": "Implemented by the Ministry of Education through the National Scholarship Portal (NSP). Provides financial assistance to meritorious students from low-income families to meet day-to-day expenses while pursuing higher studies.",
        "jurisdiction": "Central",
        "state": None,
        "department": "Department of Higher Education",
        "ministry": "Ministry of Education",
        "scheme_category": "Scholarship",
        "target_beneficiaries": "College and University Students",
        "gender_eligibility": "All",
        "social_categories": "SC, ST, OBC, General, EWS",
        "age_requirements": "18 to 25 years",
        "income_requirements": "Family annual income up to Rs 4.5 Lakh",
        "occupation_requirements": "Regular Student in recognized College/University",
        "location_requirements": "All India",
        "benefits": [
            {
                "benefit_id": "csss-benefit-1",
                "description": "Scholarship of Rs 12,000 per annum at Graduation level for first 3 years and Rs 20,000 per annum at Post-Graduation level.",
                "amount": 12000,
                "currency": "INR",
                "frequency": "Annual",
                "verification_status": "Verified"
            }
        ],
        "eligibility_rules": {
            "rules_version": "v1",
            "root": {
                "rule_id": "csss-g001",
                "type": "and",
                "description": "Mandatory eligibility criteria for CSSS.",
                "conditions": [
                    {"type": "condition", "description": "Applicant must be in the top 80th percentile of successful candidates in Class 12 board exams.", "verification_status": "Verified"},
                    {"type": "condition", "description": "Gross annual family income must not exceed Rs 4.5 Lakh per annum.", "verification_status": "Verified"},
                    {"type": "condition", "description": "Pursuing regular courses (not correspondence or distance mode) in recognized colleges/universities.", "verification_status": "Verified"},
                    {"type": "condition", "description": "Not receiving any other government scholarship or fee reimbursement.", "verification_status": "Verified"}
                ]
            }
        },
        "required_documents": [
            {"name": "Aadhaar Card", "required": True, "verification_status": "Verified"},
            {"name": "Class 12 Marksheet & Passing Certificate", "required": True, "verification_status": "Verified"},
            {"name": "Income Certificate issued by competent authority", "required": True, "verification_status": "Verified"},
            {"name": "Bank Account Passbook (linked with Aadhaar)", "required": True, "verification_status": "Verified"},
            {"name": "Proof of Admission / Bonafide Student Certificate", "required": True, "verification_status": "Verified"}
        ],
        "application_process": [
            {"step_number": 1, "channel": "National Scholarship Portal", "description": "Register on the National Scholarship Portal (scholarships.gov.in) using OTR/Aadhaar."},
            {"step_number": 2, "channel": "Online Portal", "description": "Fill the application form for Central Sector Scheme of Scholarship."},
            {"step_number": 3, "channel": "Online Portal", "description": "Upload scanned copies of required documents including income certificate and marksheet."},
            {"step_number": 4, "channel": "Institute Verification", "description": "Submit form online for institute-level electronic verification."},
            {"step_number": 5, "channel": "Direct Benefit Transfer", "description": "Upon state nodal officer approval, scholarship is disbursed directly to applicant bank account via DBT."}
        ],
        "official_information_url": "https://www.myscheme.gov.in/schemes/csss",
        "official_application_url": "https://scholarships.gov.in/",
        "faqs": [
            {"question": "Can distance education students apply?", "answer": "No, only regular students pursuing full-time degree courses in recognized colleges are eligible."},
            {"question": "What is the maximum income limit?", "answer": "The annual family income limit is Rs 4.5 Lakh per annum."}
        ],
        "last_verified_at": "2026-08-20",
        "status": "Active"
    },
    {
        "scheme_id": "sch-central-pmkisan-002",
        "scheme_name": "Pradhan Mantri Kisan Samman Nidhi (PM-KISAN)",
        "scheme_version": "2026-08-07-v1",
        "short_description": "Direct income support of Rs 6,000 per year to landholding farmer families across India.",
        "description": "PM-KISAN is a Central Sector Scheme providing income support to all landholding farmer families in the country to supplement their financial needs for procuring agricultural inputs and domestic needs.",
        "jurisdiction": "Central",
        "state": None,
        "department": "Department of Agriculture and Farmers Welfare",
        "ministry": "Ministry of Agriculture and Farmers Welfare",
        "scheme_category": "Agriculture",
        "target_beneficiaries": "Landholding Farmer Families",
        "gender_eligibility": "All",
        "social_categories": "SC, ST, OBC, General, EWS",
        "age_requirements": "18 years and above",
        "income_requirements": "Farmer families with cultivable landholding (excluding income-tax payers and high economic status holders)",
        "occupation_requirements": "Landholding Farmer",
        "location_requirements": "All India",
        "benefits": [
            {
                "benefit_id": "pmkisan-benefit-1",
                "description": "Financial benefit of Rs 6,000 per year payable in three equal installments of Rs 2,000 every four months.",
                "amount": 6000,
                "currency": "INR",
                "frequency": "Annual (3 installments)",
                "verification_status": "Verified"
            }
        ],
        "eligibility_rules": {
            "rules_version": "v1",
            "root": {
                "rule_id": "pmkisan-g001",
                "type": "and",
                "description": "Eligibility conditions for PM-KISAN.",
                "conditions": [
                    {"type": "condition", "description": "Farmer family owning cultivable land registered in state land records.", "verification_status": "Verified"},
                    {"type": "condition", "description": "Must complete e-KYC via Aadhaar-linked OTP or biometric verification.", "verification_status": "Verified"},
                    {"type": "condition", "description": "Institutional landholders, serving/retired government officers, and income tax payers in last assessment year are excluded.", "verification_status": "Verified"}
                ]
            }
        },
        "required_documents": [
            {"name": "Aadhaar Card", "required": True, "verification_status": "Verified"},
            {"name": "Landholding Document / Khatauni / Jamabandi", "required": True, "verification_status": "Verified"},
            {"name": "Bank Account Details (Aadhaar Seeded)", "required": True, "verification_status": "Verified"},
            {"name": "Mobile Number registered with Aadhaar", "required": True, "verification_status": "Verified"}
        ],
        "application_process": [
            {"step_number": 1, "channel": "PM-KISAN Portal / Mobile App / CSC", "description": "Visit pmkisan.gov.in or nearest Common Service Centre (CSC)."},
            {"step_number": 2, "channel": "Online Portal", "description": "Click on 'Farmers Corner' -> 'New Farmer Registration'."},
            {"step_number": 3, "channel": "Online Portal", "description": "Enter Aadhaar number, state, land details, and bank account information."},
            {"step_number": 4, "channel": "Verification", "description": "Application verified electronically by local revenue officer / Nodal Officer."},
            {"step_number": 5, "channel": "DBT Transfer", "description": "Installments credited directly to Aadhaar-seeded bank account."}
        ],
        "official_information_url": "https://www.myscheme.gov.in/schemes/pm-kisan",
        "official_application_url": "https://pmkisan.gov.in/",
        "faqs": [
            {"question": "How much financial support is provided?", "answer": "Rs 6,000 per year transferred in 3 equal installments of Rs 2,000 each."},
            {"question": "Is e-KYC compulsory?", "answer": "Yes, e-KYC is mandatory for receiving PM-KISAN installments."}
        ],
        "last_verified_at": "2026-08-20",
        "status": "Active"
    },
    {
        "scheme_id": "sch-central-sukanya-003",
        "scheme_name": "Sukanya Samriddhi Yojana (SSY)",
        "scheme_version": "2026-08-07-v1",
        "short_description": "Small deposit savings scheme for girl children with attractive interest rate and tax benefits.",
        "description": "Launched under the Beti Bachao Beti Padhao campaign, Sukanya Samriddhi Yojana encourages parents to build a fund for the future education and marriage expenses of their female child.",
        "jurisdiction": "Central",
        "state": None,
        "department": "Department of Posts / Department of Economic Affairs",
        "ministry": "Ministry of Finance",
        "scheme_category": "Women & Child Development",
        "target_beneficiaries": "Girl Child (up to 10 years of age)",
        "gender_eligibility": "Female",
        "social_categories": "SC, ST, OBC, General, EWS",
        "age_requirements": "Below 10 years of age at the time of account opening",
        "income_requirements": "No income limit",
        "occupation_requirements": "Parents/Legal Guardians of Girl Child",
        "location_requirements": "All India",
        "benefits": [
            {
                "benefit_id": "ssy-benefit-1",
                "description": "High interest rate (currently 8.2% per annum compounded annually) with tax exemption under Section 80C and triple-tax-free status (EEE).",
                "amount": None,
                "currency": "INR",
                "frequency": "Maturity / Annual Interest",
                "verification_status": "Verified"
            }
        ],
        "eligibility_rules": {
            "rules_version": "v1",
            "root": {
                "rule_id": "ssy-g001",
                "type": "and",
                "description": "Eligibility conditions for Sukanya Samriddhi Yojana.",
                "conditions": [
                    {"type": "condition", "description": "Account can be opened by natural or legal guardian in the name of a girl child from birth till age of 10 years.", "verification_status": "Verified"},
                    {"type": "condition", "description": "Only one account per girl child, and maximum 2 girl children per family (exceptions for twins/triplets).", "verification_status": "Verified"},
                    {"type": "condition", "description": "Minimum deposit Rs 250 and maximum Rs 1.5 Lakh in a financial year.", "verification_status": "Verified"}
                ]
            }
        },
        "required_documents": [
            {"name": "Birth Certificate of Girl Child", "required": True, "verification_status": "Verified"},
            {"name": "Identity Proof of Parent/Guardian (Aadhaar / PAN Card)", "required": True, "verification_status": "Verified"},
            {"name": "Address Proof of Guardian", "required": True, "verification_status": "Verified"},
            {"name": "Passport size photographs of child and guardian", "required": True, "verification_status": "Verified"}
        ],
        "application_process": [
            {"step_number": 1, "channel": "Post Office / Authorized Banks", "description": "Visit any Post Office branch or authorized public/private sector commercial bank."},
            {"step_number": 2, "channel": "Application Form", "description": "Fill Sukanya Samriddhi Account Opening Form."},
            {"step_number": 3, "channel": "Document Submission", "description": "Submit filled form along with birth certificate of girl child and guardian KYC documents."},
            {"step_number": 4, "channel": "Initial Deposit", "description": "Deposit initial amount (minimum Rs 250) via cash, cheque, or demand draft."},
            {"step_number": 5, "channel": "Passbook Issuance", "description": "Bank/Post Office issues account passbook recording deposits and interest."}
        ],
        "official_information_url": "https://www.myscheme.gov.in/schemes/ssy",
        "official_application_url": "https://www.indiapost.gov.in/",
        "faqs": [
            {"question": "What is the age limit for girl child?", "answer": "Account must be opened before the girl child attains 10 years of age."},
            {"question": "When does the account mature?", "answer": "Matures after 21 years from account opening or upon marriage after age 18."}
        ],
        "last_verified_at": "2026-08-20",
        "status": "Active"
    },
    {
        "scheme_id": "sch-central-pmmudra-004",
        "scheme_name": "Pradhan Mantri MUDRA Yojana (PMMY)",
        "scheme_version": "2026-08-07-v1",
        "short_description": "Collateral-free loans up to Rs 20 Lakh for non-corporate, non-farm small and micro enterprises.",
        "description": "PMMY provides institutional micro-credit to small business entrepreneurs for income-generating activities in manufacturing, trading, service sectors, and agriculture-allied activities across Shishu, Kishore, Tarun, and Tarun Plus categories.",
        "jurisdiction": "Central",
        "state": None,
        "department": "Department of Financial Services",
        "ministry": "Ministry of Finance",
        "scheme_category": "Business & MSME",
        "target_beneficiaries": "Micro Entrepreneurs, Small Business Owners, Street Vendors, Artisans",
        "gender_eligibility": "All",
        "social_categories": "SC, ST, OBC, General, EWS",
        "age_requirements": "18 years and above",
        "income_requirements": "No prior income threshold; creditworthiness for business proposal",
        "occupation_requirements": "Micro Entrepreneur / Self-Employed / Small Retailer",
        "location_requirements": "All India",
        "benefits": [
            {
                "benefit_id": "mudra-benefit-1",
                "description": "Collateral-free business loan: Shishu (up to Rs 50,000), Kishore (Rs 50,000 to Rs 5 Lakh), Tarun (Rs 5 Lakh to Rs 10 Lakh), Tarun Plus (up to Rs 20 Lakh for previous successful repayment).",
                "amount": 2000000,
                "currency": "INR",
                "frequency": "One-time / Term Loan / Working Capital",
                "verification_status": "Verified"
            }
        ],
        "eligibility_rules": {
            "rules_version": "v1",
            "root": {
                "rule_id": "mudra-g001",
                "type": "and",
                "description": "Eligibility conditions for PMMY.",
                "conditions": [
                    {"type": "condition", "description": "Any Indian citizen with a viable business plan for non-farm income-generating activity.", "verification_status": "Verified"},
                    {"type": "condition", "description": "Must not be a defaulter to any financial institution/bank.", "verification_status": "Verified"},
                    {"type": "condition", "description": "Loan extended through Banks, NBFCs, and MFIs without requirement of collateral security.", "verification_status": "Verified"}
                ]
            }
        },
        "required_documents": [
            {"name": "Identity Proof (Aadhaar / Voter ID / PAN Card)", "required": True, "verification_status": "Verified"},
            {"name": "Proof of Residence", "required": True, "verification_status": "Verified"},
            {"name": "Business Plan / Project Proposal / Quotation for machinery", "required": True, "verification_status": "Verified"},
            {"name": "Bank Statement for last 6 months", "required": True, "verification_status": "Verified"},
            {"name": "Proof of Business Identity / Registration (GST / Udyam Certificate if available)", "required": False, "verification_status": "Verified"}
        ],
        "application_process": [
            {"step_number": 1, "channel": "JanSamarth Portal / Bank Branch", "description": "Visit jansamarth.in or approach commercial bank / RRB / MFI."},
            {"step_number": 2, "channel": "Online Application", "description": "Select MUDRA category (Shishu, Kishore, or Tarun) and fill JanSamarth application."},
            {"step_number": 3, "channel": "Business Detail Submission", "description": "Enter proposed business activity, loan requirement, and upload identity/address proof."},
            {"step_number": 4, "channel": "Bank Verification", "description": "Bank reviews business feasibility and credit check."},
            {"step_number": 5, "channel": "Sanction & Disbursal", "description": "Loan sanctioned and MUDRA Card issued for working capital withdrawals."}
        ],
        "official_information_url": "https://www.myscheme.gov.in/schemes/pmmy",
        "official_application_url": "https://www.jansamarth.in/",
        "faqs": [
            {"question": "Is collateral needed for MUDRA loan?", "answer": "No collateral is required for MUDRA loans."},
            {"question": "What are the loan limits?", "answer": "Shishu: up to Rs 50k; Kishore: Rs 50k-5L; Tarun: Rs 5L-10L; Tarun Plus: up to Rs 20L."}
        ],
        "last_verified_at": "2026-08-20",
        "status": "Active"
    },
    {
        "scheme_id": "sch-central-pmjay-005",
        "scheme_name": "Ayushman Bharat - Pradhan Mantri Jan Arogya Yojana (PM-JAY)",
        "scheme_version": "2026-08-07-v1",
        "short_description": "Health insurance cover of Rs 5 Lakh per family per year for secondary and tertiary hospitalization.",
        "description": "PM-JAY is the world's largest government-funded health assurance scheme. It provides cashless and paperless access to healthcare services for poor and vulnerable families across empanelled public and private hospitals in India.",
        "jurisdiction": "Central",
        "state": None,
        "department": "National Health Authority",
        "ministry": "Ministry of Health and Family Welfare",
        "scheme_category": "Health & Healthcare",
        "target_beneficiaries": "Poor and Vulnerable Families, Senior Citizens aged 70+",
        "gender_eligibility": "All",
        "social_categories": "SC, ST, OBC, General, EWS",
        "age_requirements": "All ages (Special Universal Cover for Senior Citizens aged 70 and above)",
        "income_requirements": "Families identified based on SECC 2011 deprivation criteria or Ayushman Vaya Vandana Card holders",
        "occupation_requirements": "Informal Workers, Daily Wagers, Rural Poor, Urban Occupational Categories",
        "location_requirements": "All India",
        "benefits": [
            {
                "benefit_id": "pmjay-benefit-1",
                "description": "Cashless health cover up to Rs 500,000 per family per year for 1,900+ medical procedures across empanelled hospitals.",
                "amount": 500000,
                "currency": "INR",
                "frequency": "Annual per family",
                "verification_status": "Verified"
            }
        ],
        "eligibility_rules": {
            "rules_version": "v1",
            "root": {
                "rule_id": "pmjay-g001",
                "type": "and",
                "description": "Eligibility criteria for Ayushman Bharat PM-JAY.",
                "conditions": [
                    {"type": "condition", "description": "Families listed in SECC 2011 database or RSBY cardholders.", "verification_status": "Verified"},
                    {"type": "condition", "description": "All senior citizens aged 70 years and above (irrespective of income) under Ayushman Vaya Vandana.", "verification_status": "Verified"},
                    {"type": "condition", "description": "No restriction on family size or age of members.", "verification_status": "Verified"}
                ]
            }
        },
        "required_documents": [
            {"name": "Aadhaar Card", "required": True, "verification_status": "Verified"},
            {"name": "Ration Card / Family Proof", "required": True, "verification_status": "Verified"},
            {"name": "Mobile Number", "required": True, "verification_status": "Verified"}
        ],
        "application_process": [
            {"step_number": 1, "channel": "Ayushman App / Portal / PMJAY Kiosk", "description": "Check eligibility on beneficiary.nha.gov.in or Ayushman App."},
            {"step_number": 2, "channel": "e-KYC", "description": "Perform self-eKYC using Aadhaar OTP or facial authentication."},
            {"step_number": 3, "channel": "Ayushman Card Download", "description": "Upon approval, download the digital Ayushman Card."},
            {"step_number": 4, "channel": "Hospitalization", "description": "Present Ayushman Card at empanelled hospital for cashless treatment."}
        ],
        "official_information_url": "https://www.myscheme.gov.in/schemes/pm-jay",
        "official_application_url": "https://beneficiary.nha.gov.in/",
        "faqs": [
            {"question": "How much health cover is provided?", "answer": "Rs 5 Lakh per family per year for hospitalization."},
            {"question": "Are pre-existing diseases covered?", "answer": "Yes, all pre-existing medical conditions are covered from Day 1."}
        ],
        "last_verified_at": "2026-08-20",
        "status": "Active"
    },
    {
        "scheme_id": "sch-central-apy-006",
        "scheme_name": "Atal Pension Yojana (APY)",
        "scheme_version": "2026-08-07-v1",
        "short_description": "Guaranteed monthly pension of Rs 1,000 to Rs 5,000 for unorganized sector workers.",
        "description": "Atal Pension Yojana is a government-backed pension scheme targeted at unorganized sector workers to provide financial security in old age with guaranteed minimum monthly pension options.",
        "jurisdiction": "Central",
        "state": None,
        "department": "PFRDA / Department of Financial Services",
        "ministry": "Ministry of Finance",
        "scheme_category": "Senior Citizen & Pension",
        "target_beneficiaries": "Unorganized Sector Workers, Self-Employed Citizens",
        "gender_eligibility": "All",
        "social_categories": "SC, ST, OBC, General, EWS",
        "age_requirements": "18 to 40 years at entry",
        "income_requirements": "Non-income tax payer",
        "occupation_requirements": "Unorganized Sector Worker",
        "location_requirements": "All India",
        "benefits": [
            {
                "benefit_id": "apy-benefit-1",
                "description": "Guaranteed monthly pension of Rs 1,000, Rs 2,000, Rs 3,000, Rs 4,000, or Rs 5,000 starting at age 60, followed by spouse pension and corpus payout to nominee.",
                "amount": 5000,
                "currency": "INR",
                "frequency": "Monthly after age 60",
                "verification_status": "Verified"
            }
        ],
        "eligibility_rules": {
            "rules_version": "v1",
            "root": {
                "rule_id": "apy-g001",
                "type": "and",
                "description": "Eligibility conditions for APY.",
                "conditions": [
                    {"type": "condition", "description": "Indian citizen aged between 18 and 40 years.", "verification_status": "Verified"},
                    {"type": "condition", "description": "Must have a savings bank account linked with mobile and Aadhaar.", "verification_status": "Verified"},
                    {"type": "condition", "description": "Must not be an income tax payer.", "verification_status": "Verified"}
                ]
            }
        },
        "required_documents": [
            {"name": "Aadhaar Card", "required": True, "verification_status": "Verified"},
            {"name": "Savings Bank Account / Post Office Account details", "required": True, "verification_status": "Verified"},
            {"name": "Mobile Number", "required": True, "verification_status": "Verified"}
        ],
        "application_process": [
            {"step_number": 1, "channel": "Bank Branch / Net Banking", "description": "Approach bank branch where savings account is maintained or log into net banking."},
            {"step_number": 2, "channel": "APY Form", "description": "Fill APY registration form specifying pension choice (Rs 1,000 to Rs 5,000)."},
            {"step_number": 3, "channel": "Auto-Debit Authorization", "description": "Provide auto-debit consent for monthly/quarterly premium deduction."},
            {"step_number": 4, "channel": "PRAN Generation", "description": "PFRDA generates Permanent Retirement Account Number (PRAN)."}
        ],
        "official_information_url": "https://www.myscheme.gov.in/schemes/apy",
        "official_application_url": "https://www.pfrda.org.in/",
        "faqs": [
            {"question": "What is the entry age?", "answer": "Citizen must be between 18 and 40 years old."},
            {"question": "Can income tax payers join?", "answer": "No, citizens who pay income tax are not eligible to join APY."}
        ],
        "last_verified_at": "2026-08-20",
        "status": "Active"
    },
    {
        "scheme_id": "sch-state-mahadbt-007",
        "scheme_name": "Post Matric Scholarship to OBC Students (Maharashtra Mahadbt)",
        "scheme_version": "2026-08-07-v1",
        "short_description": "Post-matric educational tuition and maintenance allowance for OBC students in Maharashtra.",
        "description": "State scheme implemented by the Other Backward Bahujan Welfare Department, Government of Maharashtra. Reimburses tuition fees, exam fees, and maintenance allowance to eligible OBC students.",
        "jurisdiction": "State",
        "state": "Maharashtra",
        "department": "Other Backward Bahujan Welfare Department",
        "ministry": "Government of Maharashtra",
        "scheme_category": "Scholarship",
        "target_beneficiaries": "OBC Post-Matric Students residing in Maharashtra",
        "gender_eligibility": "All",
        "social_categories": "OBC",
        "age_requirements": "Post-matric age group (Class 11 to PhD)",
        "income_requirements": "Annual family income up to Rs 1.00 Lakh (full scholarship) or up to Rs 8.00 Lakh (tuition fee waiver)",
        "occupation_requirements": "Student pursuing post-matric courses in Maharashtra",
        "location_requirements": "Domicile of Maharashtra State",
        "benefits": [
            {
                "benefit_id": "mahadbt-obc-1",
                "description": "100% Tuition Fee & Examination Fee reimbursement plus monthly maintenance allowance up to Rs 425 per month for day scholars / Rs 750 for hostellers.",
                "amount": 10000,
                "currency": "INR",
                "frequency": "Academic Year",
                "verification_status": "Verified"
            }
        ],
        "eligibility_rules": {
            "rules_version": "v1",
            "root": {
                "rule_id": "mahadbt-g001",
                "type": "and",
                "description": "Eligibility conditions for Maharashtra OBC Post Matric Scholarship.",
                "conditions": [
                    {"type": "condition", "description": "Applicant must belong to OBC category and be a resident domicile of Maharashtra.", "verification_status": "Verified"},
                    {"type": "condition", "description": "Annual family income must not exceed Rs 1.00 Lakh for maintenance allowance and Rs 8.00 Lakh for fee waiver.", "verification_status": "Verified"},
                    {"type": "condition", "description": "Admitted to recognized post-matric course in Maharashtra.", "verification_status": "Verified"}
                ]
            }
        },
        "required_documents": [
            {"name": "Maharashtra Domicile Certificate", "required": True, "verification_status": "Verified"},
            {"name": "OBC Caste Certificate issued by Maharashtra authority", "required": True, "verification_status": "Verified"},
            {"name": "Income Certificate issued by Tehsildar", "required": True, "verification_status": "Verified"},
            {"name": "Marksheet of Previous Examination Passed", "required": True, "verification_status": "Verified"},
            {"name": "Fee Receipt & College Bonafide Certificate", "required": True, "verification_status": "Verified"},
            {"name": "Aadhaar Card linked to Bank Account", "required": True, "verification_status": "Verified"}
        ],
        "application_process": [
            {"step_number": 1, "channel": "MahaDBT Portal", "description": "Visit mahadbt.maharashtra.gov.in and click 'New Applicant Registration'."},
            {"step_number": 2, "channel": "Aadhaar e-KYC", "description": "Authenticate profile using Aadhaar OTP or biometric scan."},
            {"step_number": 3, "channel": "Profile Filling", "description": "Fill personal, caste, income, domicile, and academic course details."},
            {"step_number": 4, "channel": "Scheme Selection", "description": "Select 'Post Matric Scholarship to OBC Students' under VJNT, OBC and SBC Welfare Department."},
            {"step_number": 5, "channel": "Upload & Submit", "description": "Upload documents and submit to college for scrutinization."}
        ],
        "official_information_url": "https://www.myscheme.gov.in/schemes/mahadbt-obc-scholarship",
        "official_application_url": "https://mahadbt.maharashtra.gov.in/",
        "faqs": [
            {"question": "What is the family income limit for OBC scholarship in Maharashtra?", "answer": "Up to Rs 1 Lakh for maintenance allowance; up to Rs 8 Lakh for tuition fee waiver."},
            {"question": "Is Maharashtra domicile required?", "answer": "Yes, Maharashtra domicile certificate is mandatory."}
        ],
        "last_verified_at": "2026-08-20",
        "status": "Active"
    },
    {
        "scheme_id": "sch-state-gujarat-mysy-008",
        "scheme_name": "Mukhyamantri Yuva Swavalamban Yojana (MYSY Gujarat)",
        "scheme_version": "2026-08-07-v1",
        "short_description": "Financial scholarship support for higher education students in Gujarat.",
        "description": "MYSY is a flagship Gujarat State government scheme providing financial assistance for tuition fees, hostel allowance, and book equipment grants to meritorious students pursuing Diploma, Bachelor's, and Professional degrees.",
        "jurisdiction": "State",
        "state": "Gujarat",
        "department": "Education Department",
        "ministry": "Government of Gujarat",
        "scheme_category": "Scholarship",
        "target_beneficiaries": "Students pursuing Higher Education in Gujarat",
        "gender_eligibility": "All",
        "social_categories": "SC, ST, OBC, General, EWS",
        "age_requirements": "Below 25 years",
        "income_requirements": "Annual family income up to Rs 6.00 Lakh",
        "occupation_requirements": "Student with 80+ percentile in 10th/12th or 65+ percentile in Diploma",
        "location_requirements": "Domicile of Gujarat State",
        "benefits": [
            {
                "benefit_id": "mysy-benefit-1",
                "description": "50% tuition fee grant (up to Rs 2.00 Lakh/year for Medical/Dental, Rs 50,000 for Engineering), plus Rs 1,200/month hostel allowance and Rs 10,000 book/equipment grant.",
                "amount": 200000,
                "currency": "INR",
                "frequency": "Annual",
                "verification_status": "Verified"
            }
        ],
        "eligibility_rules": {
            "rules_version": "v1",
            "root": {
                "rule_id": "mysy-g001",
                "type": "and",
                "description": "Eligibility criteria for MYSY Gujarat.",
                "conditions": [
                    {"type": "condition", "description": "Student must have secured 80 or more percentile in 10th/12th board exams or 65+ percentile in Diploma.", "verification_status": "Verified"},
                    {"type": "condition", "description": "Annual family income must be less than or equal to Rs 6,00,000 per annum.", "verification_status": "Verified"},
                    {"type": "condition", "description": "Must be a domicile resident of Gujarat State studying in recognized college.", "verification_status": "Verified"}
                ]
            }
        },
        "required_documents": [
            {"name": "Gujarat Domicile Certificate", "required": True, "verification_status": "Verified"},
            {"name": "Income Certificate issued by Mamlatdar / TDO", "required": True, "verification_status": "Verified"},
            {"name": "10th / 12th / Diploma Marksheet showing Percentile", "required": True, "verification_status": "Verified"},
            {"name": "College Admission Letter & Fee Receipt", "required": True, "verification_status": "Verified"},
            {"name": "Bank Passbook linked with Aadhaar", "required": True, "verification_status": "Verified"}
        ],
        "application_process": [
            {"step_number": 1, "channel": "MYSY Gujarat Portal", "description": "Visit mysy.guj.nic.in and click 'Fresh Application'."},
            {"step_number": 2, "channel": "Registration", "description": "Register with board, passing year, seat number, and mobile number."},
            {"step_number": 3, "channel": "Form Filling", "description": "Fill personal, family income, and college course details."},
            {"step_number": 4, "channel": "Document Upload & Help Center", "description": "Upload documents online and verify physical documents at designated Help Center."},
            {"step_number": 5, "channel": "DBT Sanction", "description": "Scholarship disbursed directly to student bank account."}
        ],
        "official_information_url": "https://www.myscheme.gov.in/schemes/mysy-gujarat",
        "official_application_url": "https://mysy.guj.nic.in/",
        "faqs": [
            {"question": "What is the percentile criteria for MYSY?", "answer": "80 or above percentile in Class 10/12, or 65+ percentile for Diploma students."},
            {"question": "What is the family income limit for MYSY?", "answer": "Up to Rs 6 Lakh per annum."}
        ],
        "last_verified_at": "2026-08-20",
        "status": "Active"
    },
    {
        "scheme_id": "sch-central-pmis-009",
        "scheme_name": "PM Internship Scheme (PMIS)",
        "scheme_version": "2026-08-07-v1",
        "short_description": "Paid 12-month internships in top 500 companies for youth aged 21 to 24.",
        "description": "Under Ministry of Corporate Affairs / MY Bharat platform, PMIS offers young graduates and diploma holders hands-on corporate exposure with a monthly stipend of Rs 5,000 and one-time grant of Rs 6,000.",
        "jurisdiction": "Central",
        "state": None,
        "department": "Department of Youth Affairs / Ministry of Corporate Affairs",
        "ministry": "Ministry of Corporate Affairs",
        "scheme_category": "Skill & Employment",
        "target_beneficiaries": "Youth aged 21 to 24 with Higher Secondary, ITI, Diploma, or BA/BSc/BCom degrees",
        "gender_eligibility": "All",
        "social_categories": "SC, ST, OBC, General, EWS",
        "age_requirements": "21 to 24 years",
        "income_requirements": "Family income not exceeding Rs 8 Lakh per annum; no family member in government service",
        "occupation_requirements": "Unemployed Youth pursuing internship",
        "location_requirements": "All India",
        "benefits": [
            {
                "benefit_id": "pmis-benefit-1",
                "description": "Monthly stipend of Rs 5,000 (Rs 4,500 from Govt + Rs 500 from Company CSR) for 12 months, plus one-time incidentals grant of Rs 6,000.",
                "amount": 66000,
                "currency": "INR",
                "frequency": "Monthly + One-time grant",
                "verification_status": "Verified"
            }
        ],
        "eligibility_rules": {
            "rules_version": "v1",
            "root": {
                "rule_id": "pmis-g001",
                "type": "and",
                "description": "Eligibility criteria for PM Internship Scheme.",
                "conditions": [
                    {"type": "condition", "description": "Applicant age must be between 21 and 24 years.", "verification_status": "Verified"},
                    {"type": "condition", "description": "Educational qualification: Passed Higher Secondary (10+2), ITI, Diploma, or undergraduate degrees (BA, BSc, BCom, BBA, BCA, BPharma).", "verification_status": "Verified"},
                    {"type": "condition", "description": "IIT, IIM, IISER, CA, CMA, CS, MBBS, BDS, MBA, Master's degree holders are NOT eligible.", "verification_status": "Verified"},
                    {"type": "condition", "description": "Family income must be below Rs 8.00 Lakh per annum.", "verification_status": "Verified"}
                ]
            }
        },
        "required_documents": [
            {"name": "Aadhaar Card", "required": True, "verification_status": "Verified"},
            {"name": "Educational Certificates & Marksheets (10th, 12th, ITI/Diploma/Degree)", "required": True, "verification_status": "Verified"},
            {"name": "Self-Declaration of Family Income (< Rs 8 Lakh)", "required": True, "verification_status": "Verified"},
            {"name": "Bank Account Details (Aadhaar Seeded)", "required": True, "verification_status": "Verified"}
        ],
        "application_process": [
            {"step_number": 1, "channel": "PM Internship Portal", "description": "Visit pminternship.mca.gov.in or mybharat.gov.in."},
            {"step_number": 2, "channel": "Registration", "description": "Register using mobile number and complete e-KYC using Aadhaar."},
            {"step_number": 3, "channel": "Profile & Resume", "description": "Fill educational details, skill preferences, and locations."},
            {"step_number": 4, "channel": "Internship Selection", "description": "Select up to 5 internship options across participating companies."},
            {"step_number": 5, "channel": "Offer Letter", "description": "Companies shortlist candidates and issue digital offer letter."}
        ],
        "official_information_url": "https://www.myscheme.gov.in/schemes/pmis",
        "official_application_url": "https://pminternship.mca.gov.in/",
        "faqs": [
            {"question": "What is the monthly stipend for PM Internship Scheme?", "answer": "Rs 5,000 per month for 12 months, plus Rs 6,000 one-time grant."},
            {"question": "Are post-graduates eligible?", "answer": "No, post-graduates and Master's degree holders are excluded."}
        ],
        "last_verified_at": "2026-08-20",
        "status": "Active"
    },
    {
        "scheme_id": "sch-state-maharashtra-ladki-bahin-010",
        "scheme_name": "Mukhyamantri Majhi Ladki Bahin Yojana (Maharashtra)",
        "scheme_version": "2026-08-07-v1",
        "short_description": "Monthly financial assistance of Rs 1,500 for eligible women in Maharashtra.",
        "description": "Flagship welfare initiative of the Government of Maharashtra providing direct cash transfers to women aged 21 to 65 years to foster financial independence, nutrition, and empowerment.",
        "jurisdiction": "State",
        "state": "Maharashtra",
        "department": "Women and Child Development Department",
        "ministry": "Government of Maharashtra",
        "scheme_category": "Women & Child Development",
        "target_beneficiaries": "Married, Divorced, Widowed, and Single Women in Maharashtra",
        "gender_eligibility": "Female",
        "social_categories": "SC, ST, OBC, General, EWS",
        "age_requirements": "21 to 65 years",
        "income_requirements": "Annual family income up to Rs 2.50 Lakh (or Yellow/Orange Ration Card holders)",
        "occupation_requirements": "Non-income tax paying households",
        "location_requirements": "Domicile resident of Maharashtra State",
        "benefits": [
            {
                "benefit_id": "ladki-bahin-benefit-1",
                "description": "Monthly financial assistance of Rs 1,500 transferred directly into beneficiary Aadhaar-linked bank account via DBT.",
                "amount": 18000,
                "currency": "INR",
                "frequency": "Monthly (Rs 1,500/month)",
                "verification_status": "Verified"
            }
        ],
        "eligibility_rules": {
            "rules_version": "v1",
            "root": {
                "rule_id": "ladki-bahin-g001",
                "type": "and",
                "description": "Eligibility criteria for Majhi Ladki Bahin Yojana.",
                "conditions": [
                    {"type": "condition", "description": "Woman applicant must be a resident of Maharashtra state aged 21 to 65 years.", "verification_status": "Verified"},
                    {"type": "condition", "description": "Annual family income must not exceed Rs 2.50 Lakh.", "verification_status": "Verified"},
                    {"type": "condition", "description": "No family member should be a permanent government employee or income tax payer.", "verification_status": "Verified"}
                ]
            }
        },
        "required_documents": [
            {"name": "Aadhaar Card", "required": True, "verification_status": "Verified"},
            {"name": "Maharashtra Domicile Certificate or Ration Card / Voter ID issued in Maharashtra", "required": True, "verification_status": "Verified"},
            {"name": "Income Certificate / Orange or Yellow Ration Card", "required": True, "verification_status": "Verified"},
            {"name": "Bank Account Details (Aadhaar Seeded)", "required": True, "verification_status": "Verified"},
            {"name": "Self-Declaration Form", "required": True, "verification_status": "Verified"}
        ],
        "application_process": [
            {"step_number": 1, "channel": "Nari Shakti Doot App / Portal / Anganwadi", "description": "Apply via Nari Shakti Doot Mobile App, official portal, or visit Anganwadi / Setu Kendra."},
            {"step_number": 2, "channel": "Registration", "description": "Register mobile number and verify via OTP."},
            {"step_number": 3, "channel": "Profile Filling", "description": "Enter Aadhaar details, address, family income, and bank account info."},
            {"step_number": 4, "channel": "Document Upload", "description": "Upload photograph, Aadhaar, ration card/domicile, and self-declaration."},
            {"step_number": 5, "channel": "Scrutiny & DBT", "description": "After Anganwadi/Taluka scrutiny, monthly Rs 1,500 is credited via DBT."}
        ],
        "official_information_url": "https://www.myscheme.gov.in/schemes/ladki-bahin-maharashtra",
        "official_application_url": "https://ladkibahin.maharashtra.gov.in/",
        "faqs": [
            {"question": "How much money is given under Ladki Bahin Yojana?", "answer": "Rs 1,500 per month (Rs 18,000 annually)."},
            {"question": "What is the age limit?", "answer": "Women aged between 21 and 65 years."}
        ],
        "last_verified_at": "2026-08-20",
        "status": "Active"
    }
]

def main():
    print(f"Building expanded myScheme catalogue dataset with {len(schemes_catalog)} full scheme records...")
    output_data = {
        "dataset_version": "2026-08-07-v1",
        "total_schemes": len(schemes_catalog),
        "source": "myScheme Official Catalog",
        "schemes": schemes_catalog
    }
    DATASET_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(DATASET_PATH, "w", encoding="utf-8") as f:
        json.dump(output_data, f, indent=2, ensure_ascii=False)
    print(f"Successfully saved complete scheme dataset to {DATASET_PATH}")

if __name__ == "__main__":
    main()
