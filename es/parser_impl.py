import re
import pdfplumber
import nltk
from nltk.corpus import stopwords

SKILLS_DB = [
    "Python", "JavaScript", "Java", "C++", "C#", "Ruby", "Go", "Rust", "Swift",
    "TypeScript", "PHP", "Kotlin", "Scala", "R", "MATLAB", "Bash", "Shell",
    "React", "Vue", "Angular", "Django", "Flask", "FastAPI", "Spring", "Node.js",
    "SQL", "PostgreSQL", "MySQL", "MongoDB", "Redis", "Elasticsearch",
    "AWS", "GCP", "Azure", "Docker", "Kubernetes", "Terraform", "CI/CD",
    "Git", "Linux", "REST", "GraphQL", "gRPC", "Microservices",
    "Machine Learning", "Deep Learning", "TensorFlow", "PyTorch", "scikit-learn",
    "Data Analysis", "Statistics", "Excel", "Tableau", "Power BI",
    "Communication", "Leadership", "Teamwork", "Problem solving", "Management",
    "Training", "Coaching", "Customer service", "English", "Mathematics",
    "Business management", "Retail", "Sales", "Marketing", "Email",
    "Mobile", "Newspaper", "Sports", "Research", "Writing", "Editing",
    "Financial", "Health", "Healthcare", "Counseling", "Supervisor",
    "Volunteer", "Coordinat", "Planning", "Scheduling", "Client",
    "Childcare", "Teaching", "Assist", "Outreach", "Database",
]

DEGREE_KEYWORDS = [
    "bachelor", "master", "phd", "doctorate", "b.sc", "m.sc", "b.e", "m.e",
    "b.tech", "m.tech", "mba", "b.com", "m.com", "b.a", "m.a", "b.s", "m.s",
]

COLLEGE_KEYWORDS = [
    "university", "college", "institute", "school", "academy",
]

DESIGNATION_KEYWORDS = [
    "engineer", "developer", "manager", "analyst", "designer", "consultant",
    "intern", "director", "officer", "lead", "architect", "scientist",
    "coordinator", "specialist", "executive", "associate", "assistant",
    "volunteer", "technician", "administrator", "supervisor",
]

_EXP_HEADERS = ["experience", "work history", "employment", "work experience", "professional experience"]
_EDU_HEADERS = ["education", "academic", "qualification"]
_SKILL_HEADERS = ["skills", "technical skills", "core competencies", "expertise"]
_ALL_HEADERS = _EXP_HEADERS + _EDU_HEADERS + _SKILL_HEADERS


class ResumeParser:
    def __init__(self, path: str):
        self.path = path
        self._text = ""
        self._lines = []
        self._pages = 0
        self._parse_pdf()

    def _parse_pdf(self):
        with pdfplumber.open(self.path) as pdf:
            self._pages = len(pdf.pages)
            self._text = "\n".join(page.extract_text() or "" for page in pdf.pages)
        self._lines = [l.strip() for l in self._text.splitlines() if l.strip()]

    def _extract_email(self):
        m = re.search(r"[\w.+-]+@[\w-]+\.[a-zA-Z]{2,}", self._text)
        return m.group(0) if m else None

    def _extract_mobile(self):
        for m in re.finditer(r"(\+?\d[\d\s\-().]{7,}\d)", self._text):
            raw = m.group(0).strip()
            # skip year ranges like 1999-2002
            if re.fullmatch(r"\d{4}\s*[-–]\s*\d{4}", raw):
                continue
            digits = re.sub(r"\D", "", raw)
            if 7 <= len(digits) <= 15:
                return raw
        return None

    def _extract_linkedin(self):
        m = re.search(r"linkedin\.com/in/[\w-]+", self._text, re.IGNORECASE)
        return "https://" + m.group(0) if m else None

    _NAME_NOISE = {"resume", "cv", "curriculum", "vitae", "sample", "profile", "page"}

    def _extract_name(self):
        stop = set(stopwords.words("english"))
        for line in self._lines[:10]:
            words = line.split()
            if (2 <= len(words) <= 4
                    and all(w[0].isupper() for w in words if w.isalpha())
                    and not any(w.lower() in stop for w in words)
                    and not any(w.lower() in self._NAME_NOISE for w in words)
                    and not re.search(r"\d|@|http|\.com", line)):
                return line
        return None

    def _extract_skills(self):
        text_lower = self._text.lower()
        return [s for s in SKILLS_DB
                if re.search(r"\b" + re.escape(s.lower()), text_lower)
                and len(s) > 1]

    def _extract_degree(self):
        for line in self._lines:
            if any(k in line.lower() for k in DEGREE_KEYWORDS):
                return line
        return None

    def _extract_college(self):
        for line in self._lines:
            if any(k in line.lower() for k in COLLEGE_KEYWORDS):
                return line
        return None

    def _extract_designations(self):
        found = [
            l for l in self._lines
            if any(k in l.lower() for k in DESIGNATION_KEYWORDS)
            and len(l.split()) <= 8
            and not l.startswith("•")
            and not re.search(r"\d{4}", l)
        ]
        return found or None

    def _section_lines(self, headers):
        in_section = False
        lines = []
        for line in self._lines:
            ll = line.lower()
            if any(h in ll for h in headers):
                in_section = True
                continue
            if in_section:
                if any(h in ll for h in _ALL_HEADERS):
                    break
                lines.append(line)
        return lines or None

    def _extract_companies(self):
        exp = self._section_lines(_EXP_HEADERS)
        if not exp:
            return None
        companies = [
            l for l in exp
            if l and l[0].isupper()
            and not re.search(r"\d{4}", l)
            and not any(k in l.lower() for k in DESIGNATION_KEYWORDS)
        ]
        return companies[:5] or None

    def _extract_total_experience(self):
        years = re.findall(r"(\d+)\s*(?:year|yr)", self._text, re.IGNORECASE)
        return sum(int(y) for y in years) if years else 0

    def get_extracted_data(self):
        return {
            "name": self._extract_name(),
            "email": self._extract_email(),
            "mobile_number": self._extract_mobile(),
            "skills": self._extract_skills(),
            "college_name": self._extract_college(),
            "degree": self._extract_degree(),
            "designation": self._extract_designations(),
            "experience": self._section_lines(_EXP_HEADERS),
            "company_names": self._extract_companies(),
            "no_of_pages": self._pages,
            "total_experience": self._extract_total_experience(),
            "linkedin": self._extract_linkedin(),
        }
