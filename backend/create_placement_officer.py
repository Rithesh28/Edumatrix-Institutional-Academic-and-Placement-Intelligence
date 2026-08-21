"""
Create Placement Officer User
"""

from app.core.database import SessionLocal
from app.models.user import User, UserRole
from app.core.security import get_password_hash

def create_placement_officer():
    db = SessionLocal()
    
    try:
        # Check if placement officer exists
        existing = db.query(User).filter(User.email == 'placement@gmail.com').first()
        if existing:
            print(f'✅ Placement officer already exists: {existing.email}')
            print(f'   Role: {existing.role.value if existing.role else "N/A"}')
        else:
            # Create placement officer - using lowercase "placement_officer"
            new_user = User(
                name='Placement Officer',
                email='placement@gmail.com',
                password_hash=get_password_hash('12345'),
                role='placement_officer',  # Use lowercase string
                department='CS',
                is_active=True
            )
            db.add(new_user)
            db.commit()
            db.refresh(new_user)
            print('✅ Placement officer created!')
            print('   Email: placement@gmail.com')
            print('   Password: 12345')
            print(f'   ID: {new_user.id}')
        
        # List all users
        print('\n📋 All users:')
        users = db.query(User).all()
        for u in users:
            role_value = u.role.value if u.role else 'N/A'
            print(f'   - {u.email} ({role_value})')
        
    except Exception as e:
        print(f'❌ Error: {str(e)}')
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    create_placement_officer()