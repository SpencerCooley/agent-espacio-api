#!/usr/bin/env python3
"""
Create first admin user via CLI.

This script creates the initial admin user when setting up Agent Espacio
on a fresh VPS. It requires that no users exist in the database yet.

Usage:
    docker compose exec -it agentespacio_api python scripts/create_admin.py

Or as part of the setup process.
"""
import sys
import os

# Add project root to Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from models.user import User
from models.enums import RoleEnum
from utils.password import hash_password

# Database URL from environment or default
DATABASE_URL = os.environ.get(
    'DATABASE_URL',
    'postgresql://agentespacio:agentespacio@db:5432/agentespacio_db'
)


def create_admin():
    """Interactive CLI to create the first admin user."""
    print("=" * 60)
    print("Agent Espacio - Create First Admin User")
    print("=" * 60)
    print()
    
    # Get user input
    email = input("Admin email: ").strip()
    
    # Simple password input (no echo for security)
    import getpass
    password = getpass.getpass("Admin password (min 8 chars): ").strip()
    confirm_password = getpass.getpass("Confirm password: ").strip()
    
    # Validation
    if not email:
        print("\nError: Email is required")
        return False
    
    if not password:
        print("\nError: Password is required")
        return False
    
    if len(password) < 8:
        print("\nError: Password must be at least 8 characters")
        return False
    
    if password != confirm_password:
        print("\nError: Passwords do not match")
        return False
    
    # Connect to database
    try:
        engine = create_engine(DATABASE_URL)
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        db = SessionLocal()
    except Exception as e:
        print(f"\nError: Could not connect to database: {e}")
        return False
    
    try:
        # Check if any users exist
        existing_user = db.query(User).first()
        if existing_user:
            print("\nError: Users already exist in the database.")
            print("This script can only be used to create the FIRST admin user.")
            print("\nTo create additional users, use the API:")
            print("  POST /users (requires admin authentication)")
            return False
        
        # Create admin user
        admin = User(
            email=email,
            hashed_password=hash_password(password),
            role=RoleEnum.admin,
            is_confirmed=True
        )
        
        db.add(admin)
        db.commit()
        db.refresh(admin)
        
        print()
        print("=" * 60)
        print("SUCCESS! Admin user created.")
        print("=" * 60)
        print(f"Email: {email}")
        print(f"Role: admin")
        print()
        print("You can now login at:")
        print("  http://YOUR_VPS_IP:8000/docs")
        print()
        print("Or use the API:")
        print("  POST /auth/login")
        print()
        print("=" * 60)
        
        return True
        
    except Exception as e:
        print(f"\nError creating admin user: {e}")
        return False
    finally:
        db.close()


if __name__ == "__main__":
    success = create_admin()
    sys.exit(0 if success else 1)
