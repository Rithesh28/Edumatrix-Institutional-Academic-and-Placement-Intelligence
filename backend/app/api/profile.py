"""
Profile API Endpoints - Student Profile, Skills, Projects, Certifications
"""

from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from sqlalchemy.orm import Session
from typing import List
import os
import shutil
import uuid

from ..core.database import get_db
from ..api.auth import get_current_user
from ..models.user import User, UserRole
from ..models.profile import (
    StudentProfileExtended,
    Skill,
    SkillProficiency,
    Project,
    ProjectType,
    ProjectStatus,
    PlacementStatus
)
from ..models.certification import Certification
from ..schemas.profile import (
    ProfileUpdate,
    ProfileResponse,
    SkillCreate,
    SkillUpdate,
    SkillResponse,
    ProjectCreate,
    ProjectUpdate,
    ProjectResponse,
    PlacementStatus as PlacementStatusEnum
)
from ..schemas.certification import (
    CertificationCreate,
    CertificationUpdate,
    CertificationResponse
)

router = APIRouter(prefix="/profile", tags=["Profile"])

# Upload directory for profile pictures
UPLOAD_DIR = "uploads/profile_pictures"
os.makedirs(UPLOAD_DIR, exist_ok=True)


# ============================================
# Profile Endpoints
# ============================================

def get_or_create_profile(user_id: int, db: Session) -> StudentProfileExtended:
    """Get or create student profile"""
    profile = db.query(StudentProfileExtended).filter(StudentProfileExtended.user_id == user_id).first()
    if not profile:
        profile = StudentProfileExtended(user_id=user_id)
        db.add(profile)
        db.commit()
        db.refresh(profile)
    return profile


@router.get("/me", response_model=ProfileResponse)
async def get_my_profile(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get current user's profile"""
    
    if current_user.role != UserRole.STUDENT:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only students can access profile"
        )
    
    profile = get_or_create_profile(current_user.id, db)
    
    # Fetch related data
    skills = db.query(Skill).filter(Skill.student_id == profile.id).all()
    certifications = db.query(Certification).filter(Certification.student_id == profile.id).all()
    projects = db.query(Project).filter(Project.student_id == profile.id, Project.is_active == 1).all()
    
    # Build response
    response = ProfileResponse.model_validate(profile)
    response.skills = [SkillResponse.model_validate(s) for s in skills]
    response.certifications = [CertificationResponse.model_validate(c) for c in certifications]
    response.projects = [ProjectResponse.model_validate(p) for p in projects]
    
    return response


@router.put("/me", response_model=ProfileResponse)
async def update_my_profile(
    profile_data: ProfileUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update current user's profile"""
    
    if current_user.role != UserRole.STUDENT:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only students can update profile"
        )
    
    profile = get_or_create_profile(current_user.id, db)
    
    # Update fields
    for key, value in profile_data.model_dump(exclude_unset=True).items():
        setattr(profile, key, value)
    
    db.commit()
    db.refresh(profile)
    
    # Fetch related data
    skills = db.query(Skill).filter(Skill.student_id == profile.id).all()
    certifications = db.query(Certification).filter(Certification.student_id == profile.id).all()
    projects = db.query(Project).filter(Project.student_id == profile.id, Project.is_active == 1).all()
    
    response = ProfileResponse.model_validate(profile)
    response.skills = [SkillResponse.model_validate(s) for s in skills]
    response.certifications = [CertificationResponse.model_validate(c) for c in certifications]
    response.projects = [ProjectResponse.model_validate(p) for p in projects]
    
    return response


