from flask_sqlalchemy import SQLAlchemy #importando a classe SQLAchemy

db = SQLAlchemy() #instância da classe SQLalchemy que codifica/decodificada facilidades SQL


class Usuario(db.Model): #criação da tabela Usuario como objeto
    id = db.Column(db.Integer, primary_key=True) #identificador, chave primária
    nome = db.Column(db.String(100), nullable=False) #nome, não nulo
    email = db.Column(db.String(100), unique=True, nullable=False) #email, único, não nulo
    cpf = db.Column(db.String(11), unique=True, nullable=False) #cpf, único, não nulo
    senha_hash = db.Column(db.String(200), nullable=False) #senha, não nula (futuramente será trasnformada em hash (criptografia))

    @staticmethod #métodos da classe, pois precisa de retorno tendo um objeto existente ou não
    def buscar_por_email(email_procurado): #função, procura principal, preenche o "self"
        return Usuario.query.filter_by(email=email_procurado).first() #consulta email no bd, retornando primeira ocorrência
    #Sucesso = Retorna instância do objeto Usuario / Fracasso = Retorna None (equivalente do NULL em SQL)


    def verificar_senha(self, senha_digitada): #self = objeto preenchido APÓS o método buscar_por_email
        return self.senha_hash == senha_digitada #comparação da senha digitada com o objeto
    #True(1) se igual/ False(0) se diferente

    #OBS: O self só existe se o buscar_por_email tiver sucedido, se não ele não é "alocado"
    #Logo, no login, checar email primeiro para não tentar acessar campo inexistente
