"""
Resume Analyzer API Endpoints

Provides REST API for resume operations:
- Upload resume (PDF, DOCX, Image)
- Get resume details
- List resumes with filters
- Get ATS score
- Delete resume
"""

from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Query
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from typing import List, Optional
import logging
from datetime import datetime

from ..core.database import get_db
from ..api.auth import get_current_user
from ..models.user import User, UserRole
from ..models.resume import Resume, ResumeStatus
from ..models.file import File as FileModel
from ..schemas.resume import (
    ResumeResponse,
    ResumeDetailResponse,
    ResumeUploadResponse,
    ResumeUpdate,
    ResumeUpdateStatus,
    ResumeListResponse,
    AtsScoreResponse,
    ResumeStatusEnum
)
from ..services.resume_parser import resume_parser
from ..services.resume_analyzer_service import resume_analyzer_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/resume", tags=["Resume Analyzer"])


# ============================================
# UPLOAD ENDPOINT - FIXED
# ============================================

@router.post("/upload", response_model=ResumeUploadResponse)
async def upload_resume(
    file: UploadFile = File(...),  # ✅ FIXED: Ellipsis is the default value, not argument to File()
    student_id: Optional[int] = Query(None, description="Student ID (for placement officers)"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Upload and analyze a resume.
    
    Supports: PDF, DOCX, JPG, PNG
    """
    
    # Check permissions
    if current_user.role == UserRole.STUDENT:
        student_id = current_user.id
        student = current_user
    elif current_user.role in [UserRole.PLACEMENT_OFFICER, UserRole.ADMIN]:
        if student_id:
            student = db.query(User).filter(User.id == student_id).first()
            if not student:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Student with ID {student_id} not found"
                )
        else:
            student_id = current_user.id
            student = current_user
    else:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only students, placement officers, and admins can upload resumes"
        )
    
    # Check file type
    allowed_extensions = ['.pdf', '.docx', '.doc', '.jpg', '.jpeg', '.png']
    ext = '.' + file.filename.split('.')[-1].lower()
    
    if ext not in allowed_extensions:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File type not allowed. Allowed: {', '.join(allowed_extensions)}"
        )
    
    try:
        # Read file content
        content = await file.read()
        
        # Create a file record in database
        import uuid
        
        file_id = uuid.uuid4()
        file_extension = file.filename.split('.')[-1]
        stored_filename = f"{file_id}.{file_extension}"
        
        # Create file record
        file_record = FileModel(
            id=file_id,
            filename=file.filename,
            file_size=len(content),
            mime_type=file.content_type or "application/octet-stream",
            bucket="resumes",
            object_key=f"resumes/{stored_filename}",
            title=f"Resume - {student.name}",
            description=f"Resume uploaded by {current_user.name}",
            file_type="resume",
            department=student.department or "General",
            uploaded_by=current_user.id
        )
        
        db.add(file_record)
        db.commit()
        db.refresh(file_record)
        
        # Create resume record
        resume = Resume(
            student_id=student_id,
            file_id=file_id,
            status=ResumeStatus.PENDING
        )
        db.add(resume)
        db.commit()
        db.refresh(resume)
        
        # Parse the resume
        try:
            parse_result = resume_parser.parse_resume(
                file_path=file.filename,
                content=content
            )
            
            if parse_result['success']:
                entities = parse_result.get('entities', {})
                parsed_name = entities.get('name', '').strip()
                resume.name = parsed_name if (parsed_name and len(parsed_name) > 2 and parsed_name.lower() not in ['python', 'java', 'c++', 'sql']) else (student.name or "Student Resume")
                resume.email = entities.get('email', '') or student.email or ""
                resume.phone = entities.get('phone', '') or ""
                resume.skills = entities.get('skills', [])
                
                # Format education
                education_list = []
                for edu in entities.get('education', []):
                    if isinstance(edu, str):
                        education_list.append({"degree": edu})
                    elif isinstance(edu, dict):
                        education_list.append(edu)
                resume.education = education_list
                
                # Format experience
                experience_list = []
                for exp in entities.get('experience', []):
                    if isinstance(exp, str):
                        experience_list.append({"title": exp})
                    elif isinstance(exp, dict):
                        experience_list.append(exp)
                resume.experience = experience_list
                
                # Format projects
                projects_list = []
                for proj in entities.get('projects', []):
                    if isinstance(proj, str):
                        projects_list.append({"name": proj})
                    elif isinstance(proj, dict):
                        projects_list.append(proj)
                resume.projects = projects_list
                
                # Format certifications
                cert_list = []
                for cert in entities.get('certifications', []):
                    if isinstance(cert, str):
                        cert_list.append({"name": cert})
                    elif isinstance(cert, dict):
                        cert_list.append(cert)
                resume.certifications = cert_list
                
                resume.status = ResumeStatus.PROCESSING
                db.commit()
                
                # Analyze resume (ATS score)
                analysis = resume_analyzer_service.analyze_resume(db, resume.id)
                
                if analysis['success']:
                    resume.status = ResumeStatus.COMPLETED
                    db.commit()
                    logger.info(f"✅ Resume {resume.id} processed successfully")
                else:
                    resume.status = ResumeStatus.FAILED
                    db.commit()
                    logger.error(f"❌ Resume analysis failed: {analysis.get('error')}")
            else:
                logger.error(f"❌ Resume parsing failed: {parse_result.get('error')}")
                resume.status = ResumeStatus.FAILED
                db.commit()
                
        except Exception as e:
            logger.error(f"❌ Resume processing failed: {str(e)}")
            resume.status = ResumeStatus.FAILED
            db.commit()
        
        return ResumeUploadResponse(
            success=True,
            message="Resume uploaded and processing started",
            resume_id=resume.id,
            status=resume.status
        )
        
    except Exception as e:
        logger.error(f"❌ Resume upload failed: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


# ============================================
# GET RESUME DETAILS
# ============================================

@router.get("/{resume_id}", response_model=ResumeDetailResponse)
async def get_resume(
    resume_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get resume details by ID."""
    
    resume = db.query(Resume).filter(Resume.id == resume_id).first()
    if not resume:
        raise HTTPException(status_code=404, detail="Resume not found")
    
    # Check permissions
    if current_user.role == UserRole.STUDENT and resume.student_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only view your own resume"
        )
    
    if current_user.role not in [UserRole.STUDENT, UserRole.PLACEMENT_OFFICER, UserRole.ADMIN]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied"
        )
    
    # Get student name
    student = db.query(User).filter(User.id == resume.student_id).first()
    
    # Get file details
    file_details = None
    if resume.file_id:
        file_record = db.query(FileModel).filter(FileModel.id == resume.file_id).first()
        if file_record:
            file_details = {
                "id": str(file_record.id),
                "filename": file_record.filename,
                "file_size": file_record.file_size,
                "mime_type": file_record.mime_type,
                "download_url": f"/files/{file_record.id}/download"
            }
    
    # Create response
    response = ResumeDetailResponse(
        id=resume.id,
        student_id=resume.student_id,
        student_name=student.name if student else None,
        file_id=resume.file_id,
        name=resume.name,
        email=resume.email,
        phone=resume.phone,
        skills=resume.skills or [],
        education=resume.education or [],
        experience=resume.experience or [],
        projects=resume.projects or [],
        certifications=resume.certifications or [],
        internships=resume.internships or [],
        additional_data=resume.additional_data or {},
        ats_score=resume.ats_score,
        suggestions=resume.suggestions or [],
        skill_gap=resume.skill_gap or [],
        status=resume.status,
        created_at=resume.created_at,
        updated_at=resume.updated_at,
        file_details=file_details,
        ats_summary=resume.get_ats_summary() if hasattr(resume, 'get_ats_summary') else None
    )
    
    return response


