"""Jerry Ayodele's CV profile — single source of truth for the application agent."""

PROFILE = {
    "name": "Jerry Ayodele",
    "email": "kolaayodele@gmail.com",
    "phone": "+447432515291",
    "location": "London, England",
    "linkedin": "https://www.linkedin.com/in/jerryayodele",
    "title": "Senior Product Leader | Consumer Experience & Scalable Innovation",
    "summary": (
        "Strategic Product Leader with a proven record of scaling high-performance teams and "
        "delivering complex digital innovations for global enterprises. Expert in bridging the "
        "gap between technical execution and business growth, with specific success in managing "
        "AI-driven conversational tools and optimising core user journeys for mobile applications. "
        "Adept at navigating high-friction technical environments to deliver seamless, secure, and "
        "intuitive consumer experiences."
    ),
    "competencies": [
        "Product Vision & Strategy: Leading multi-market revenue growth and strategic roadmaps.",
        "Consumer Experience: Revamping mobile apps to drive product-led growth and user-centric discovery.",
        "AI & Automation: Orchestrating and delivering roadmaps for multi-market AI chatbots and automated digital tools.",
        "Global Leadership: Establishing unified Global Product Practices and mentoring international teams.",
        "Data-Driven Execution: Utilising UX analytics and product validation methodologies to optimise performance.",
    ],
    "experience": [
        {
            "company": "MUFG Pensions and Market Services",
            "title": "Product Lead (Employee Shareplans)",
            "location": "London, England",
            "dates": "March 2023 – Present",
            "highlights": [
                "Spearheaded the UK launch of the Investor Centre, a premier asset management platform, enabling new high-volume revenue streams and transactional capabilities.",
                "Architected product validation methodologies to streamline complex financial operations for FTSE 100 clients, ensuring a seamless user journey.",
                "Led international hiring and established a unified Global Product Practice across the UK, India, and Australia to scale the product organisation.",
                "Directed roadmaps that secured major enterprise contracts by delivering secure, frictionless customer payment and asset management experiences.",
            ],
        },
        {
            "company": "HYD",
            "title": "Product Owner",
            "location": "London, England",
            "dates": "May 2021 – January 2023",
            "highlights": [
                "Orchestrated the roadmap for a multi-market AI chatbot (Whiskas/Mars), managing over 150k sessions across four international territories.",
                "Revamped the 'School of Life' app (100k+ downloads), utilising user-validated data to drive product-led growth and enhanced core navigation.",
                "Managed the global deployment of UX analytics for PepsiCo, optimising enterprise-scale digital tools through cross-functional stakeholder leadership.",
            ],
        },
        {
            "company": "Compuco",
            "title": "Product Manager",
            "location": "London, England",
            "dates": "May 2019 – September 2020",
            "highlights": [
                "Led the delivery of complex systems for major UK unions and managed enterprise accounts for the United Nations.",
                "Developed a Financial Prospecting Extension for global nonprofits to track high-value prospects and manage fundraising pipelines.",
            ],
        },
        {
            "company": "Atlas Creative Consultancy",
            "title": "Product Manager",
            "location": "Lagos, Nigeria",
            "dates": "May 2016 – September 2018",
            "highlights": [
                "Directed end-to-end digital transformation for 15+ clients, establishing their inaugural online market presence through WordPress platform development.",
                "Owned comprehensive product strategy, including positioning and go-to-market plans for diverse client portfolios.",
            ],
        },
    ],
    "education": [
        {
            "degree": "Bachelor's in Computer Science (Software Engineering)",
            "institution": "DePaul University",
            "location": "Chicago, IL",
        }
    ],
}

CV_TEXT = f"""
Name: {PROFILE['name']}
Title: {PROFILE['title']}
Email: {PROFILE['email']} | Phone: {PROFILE['phone']} | Location: {PROFILE['location']}
LinkedIn: {PROFILE['linkedin']}

SUMMARY:
{PROFILE['summary']}

CORE COMPETENCIES:
{chr(10).join('- ' + c for c in PROFILE['competencies'])}

EXPERIENCE:
""" + "\n".join(
    f"\n{exp['company']} | {exp['title']} | {exp['location']} | {exp['dates']}\n"
    + "\n".join(f"  • {h}" for h in exp["highlights"])
    for exp in PROFILE["experience"]
) + f"""

EDUCATION:
{PROFILE['education'][0]['degree']} — {PROFILE['education'][0]['institution']}, {PROFILE['education'][0]['location']}
"""
