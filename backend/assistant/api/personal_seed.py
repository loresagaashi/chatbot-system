"""
Helpers for seeding personal/professional data (such as your CV) directly
from code, so it is always available to the assistant as long‑term memory.

Edit the `PERSONAL_CV_TEXT` string below and paste your actual CV or
professional summary there. On server start, the `ApiConfig.ready()` hook
will call `ensure_personal_cv_document` which:

- Creates (or updates) a `ProfessionalDocument` row with this content
- Generates an embedding for it
- Makes it available to semantic search during conversations
"""

from typing import Optional


# TODO: Paste your real CV / professional summary into this string.
PERSONAL_CV_TEXT: str = """
Name: Loresa Gashi
Role: Software & AI Developer
Contact:

Phone: (+383) 45605588

Email: loresag17@gmail.com

LinkedIn: https://www.linkedin.com/in/loresagashi/

Location: Prishtina, Kosovo

About Me:
Ambitious Software Developer with strong ownership, passion for meaningful projects, and hands-on experience in full-stack development, teaching, curriculum creation, and applied machine learning.

Skills:

Java, Spring Boot, Spring Security, OOP, JavaScript, React, Next.js, TypeScript, Python, PHP, .NET, C#, HTML, CSS, SQL, MySQL, PostgreSQL, MongoDB, REST APIs, GitHub, Postman, WordPress, JQuery, Agile (Scrum)

Experience:

Digital School – Junior General Tech Engineer & Instructor (April 2025 – November 2025)

Developed curriculum and hands-on coding projects, including AI/ML Advanced curriculum.

Taught PHP, Python, HTML, CSS, JavaScript, and web development fundamentals.

Mentored students on building web/software applications and assessed their progress.

Projects:

Learning Management & Student Information System – Java Spring Boot, ReactJS, PostgreSQL, MongoDB

Food Ordering App – Java Spring Boot, ReactJS, MySQL, Stripe payments

Pet Adoption Platform – HTML, CSS, JavaScript, PHP

Honours & Awards:

Erasmus+ ELEGANTS Program – Project Participant & Winner

Contributed to AR-based memorial project “Voices of the Fallen.”

Hackathon Prizren – Digital Skills Festival

Built a smart-city real-time temperature management system (React, JS, Python)

Education:

Bachelor’s Degree – Computer Science & Engineering
University for Business and Technology (2022–2025)

Relevant subjects: Algorithms, Software Engineering, Database Systems, AI Fundamentals, Software Architecture, Mathematics

Web Application Developer Course – Beetroot Academy
Java Programming Course – Cacttus Education

Languages:

Albanian – Native

English – C1 (Listening, Reading, Speaking, Writing)
"""


def ensure_personal_cv_document() -> Optional[int]:
    """
    Ensure that a `ProfessionalDocument` entry exists for the built‑in CV.

    Returns the document's primary key, or None if seeding fails (errors are
    intentionally swallowed so that startup is not blocked).
    """
    # Avoid import cycles and only touch the ORM once Django is fully loaded.
    from .models import ProfessionalDocument
    from .memory import ensure_document_embedding

    text = (PERSONAL_CV_TEXT or "").strip()
    if not text:
        # Nothing to seed – user has not customized the text yet.
        return None

    try:
        # Use a stable title so we can find/update the same row on every
        # startup rather than creating duplicates.
        doc, created = ProfessionalDocument.objects.get_or_create(
            title="Personal CV (built‑in)",
            defaults={
                "content": text,
                "metadata": {
                    "source": "built_in_cv",
                },
            },
        )

        # If the content changed in code, keep the DB row in sync.
        if not created and doc.content != text:
            doc.content = text
            metadata = dict(doc.metadata or {})
            metadata.setdefault("source", "built_in_cv")
            doc.metadata = metadata
            doc.save(update_fields=["content", "metadata", "updated"])

        ensure_document_embedding(doc)
        return doc.pk
    except Exception:
        # Silently ignore any seeding errors; we don't want them to crash the
        # server during e.g. migrations or when the DB is not ready yet.
        return None