# ============================================
# LIST RESUMES
# ============================================

@router.get("/", response_model=ResumeListResponse)
async def list_resumes(
    student_id: Optional[int] = Query(None, description="Filter by student ID"),
    status: Optional[ResumeStatusEnum] = Query(None, description="Filter by status"),
    min_ats_score: Optional[float] = Query(None, ge=0, le=100),
    max_ats_score: Optional[float] = Query(None, ge=0, le=100),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """List resumes with filters."""
    
    query = db.query(Resume)
    
    # Apply filters
    if current_user.role == UserRole.STUDENT:
        query = query.filter(Resume.student_id == current_user.id)
    elif current_user.role in [UserRole.PLACEMENT_OFFICER, UserRole.ADMIN]:
        if student_id:
            query = query.filter(Resume.student_id == student_id)
    else:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied"
        )
    
    if status:
        query = query.filter(Resume.status == status)
    
    if min_ats_score:
        query = query.filter(Resume.ats_score >= min_ats_score)
    
    if max_ats_score:
        query = query.filter(Resume.ats_score <= max_ats_score)
    
    total = query.count()
    resumes = query.order_by(Resume.created_at.desc()).offset(offset).limit(limit).all()
    
    resume_list = []
    for resume in resumes:
        student = db.query(User).filter(User.id == resume.student_id).first()
        resume_data = {
            "id": resume.id,
            "student_id": resume.student_id,
            "student_name": student.name if student else None,
            "file_id": resume.file_id,
            "name": resume.name,
            "email": resume.email,
            "phone": resume.phone,
            "skills": resume.skills or [],
            "education": resume.education or [],
            "experience": resume.experience or [],
            "projects": resume.projects or [],
            "certifications": resume.certifications or [],
            "internships": resume.internships or [],
            "additional_data": resume.additional_data or {},
            "ats_score": resume.ats_score,
            "suggestions": resume.suggestions or [],
            "skill_gap": resume.skill_gap or [],
            "status": resume.status,
            "created_at": resume.created_at,
            "updated_at": resume.updated_at
        }
        resume_list.append(ResumeResponse(**resume_data))
    
    return ResumeListResponse(
        total=total,
        limit=limit,
        offset=offset,
        resumes=resume_list
    )


