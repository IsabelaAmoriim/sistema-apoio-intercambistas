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
    #relacionamento para conexão da classe DocumentoUsuario
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
    #relacionamento com Universidade
    universidades = db.relationship('Universidade', backref='pais_origem', lazy=True)
    #relacionamento com Documentos
    documentos_exigidos = db.relationship('Documento', backref='pais_pertencente', lazy=True)

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
    #Coluna que diz se o documento é geral (NULL/None) ou de um país específico
    pais_id = db.Column(db.Integer, db.ForeignKey('pais.id'), nullable=True)
    #relacionamento para conexão da classe DocumentoUsuario
    envios_dos_alunos = db.relationship('DocumentoUsuario', backref='tipo_documento', lazy=True)

class DocumentoUsuario(db.Model):
    __tablename__ = 'documento_usuario'
    id = db.Column(db.Integer, primary_key=True)

    usuario_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    documento_id = db.Column(db.Integer, db.ForeignKey('documento.id'), nullable=False)

    #caminho do arquivo guarda o endereço (diretório) da foto/documento
    caminho_arquivo = db.Column(db.String(255), nullable=True)
    status = db.Column(db.String(20), default="Pendente")

