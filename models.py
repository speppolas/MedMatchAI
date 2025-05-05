from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.dialects.postgresql import JSONB

db = SQLAlchemy()

class ClinicalTrial(db.Model):
    """Modello per i trial clinici dell'Istituto Nazionale dei Tumori."""
    
    __tablename__ = 'clinical_trials'
    
    id = db.Column(db.String(30), primary_key=True)
    title = db.Column(db.String(500), nullable=False)
    phase = db.Column(db.String(20), nullable=False)
    description = db.Column(db.Text, nullable=False)
    inclusion_criteria = db.Column(JSONB, nullable=False, default=[])
    exclusion_criteria = db.Column(JSONB, nullable=False, default=[])
    
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
            'exclusion_criteria': self.exclusion_criteria
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