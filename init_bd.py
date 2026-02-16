from flask import Flask
from models import db, Usuario #importa de "models.py" o objeto db e classe Usuario

app = Flask(__name__) #inicia classe Flask (recursos de servidor) e define diretório atual como uma base do projeto
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///intercambio.db' #configuração e diretório do db (SQLite)
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False #desliga funções desnecessárias do SQLAlchemy

db.init_app(app) #conecta o db com o Flask (servidor)

def criar_base_de_dados(): #função de criação do db
    with app.app_context(): #abre a "conexão"/processo para db e Flask trabalharem juntos
  
        db.create_all() #cria todas tabelas atreladas ao db
        print("Banco de dados e tabelas criados com sucesso!")

        if not Usuario.buscar_por_email("teste@intercambio.com"): #se não existir no db esse email, entra
            usuario_teste = Usuario( #inserção manual de intercambista teste
                nome="João Intercambista",
                email="teste@intercambio.com",
                cpf="12345678901",
                senha_hash="123456"
            )
            
            db.session.add(usuario_teste) #prepara objeto usuario_teste para gravação no db
            db.session.commit() #gravação no db de objetos preparados
            print("Banco criado e usuário de teste adicionado!")
        else:
            print("Banco já existia e usuário de teste já estava lá.")

if __name__ == "__main__": #caso esse arquivo/script seja executado diretamente
     criar_base_de_dados() #chama/executa a função de criar o db