# ============================================
# GET ATS SCORE
# ============================================

@router.get("/{resume_id}/score", response_model=AtsScoreResponse)
async def get_ats_score(
    resume_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get ATS score and breakdown for a resume."""
    
    resume = db.query(Resume).filter(Resume.id == resume_id).first()
    if not resume:
        raise HTTPException(status_code=404, detail="Resume not found")
    
    # Check permissions
    if current_user.role == UserRole.STUDENT and resume.student_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only view your own resume scores"
        )
    
    if current_user.role not in [UserRole.STUDENT, UserRole.PLACEMENT_OFFICER, UserRole.ADMIN]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied"
        )
    
    if resume.ats_score is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="ATS score not available. Resume may not be processed yet."
        )
    
    student = db.query(User).filter(User.id == resume.student_id).first()
    
    return AtsScoreResponse(
        resume_id=resume.id,
        student_id=resume.student_id,
        student_name=student.name if student else "Unknown",
        ats_score=resume.ats_score,
        skill_match=resume_analyzer_service._calculate_skills_score(resume),
        education_match=resume_analyzer_service._calculate_education_score(resume),
        experience_match=resume_analyzer_service._calculate_experience_score(resume),
        project_match=resume_analyzer_service._calculate_projects_score(resume),
        certification_match=resume_analyzer_service._calculate_certifications_score(resume),
        format_score=resume_analyzer_service._calculate_format_score(resume),
        suggestions=resume.suggestions or [],
        skill_gap=resume.skill_gap or []
    )


# ============================================
# GET SUGGESTIONS
# ============================================

@router.get("/{resume_id}/suggestions")
async def get_suggestions(
    resume_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get improvement suggestions for a resume."""
    
    resume = db.query(Resume).filter(Resume.id == resume_id).first()
    if not resume:
        raise HTTPException(status_code=404, detail="Resume not found")
    
    # Check permissions
    if current_user.role == UserRole.STUDENT and resume.student_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only view your own resume suggestions"
        )
    
    if current_user.role not in [UserRole.STUDENT, UserRole.PLACEMENT_OFFICER, UserRole.ADMIN]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied"
        )
    
    return {
        "resume_id": resume.id,
        "suggestions": resume.suggestions or [],
        "total_suggestions": len(resume.suggestions or []),
        "high_priority": len([s for s in resume.suggestions or [] if s.get("priority") == "high"]),
        "medium_priority": len([s for s in resume.suggestions or [] if s.get("priority") == "medium"]),
        "low_priority": len([s for s in resume.suggestions or [] if s.get("priority") == "low"])
    }


# ============================================
# UPDATE RESUME
# ============================================

