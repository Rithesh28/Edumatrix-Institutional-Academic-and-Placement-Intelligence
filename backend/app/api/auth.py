from fastapi import APIRouter, Depends, HTTPException, status, Query
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from datetime import timedelta
from typing import Optional

from ..core.database import get_db
from ..core.security import verify_password, get_password_hash, create_access_token, decode_access_token
from ..models.user import User, LecturerProfile, UserRole
from ..models.profile import StudentProfile
from ..schemas.user import UserCreate, UserLogin, UserResponse, Token, StudentProfileResponse, LecturerProfileResponse
from ..core.config import settings

router = APIRouter(prefix="/auth", tags=["Authentication"])

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")
oauth2_scheme_optional = OAuth2PasswordBearer(tokenUrl="/auth/login", auto_error=False)

def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    """Get the current authenticated user from JWT token"""
    payload = decode_access_token(token)
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    user_id = payload.get("id")
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
        )
    
    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )
    
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account is disabled",
        )
    
    return user

def get_current_user_flexible(
    header_token: Optional[str] = Depends(oauth2_scheme_optional),
    query_token: Optional[str] = Query(None, alias="token"),
    db: Session = Depends(get_db)
) -> User:
    """Get authenticated user from Authorization header or URL token parameter."""
    token = header_token or query_token
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return get_current_user(token=token, db=db)

def get_current_active_user(current_user: User = Depends(get_current_user)):
    """Get current active user"""
    if not current_user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
    return current_user

# ============================================
# ADD PLACEMENT OFFICER DEPENDENCY
# ============================================

def get_current_placement_officer(
    current_user: User = Depends(get_current_user)
) -> User:
    """Get current user and verify they are a placement officer or admin."""
    if current_user.role not in [UserRole.PLACEMENT_OFFICER, UserRole.ADMIN]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only Placement Officers and Admins can perform this action"
        )
    return current_user

# ============================================
# AUTH ENDPOINTS
# ============================================

@router.post("/register", response_model=Token)
async def register(user_data: UserCreate, db: Session = Depends(get_db)):
    """Register a new user"""
    
    # Check if user already exists
    existing_user = db.query(User).filter(User.email == user_data.email).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
    
    # Create new user
    hashed_password = get_password_hash(user_data.password)
    new_user = User(
        name=user_data.name,
        email=user_data.email,
        password_hash=hashed_password,
        role=user_data.role,
        department=user_data.department
    )
    
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    
    # Create profile based on role
    if user_data.role == UserRole.STUDENT:
        student_profile = StudentProfile(user_id=new_user.id, skills=[], year=None, branch=None, cgpa=None)
        db.add(student_profile)
    elif user_data.role == UserRole.LECTURER:
        lecturer_profile = LecturerProfile(user_id=new_user.id, subjects=[], department=user_data.department, api_enabled=False)
        db.add(lecturer_profile)
    
    db.commit()
    
    # Create access token
    access_token = create_access_token(
        data={"id": new_user.id, "email": new_user.email, "role": new_user.role.value}
    )
    
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": UserResponse.model_validate(new_user)
    }

@router.post("/login", response_model=Token)
async def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    """Login user with email and password"""
    
    # Find user by email
    user = db.query(User).filter(User.email == form_data.username).first()
    
    if not user or not verify_password(form_data.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account is disabled",
        )
    
    # Create access token
    access_token = create_access_token(
        data={"id": user.id, "email": user.email, "role": user.role.value}
    )
    
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": UserResponse.model_validate(user)
    }

@router.get("/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_user)):
    """Get current logged-in user info"""
    return current_user

@router.get("/me/profile")
async def get_my_profile(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Get current user's profile based on role"""
    
    if current_user.role == UserRole.STUDENT:
        profile = db.query(StudentProfile).filter(StudentProfile.user_id == current_user.id).first()
        if profile:
            return StudentProfileResponse.model_validate(profile)
    elif current_user.role == UserRole.LECTURER:
        profile = db.query(LecturerProfile).filter(LecturerProfile.user_id == current_user.id).first()
        if profile:
            return LecturerProfileResponse.model_validate(profile)
    
    return None

@router.post("/logout")
async def logout():
    """Logout user (client just discards token)"""
    return {"message": "Successfully logged out"}