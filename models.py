from datetime import date, datetime, timezone

from database import db
from werkzeug.security import check_password_hash, generate_password_hash


def agora_utc():
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Usuario(db.Model):
    __tablename__ = "usuarios"
    __table_args__ = (
        db.CheckConstraint(
            "length(nome) BETWEEN 3 AND 50",
            name="ck_usuarios_nome_tamanho",
        ),
    )

    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(50), nullable=False, unique=True, index=True)
    senha_hash = db.Column(db.String(255), nullable=False)
    data_criacao = db.Column(db.DateTime, nullable=False, default=agora_utc)
    onboarding_concluido = db.Column(db.Boolean, nullable=False, default=False)
    tarefas = db.relationship(
        "Tarefa",
        back_populates="usuario",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    categorias = db.relationship(
        "Categoria",
        back_populates="usuario",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    def definir_senha(self, senha):
        self.senha_hash = generate_password_hash(senha)

    def verificar_senha(self, senha):
        return check_password_hash(self.senha_hash, senha)

    def to_dict(self):
        return {
            "id": self.id,
            "nome": self.nome,
            "onboarding_concluido": self.onboarding_concluido,
        }


class Categoria(db.Model):
    __tablename__ = "categorias"
    __table_args__ = (
        db.UniqueConstraint(
            "user_id",
            "nome_chave",
            name="uq_categorias_usuario_nome",
        ),
        db.CheckConstraint(
            "length(trim(nome)) BETWEEN 1 AND 100",
            name="ck_categorias_nome_tamanho",
        ),
        db.CheckConstraint(
            "length(nome_chave) BETWEEN 1 AND 100",
            name="ck_categorias_nome_chave_tamanho",
        ),
        db.CheckConstraint(
            "length(cor) = 7",
            name="ck_categorias_cor_tamanho",
        ),
        db.CheckConstraint(
            "icone IS NULL OR length(icone) <= 20",
            name="ck_categorias_icone_tamanho",
        ),
    )

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer,
        db.ForeignKey("usuarios.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    nome = db.Column(db.String(100), nullable=False)
    nome_chave = db.Column(db.String(100), nullable=False)
    cor = db.Column(db.String(7), nullable=False, default="#7C6DF2")
    icone = db.Column(db.String(20), nullable=True)
    usuario = db.relationship("Usuario", back_populates="categorias")

    def to_dict(self):
        return {
            "id": self.id,
            "nome": self.nome,
            "cor": self.cor,
            "icone": self.icone,
        }


class Tarefa(db.Model):
    __tablename__ = "tarefas"
    __table_args__ = (
        db.CheckConstraint(
            "prioridade IN ('baixa', 'media', 'alta')",
            name="ck_tarefas_prioridade",
        ),
        db.CheckConstraint(
            "status IN ('pendente', 'concluida')",
            name="ck_tarefas_status",
        ),
        db.CheckConstraint(
            "length(trim(titulo)) BETWEEN 1 AND 200",
            name="ck_tarefas_titulo_tamanho",
        ),
        db.CheckConstraint(
            "categoria IS NULL OR length(categoria) <= 100",
            name="ck_tarefas_categoria_tamanho",
        ),
        db.CheckConstraint(
            "descricao IS NULL OR length(descricao) <= 5000",
            name="ck_tarefas_descricao_tamanho",
        ),
        db.CheckConstraint(
            "(arquivada = 0 AND data_arquivamento IS NULL) OR "
            "(arquivada = 1 AND data_arquivamento IS NOT NULL)",
            name="ck_tarefas_arquivamento_consistente",
        ),
        db.Index("ix_tarefas_usuario_arquivada", "user_id", "arquivada"),
        db.Index("ix_tarefas_usuario_prazo", "user_id", "data_limite"),
    )

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer,
        db.ForeignKey("usuarios.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    titulo = db.Column(db.String(200), nullable=False)
    descricao = db.Column(db.String(5000), nullable=True)
    categoria = db.Column(db.String(100), nullable=True)
    prioridade = db.Column(db.String(10), nullable=False, default="media")
    status = db.Column(db.String(10), nullable=False, default="pendente")
    data_criacao = db.Column(db.DateTime, nullable=False, default=agora_utc)
    data_limite = db.Column(db.Date, nullable=True)
    data_conclusao = db.Column(db.DateTime, nullable=True)
    arquivada = db.Column(db.Boolean, nullable=False, default=False)
    data_arquivamento = db.Column(db.DateTime, nullable=True)
    usuario = db.relationship("Usuario", back_populates="tarefas")

    @property
    def atrasada(self):
        return (
            not self.arquivada
            and self.status == "pendente"
            and self.data_limite is not None
            and self.data_limite < date.today()
        )

    def to_dict(self):
        return {
            "id": self.id,
            "titulo": self.titulo,
            "descricao": self.descricao,
            "categoria": self.categoria,
            "prioridade": self.prioridade,
            "status": self.status,
            "data_criacao": self.data_criacao.isoformat() + "Z",
            "data_limite": self.data_limite.isoformat() if self.data_limite else None,
            "data_conclusao": (
                self.data_conclusao.isoformat() + "Z"
                if self.data_conclusao
                else None
            ),
            "arquivada": self.arquivada,
            "data_arquivamento": (
                self.data_arquivamento.isoformat() + "Z"
                if self.data_arquivamento
                else None
            ),
            "atrasada": self.atrasada,
        }