@router.post("/upload-picture")
async def upload_profile_picture(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Upload profile picture"""
    
    if current_user.role != UserRole.STUDENT:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only students can upload profile picture"
        )
    
    # Validate file type
    allowed_types = ["image/jpeg", "image/png", "image/jpg"]
    if file.content_type not in allowed_types:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only JPEG, JPG, PNG images are allowed"
        )
    
    # Generate unique filename
    ext = file.filename.split(".")[-1]
    filename = f"{uuid.uuid4()}.{ext}"
    filepath = os.path.join(UPLOAD_DIR, filename)
    
    # Save file
    with open(filepath, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    
    # Update profile
    profile = get_or_create_profile(current_user.id, db)
    profile.profile_picture_url = f"/{filepath}"
    db.commit()
    
    return {"message": "Profile picture uploaded successfully", "url": profile.profile_picture_url}


# ============================================
# Skills Endpoints
# ============================================

@router.get("/skills", response_model=List[SkillResponse])
async def get_my_skills(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get all skills for current user"""
    
    profile = get_or_create_profile(current_user.id, db)
    skills = db.query(Skill).filter(Skill.student_id == profile.id).all()
    return skills


@router.post("/skills", response_model=SkillResponse)
async def add_skill(
    skill_data: SkillCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Add a skill to current user's profile"""
    
    profile = get_or_create_profile(current_user.id, db)
    
    # Check if skill already exists
    existing = db.query(Skill).filter(
        Skill.student_id == profile.id,
        Skill.name == skill_data.name
    ).first()
    
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Skill already exists"
        )
    
    new_skill = Skill(
        student_id=profile.id,
        name=skill_data.name,
        proficiency=skill_data.proficiency
    )
    db.add(new_skill)
    db.commit()
    db.refresh(new_skill)
    
    return new_skill


@router.put("/skills/{skill_id}", response_model=SkillResponse)
async def update_skill(
    skill_id: int,
    skill_data: SkillUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update a skill"""
    
    profile = get_or_create_profile(current_user.id, db)
    skill = db.query(Skill).filter(
        Skill.id == skill_id,
        Skill.student_id == profile.id
    ).first()
    
    if not skill:
        raise HTTPException(status_code=404, detail="Skill not found")
    
    for key, value in skill_data.model_dump(exclude_unset=True).items():
        setattr(skill, key, value)
    
    db.commit()
    db.refresh(skill)
    
    return skill


@router.delete("/skills/{skill_id}")
async def delete_skill(
    skill_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Delete a skill"""
    
    profile = get_or_create_profile(current_user.id, db)
    skill = db.query(Skill).filter(
        Skill.id == skill_id,
        Skill.student_id == profile.id
    ).first()
    
    if not skill:
        raise HTTPException(status_code=404, detail="Skill not found")
    
    db.delete(skill)
    db.commit()
    
    return {"message": "Skill deleted successfully"}


# ============================================
# Projects Endpoints
# ============================================

@router.get("/projects", response_model=List[ProjectResponse])
async def get_my_projects(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get all projects for current user"""
    
    profile = get_or_create_profile(current_user.id, db)
    projects = db.query(Project).filter(
        Project.student_id == profile.id,
        Project.is_active == 1
    ).all()
    
    return projects


@router.post("/projects", response_model=ProjectResponse)
async def add_project(
    project_data: ProjectCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Add a project to current user's profile"""
    
    profile = get_or_create_profile(current_user.id, db)
    
    new_project = Project(
        student_id=profile.id,
        name=project_data.name,
        description=project_data.description,
        technologies=project_data.technologies,
        project_type=project_data.project_type,
        status=project_data.status,
        github_link=project_data.github_link,
        live_link=project_data.live_link,
        start_date=project_data.start_date,
        end_date=project_data.end_date
    )
    db.add(new_project)
    db.commit()
    db.refresh(new_project)
    
    return new_project


@router.put("/projects/{project_id}", response_model=ProjectResponse)
async def update_project(
    project_id: int,
    project_data: ProjectUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update a project"""
    
    profile = get_or_create_profile(current_user.id, db)
    project = db.query(Project).filter(
        Project.id == project_id,
        Project.student_id == profile.id
    ).first()
    
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    for key, value in project_data.model_dump(exclude_unset=True).items():
        setattr(project, key, value)
    
    db.commit()
    db.refresh(project)
    
    return project


@router.delete("/projects/{project_id}")
async def delete_project(
    project_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Soft delete a project (set is_active = 0)"""
    
    profile = get_or_create_profile(current_user.id, db)
    project = db.query(Project).filter(
        Project.id == project_id,
        Project.student_id == profile.id
    ).first()
    
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    project.is_active = 0
    db.commit()
    
    return {"message": "Project deleted successfully"}


# ============================================
# Certifications Endpoints
# ============================================

@router.get("/certifications", response_model=List[CertificationResponse])
async def get_my_certifications(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get all certifications for current user"""
    
    if current_user.role != UserRole.STUDENT:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only students can access certifications"
        )
    
    profile = get_or_create_profile(current_user.id, db)
    certifications = db.query(Certification).filter(
        Certification.student_id == profile.id
    ).all()
    
    return certifications


@router.post("/certifications", response_model=CertificationResponse)
async def add_certification(
    cert_data: CertificationCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Add a certification to current user's profile"""
    
    if current_user.role != UserRole.STUDENT:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only students can add certifications"
        )
    
    profile = get_or_create_profile(current_user.id, db)
    
    new_cert = Certification(
        student_id=profile.id,
        name=cert_data.name,
        issuer=cert_data.issuer,
        credential_id=cert_data.credential_id,
        issue_date=cert_data.issue_date,
        expiry_date=cert_data.expiry_date
    )
    db.add(new_cert)
    db.commit()
    db.refresh(new_cert)
    
    return new_cert


@router.put("/certifications/{cert_id}", response_model=CertificationResponse)
async def update_certification(
    cert_id: int,
    cert_data: CertificationUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update a certification"""
    
    if current_user.role != UserRole.STUDENT:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only students can update certifications"
        )
    
    profile = get_or_create_profile(current_user.id, db)
    cert = db.query(Certification).filter(
        Certification.id == cert_id,
        Certification.student_id == profile.id
    ).first()
    
    if not cert:
        raise HTTPException(status_code=404, detail="Certification not found")
    
    for key, value in cert_data.model_dump(exclude_unset=True).items():
        setattr(cert, key, value)
    
    db.commit()
    db.refresh(cert)
    
    return cert


@router.delete("/certifications/{cert_id}")
async def delete_certification(
    cert_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Delete a certification"""
    
    if current_user.role != UserRole.STUDENT:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only students can delete certifications"
        )
    
    profile = get_or_create_profile(current_user.id, db)
    cert = db.query(Certification).filter(
        Certification.id == cert_id,
        Certification.student_id == profile.id
    ).first()
    
    if not cert:
        raise HTTPException(status_code=404, detail="Certification not found")
    
    db.delete(cert)
    db.commit()
    
    return {"message": "Certification deleted successfully"}