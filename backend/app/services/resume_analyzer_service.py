"""
Resume Analyzer Service

Core service for resume analysis including:
- ATS Score calculation
- Skill gap analysis
- Improvement suggestions
- Resume ranking
"""

import logging
import re
from typing import Dict, Any, List, Optional, Tuple
from sqlalchemy.orm import Session

from ..models.resume import Resume, ResumeStatus
from ..models.user import User
from ..models.profile import StudentProfile
from ..schemas.resume import (
    SuggestionItem,
    AtsScoreResponse,
    ResumeResponse
)

logger = logging.getLogger(__name__)


class ResumeAnalyzerService:
    """
    Resume analyzer service for ATS scoring and suggestions.
    """
    
    # ATS Score Weights
    WEIGHTS = {
        'skills': 0.30,
        'education': 0.20,
        'experience': 0.20,
        'projects': 0.15,
        'certifications': 0.10,
        'format': 0.05
    }
    
    # Skill database (common technical skills)
    SKILL_DATABASE = {
        'programming_languages': [
            'python', 'java', 'javascript', 'c++', 'c#', 'ruby', 'go', 'rust',
            'swift', 'kotlin', 'typescript', 'php', 'r', 'scala', 'perl'
        ],
        'frameworks_libraries': [
            'react', 'angular', 'vue', 'django', 'flask', 'fastapi', 'spring',
            'hibernate', 'node', 'express', 'tensorflow', 'pytorch', 'scikit-learn',
            'pandas', 'numpy', 'matplotlib', 'plotly', 'd3'
        ],
        'databases': [
            'sql', 'mysql', 'postgresql', 'mongodb', 'redis', 'oracle', 'sqlite',
            'cassandra', 'elasticsearch', 'dynamodb', 'firebase'
        ],
        'cloud_devops': [
            'aws', 'azure', 'gcp', 'docker', 'kubernetes', 'jenkins', 'git',
            'github', 'gitlab', 'terraform', 'ansible', 'circleci', 'github actions'
        ],
        'ml_ai': [
            'machine learning', 'deep learning', 'nlp', 'computer vision',
            'llm', 'rag', 'langchain', 'huggingface', 'openai', 'anthropic'
        ],
        'other': [
            'agile', 'scrum', 'jira', 'confluence', 'linux', 'bash',
            'rest api', 'graphql', 'websocket', 'grpc', 'microservices'
        ]
    }
    
    def __init__(self):
        self.all_skills = []
        for category, skills in self.SKILL_DATABASE.items():
            self.all_skills.extend(skills)
        
        # Common degree patterns
        self.degree_patterns = [
            'b.tech', 'b.e', 'bachelor', 'm.tech', 'm.e', 'master',
            'phd', 'mca', 'mba', 'b.sc', 'm.sc', 'bca', 'b.com', 'm.com'
        ]
    
    def analyze_resume(self, db: Session, resume_id: int) -> Dict[str, Any]:
        """
        Analyze a resume and update with ATS score and suggestions.
        
        Args:
            db: Database session
            resume_id: Resume ID
            
        Returns:
            Dict with analysis results
        """
        try:
            # Get resume
            resume = db.query(Resume).filter(Resume.id == resume_id).first()
            if not resume:
                return {'success': False, 'error': 'Resume not found'}
            
            # Update status to processing
            resume.status = ResumeStatus.PROCESSING
            db.commit()
            
            # Calculate ATS score
            ats_score, breakdown = self.calculate_ats_score(resume)
            
            # Generate suggestions
            suggestions = self.generate_suggestions(resume, breakdown)
            
            # Identify skill gaps
            skill_gap = self.identify_skill_gaps(resume)
            
            # Update resume with results
            resume.ats_score = ats_score
            resume.suggestions = [s.model_dump() if hasattr(s, 'model_dump') else (s.dict() if hasattr(s, 'dict') else s) for s in suggestions]
            resume.skill_gap = skill_gap
            resume.status = ResumeStatus.COMPLETED
            
            db.commit()
            
            return {
                'success': True,
                'resume_id': resume_id,
                'ats_score': ats_score,
                'breakdown': breakdown,
                'suggestions': suggestions,
                'skill_gap': skill_gap
            }
            
        except Exception as e:
            logger.error(f"❌ Resume analysis failed: {str(e)}", exc_info=True)
            
            # Update status to failed
            resume = db.query(Resume).filter(Resume.id == resume_id).first()
            if resume:
                resume.status = ResumeStatus.FAILED
                db.commit()
            
            return {'success': False, 'error': str(e)}
    
    def calculate_ats_score(self, resume: Resume) -> Tuple[float, Dict[str, float]]:
        """
        Calculate ATS score based on resume content.
        
        Returns:
            Tuple of (total_score, breakdown)
        """
        breakdown = {}
        total_score = 0.0
        
        # 1. Skills Score (30%)
        skills_score = self._calculate_skills_score(resume)
        breakdown['skills'] = skills_score
        total_score += skills_score * self.WEIGHTS['skills']
        
        # 2. Education Score (20%)
        education_score = self._calculate_education_score(resume)
        breakdown['education'] = education_score
        total_score += education_score * self.WEIGHTS['education']
        
        # 3. Experience Score (20%)
        experience_score = self._calculate_experience_score(resume)
        breakdown['experience'] = experience_score
        total_score += experience_score * self.WEIGHTS['experience']
        
        # 4. Projects Score (15%)
        projects_score = self._calculate_projects_score(resume)
        breakdown['projects'] = projects_score
        total_score += projects_score * self.WEIGHTS['projects']
        
        # 5. Certifications Score (10%)
        cert_score = self._calculate_certifications_score(resume)
        breakdown['certifications'] = cert_score
        total_score += cert_score * self.WEIGHTS['certifications']
        
        # 6. Format Score (5%)
        format_score = self._calculate_format_score(resume)
        breakdown['format'] = format_score
        total_score += format_score * self.WEIGHTS['format']
        
        # Round to 1 decimal
        total_score = round(total_score, 1)
        
        logger.info(f"📊 ATS Score: {total_score}%")
        return total_score, breakdown
    
    def _calculate_skills_score(self, resume: Resume) -> float:
        """Calculate skills score (0-100) dynamically based on quantity, diversity, and market demand."""
        skills = resume.skills or []
        if not skills:
            return 0.0
        
        skill_count = len(skills)
        # Quantity score: 6 points per unique skill up to 60 max
        count_score = min(skill_count * 6.0, 60.0)
        
        # In-demand high-value tech skills (Python, Cloud, React, Docker, ML, DB, etc.)
        high_demand = {'python', 'java', 'sql', 'aws', 'docker', 'react', 'machine learning', 'fastapi', 'postgresql', 'kubernetes', 'typescript', 'deep learning', 'node', 'c++'}
        matched_high = sum(1 for s in skills if (s.lower() if isinstance(s, str) else '') in high_demand)
        high_demand_score = min(matched_high * 4.0, 25.0)
        
        # Skill diversity across categories (Programming, Web, Cloud/DevOps, Database, AI/ML)
        categories = {
            'prog': {'python', 'java', 'c++', 'c#', 'javascript', 'typescript', 'go', 'rust', 'kotlin', 'php', 'ruby'},
            'web': {'react', 'react native', 'angular', 'vue', 'django', 'flask', 'fastapi', 'node', 'express', 'html', 'css', 'tailwind', 'nextjs'},
            'cloud_devops': {'aws', 'azure', 'gcp', 'docker', 'kubernetes', 'git', 'github', 'ci/cd', 'linux', 'bash'},
            'database': {'sql', 'postgresql', 'mysql', 'mongodb', 'redis', 'sqlite'},
            'ai_data': {'machine learning', 'deep learning', 'nlp', 'ai', 'tensorflow', 'pytorch', 'pandas', 'numpy', 'scikit-learn', 'data structures', 'algorithms'}
        }
        
        skills_set = {s.lower() if isinstance(s, str) else '' for s in skills}
        covered_cats = sum(1 for cat_skills in categories.values() if cat_skills.intersection(skills_set))
        diversity_score = covered_cats * 3.0  # Up to 15.0
        
        total_skills_score = count_score + high_demand_score + diversity_score
        return min(max(total_skills_score, 10.0), 100.0)
    
    def _calculate_education_score(self, resume: Resume) -> float:
        """Calculate education score (0-100) based on degree level, branch, and CGPA."""
        education = resume.education or []
        if not education:
            return 25.0
        
        score = 50.0  # Base score
        
        # Analyze education text / objects
        edu_text = ' '.join([
            (e.get('degree', '') + ' ' + str(e.get('cgpa', ''))) if isinstance(e, dict) else str(e)
            for e in education
        ]).lower()
        
        # 1. Degree Level
        if any(d in edu_text for d in ['phd', 'doctorate']):
            score += 35.0
        elif any(d in edu_text for d in ['m.tech', 'm.e', 'master', 'mca', 'mba', 'm.sc']):
            score += 25.0
        elif any(d in edu_text for d in ['b.tech', 'b.e', 'bachelor', 'b.sc', 'bca']):
            score += 20.0
        else:
            score += 10.0
        
        # 2. Branch Relevance (Computer Science / Tech)
        if any(b in edu_text for b in ['computer', 'information', 'software', 'data science', 'artificial intelligence', 'electronics']):
            score += 10.0
        
        # 3. CGPA / Academic performance
        cgpa_val = None
        for e in education:
            if isinstance(e, dict) and e.get('cgpa'):
                try:
                    cgpa_val = float(e['cgpa'])
                except:
                    pass
        
        if cgpa_val:
            if cgpa_val >= 9.0:
                score += 15.0
            elif cgpa_val >= 8.0:
                score += 10.0
            elif cgpa_val >= 7.0:
                score += 5.0
        
        return min(max(score, 20.0), 100.0)
    
    def _calculate_experience_score(self, resume: Resume) -> float:
        """Calculate experience score (0-100) based on roles, internships, and depth."""
        experience = resume.experience or []
        if not experience:
            return 20.0  # Entry-level / fresher baseline
        
        exp_count = len(experience)
        score = 40.0 + min(exp_count * 15.0, 40.0)  # 55 for 1, 70 for 2, 80+ for 3+
        
        exp_text = ' '.join([
            (e.get('title', '') + ' ' + e.get('description', '')) if isinstance(e, dict) else str(e)
            for e in experience
        ]).lower()
        
        # Engineering / Dev / Lead roles
        if any(r in exp_text for r in ['senior', 'lead', 'architect', 'full stack', 'software engineer']):
            score += 12.0
        elif any(r in exp_text for r in ['intern', 'developer', 'analyst', 'engineer']):
            score += 8.0
        
        # Action verbs in description
        if any(v in exp_text for v in ['developed', 'implemented', 'designed', 'built', 'optimized', 'scaled', 'integrated']):
            score += 8.0
        
        return min(max(score, 15.0), 100.0)
    
    def _calculate_projects_score(self, resume: Resume) -> float:
        """Calculate projects score (0-100) based on project count, complexity, and tech stack."""
        projects = resume.projects or []
        if not projects:
            return 25.0
        
        proj_count = len(projects)
        score = 45.0 + min(proj_count * 12.0, 36.0)  # 57 for 1, 69 for 2, 81 for 3, 90+ for 4+
        
        proj_text = ' '.join([
            (p.get('name', '') + ' ' + p.get('description', '')) if isinstance(p, dict) else str(p)
            for p in projects
        ]).lower()
        
        # High impact tech keywords in projects
        if any(t in proj_text for t in ['react', 'python', 'fastapi', 'docker', 'ai', 'ml', 'api', 'database', 'platform', 'app']):
            score += 10.0
        
        # GitHub / live deployment references
        if 'github' in proj_text or 'http' in proj_text or 'live' in proj_text:
            score += 9.0
        
        return min(max(score, 20.0), 100.0)
    
    def _calculate_certifications_score(self, resume: Resume) -> float:
        """Calculate certifications score (0-100) based on verified and industry credentials."""
        certifications = resume.certifications or []
        if not certifications:
            return 20.0  # Optional section baseline
        
        cert_count = len(certifications)
        score = 35.0 + min(cert_count * 15.0, 35.0)  # 50 for 1, 65 for 2, 70+ for 3+
        
        cert_text = ' '.join([
            c.get('name', '') if isinstance(c, dict) else str(c)
            for c in certifications
        ]).lower()
        
        # Cloud & Premium certifications
        premium_certs = ['aws', 'azure', 'gcp', 'google cloud', 'oracle', 'cisco', 'ccna', 'pmp', 'scrum master', 'kubernetes', 'tensorflow']
        matched_premium = sum(1 for p in premium_certs if p in cert_text)
        score += min(matched_premium * 15.0, 30.0)
        
        return min(max(score, 10.0), 100.0)
    
    def _calculate_format_score(self, resume: Resume) -> float:
        """Calculate resume format and completeness score (0-100)."""
        score = 50.0  # Base structure score
        
        # Section presence (skills, education, projects, experience)
        if resume.skills and len(resume.skills) >= 3:
            score += 12.0
        if resume.education and len(resume.education) > 0:
            score += 12.0
        if resume.projects and len(resume.projects) > 0:
            score += 10.0
        if resume.experience and len(resume.experience) > 0:
            score += 8.0
        
        # Contact information completeness
        if resume.email and '@' in resume.email:
            score += 4.0
        if resume.phone and len(resume.phone) >= 7:
            score += 4.0
        
        return min(max(score, 30.0), 100.0)
    
    def generate_suggestions(self, resume: Resume, breakdown: Dict[str, float]) -> List[SuggestionItem]:
        """
        Generate improvement suggestions based on analysis.
        
        Args:
            resume: Resume object
            breakdown: Score breakdown by category
            
        Returns:
            List of SuggestionItem objects
        """
        suggestions = []
        
        # 1. Skills suggestions
        skills_score = breakdown.get('skills', 0)
        if skills_score < 60:
            if not resume.skills or len(resume.skills) < 3:
                suggestions.append(SuggestionItem(
                    category='skills',
                    message='Add more technical skills to your resume. Include programming languages, frameworks, and tools.',
                    priority='high',
                    impact='+8 to +15 points'
                ))
            else:
                # Suggest specific skills
                all_skills_lower = [s.lower() for s in (resume.skills or [])]
                missing_skills = []
                for skill in self.all_skills[:10]:
                    if skill not in all_skills_lower and skill not in missing_skills:
                        missing_skills.append(skill)
                
                if missing_skills:
                    suggestions.append(SuggestionItem(
                        category='skills',
                        message=f"Consider adding these in-demand skills: {', '.join(missing_skills[:5])}",
                        priority='high' if len(missing_skills) > 3 else 'medium',
                        impact='+5 to +10 points'
                    ))
        
        # 2. Education suggestions
        education_score = breakdown.get('education', 0)
        if education_score < 50:
            if not resume.education or len(resume.education) == 0:
                suggestions.append(SuggestionItem(
                    category='education',
                    message='Add your education details including degree, institution, and graduation year.',
                    priority='high',
                    impact='+10 to +15 points'
                ))
            else:
                suggestions.append(SuggestionItem(
                    category='education',
                    message='Include your CGPA, relevant coursework, or academic achievements.',
                    priority='medium',
                    impact='+5 to +10 points'
                ))
        
        # 3. Experience suggestions
        experience_score = breakdown.get('experience', 0)
        if experience_score < 50:
            if not resume.experience or len(resume.experience) == 0:
                suggestions.append(SuggestionItem(
                    category='experience',
                    message='Add work experience or internships to strengthen your resume.',
                    priority='high',
                    impact='+10 to +20 points'
                ))
            else:
                suggestions.append(SuggestionItem(
                    category='experience',
                    message='Quantify your achievements with numbers (e.g., "Improved efficiency by 30%").',
                    priority='high',
                    impact='+5 to +10 points'
                ))
        
        # 4. Projects suggestions
        projects_score = breakdown.get('projects', 0)
        if projects_score < 50:
            if not resume.projects or len(resume.projects) == 0:
                suggestions.append(SuggestionItem(
                    category='projects',
                    message='Add 2-3 projects with descriptions and technologies used.',
                    priority='high',
                    impact='+10 to +15 points'
                ))
            else:
                suggestions.append(SuggestionItem(
                    category='projects',
                    message='Include GitHub links or detailed project descriptions.',
                    priority='medium',
                    impact='+5 to +8 points'
                ))
        
        # 5. Certifications suggestions
        cert_score = breakdown.get('certifications', 0)
        if cert_score < 30:
            suggestions.append(SuggestionItem(
                category='certifications',
                message='Add relevant certifications (e.g., AWS, Azure, Google Cloud, CompTIA).',
                priority='medium',
                impact='+5 to +10 points'
            ))
        
        # 6. Contact information
        if not resume.email or not resume.phone:
            suggestions.append(SuggestionItem(
                category='format',
                message='Include your email and phone number for employers to contact you.',
                priority='high',
                impact='+5 points'
            ))
        
        # 7. Skill gap suggestions (if skills exist)
        if resume.skills:
            skill_gap = self.identify_skill_gaps(resume)
            if skill_gap:
                suggestions.append(SuggestionItem(
                    category='skills',
                    message=f"You're missing these skills: {', '.join(skill_gap[:5])}. Consider adding them.",
                    priority='medium',
                    impact='+3 to +5 points'
                ))
        
        # Limit suggestions
        return suggestions[:10]
    
    def identify_skill_gaps(self, resume: Resume) -> List[str]:
        """
        Identify missing skills based on common requirements.
        
        Args:
            resume: Resume object
            
        Returns:
            List of missing skills
        """
        current_skills = [s.lower() for s in (resume.skills or [])]
        missing = []
        
        # Check for common skills
        common_skills = [
            'python', 'java', 'sql', 'git', 'docker', 'linux', 'aws',
            'machine learning', 'deep learning', 'react', 'node', 'express',
            'mongodb', 'postgresql', 'redis', 'kubernetes', 'tensorflow'
        ]
        
        for skill in common_skills:
            found = False
            for current in current_skills:
                if skill in current or current in skill:
                    found = True
                    break
            if not found:
                missing.append(skill)
        
        return missing[:10]
    
    def compare_resumes(self, resumes: List[Resume]) -> List[Dict[str, Any]]:
        """
        Compare multiple resumes and rank them by ATS score.
        
        Args:
            resumes: List of Resume objects
            
        Returns:
            List of ranked resumes with scores
        """
        results = []
        for resume in resumes:
            results.append({
                'resume_id': resume.id,
                'name': resume.name,
                'ats_score': resume.ats_score or 0,
                'skills': resume.skills or [],
                'education': len(resume.education or []),
                'experience': len(resume.experience or []),
                'projects': len(resume.projects or [])
            })
        
        # Sort by ATS score (highest first)
        results.sort(key=lambda x: x['ats_score'], reverse=True)
        
        return results
    
    def get_resume_summary(self, resume: Resume) -> Dict[str, Any]:
        """
        Get a summary of the resume analysis.
        
        Args:
            resume: Resume object
            
        Returns:
            Dict with summary information
        """
        ats_summary = resume.get_ats_summary() if hasattr(resume, 'get_ats_summary') else {}
        
        return {
            'id': resume.id,
            'name': resume.name,
            'email': resume.email,
            'ats_score': resume.ats_score,
            'skill_count': len(resume.skills or []),
            'education_count': len(resume.education or []),
            'experience_count': len(resume.experience or []),
            'projects_count': len(resume.projects or []),
            'certifications_count': len(resume.certifications or []),
            'suggestions_count': len(resume.suggestions or []),
            'suggestions': resume.suggestions or [],
            'skill_gap': resume.skill_gap or []
        }


# Singleton instance
resume_analyzer_service = ResumeAnalyzerService()