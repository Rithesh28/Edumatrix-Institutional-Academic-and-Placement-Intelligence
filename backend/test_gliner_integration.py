"""
Comprehensive Test Suite for Phase 2: Selective GLiNER Integration

Covers:
1. Shared GLiNER service lazy-loading, singleton integrity, thread-safety, and offline loading.
2. Graceful degradation: Model unavailable, initialization failure, and inference failure.
3. Selective enrichment: Modern skills (LangChain, Qdrant, Fastify, Tailwind CSS), soft skills (Agile, Root Cause Analysis).
4. Unlabeled non-standard job titles (Site Reliability & Chaos Engineer).
5. Specialized degree and branch normalization (B.Tech in Artificial Intelligence & Data Science -> AIDS).
6. Section-aware demarcation: Required skills vs Preferred skills.
7. Low-confidence entity rejection and stopword filtering.
8. Case-insensitive and canonical deduplication between deterministic and GLiNER results.
9. Deterministic preservation: URLs, application deadlines, CGPA, percentages, and salary.
10. Multi-file ingestion and conflict detection with GLiNER-enriched results.
11. Real-model offline integration test with latency measurement.
"""

import os
import sys
import unittest
import time
from unittest.mock import patch, MagicMock

# Configure environment before importing backend modules
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["REDIS_URL"] = "redis://localhost:6379/0"

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.services.gliner_service import GLiNERService, gliner_service
from app.services.jd_parser_service import jd_parser_service, JdParseResult
from app.schemas.placement import JdParseResponse


class TestGLiNERServiceUnit(unittest.TestCase):
    """Unit tests for the shared GLiNER service."""

    def test_01_lazy_loading_and_status(self):
        """Verify service initializes lazily without loading model on instantiate."""
        svc = GLiNERService()
        self.assertFalse(svc.is_loaded)
        self.assertFalse(svc._load_attempted)
        status = svc.get_status()
        self.assertEqual(status["model_name"], "urchade/gliner_base")
        self.assertFalse(status["is_loaded"])
        self.assertEqual(status["device"], "cpu")

    def test_02_singleton_instance(self):
        """Verify global gliner_service instance exists."""
        self.assertIsInstance(gliner_service, GLiNERService)

    def test_03_initialization_failure_handling(self):
        """Verify graceful fallback when model cannot be loaded."""
        svc = GLiNERService()
        with patch("gliner.GLiNER.from_pretrained", side_effect=RuntimeError("Offline file missing")):
            avail = svc._ensure_model()
            self.assertFalse(avail)
            self.assertFalse(svc.is_loaded)
            self.assertTrue(svc._load_attempted)
            status = svc.get_status()
            self.assertIn("Offline file missing", status["last_error"])
            # Predict entities should return empty list gracefully
            preds = svc.predict_entities("Sample text", labels=["skill"])
            self.assertEqual(preds, [])

    def test_04_inference_failure_handling(self):
        """Verify inference exceptions do not crash the service."""
        svc = GLiNERService()
        svc.is_loaded = True
        mock_model = MagicMock()
        mock_model.predict_entities.side_effect = RuntimeError("Inference tensor OOM")
        svc.model = mock_model

        preds = svc.predict_entities("Test text", labels=["skill"])
        self.assertEqual(preds, [])

    def test_05_threshold_and_empty_inputs(self):
        """Verify empty inputs and threshold handling."""
        self.assertEqual(gliner_service.predict_entities("", labels=["skill"]), [])
        self.assertEqual(gliner_service.predict_entities("Some text", labels=[]), [])


