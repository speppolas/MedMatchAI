#models.py

from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import JSON, Index

db = SQLAlchemy()

class ClinicalTrial(db.Model):
    __tablename__ = 'clinical_trials'

    id = db.Column(db.String(30), primary_key=True)
    title = db.Column(db.String(500), nullable=False, index=True)
    phase = db.Column(db.String(20), nullable=False, index=True)
    description = db.Column(db.Text, nullable=False)
    inclusion_criteria = db.Column(JSON, nullable=False, default=list)
    exclusion_criteria = db.Column(JSON, nullable=False, default=list)
    status = db.Column(db.String(50), index=True)
    start_date = db.Column(db.String(50))
    completion_date = db.Column(db.String(50))
    sponsor = db.Column(db.String(200))
    last_updated = db.Column(db.String(50))
    locations = db.Column(JSON, default=list)
    min_age = db.Column(db.String(50))
    max_age = db.Column(db.String(50))
    gender = db.Column(db.String(50))
    org_study_id = db.Column(db.String(100), unique=True, nullable=False)
    secondary_ids = db.Column(JSON, default=list)

    def __repr__(self):
        return f"<ClinicalTrial {self.id}: {self.title}>"
    
    
    
    '''
    def to_dict(self):
        """Converts the clinical trial to a dictionary."""
        return {
            'id': self.id,
            'title': self.title,
            'phase': self.phase,
            'description': self.description,
            'inclusion_criteria': self.inclusion_criteria,
            'exclusion_criteria': self.exclusion_criteria,
            'status': self.status,
            'start_date': self.start_date,
            'completion_date': self.completion_date,
            'sponsor': self.sponsor,
            'last_updated': self.last_updated,
            'locations': self.locations,
            'min_age': self.min_age,
            'max_age': self.max_age,
            'gender': self.gender,
            'org_study_id': self.org_study_id,
            'secondary_ids': self.secondary_ids
        }
        '''