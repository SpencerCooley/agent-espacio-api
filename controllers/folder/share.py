"""
Folder controller - share toggle.
"""
from uuid import uuid4, UUID

from sqlalchemy.orm import Session

from models.folder import Folder


def toggle_folder_share(db: Session, folder: Folder) -> Folder:
    """
    Toggle a folder's public sharing status.
    
    If currently private, makes it public and generates a public_magic_id.
    If currently public, makes it private and clears the public_magic_id.
    
    Args:
        db: Database session
        folder: Folder to toggle
        
    Returns:
        Updated folder object
    """
    if folder.is_public:
        folder.is_public = False
        folder.public_magic_id = None
    else:
        folder.is_public = True
        folder.public_magic_id = uuid4()
    
    db.commit()
    db.refresh(folder)
    return folder
