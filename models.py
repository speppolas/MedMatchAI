from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import JSON

db = SQLAlchemy()

class ClinicalTrial(db.Model):
    """Model for clinical trials."""
    
    __tablename__ = 'clinical_trials'

    id = db.Column(db.String(30), primary_key=True)
    title = db.Column(db.String(500), nullable=False)
    phase = db.Column(db.String(20), nullable=False)
    description = db.Column(db.Text, nullable=False)
    inclusion_criteria = db.Column(JSON, nullable=False, default=list)
    exclusion_criteria = db.Column(JSON, nullable=False, default=list)
    status = db.Column(db.String(50))
    start_date = db.Column(db.String(50))
    completion_date = db.Column(db.String(50))
    sponsor = db.Column(db.String(200))
    last_updated = db.Column(db.String(50))
    locations = db.Column(JSON, default=list)
    min_age = db.Column(db.String(50))
    max_age = db.Column(db.String(50))
    gender = db.Column(db.String(50))
    org_study_id = db.Column(db.String(100))  # Organization study ID (e.g. D5087C00001)
    secondary_ids = db.Column(JSON, default=list)  # Other study IDs
    
    # Relazione con i criteri di inclusione/esclusione (alternativa al JSONB)
    # inclusion_criteria = db.relationship('Criterion', backref='inclusion_trial',
    #                                    primaryjoin="and_(Criterion.trial_id==ClinicalTrial.id, "
    #                                               "Criterion.is_inclusion==True)")
    # exclusion_criteria = db.relationship('Criterion', backref='exclusion_trial',
    #                                    primaryjoin="and_(Criterion.trial_id==ClinicalTrial.id, "
    #                                               "Criterion.is_inclusion==False)")
    
    def __repr__(self):
        return f"<ClinicalTrial {self.id}: {self.title}>"
    
    def to_dict(self):
        """Converte il trial clinico in un dizionario."""
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
    
# Modello alternativo per i criteri come tabella separata
# class Criterion(db.Model):
#     """Modello per i criteri di inclusione/esclusione."""
#     
#     __tablename__ = 'criteria'
#     
#     id = db.Column(db.Integer, primary_key=True)
#     trial_id = db.Column(db.String(30), db.ForeignKey('clinical_trials.id'), nullable=False)
#     is_inclusion = db.Column(db.Boolean, nullable=False, default=True)
#     type = db.Column(db.String(50), nullable=False)
#     text = db.Column(db.Text, nullable=False)
#     
#     def to_dict(self):
#         """Converte il criterio in un dizionario."""
#         return {
#             'type': self.type,
#             'text': self.text
#         }