@router.patch("/{resume_id}", response_model=ResumeResponse)
async def update_resume(
    resume_id: int,
    update_data: ResumeUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update resume data."""
    
    resume = db.query(Resume).filter(Resume.id == resume_id).first()
    if not resume:
        raise HTTPException(status_code=404, detail="Resume not found")
    
    # Check permissions
    if current_user.role == UserRole.STUDENT and resume.student_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only update your own resume"
        )
    
    if current_user.role not in [UserRole.STUDENT, UserRole.PLACEMENT_OFFICER, UserRole.ADMIN]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied"
        )
    
    update_dict = update_data.model_dump(exclude_unset=True)
    for key, value in update_dict.items():
        if hasattr(resume, key):
            setattr(resume, key, value)
    
    resume.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(resume)
    
    student = db.query(User).filter(User.id == resume.student_id).first()
    resume_data = resume.to_dict()
    resume_data['student_name'] = student.name if student else None
    
    return ResumeResponse(**resume_data)


# ============================================
# UPDATE STATUS
# ============================================

@router.patch("/{resume_id}/status")
async def update_resume_status(
    resume_id: int,
    status_data: ResumeUpdateStatus,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update resume processing status."""
    
    if current_user.role not in [UserRole.PLACEMENT_OFFICER, UserRole.ADMIN]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only placement officers and admins can update status"
        )
    
    resume = db.query(Resume).filter(Resume.id == resume_id).first()
    if not resume:
        raise HTTPException(status_code=404, detail="Resume not found")
    
    resume.status = status_data.status
    resume.updated_at = datetime.utcnow()
    db.commit()
    
    return {"message": f"Resume status updated to {status_data.status.value}"}


# ============================================
# DELETE RESUME
# ============================================

@router.delete("/{resume_id}")
async def delete_resume(
    resume_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Delete a resume."""
    
    resume = db.query(Resume).filter(Resume.id == resume_id).first()
    if not resume:
        raise HTTPException(status_code=404, detail="Resume not found")
    
    # Check permissions
    if current_user.role == UserRole.STUDENT and resume.student_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only delete your own resume"
        )
    
    if current_user.role not in [UserRole.STUDENT, UserRole.PLACEMENT_OFFICER, UserRole.ADMIN]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied"
        )
    
    db.delete(resume)
    db.commit()
    
    return {"message": "Resume deleted successfully"}


@router.post("/{resume_id}/reanalyze")
async def reanalyze_resume(
    resume_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Re-analyze an existing resume to calculate ATS score."""
    resume = db.query(Resume).filter(Resume.id == resume_id).first()
    if not resume:
        raise HTTPException(status_code=404, detail="Resume not found")
    
    if current_user.role == UserRole.STUDENT and resume.student_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    analysis = resume_analyzer_service.analyze_resume(db, resume.id)
    if analysis.get('success'):
        resume.status = ResumeStatus.COMPLETED
        db.commit()
        db.refresh(resume)
        return {"success": True, "message": "Resume re-analyzed successfully", "ats_score": resume.ats_score}
    else:
        return {"success": False, "message": analysis.get('error', 'Reanalysis failed')}


# ============================================
# COMPARE RESUMES
# ============================================

@router.post("/compare")
async def compare_resumes(
    resume_ids: List[int],
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Compare multiple resumes by ATS score."""
    
    if current_user.role not in [UserRole.PLACEMENT_OFFICER, UserRole.ADMIN]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only placement officers and admins can compare resumes"
        )
    
    resumes = db.query(Resume).filter(Resume.id.in_(resume_ids)).all()
    
    if not resumes:
        raise HTTPException(status_code=404, detail="No resumes found")
    
    result = resume_analyzer_service.compare_resumes(resumes)
    
    return {
        "total": len(result),
        "resumes": result
    }


# ============================================
# EXPORT RESUME DATA
# ============================================

@router.get("/{resume_id}/export")
async def export_resume_data(
    resume_id: int,
    format: str = Query("json", description="Export format: json, csv"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Export resume data in various formats."""
    
    resume = db.query(Resume).filter(Resume.id == resume_id).first()
    if not resume:
        raise HTTPException(status_code=404, detail="Resume not found")
    
    # Check permissions
    if current_user.role == UserRole.STUDENT and resume.student_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only export your own resume"
        )
    
    if current_user.role not in [UserRole.STUDENT, UserRole.PLACEMENT_OFFICER, UserRole.ADMIN]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied"
        )
    
    if format == "json":
        return resume.to_dict()
    elif format == "csv":
        import csv
        from io import StringIO
        
        output = StringIO()
        writer = csv.writer(output)
        writer.writerow(["Field", "Value"])
        for key, value in resume.to_dict().items():
            writer.writerow([key, str(value)])
        
        return JSONResponse(
            content=output.getvalue(),
            media_type="text/csv",
            headers={
                "Content-Disposition": f'attachment; filename="resume_{resume_id}.csv"'
            }
        )
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported format: {format}"
        )