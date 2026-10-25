"""A small, hand-maintained dictionary of skills and tools.

Each skill has a canonical name, the ways people write it, whether it's a
language/concept ("technical_skill") or a product ("tool"), and an optional
family. Two skills in the same family count as *related* (e.g. MySQL is
related experience for a PostgreSQL requirement), never as the same thing.

Matching is plain text: transparent and predictable, but it only knows the
words listed here. Add entries as you meet new job descriptions.
"""

import re
from dataclasses import dataclass
from functools import lru_cache


@dataclass(frozen=True)
class Skill:
    name: str
    aliases: tuple[str, ...]
    kind: str  # "technical_skill" | "tool"
    family: str | None = None


def _s(name: str, *aliases: str, kind: str = "technical_skill", family: str | None = None) -> Skill:
    return Skill(name, (name.lower(), *(a.lower() for a in aliases)), kind, family)


SKILLS: list[Skill] = [
    # Programming languages
    _s("Python", family="language"),
    _s("Java", family="language"),
    _s("JavaScript", "js", "ecmascript", family="language"),
    _s("TypeScript", "ts", family="language"),
    _s("C", "c language", family="language"),
    _s("C++", "cpp", family="language"),
    _s("C#", "c sharp", "csharp", family="language"),
    _s("Go", "golang", family="language"),
    _s("Rust", family="language"),
    _s("Kotlin", family="language"),
    _s("Swift", family="language"),
    _s("PHP", family="language"),
    _s("Ruby", family="language"),
    # Bare "R" would match "R&D" and initials, so only explicit forms count.
    Skill("R", ("r language", "r programming", "rstudio"), "technical_skill", "language"),
    _s("Scala", family="language"),
    _s("Dart", family="language"),
    _s("SQL", "structured query language", family="query"),
    _s("Bash", "shell scripting", family="scripting"),
    _s("HTML", "html5", family="markup"),
    _s("CSS", "css3", family="markup"),
    # Web frameworks and libraries
    _s("React", "react.js", "reactjs", kind="tool", family="frontend_framework"),
    _s("Next.js", "nextjs", "next js", kind="tool", family="frontend_framework"),
    _s("Vue", "vue.js", "vuejs", kind="tool", family="frontend_framework"),
    _s("Angular", "angularjs", kind="tool", family="frontend_framework"),
    _s("Svelte", kind="tool", family="frontend_framework"),
    _s("Tailwind CSS", "tailwind", kind="tool", family="css_framework"),
    _s("Bootstrap", kind="tool", family="css_framework"),
    _s("Node.js", "nodejs", "node", kind="tool", family="js_backend"),
    _s("Express", "express.js", "expressjs", kind="tool", family="js_backend"),
    _s("NestJS", "nest.js", kind="tool", family="js_backend"),
    _s("Django", kind="tool", family="python_web"),
    _s("Flask", kind="tool", family="python_web"),
    _s("FastAPI", kind="tool", family="python_web"),
    _s("Spring Boot", "spring", kind="tool", family="java_web"),
    _s("ASP.NET", ".net", "dotnet", ".net core", kind="tool", family="dotnet"),
    _s("Laravel", kind="tool", family="php_web"),
    _s("Ruby on Rails", "rails", kind="tool", family="ruby_web"),
    _s("GraphQL", kind="tool", family="api_style"),
    _s("REST APIs", "rest api", "restful", "rest", "restful apis", "rest apis", family="api_style"),
    _s("gRPC", kind="tool", family="api_style"),
    # Data and ML
    _s("Pandas", kind="tool", family="python_data"),
    _s("NumPy", kind="tool", family="python_data"),
    _s("scikit-learn", "sklearn", "scikit learn", kind="tool", family="ml_library"),
    _s("TensorFlow", kind="tool", family="ml_library"),
    _s("PyTorch", kind="tool", family="ml_library"),
    _s("Machine learning", "ml", family="ml"),
    _s("Deep learning", family="ml"),
    _s("Natural language processing", "nlp", family="ml"),
    _s("Data analysis", "data analytics", family="data"),
    _s("Power BI", "powerbi", kind="tool", family="bi"),
    _s("Tableau", kind="tool", family="bi"),
    _s("Excel", "microsoft excel", "ms excel", kind="tool", family="bi"),
    _s("Apache Spark", "spark", "pyspark", kind="tool", family="big_data"),
    _s("Airflow", "apache airflow", kind="tool", family="orchestration"),
    # Databases
    _s("PostgreSQL", "postgres", "postgresql", kind="tool", family="relational_db"),
    _s("MySQL", kind="tool", family="relational_db"),
    _s("SQLite", kind="tool", family="relational_db"),
    _s("SQL Server", "mssql", "microsoft sql server", kind="tool", family="relational_db"),
    _s("Oracle Database", "oracle db", "oracle", kind="tool", family="relational_db"),
    _s("MongoDB", "mongo", kind="tool", family="document_db"),
    _s("Redis", kind="tool", family="cache"),
    _s("Elasticsearch", "elastic search", kind="tool", family="search"),
    _s("Firebase", kind="tool", family="baas"),
    _s("SQLAlchemy", kind="tool", family="orm"),
    _s("Prisma", kind="tool", family="orm"),
    _s("Hibernate", kind="tool", family="orm"),
    # DevOps and cloud
    _s("Docker", kind="tool", family="containers"),
    _s("Kubernetes", "k8s", kind="tool", family="containers"),
    _s("AWS", "amazon web services", kind="tool", family="cloud"),
    _s("Azure", "microsoft azure", kind="tool", family="cloud"),
    _s("Google Cloud", "gcp", "google cloud platform", kind="tool", family="cloud"),
    _s("Terraform", kind="tool", family="iac"),
    _s("Ansible", kind="tool", family="iac"),
    _s("Linux", "unix", family="os"),
    _s("Nginx", kind="tool", family="web_server"),
    _s("CI/CD", "ci cd", "continuous integration", "continuous delivery", "continuous deployment", family="cicd"),
    _s("GitHub Actions", kind="tool", family="cicd"),
    _s("GitLab CI", kind="tool", family="cicd"),
    _s("Jenkins", kind="tool", family="cicd"),
    _s("Git", kind="tool", family="vcs"),
    _s("GitHub", kind="tool", family="vcs"),
    _s("Kafka", "apache kafka", kind="tool", family="messaging"),
    _s("RabbitMQ", kind="tool", family="messaging"),
    _s("Microservices", "microservice", family="architecture"),
    # Testing and quality
    _s("Unit testing", "unit tests", family="testing"),
    _s("Test automation", "automated testing", "automation testing", family="testing"),
    _s("Pytest", kind="tool", family="test_framework"),
    _s("Jest", kind="tool", family="test_framework"),
    _s("JUnit", kind="tool", family="test_framework"),
    _s("Selenium", kind="tool", family="ui_test"),
    _s("Cypress", kind="tool", family="ui_test"),
    _s("Playwright", kind="tool", family="ui_test"),
    _s("Postman", kind="tool", family="api_test"),
    _s("API testing", family="api_test"),
    _s("Manual testing", family="testing"),
    # Concepts
    _s("Data structures", "data structure", family="cs_fundamentals"),
    _s("Algorithms", "algorithm", family="cs_fundamentals"),
    _s("Object-oriented programming", "oop", "object oriented programming", "object-oriented", family="cs_fundamentals"),
    _s("System design", family="architecture"),
    _s("Agile", "scrum", "kanban", family="process"),
    _s("Jira", kind="tool", family="process"),
    _s("Figma", kind="tool", family="design"),
    _s("Android", kind="tool", family="mobile"),
    _s("iOS", kind="tool", family="mobile"),
    _s("Flutter", kind="tool", family="mobile"),
    _s("React Native", kind="tool", family="mobile"),
]

