from src.extensions import db
from datetime import datetime
import json


class KimResponseSession(db.Model):
    """جلسة كيم ريسبونس — المعلم أو الأدمن ينشئها ويختار الأسئلة"""
    __tablename__ = 'kim_response_sessions'

    id                    = db.Column(db.Integer, primary_key=True)
    teacher_id            = db.Column(db.Integer, db.ForeignKey('teachers.id'), nullable=True)
    admin_id              = db.Column(db.Integer, db.ForeignKey('user.id'),     nullable=True)
    title                 = db.Column(db.String(200), nullable=False, default='جلسة كيم ريسبونس')
    _question_ids         = db.Column('question_ids', db.Text, nullable=False)  # JSON array
    current_question_idx  = db.Column(db.Integer, nullable=False, default=0)
    status                = db.Column(db.String(20), nullable=False, default='waiting')
    # waiting → active → finished
    created_at            = db.Column(db.DateTime, default=datetime.utcnow)
    finished_at           = db.Column(db.DateTime, nullable=True)

    answers  = db.relationship('KimResponseAnswer', backref='session',
                               lazy=True, cascade='all, delete-orphan')
    teacher  = db.relationship('Teacher', backref='kim_sessions', lazy=True)

    @property
    def question_ids(self):
        return json.loads(self._question_ids) if self._question_ids else []

    @question_ids.setter
    def question_ids(self, value):
        self._question_ids = json.dumps(value)

    @property
    def current_question_id(self):
        ids = self.question_ids
        if 0 <= self.current_question_idx < len(ids):
            return ids[self.current_question_idx]
        return None

    @property
    def total_questions(self):
        return len(self.question_ids)

    def to_dict(self):
        return {
            'id':                   self.id,
            'teacher_id':           self.teacher_id,
            'admin_id':             self.admin_id,
            'title':                self.title,
            'question_ids':         self.question_ids,
            'total_questions':      self.total_questions,
            'current_question_idx': self.current_question_idx,
            'current_question_id':  self.current_question_id,
            'status':               self.status,
            'created_at':           self.created_at.isoformat() if self.created_at else None,
        }


class KimResponseAnswer(db.Model):
    """إجابة طالب واحد على سؤال واحد في جلسة"""
    __tablename__ = 'kim_response_answers'

    id          = db.Column(db.Integer, primary_key=True)
    session_id  = db.Column(db.Integer, db.ForeignKey('kim_response_sessions.id'), nullable=False)
    student_id  = db.Column(db.Integer, db.ForeignKey('students.id'), nullable=False)
    question_id = db.Column(db.Integer, db.ForeignKey('questions.question_id'), nullable=False)
    answer      = db.Column(db.String(1), nullable=False)   # A / B / C / D
    is_correct  = db.Column(db.Boolean, nullable=False, default=False)
    scanned_at  = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (
        db.UniqueConstraint('session_id', 'student_id', 'question_id',
                            name='uq_kim_answer'),
    )

    student  = db.relationship('Student', backref='kim_answers', lazy=True)
    question = db.relationship('Question', backref='kim_answers', lazy=True)

    def to_dict(self):
        return {
            'id':           self.id,
            'session_id':   self.session_id,
            'student_id':   self.student_id,
            'student_name': self.student.name if self.student else '',
            'question_id':  self.question_id,
            'answer':       self.answer,
            'is_correct':   self.is_correct,
            'scanned_at':   self.scanned_at.isoformat() if self.scanned_at else None,
        }
