"""
Skill Normalizer Service

Centralized skill normalization and canonical synonym mapping.
Handles:
- Whitespace stripping and compaction
- Lowercase normalization
- Punctuation / hyphen normalization
- Explicitly maintained canonical alias / synonym dictionary
"""

import re
from typing import Optional, Dict


class SkillNormalizer:
    """Centralized service for normalizing and canonically mapping skill names."""

    # Curated, maintainable mapping of aliases/acronyms to canonical skill representations.
    # We do NOT aggressively expand unknown acronyms. Only explicitly supported mappings.
    CANONICAL_MAP: Dict[str, str] = {
        # AI / ML / Data Science
        "ml": "machine learning",
        "machine learning": "machine learning",
        "machine-learning": "machine learning",
        "ai": "artificial intelligence",
        "artificial intelligence": "artificial intelligence",
        "artificial-intelligence": "artificial intelligence",
        "dl": "deep learning",
        "deep learning": "deep learning",
        "deep-learning": "deep learning",
        "nlp": "natural language processing",
        "natural language processing": "natural language processing",
        "cv": "computer vision",
        "computer vision": "computer vision",
        
        # Web Frameworks & Libraries
        "react": "react",
        "reactjs": "react",
        "react.js": "react",
        "react-js": "react",
        "vue": "vue",
        "vuejs": "vue",
        "vue.js": "vue",
        "angular": "angular",
        "angularjs": "angular",
        "angular.js": "angular",
        "node": "node.js",
        "nodejs": "node.js",
        "node.js": "node.js",
        "express": "express.js",
        "expressjs": "express.js",
        "express.js": "express.js",
        "django": "django",
        "fastapi": "fastapi",
        "flask": "flask",
        "spring": "spring boot",
        "springboot": "spring boot",
        "spring boot": "spring boot",
        "spring-boot": "spring boot",
        "nextjs": "next.js",
        "next.js": "next.js",
        
        # Languages
        "py": "python",
        "python": "python",
        "js": "javascript",
        "javascript": "javascript",
        "ts": "typescript",
        "typescript": "typescript",
        "golang": "go",
        "go": "go",
        "c++": "c++",
        "cpp": "c++",
        "c#": "c#",
        "csharp": "c#",
        "c-sharp": "c#",
        
        # Databases & Storage
        "postgres": "postgresql",
        "postgresql": "postgresql",
        "psql": "postgresql",
        "mongo": "mongodb",
        "mongodb": "mongodb",
        "mysql": "mysql",
        "redis": "redis",
        
        # Cloud & DevOps
        "k8s": "kubernetes",
        "kubernetes": "kubernetes",
        "docker": "docker",
        "aws": "amazon web services",
        "amazon web services": "amazon web services",
        "gcp": "google cloud platform",
        "google cloud": "google cloud platform",
        "google cloud platform": "google cloud platform",
        "azure": "microsoft azure",
        "microsoft azure": "microsoft azure",
        "ci/cd": "ci/cd",
        "cicd": "ci/cd",
        "ci-cd": "ci/cd",
        
        # Computer Science Fundamentals & Web Core
        "dsa": "data structures and algorithms",
        "data structures": "data structures",
        "algorithms": "algorithms",
        "oop": "object-oriented programming",
        "oops": "object-oriented programming",
        "object oriented programming": "object-oriented programming",
        "rest": "rest api",
        "rest api": "rest api",
        "restful api": "rest api",
        "restful apis": "rest api",
        "graphql": "graphql",
        "html": "html",
        "html5": "html",
        "css": "css",
        "css3": "css",
        "git": "git",
        "github": "github"
    }

    @classmethod
    def clean_text(cls, skill: Optional[str]) -> str:
        """
        Normalize skill string:
        - Trim whitespace
        - Lowercase
        - Replace internal hyphens/underscores with spaces unless part of special tokens (c++, c#, .net, node.js)
        - Collapse multiple spaces
        """
        if not skill:
            return ""
        
        text = str(skill).strip().lower()
        if not text:
            return ""
        
        # Preserve special tokens like c++, c#, .net
        if text in {"c++", "cpp", "c#", "csharp", ".net", "dotnet"}:
            return text
        
        # Replace hyphens and underscores with spaces
        text = re.sub(r'[\-_]+', ' ', text)
        # Collapse multi-spaces
        text = re.sub(r'\s+', ' ', text)
        return text.strip()

    @classmethod
    def normalize(cls, skill: Optional[str]) -> str:
        """Return basic normalized representation."""
        return cls.clean_text(skill)

    @classmethod
    def get_canonical(cls, skill: Optional[str]) -> str:
        """
        Return the canonical representation of a skill if mapped,
        otherwise return the cleaned normalized string.
        """
        cleaned = cls.clean_text(skill)
        if not cleaned:
            return ""
        return cls.CANONICAL_MAP.get(cleaned, cleaned)

    @classmethod
    def is_exact_match(cls, skill1: Optional[str], skill2: Optional[str]) -> bool:
        """Check if two skills match on exact normalized string equality."""
        n1 = cls.clean_text(skill1)
        n2 = cls.clean_text(skill2)
        return bool(n1 and n2 and n1 == n2)

    @classmethod
    def is_canonical_match(cls, skill1: Optional[str], skill2: Optional[str]) -> bool:
        """Check if two skills match on canonical representation equality."""
        c1 = cls.get_canonical(skill1)
        c2 = cls.get_canonical(skill2)
        return bool(c1 and c2 and c1 == c2)


# Global singleton instance
skill_normalizer = SkillNormalizer()
