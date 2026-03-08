from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, date


db = SQLAlchemy()

class Usuario(UserMixin, db.Model):
    __tablename__ = 'usuario'
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    cpf = db.Column(db.String(11), unique=True, nullable=False)
    senha_hash = db.Column(db.String(200), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)
    
    # relacionamento pra classe DocumentoUsuario
    documentos_enviados = db.relationship('DocumentoUsuario', backref='dono_do_documento', lazy=True)
    inscricoes = db.relationship('Inscricao', backref='usuario', lazy=True)
    
    @staticmethod
    def buscar_por_email(email_procurado):
        return Usuario.query.filter_by(email=email_procurado).first()
    
    def definir_senha(self, senha):
        self.senha_hash = generate_password_hash(senha)
    
    def verificar_senha(self, senha_digitada):
        return check_password_hash(self.senha_hash, senha_digitada)
    
    # verificar se tá inscrito num edital
    def esta_inscrito_no_edital(self, edital_id):
        inscricao = Inscricao.query.filter_by(
            usuario_id=self.id,
            edital_id=edital_id
        ).first()
        return inscricao is not None
    
    # retornar a inscrição ativa do usuário em um edital
    def get_inscricao_ativa(self, edital_id):
        return Inscricao.query.filter_by(
            usuario_id=self.id,
            edital_id=edital_id,
            status='Ativa'
        ).first()
    
    # retornar lista de nomes de documentos faltantes pra um edital
    def documentos_faltantes_para_edital(self, edital):
        docs_enviados = DocumentoUsuario.query.filter_by(
            usuario_id=self.id
        ).all()
        ids_enviados = [d.documento_id for d in docs_enviados]
        
        faltantes = []
        for doc in edital.documentos_exigidos:
            if doc.id not in ids_enviados:
                faltantes.append(doc.nome)
        return faltantes
    
    # checar se enviou todos os documentos de um edital
    def enviou_todos_documentos_edital(self, edital):
        return len(self.documentos_faltantes_para_edital(edital)) == 0


class Pais(db.Model):
    __tablename__ = 'pais'
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), unique=True, nullable=False)
    iso = db.Column(db.String(2), unique=True)
    desc = db.Column(db.String(500), nullable=True)
    
    # relacionamento com universidade
    universidades = db.relationship('Universidade', backref='pais_origem', lazy=True)
    
    # métodos de busca
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
    
    # relacionamentos
    envios_dos_alunos = db.relationship('DocumentoUsuario', backref='tipo_documento', lazy=True)


class DocumentoUsuario(db.Model):
    __tablename__ = 'documento_usuario'
    id = db.Column(db.Integer, primary_key=True)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    documento_id = db.Column(db.Integer, db.ForeignKey('documento.id'), nullable=False)
    caminho_arquivo = db.Column(db.String(255), nullable=True)
    status = db.Column(db.String(20), default="Pendente")


# tabela associativa da relação muitos -> muitos entre edital e documento
edital_documento = db.Table(
    'edital_documento',
    db.Column('edital_id', db.Integer, db.ForeignKey('edital.id'), primary_key=True),
    db.Column('documento_id', db.Integer, db.ForeignKey('documento.id'), primary_key=True)
)


class Edital(db.Model):
    __tablename__ = 'edital'
    id = db.Column(db.Integer, primary_key=True)
    titulo = db.Column(db.String(200), nullable=False)
    descricao = db.Column(db.String(500), nullable=True)
    encerrado = db.Column(db.Boolean, default=False)
    data_ini_edital = db.Column(db.Date, nullable=False)
    data_fim_edital = db.Column(db.Date, nullable=False)
    data_ini_programa = db.Column(db.Date, nullable=False)
    data_fim_programa = db.Column(db.Date, nullable=False)
    vagas = db.Column(db.Integer, nullable=False)

    # cada edital tem uma universidade
    universidade_id = db.Column(db.Integer, db.ForeignKey('universidade.id'), nullable=False)
    universidade = db.relationship('Universidade', backref='editais')

    # relação muitos -> muitos com documentos
    documentos_exigidos = db.relationship(
        'Documento',
        secondary=edital_documento,
        backref='editais_relacionados',
        lazy=True
    )
    
    # relacionamento com inscrições
    inscricoes = db.relationship('Inscricao', backref='edital', lazy=True)
    
    # verifica se tá no período de inscrição
    def esta_no_periodo_inscricao(self):
        hoje = date.today()
        return self.data_ini_edital <= hoje <= self.data_fim_edital
    
    # verifica se as inscrições ainda não começaram
    def inscricoes_nao_iniciadas(self):
        return date.today() < self.data_ini_edital
    
    # verifica se as inscrições já encerraram
    def inscricoes_encerradas(self):
        return date.today() > self.data_fim_edital
    
    # retorna o número de inscrições ativas
    def contar_inscricoes_ativas(self):
        return Inscricao.query.filter_by(
            edital_id=self.id,
            status='Ativa'
        ).count()
    
    # verifica se ainda há vagas disponíveis
    def tem_vagas_disponiveis(self):
        return self.contar_inscricoes_ativas() < self.vagas


class Inscricao(db.Model):
    __tablename__ = 'inscricao'
    id = db.Column(db.Integer, primary_key=True)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    data_inscricao = db.Column(db.DateTime, default=db.func.now())
    edital_id = db.Column(db.Integer, db.ForeignKey('edital.id'), nullable=False)
    status = db.Column(db.String(30), default='Pendente')
    
    # cancela a inscrição
    def cancelar(self):
        self.status = 'Cancelada'
        db.session.commit()
    
    # ativa a inscrição
    def ativar(self):
        self.status = 'Ativa'
        db.session.commit()
    
    # verifica se tá ativa
    def esta_ativa(self):
        return self.status == 'Ativa'

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
    """Popula o banco com usuários administradores padrões"""
    admins = [
        {"nome": "Admin Breno", "email": "breno@gmail.com", "cpf": "00000000000", "senha": "breno123"},
        {"nome": "Admin Clara", "email": "clara@gmail.com", "cpf": "00000000001", "senha": "clara123"},
        {"nome": "Admin Eduardo", "email": "eduardo@gmail.com", "cpf": "00000000002", "senha": "eduardo123"},
        {"nome": "Admin Isabela", "email": "isabela@gmail.com", "cpf": "00000000003", "senha": "isabela123"},
        {"nome": "Admin Patrick", "email": "patrick@gmail.com", "cpf": "00000000004", "senha": "patrick123"}
    ]

    for data in admins:
        # só cria se o e-mail não estiver no banco
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