SKILLS_BY_NAME = {skill.name: skill for skill in SKILLS}


@lru_cache(maxsize=1)
def _patterns() -> list[tuple[re.Pattern[str], Skill]]:
    """One regex per alias, longest aliases first so "React Native" wins over "React"."""
    entries = [(alias, skill) for skill in SKILLS for alias in skill.aliases]
    entries.sort(key=lambda entry: len(entry[0]), reverse=True)
    patterns = []
    for alias, skill in entries:
        # Word-ish boundaries that also work for names like "C++", "C#", ".NET", "Next.js".
        escaped = re.escape(alias)
        patterns.append((re.compile(rf"(?<![\w+#.]){escaped}(?![\w+#])", re.IGNORECASE), skill))
    return patterns


# Aliases that are also ordinary words only count when capitalised as a name:
# "Go" not "go", "Excel" not "excel in a team", "REST" not "the rest of".
_CASE_SENSITIVE = {
    "c": "C", "go": "Go", "ts": "TS", "js": "JS", "ml": "ML", "rest": "REST", "spring": "Spring",
    "node": "Node", "oracle": "Oracle", "excel": "Excel", "swift": "Swift", "express": "Express",
    "spark": "Spark", "rust": "Rust", "ruby": "Ruby", "dart": "Dart", "jest": "Jest",
}


def find_skills(text: str) -> list[tuple[Skill, int, int]]:
    """All known skills in `text` as (skill, start, end), without overlaps, in text order."""
    taken: list[tuple[int, int]] = []
    found: list[tuple[Skill, int, int]] = []
    for pattern, skill in _patterns():
        for match in pattern.finditer(text):
            start, end = match.span()
            if any(start < t_end and end > t_start for t_start, t_end in taken):
                continue
            written = match.group(0)
            required = _CASE_SENSITIVE.get(written.lower())
            if required is not None and written != required:
                continue  # "go" in "go-to", "rest" in "the rest of": ordinary words, not skills
            taken.append((start, end))
            found.append((skill, start, end))
    found.sort(key=lambda item: item[1])
    return found


def skill_names(text: str) -> list[str]:
    seen: list[str] = []
    for skill, _, _ in find_skills(text):
        if skill.name not in seen:
            seen.append(skill.name)
    return seen
