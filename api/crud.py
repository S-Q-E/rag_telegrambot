from sqlalchemy.orm import Session
from . import db as models
from . import schemas

def get_user_by_email(db: Session, email: str):
    return db.query(models.User).filter(models.User.email == email).first()

def create_user(db: Session, user: schemas.UserCreate, hashed_password: str):
    db_user = models.User(
        email=user.email,
        hashed_password=hashed_password,
        telegram_id=user.telegram_id,
        tariff=user.tariff,
        limits=user.limits
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user
