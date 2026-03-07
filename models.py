from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()

class Usuario(UserMixin, db.Model):
    __tablename__ = 'usuario'
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    cpf = db.Column(db.String(11), unique=True, nullable=False)
    senha_hash = db.Column(db.String(200), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)
    
    documentos_enviados = db.relationship('DocumentoUsuario', backref='dono_do_documento', lazy=True)
    
    @staticmethod
    def buscar_por_email(email_procurado):
        return Usuario.query.filter_by(email=email_procurado).first()
    
    def definir_senha(self, senha):
        self.senha_hash = generate_password_hash(senha)
    
    def verificar_senha(self, senha_digitada):
        return check_password_hash(self.senha_hash, senha_digitada)

class Pais(db.Model):
    __tablename__ = 'pais'
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), unique=True, nullable=False)
    iso = db.Column(db.String(2), unique=True)
    desc = db.Column(db.String(500), nullable=True)
    
    universidades = db.relationship('Universidade', backref='pais_origem', lazy=True)
    
    @staticmethod
    def buscar_por_nome(nome_procurado):
        return Pais.query.filter_by(nome=nome_procurado).first()
    
    @staticmethod
    def buscar_por_id(id_procurado):
        return Pais.query.filter_by(id=id_procurado).first()

class Universidade(db.Model):
    __tablename__ = 'universidade'
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(200), unique=True, nullable=False)
    endereco = db.Column(db.String(200), nullable=True)
    pais_id = db.Column(db.Integer, db.ForeignKey('pais.id'), nullable=False)

class Documento(db.Model):
    __tablename__ = 'documento'
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    descricao = db.Column(db.String(350), nullable=True)
    obrigatoriedade = db.Column(db.Boolean, default=True)
    pais_id = db.Column(db.Integer, db.ForeignKey('pais.id'), nullable=True)
    envios_dos_alunos = db.relationship('DocumentoUsuario', backref='tipo_documento', lazy=True)

class DocumentoUsuario(db.Model):
    __tablename__ = 'documento_usuario'
    id = db.Column(db.Integer, primary_key=True)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    documento_id = db.Column(db.Integer, db.ForeignKey('documento.id'), nullable=False)
    caminho_arquivo = db.Column(db.String(255), nullable=True)
    status = db.Column(db.String(20), default="Pendente")

edital_documento = db.Table('edital_documento',
    db.Column('edital_id', db.Integer, db.ForeignKey('edital.id'), primary_key=True),
    db.Column('documento_id', db.Integer, db.ForeignKey('documento.id'), primary_key=True)
)

class Edital(db.Model):
    __tablename__ = 'edital'
    id = db.Column(db.Integer, primary_key=True)
    titulo = db.Column(db.String(200), nullable=False)
    descricao = db.Column(db.String(500), nullable=True)
    encerrado = db.Column(db.Boolean, default=False)
    vagas = db.Column(db.Integer, nullable=False)
    
    data_ini_edital = db.Column(db.Date, nullable=False)
    data_fim_edital = db.Column(db.Date, nullable=False)
    data_ini_programa = db.Column(db.Date, nullable=True)
    data_fim_programa = db.Column(db.Date, nullable=True)
    
    universidade_id = db.Column(db.Integer, db.ForeignKey('universidade.id'), nullable=False)
    universidade = db.relationship('Universidade', backref='editais')
    
    documentos_exigidos = db.relationship('Documento', secondary=edital_documento, lazy='subquery', backref=db.backref('editais', lazy=True))

# --- CLASSE INSCRIÇÃO (O PROCESSO SELETIVO) ---
from datetime import datetime

class Inscricao(db.Model):
    __tablename__ = 'inscricao'
    id = db.Column(db.Integer, primary_key=True)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    edital_id = db.Column(db.Integer, db.ForeignKey('edital.id'), nullable=False)
    
    cra = db.Column(db.Float, nullable=False) # Guarda a nota de 0 a 10 ou 0 a 100
    carta_motivacao = db.Column(db.Text, nullable=False) # Guarda o texto escrito pelo aluno
    status = db.Column(db.String(20), default="Em Análise") # Status: Em Análise, Aprovado, Reprovado
    data_inscricao = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relacionamentos para ligar tudo
    usuario = db.relationship('Usuario', backref=db.backref('inscricoes', lazy=True))
    edital = db.relationship('Edital', backref=db.backref('inscricoes', lazy=True))

    # --- CLASSE TÓPICO (FÓRUM) ---
class Topico(db.Model):
    __tablename__ = 'topico'
    id = db.Column(db.Integer, primary_key=True)
    titulo = db.Column(db.String(200), nullable=False)
    conteudo = db.Column(db.Text, nullable=False)
    data_criacao = db.Column(db.DateTime, default=datetime.utcnow)
    
    # O tópico pertence a um usuário
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    autor = db.relationship('Usuario', backref=db.backref('topicos', lazy=True))

def seed_database():
    admins = [
        {"nome": "Admin Breno", "email": "breno@gmail.com", "cpf": "00000000000", "senha": "breno123"},
        {"nome": "Admin Clara", "email": "clara@gmail.com", "cpf": "00000000001", "senha": "clara123"},
        {"nome": "Admin Eduardo", "email": "eduardo@gmail.com", "cpf": "00000000002", "senha": "eduardo123"},
        {"nome": "Admin Isabela", "email": "isabela@gmail.com", "cpf": "00000000003", "senha": "isabela123"},
        {"nome": "Admin Patrick", "email": "patrick@gmail.com", "cpf": "00000000004", "senha": "patrick123"}
    ]

    for data in admins:
        if not Usuario.query.filter_by(email=data["email"]).first():
            novo_admin = Usuario(
                nome=data["nome"],
                email=data["email"],
                cpf=data["cpf"],
                senha_hash=generate_password_hash(data["senha"]),
                is_admin=True
            )
            db.session.add(novo_admin)
    
    db.session.commit()