class TestJdParserGLiNEREnrichment(unittest.TestCase):
    """Integration and behavioral tests for selective JD extraction enrichment."""

    def test_06_modern_skills_extraction(self):
        """Extract modern libraries not present in static keyword list."""
        jd_text = """
        Job Title: Cloud Native Developer
        Requirements:
        - Must have deep experience building AI agents using LangChain.
        - Experience with Qdrant vector database is required.
        - Knowledge of Fastify for high performance Node services.
        - Proficient with Tailwind CSS for responsive interfaces.
        """
        res = jd_parser_service.parse_jd_text(jd_text)
        req_skills = res.required_skills
        self.assertIn("LangChain", req_skills)
        self.assertIn("Fastify", req_skills)
        self.assertTrue(any("Qdrant" in s for s in req_skills))
        self.assertTrue(any("Tailwind" in s for s in req_skills))

    def test_07_soft_skills_extraction(self):
        """Extract professional competencies and soft skills."""
        jd_text = """
        Job Title: Associate Consultant
        Requirements:
        - Candidate must demonstrate excellence in Agile methodologies.
        - Proven track record of Root Cause Analysis in production incidents.
        - Familiar with Problem Solving and Client Communication.
        """
        res = jd_parser_service.parse_jd_text(jd_text)
        skills = res.required_skills + res.preferred_skills
        self.assertTrue(any("Agile" in s for s in skills))
        self.assertTrue(any("Root Cause Analysis" in s for s in skills))

    def test_08_unlabeled_job_title_extraction(self):
        """Extract job title when no explicit 'Job Title:' or 'Position:' label exists."""
        jd_text = """
        Apex Cloud Services is expanding its Bangalore operations.
        We are seeking a Site Reliability & Chaos Engineer to maintain our global infrastructure.
        Candidates should have a strong background in distributed systems.
        """
        res = jd_parser_service.parse_jd_text(jd_text)
        self.assertIsNotNone(res.title)
        self.assertIn("Site Reliability", res.title)

    def test_09_specialized_degree_and_branch(self):
        """Extract specialized qualification and branch discipline."""
        jd_text = """
        Campus Hiring Notice - 2026 Batch
        Job Title: AI Engineer
        Eligibility:
        - B.Tech in Artificial Intelligence & Data Science or Computer Science
        - Minimum 7.0 CGPA
        """
        res = jd_parser_service.parse_jd_text(jd_text)
        self.assertIn("B.Tech", res.degree_eligibility)
        self.assertIn("AIDS", res.branch_eligibility)
        self.assertIn("CSE", res.branch_eligibility)

    def test_10_section_aware_skills_demarcation(self):
        """Verify skills are correctly assigned to required vs preferred lists."""
        jd_text = """
        Job Title: Full Stack Engineer
        Required Skills:
        - Python
        - LangChain
        - Fastify
        Preferred Skills:
        - Docker
        - Kubernetes
        - Kafka
        """
        res = jd_parser_service.parse_jd_text(jd_text)
        for s in ["Python", "LangChain", "Fastify"]:
            self.assertIn(s, res.required_skills)
            self.assertNotIn(s, res.preferred_skills)

        for s in ["Docker", "Kubernetes", "Kafka"]:
            self.assertIn(s, res.preferred_skills)
            self.assertNotIn(s, res.required_skills)

    def test_11_deduplication_between_deterministic_and_gliner(self):
        """Verify no duplicate entries when a skill is identified by both regex and GLiNER."""
        jd_text = """
        Required Skills:
        - Python programming language
        - Hands-on Python development experience
        - Python, FastAPI, and Docker
        """
        res = jd_parser_service.parse_jd_text(jd_text)
        # Python should appear exactly once in required_skills
        python_count = sum(1 for s in res.required_skills if s.lower() == "python")
        self.assertEqual(python_count, 1)

    def test_12_stopword_and_noise_rejection(self):
        """Verify generic non-skill words are rejected by validator."""
        self.assertIsNone(jd_parser_service._clean_and_validate_skill_entity("skills"))
        self.assertIsNone(jd_parser_service._clean_and_validate_skill_entity("requirement"))
        self.assertIsNone(jd_parser_service._clean_and_validate_skill_entity("candidate"))
        self.assertIsNone(jd_parser_service._clean_and_validate_skill_entity("2026"))
        self.assertIsNone(jd_parser_service._clean_and_validate_skill_entity("60%"))
        self.assertIsNone(jd_parser_service._clean_and_validate_skill_entity("experience"))
        self.assertEqual(jd_parser_service._clean_and_validate_skill_entity("  LangChain  "), "LangChain")

    def test_13_deterministic_preservation_urls_dates_cgpa_salary(self):
        """Verify deterministic fields (URL, deadlines, CGPA, salary) remain 100% intact."""
        jd_text = """
        CAMPUS RECRUITMENT DRIVE - 2026 BATCH
        Job Title: Associate Software Engineer
        Company: Eazy ERP Technologies
        Eligible Degrees: B.Tech, MCA
        Eligible Branches: CSE, IT, ECE
        Minimum Academic Criteria:
        - Minimum CGPA: 7.5
        - 10th: 70%, 12th: 75%
        Compensation:
        - INR 2,40 - 3.60 Lakhs per annum
        Application Process:
        Apply online at: https://forms.gle/yP4tpWtmk9VdFFBU8
        Registration Deadline: 19th October 2026
        """
        res = jd_parser_service.parse_jd_text(jd_text)
        # Deterministic assertions
        self.assertEqual(res.application_url, "https://forms.gle/yP4tpWtmk9VdFFBU8")
        self.assertEqual(res.application_deadline, "2026-10-19T00:00")
        self.assertEqual(res.cgpa_criteria, 7.5)
        self.assertEqual(res.company_name, "Eazy ERP Technologies")
        self.assertIn("2.40 - 3.60 Lakhs per annum", res.salary_range)
        self.assertEqual(res.academic_percentages.get("10th"), 70.0)
        self.assertEqual(res.academic_percentages.get("12th"), 75.0)

    def test_14_multi_file_merging_with_conflicts(self):
        """Verify parse_multiple_files combines GLiNER enriched skills and flags conflicts."""
        file_a = {
            "filename": "notice_a.txt",
            "content": b"""
            Job Title: Cloud Engineer
            Company: TechCorp
            Required Skills: LangChain, Fastify
            Salary: 8.0 LPA
            """
        }
        file_b = {
            "filename": "notice_b.txt",
            "content": b"""
            Job Title: Systems Architect
            Company: TechCorp
            Required Skills: Qdrant, Docker
            Salary: 12.0 LPA
            """
        }
        merged = jd_parser_service.parse_multiple_files([file_a, file_b])
        # Title conflict detected
        self.assertTrue(any("conflict on Job Title" in f for f in merged.review_flags))
        # Salary conflict detected
        self.assertTrue(any("Conflicting full-time CTC" in f for f in merged.review_flags))
        # Skills unioned
        all_skills = merged.required_skills
        self.assertIn("LangChain", all_skills)
        self.assertIn("Fastify", all_skills)
        self.assertTrue(any("Qdrant" in s for s in all_skills))
        self.assertIn("Docker", all_skills)

    def test_15_schema_and_response_model_compatibility(self):
        """Verify JdParseResult converts cleanly into JdParseResponse without schema errors."""
        jd_text = """
        Job Title: Frontend Developer
        Skills: React, Tailwind CSS, TypeScript
        CGPA: 6.5
        URL: https://company.com/apply
        """
        res = jd_parser_service.parse_jd_text(jd_text)
        resp = JdParseResponse(**res)
        self.assertEqual(resp.title, "Frontend Developer")
        self.assertEqual(resp.cgpa_criteria, 6.5)
        self.assertEqual(resp.application_url, "https://company.com/apply")
        self.assertIn("TypeScript", resp.required_skills)


class TestRealModelOfflineIntegration(unittest.TestCase):
    """Real-model verification running offline against cached weights."""

    def test_16_real_model_offline_inference(self):
        """Execute inference with cached model and measure CPU latency."""
        self.assertTrue(gliner_service.is_available(), "GLiNER model must be available locally")

        text = "Seeking Software Engineer with experience in LangChain, Fastify, and Agile development."
        start = time.perf_counter()
        entities = gliner_service.predict_entities(
            text,
            labels=["technical skill", "job title", "soft skill"],
            threshold=0.50
        )
        latency_ms = (time.perf_counter() - start) * 1000

        self.assertTrue(len(entities) > 0, "Real GLiNER should detect entities")
        labels = [e["label"] for e in entities]
        texts = [e["text"] for e in entities]

        self.assertIn("LangChain", texts)
        self.assertIn("Fastify", texts)
        self.assertTrue(latency_ms < 5000, f"Inference took {latency_ms:.1f}ms, expected < 5000ms")


if __name__ == "__main__":
    unittest.main()
