from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from functools import wraps
import os
import sys
import webbrowser
import logging
from datetime import datetime
from threading import Timer
import time # Adicionado para a trava de tempo



# ==============================================================================
# CONFIGURAÇÃO DE LOGGING PROFISSIONAL
# ==============================================================================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)




# ==============================================================================
# CONFIGURAÇÃO DE AMBIENTE E FLASK (CORRIGIDO PARA EXECUTÁVEL)
# ==============================================================================
if getattr(sys, 'frozen', False):
    # Se rodando como executável (.exe)
    template_folder = os.path.join(sys._MEIPASS, 'templates')
    static_folder = os.path.join(sys._MEIPASS, 'static')
    # base_path aponta para a pasta onde o .exe está fisicamente
    base_path = os.path.dirname(sys.executable)
    app = Flask(__name__, template_folder=template_folder, static_folder=static_folder)
else:
    # Se rodando como script (.py)
    base_path = os.path.abspath(os.path.dirname(__file__))
    app = Flask(__name__)

# MELHORIA DE SEGURANÇA E ESTABILIDADE: 
app.secret_key = "foodcost_chave_fixa_para_manter_sessao_123" 
from datetime import timedelta

app.permanent_session_lifetime = timedelta(minutes=30) # Desloga após 30 min de inatividade
app.config['SESSION_PERMANENT'] = True 
app.config['SESSION_TYPE'] = 'filesystem'
app.config['SESSION_COOKIE_NAME'] = "fc_session_stable" 

# ==============================================================================
# MELHORIA: DEFINIÇÃO ROBUSTA DO CAMINHO DO BANCO DE DADOS (AJUSTADO PARA NUVEM/LOCAL)
# ==============================================================================
# ==============================================================================
# CONFIGURAÇÃO DO BANCO DE DADOS (CORRIGIDO PARA RECONHECER O RENDER)
# ==============================================================================
database_url = os.getenv("DATABASE_URL")

# Se estiver no Render, ele usa a URL do PostgreSQL. Se não, usa SQLite local.
if database_url:
    if database_url.startswith("postgres://"):
        database_url = database_url.replace("postgres://", "postgresql://", 1)
    app.config["SQLALCHEMY_DATABASE_URI"] = database_url
else:
    db_name = "database.db"
    db_path = os.path.join(base_path, db_name)
    app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{db_path}"

app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

# --- DIAGNÓSTICO VISUAL NO TERMINAL ---
print("\n" + "="*80)
print(f" >>> SISTEMA INICIADO <<<")
print(f" BANCO ATIVO: {'PostgreSQL (Nuvem)' if database_url else f'SQLite Local: {db_path}'}")
print("="*80 + "\n")

app.config["SQLALCHEMY_DATABASE_URI"] = database_url or f"sqlite:///{db_path}"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["JSON_AS_ASCII"] = False

logger.info(f"Conexão de banco estabelecida via: {'DATABASE_URL' if database_url else 'SQLite File'}")

db = SQLAlchemy(app)

@app.before_request
def verificar_loja_ativa():
    from flask import request, session, redirect, url_for, render_template, flash
    from datetime import datetime, timedelta

    # Rotas que não exigem verificação
    rotas_livres = {
        'login',
        'logout'
    }

    if request.endpoint:
        if request.endpoint in rotas_livres:
            return
        if request.endpoint.startswith('static'):
            return

    usuario_id = session.get('usuario_id')
    if not usuario_id:
        return

    usuario = db.session.get(Usuario, usuario_id)
    if not usuario:
        session.clear()
        return redirect(url_for('login'))

    # Supervisor (admin) nunca é bloqueado
    if usuario.role == 'admin':
        return

    if not usuario.loja_id:
        flash('Usuário sem loja vinculada.', 'danger')
        session.clear()
        return redirect(url_for('login'))

    loja = db.session.get(Loja, usuario.loja_id)
    if not loja or not loja.ativo:
        session.clear()
        return render_template('bloqueado.html', loja=loja), 403

    # ===============================
    # 🔐 VERIFICAÇÃO DA MÁQUINA
    # ===============================
    fp = request.cookies.get('fp')
    if not fp:
        return "Fingerprint não identificado", 403

    maquina = Maquina.query.filter_by(
        loja_id=usuario.loja_id,
        fingerprint=fp
    ).first()

    # ===============================
    # 🆕 REGISTRA MÁQUINA AUTOMATICAMENTE
    # ===============================
    if not maquina:
        maquina = Maquina(
            loja_id=usuario.loja_id,
            fingerprint=fp,
            ativa=True,
            criada_em=datetime.utcnow(),
            expira_em=datetime.utcnow() + timedelta(days=30)
        )
        db.session.add(maquina)

        log = LogAcesso(
            loja_id=usuario.loja_id,
            usuario_id=usuario.id,
            fingerprint=fp,
            ip=request.remote_addr,
            motivo='MAQUINA_REGISTRADA_AUTOMATICAMENTE'
        )
        db.session.add(log)
        db.session.commit()

    # ===============================
    # ⛔ BLOQUEIO POR STATUS
    # ===============================
    if not maquina.ativa:
        return render_template('maquina_nao_autorizada.html'), 403

    # ===============================
    # ⏳ BLOQUEIO POR LICENÇA EXPIRADA
    # ===============================
    if maquina.expira_em and maquina.expira_em < datetime.utcnow():
        return render_template(
            'licenca_expirada.html',
            maquina=maquina,
            loja=loja
        ), 403



# ==============================================================================
# TRAVA DE SEGURANÇA MESTRA (ADICIONADO)
# ==============================================================================
CHAVE_MESTRA = os.getenv("CHAVE_MESTRA")

def access_locked(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # CORREÇÃO: Se CHAVE_MESTRA existir e a sessão não estiver validada, bloqueia.
        if CHAVE_MESTRA and not session.get('acesso_validado'):
            return render_template('portal_acesso.html')
        return f(*args, **kwargs)
    return decorated_function

# ==============================================================================
# DECORADORES DE SEGURANÇA
# ==============================================================================
def login_required(f):
    @wraps(f)
    @access_locked # Garante que a chave mestra venha antes de tudo
    def decorated_function(*args, **kwargs):
        if 'usuario_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function



def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get('role') != 'admin':
            flash("ACESSO NEGADO: Requer privilégios de Administrador (Supervisor).", "danger")
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated_function

# ==============================================================================
# FILTROS DE FORMATAÇÃO JINJA2
# ==============================================================================
@app.template_filter('moeda')
def moeda_filter(v):
    try:
        return f"R$ {float(v or 0):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except:
        return "R$ 0,00"

@app.template_filter('peso')
def peso_filter(v):
    try:
        return f"{float(v or 0):,.3f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except:
        return "0,000"

@app.template_filter('percentual')
def percent_filter(v):
    try:
        return f"{float(v or 0):.2f}%"
    except:
        return "0.00%"

# ==============================================================================
# MODELOS DE DADOS (ORM) - MELHORIA: ADICIONADO USER_ID PARA ISOLAMENTO
# ==============================================================================
class Usuario(db.Model):
    __tablename__ = 'usuarios'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password = db.Column(db.String(100), nullable=False)
    role = db.Column(db.String(20), default='user')
    data_criacao = db.Column(db.DateTime, default=datetime.utcnow)
    # ===== PATCH ERP: VÍNCULO COM LOJA =====
    loja_id = db.Column(db.Integer, db.ForeignKey('lojas.id'))
    loja = db.relationship('Loja')
    # ===== PATCH ERP =====

class Maquina(db.Model):
    __tablename__ = 'maquinas'

    id = db.Column(db.Integer, primary_key=True)
    loja_id = db.Column(db.Integer, db.ForeignKey('lojas.id'))
    fingerprint = db.Column(db.String(255), unique=True)
    ativa = db.Column(db.Boolean, default=True)

    criada_em = db.Column(db.DateTime, default=datetime.utcnow)
    expira_em = db.Column(db.DateTime)



class Loja(db.Model):
    __tablename__ = 'lojas'
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(120), nullable=False)
    ativo = db.Column(db.Boolean, default=True)
    criado_em = db.Column(db.DateTime, default=datetime.utcnow)

class LogAcesso(db.Model):
    __tablename__ = 'logs_acesso'

    id = db.Column(db.Integer, primary_key=True)
    loja_id = db.Column(db.Integer, db.ForeignKey('lojas.id'))
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'))
    fingerprint = db.Column(db.String(255))
    ip = db.Column(db.String(50))
    motivo = db.Column(db.String(100))
    data = db.Column(db.DateTime, default=datetime.utcnow)


def loja_ativa_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        usuario_id = session.get('usuario_id')
        if not usuario_id:
            return redirect(url_for('login'))

        usuario = db.session.get(Usuario, usuario_id)
        loja = db.session.get(Loja, usuario.loja_id)

        if not loja or not loja.ativo:
            flash("Esta loja está bloqueada pelo supervisor.", "danger")
            session.clear()
            return redirect(url_for('login'))

        return f(*args, **kwargs)
    return decorated


class Categoria(db.Model):
    __tablename__ = 'categorias'
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(50), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'))
    # ===== PATCH ERP =====
    loja_id = db.Column(db.Integer, db.ForeignKey('lojas.id'))


class Unidade(db.Model):
    __tablename__ = 'unidades'
    id = db.Column(db.Integer, primary_key=True)
    sigla = db.Column(db.String(10), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'))

class Insumo(db.Model):
    __tablename__ = 'insumos'
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(150), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('usuarios.id')) 
    categoria_id = db.Column(db.Integer, db.ForeignKey('categorias.id'))
    unidade_id = db.Column(db.Integer, db.ForeignKey('unidades.id'))
    preco_embalagem = db.Column(db.Float, nullable=False, default=0.0)
    tamanho_embalagem = db.Column(db.Float, nullable=False, default=1.0)
    fator_correcao = db.Column(db.Float, default=1.0)
    custo_unitario = db.Column(db.Float, default=0.0)
    
    categoria = db.relationship('Categoria', backref='insumos')
    unidade = db.relationship('Unidade', backref='insumos')
    # ===== PATCH ERP =====
    loja_id = db.Column(db.Integer, db.ForeignKey('lojas.id'))


class Base(db.Model):
    __tablename__ = 'bases'
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(150), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('usuarios.id')) 
    rendimento_final = db.Column(db.Float, default=1.0)
    data_atualizacao = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    itens = db.relationship('BaseItem', backref='base', cascade='all, delete-orphan')
    # ===== PATCH ERP =====
    loja_id = db.Column(db.Integer, db.ForeignKey('lojas.id'))

    @property
    def custo_total_producao(self):
        return sum(((it.quantidade or 0) * (it.insumo.custo_unitario or 0)) for it in self.itens if it.insumo)

    @property
    def custo_por_unidade(self):
        if self.rendimento_final and self.rendimento_final > 0:
            return self.custo_total_producao / self.rendimento_final
        return 0.0

    @property
    def rendimento(self):
        return self.rendimento_final

    @property
    def custo_por_kg_litro(self):
        return self.custo_por_unidade

class BaseItem(db.Model):
    __tablename__ = 'base_itens'
    id = db.Column(db.Integer, primary_key=True)
    base_id = db.Column(db.Integer, db.ForeignKey('bases.id'))
    insumo_id = db.Column(db.Integer, db.ForeignKey('insumos.id'))
    quantidade = db.Column(db.Float, nullable=False)
    insumo = db.relationship('Insumo')
    # ===== PATCH ERP =====
    loja_id = db.Column(db.Integer, db.ForeignKey('lojas.id'))


class Ficha(db.Model):
    __tablename__ = 'fichas'
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(150), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('usuarios.id')) 
    porcoes = db.Column(db.Float, default=1.0)
    preco_venda = db.Column(db.Float, default=0.0)
    cmv_alvo = db.Column(db.Float, default=30.0)
    data_criacao = db.Column(db.DateTime, default=datetime.utcnow)
    itens = db.relationship('FichaItem', backref='ficha', cascade='all, delete-orphan')
    # ===== PATCH ERP =====
    loja_id = db.Column(db.Integer, db.ForeignKey('lojas.id'))


class FichaItem(db.Model):
    __tablename__ = 'ficha_itens'
    id = db.Column(db.Integer, primary_key=True)
    ficha_id = db.Column(db.Integer, db.ForeignKey('fichas.id'))
    tipo_item = db.Column(db.String(10)) 
    referencia_id = db.Column(db.Integer, nullable=False)
    quantidade = db.Column(db.Float, nullable=False)
    # ===== PATCH ERP =====
    loja_id = db.Column(db.Integer, db.ForeignKey('lojas.id'))


def dias_restantes(expira_em):
    hoje = datetime.now().date()
    restante = (expira_em - hoje).days
    return max(restante, 0)



@app.context_processor
def inject_loja():
    try:
        usuario_id = session.get('usuario_id')
        if not usuario_id:
            return {}

        usuario = db.session.get(Usuario, usuario_id)
        if not usuario or not getattr(usuario, 'loja_id', None):
            return {}

        loja = db.session.get(Loja, usuario.loja_id)
        if not loja:
            return {}

        return dict(loja_atual=loja)
    except Exception as e:
        logger.error(f"Erro inject_loja: {e}")
        return {}




# ==============================================================================
# MOTOR DE CÁLCULO AVANÇADO
# ==============================================================================
class EngineCalculo:
    @staticmethod
    def processar_ficha(ficha_id):
        ficha = db.session.get(Ficha, ficha_id)
        if not ficha:
            return None
        
        custo_total = 0.0
        detalhes_itens = []

        for item in ficha.itens:
            nome_item = "Desconhecido"
            custo_un = 0.0
            unidade = "-"
            
            if item.tipo_item == 'insumo':
                obj = db.session.get(Insumo, item.referencia_id)
                if obj:
                    nome_item = obj.nome
                    custo_un = obj.custo_unitario or 0
                    unidade = obj.unidade.sigla if obj.unidade else "un"
            else:
                obj = db.session.get(Base, item.referencia_id)
                if obj:
                    nome_item = f"[BASE] {obj.nome}"
                    custo_un = obj.custo_por_unidade
                    unidade = "Base"

            subtotal = (item.quantidade or 0) * (custo_un or 0)
            custo_total += subtotal
            detalhes_itens.append({
                'nome': nome_item,
                'qtd': item.quantidade,
                'un': unidade,
                'custo_un': custo_un,
                'subtotal': subtotal
            })

        custo_porcao = custo_total / ficha.porcoes if ficha.porcoes > 0 else 0
        lucro_bruto = ficha.preco_venda - custo_porcao
        margem = (lucro_bruto / ficha.preco_venda * 100) if ficha.preco_venda > 0 else 0
        cmv_real = (custo_porcao / ficha.preco_venda * 100) if ficha.preco_venda > 0 else 0
        p_sugerido = custo_porcao / (ficha.cmv_alvo / 100) if ficha.cmv_alvo > 0 else 0

        return {
            'itens': detalhes_itens,
            'custo_total': custo_total,
            'custo_porcao': custo_porcao,
            'lucro_bruto': lucro_bruto,
            'margem_contribuicao': margem,
            'cmv_real': cmv_real,
            'preco_sugerido': p_sugerido
        }

# ==============================================================================
# ROTAS DE NAVEGAÇÃO E DASHBOARD
# ==============================================================================
@app.route('/validar-chave', methods=['POST'])
def validar_chave():
    chave_digitada = request.form.get('chave_secreta')
    if chave_digitada == CHAVE_MESTRA:
        session['acesso_validado'] = True
        return redirect(url_for('login'))
    flash("Chave mestra incorreta!", "danger")
    return redirect(url_for('login'))

# ===== PATCH ERP =====
@app.route('/trocar-loja/<int:loja_id>')
@login_required
@admin_required
def trocar_loja(loja_id):
    loja = db.session.get(Loja, loja_id)
    if loja and loja.ativo:
        session['loja_id'] = loja.id
        flash(f"Loja ativa: {loja.nome}", "info")
    return redirect(url_for('index'))


@app.route('/')
@login_required
def index():
    try:
        # FILTRO POR USUÁRIO: Admin vê tudo, user vê só o dele
        if session.get('role') == 'admin':
            fichas = Ficha.query.order_by(Ficha.nome).all()
        else:
            fichas = Ficha.query.filter_by(user_id=session['usuario_id']).order_by(Ficha.nome).all()
            
        lista_final = []
        for f in fichas:
            res = EngineCalculo.processar_ficha(f.id)
            lista_final.append({'ficha': f, 'metricas': res})
        return render_template('index.html', dados=lista_final)
    except Exception as e:
        logger.error(f"Erro no Index: {e}")
        return f"Erro Crítico: {e}", 500

@app.route('/login', methods=['GET', 'POST'])
@access_locked 
def login():
    if request.method == 'POST':
        u = request.form.get('username')
        p = request.form.get('password')
        
        # BLOQUEIO MANUAL DO ADMIN PADRÃO
        if u == 'admin':
            flash("Este usuário foi desativado por segurança.", "danger")
            return render_template('login.html')

        user = Usuario.query.filter_by(username=u, password=p).first()
        # ... resto do seu código original
        if user:
            session['usuario_id'] = user.id
            session['usuario_nome'] = user.username
            session['role'] = user.role

            logger.info(f"Usuário {u} logado com sucesso.")
            # ===== PATCH ERP =====
            session['loja_id'] = user.loja_id

            return redirect(url_for('index'))
        flash("Credenciais inválidas.", "danger")
    return render_template('login.html')

@app.route('/insumos', methods=['GET', 'POST'])
@login_required
def insumos():
    uid = session['usuario_id']
    if request.method == 'POST':
        try:
            nome = request.form.get('nome').upper().strip()
            p_emb = float(request.form.get('preco').replace(',', '.'))
            t_emb = float(request.form.get('tamanho').replace(',', '.'))
            fc = float(request.form.get('fc').replace(',', '.'))
            
            novo_insumo = Insumo(
                nome=nome,
                user_id=uid, 
                categoria_id=request.form.get('categoria_id'),
                unidade_id=request.form.get('unidade_id'),
                preco_embalagem=p_emb,
                tamanho_embalagem=t_emb,
                fator_correcao=fc,
                custo_unitario=(p_emb / t_emb) * fc
            )
            db.session.add(novo_insumo)
            db.session.commit()
            flash(f"Insumo {nome} cadastrado!", "success")
        except Exception as e:
            db.session.rollback()
            flash(f"Erro ao cadastrar: {e}", "danger")
    
    # LISTAGEM ISOLADA
    if session.get('role') == 'admin':
        insumos_lista = Insumo.query.all()
        cats = Categoria.query.all()
        unis = Unidade.query.all()
    else:
        insumos_lista = Insumo.query.filter_by(user_id=uid).all()
        cats = Categoria.query.filter_by(user_id=uid).all()
        unis = Unidade.query.filter_by(user_id=uid).all()
        
    return render_template('insumos.html', lista=insumos_lista, categorias=cats, unidades=unis)

@app.route('/insumos/editar/<int:id>', methods=['GET', 'POST'])
@login_required
def editar_insumo(id):
    ins = db.session.get(Insumo, id)
    uid = session['usuario_id']
    # Proteção de acesso
    if session.get('role') != 'admin' and ins.user_id != uid:
        flash("Acesso negado.", "danger")
        return redirect(url_for('insumos'))

    if request.method == 'POST':
        try:
            ins.nome = request.form.get('nome').upper().strip()
            ins.preco_embalagem = float(request.form.get('preco').replace(',', '.'))
            ins.tamanho_embalagem = float(request.form.get('tamanho').replace(',', '.'))
            ins.fator_correcao = float(request.form.get('fc').replace(',', '.'))
            ins.custo_unitario = (ins.preco_embalagem / ins.tamanho_embalagem) * ins.fator_correcao
            ins.categoria_id = request.form.get('categoria_id')
            ins.unidade_id = request.form.get('unidade_id')
            db.session.commit()
            flash("Insumo atualizado!", "success")
            return redirect(url_for('insumos'))
        except Exception as e:
            db.session.rollback()
            flash(f"Erro na edição: {e}", "danger")
    
    # IMPORTANTE: Filtrar as categorias/unidades do usuário na edição também
    return render_template('insumos_form.html', i=ins, 
                           categorias=Categoria.query.filter_by(user_id=uid).all(), 
                           unidades=Unidade.query.filter_by(user_id=uid).all())

@app.route('/bases', methods=['GET', 'POST'])
@login_required
def bases():
    if request.method == 'POST':
        return nova_base()
    
    if session.get('role') == 'admin':
        lista = Base.query.all()
    else:
        lista = Base.query.filter_by(user_id=session['usuario_id']).all()
    return render_template('bases.html', lista=lista)

@app.route('/del/bas/<int:id>')
@login_required
@admin_required
def deletar_base_alias(id):
    return excluir('base', id)

@app.route('/bases/nova', methods=['GET', 'POST'])
@login_required
def nova_base():
    uid = session['usuario_id']
    if request.method == 'POST':
        try:
            nome_base = request.form.get('nome')
            if not nome_base:
                flash("Nome da base é obrigatório!", "warning")
                return redirect(url_for('bases'))

            rend_val = float(request.form.get('rendimento', '1').replace(',', '.') or 1)
            
            b = Base(
                nome=nome_base.upper(),
                user_id=uid,
                rendimento_final=rend_val
            )
            db.session.add(b)
            db.session.flush() 
            
            ids = request.form.getlist('insumo_id[]')
            qtds = request.form.getlist('quantidade[]')
            
            for idx, i_id in enumerate(ids):
                if i_id and idx < len(qtds):
                    qtd_val = float(qtds[idx].replace(',', '.') or 0)
                    if qtd_val > 0:
                        item = BaseItem(base_id=b.id, insumo_id=int(i_id), quantidade=qtd_val)
                        db.session.add(item)
            
            db.session.commit()
            flash(f"Base '{b.nome}' salva com sucesso!", "success")
            return redirect(url_for('bases'))
        except Exception as e:
            db.session.rollback()
            logger.error(f"Erro ao salvar base: {e}")
            flash(f"Erro ao criar base: {e}", "danger")
            
    ins = Insumo.query.filter_by(user_id=uid).all()
    return render_template('bases_form.html', insumos=ins, base=None)

@app.route('/bases/editar/<int:id>', methods=['GET', 'POST'])
@login_required
def editar_base(id):
    base_obj = db.session.get(Base, id)
    uid = session['usuario_id']
    if not base_obj or (session.get('role') != 'admin' and base_obj.user_id != uid):
        flash("Base não encontrada ou acesso negado.", "danger")
        return redirect(url_for('bases'))

    if request.method == 'POST':
        try:
            base_obj.nome = request.form.get('nome').upper()
            base_obj.rendimento_final = float(request.form.get('rendimento').replace(',', '.') or 1)
            BaseItem.query.filter_by(base_id=id).delete()
            
            ids = request.form.getlist('insumo_id[]')
            qtds = request.form.getlist('quantidade[]')
            for idx, i_id in enumerate(ids):
                if i_id and idx < len(qtds):
                    qtd_val = float(qtds[idx].replace(',', '.') or 0)
                    if qtd_val > 0:
                        db.session.add(BaseItem(base_id=id, insumo_id=int(i_id), quantidade=qtd_val))
            
            db.session.commit()
            flash("Base atualizada com sucesso!", "success")
            return redirect(url_for('bases'))
        except Exception as e:
            db.session.rollback()
            flash(f"Erro ao editar base: {e}", "danger")
            
    ins = Insumo.query.filter_by(user_id=uid).all()
    return render_template('bases_form.html', base=base_obj, insumos=ins)

@app.route('/fichas/nova', methods=['GET', 'POST'])
@login_required
def nova_ficha():
    uid = session['usuario_id']
    if request.method == 'POST':
        try:
            f = Ficha(
                nome=request.form.get('nome').upper(),
                user_id=uid, 
                porcoes=float(request.form.get('porcoes').replace(',', '.') or 1),
                preco_venda=float(request.form.get('preco_venda').replace(',', '.') or 0),
                cmv_alvo=float(request.form.get('cmv_alvo').replace(',', '.') or 30)
            )
            db.session.add(f)
            db.session.flush()
            
            i_ids = request.form.getlist('insumo_id[]')
            i_qtds = request.form.getlist('insumo_qtd[]')
            for idx, val in enumerate(i_ids):
                if val: db.session.add(FichaItem(ficha_id=f.id, tipo_item='insumo', referencia_id=int(val), quantidade=float(i_qtds[idx].replace(',', '.'))))
            
            b_ids = request.form.getlist('base_id[]')
            b_qtds = request.form.getlist('base_qtd[]')
            for idx, val in enumerate(b_ids):
                if val: db.session.add(FichaItem(ficha_id=f.id, tipo_item='base', referencia_id=int(val), quantidade=float(b_qtds[idx].replace(',', '.'))))
            
            db.session.commit()
            flash("Ficha Técnica gerada com sucesso!", "success")
            return redirect(url_for('index'))
        except Exception as e:
            db.session.rollback()
            flash(f"Erro ao salvar ficha: {e}", "danger")
            
    return render_template('ficha_form.html', insumos=Insumo.query.filter_by(user_id=uid).all(), bases=Base.query.filter_by(user_id=uid).all(), ficha=None)

@app.route('/fichas/ver/<int:id>')
@login_required
def ver_ficha(id):
    f = db.session.get(Ficha, id)
    if not f or (session.get('role') != 'admin' and f.user_id != session['usuario_id']):
        flash("Ficha não encontrada ou acesso negado.", "warning")
        return redirect(url_for('index'))
    
    metricas = EngineCalculo.processar_ficha(id)
    return render_template('ficha_ver.html', f=f, m=metricas)

@app.route('/fichas/editar/<int:id>', methods=['GET', 'POST'])
@login_required
def editar_ficha(id):
    f = db.session.get(Ficha, id)
    uid = session['usuario_id']
    if not f or (session.get('role') != 'admin' and f.user_id != uid):
        flash("Ficha não encontrada ou acesso negado.", "danger")
        return redirect(url_for('index'))

    if request.method == 'POST':
        try:
            f.nome = request.form.get('nome').upper()
            f.porcoes = float(request.form.get('porcoes').replace(',', '.'))
            f.preco_venda = float(request.form.get('preco_venda').replace(',', '.'))
            f.cmv_alvo = float(request.form.get('cmv_alvo').replace(',', '.'))
            FichaItem.query.filter_by(ficha_id=id).delete()
            
            i_ids = request.form.getlist('insumo_id[]')
            i_qtds = request.form.getlist('insumo_qtd[]')
            for idx, val in enumerate(i_ids):
                if val: db.session.add(FichaItem(ficha_id=id, tipo_item='insumo', referencia_id=int(val), quantidade=float(i_qtds[idx].replace(',', '.'))))
            
            b_ids = request.form.getlist('base_id[]')
            b_qtds = request.form.getlist('base_qtd[]')
            for idx, val in enumerate(b_ids):
                if val: db.session.add(FichaItem(ficha_id=id, tipo_item='base', referencia_id=int(val), quantidade=float(b_qtds[idx].replace(',', '.'))))
                
            db.session.commit()
            flash("Ficha Técnica atualizada com sucesso!", "info")
            return redirect(url_for('index'))
        except Exception as e:
            db.session.rollback()
            flash(f"Erro ao atualizar ficha: {e}", "danger")
            
    return render_template('ficha_form.html', ficha=f, insumos=Insumo.query.filter_by(user_id=uid).all(), bases=Base.query.filter_by(user_id=uid).all())

def acesso_config_master(f):
    def wrapper(*args, **kwargs):
        if session.get('usuario') == 'master':
            return f(*args, **kwargs)
        else:
            flash("Acesso restrito: você só pode gerenciar categorias e unidades.", "warning")
            return redirect(url_for('config_restrito'))
    wrapper.__name__ = f.__name__
    return wrapper




# ===============================
# ===============================
# CONFIGURAÇÕES GERAIS (Categorias e Unidades)
@app.route('/config')
@login_required
def config():
    uid = session.get('usuario_id')
    user = db.session.get(Usuario, uid)

    if hasattr(user, 'is_master') and user.is_master:
        return redirect(url_for('config_master'))
    elif session.get('role') == 'admin':
        return redirect(url_for('config_restrito'))
    else:
        flash("Acesso restrito!", "danger")
        return redirect(url_for('index'))


# Acesso: apenas usuários master
# ===============================
@app.route('/config_master', methods=['GET', 'POST'])
@login_required
def config_master():
    uid = session.get('usuario_id')
    user = Usuario.query.get(uid)

    if not user.is_master:
        flash("Acesso restrito para usuários master!", "danger")
        return redirect(url_for('index'))

    if request.method == 'POST':
        tipo_acao = request.form.get('tipo_acao')

        # Criar categoria
        if tipo_acao == 'add_cat':
            nome = request.form.get('nome_cat', '').upper().strip()
            if nome and not Categoria.query.filter_by(nome=nome).first():
                nova_cat = Categoria(nome=nome)
                db.session.add(nova_cat)
                db.session.commit()
                flash("Categoria criada com sucesso!", "success")
            else:
                flash("Categoria já existe ou nome inválido!", "warning")

        # Criar unidade
        elif tipo_acao == 'add_uni':
            sigla = request.form.get('sigla_uni', '').upper().strip()
            if sigla and not Unidade.query.filter_by(sigla=sigla).first():
                nova_uni = Unidade(sigla=sigla)
                db.session.add(nova_uni)
                db.session.commit()
                flash("Unidade criada com sucesso!", "success")
            else:
                flash("Unidade já existe ou sigla inválida!", "warning")

    # Busca completa
    lojas = Loja.query.all()
    maquinas = Maquina.query.all()
    usuarios = Usuario.query.all()
    categorias = Categoria.query.all()
    unidades = Unidade.query.all()

    return render_template(
        'config_master.html',
        lojas=lojas,
        maquinas=maquinas,
        usuarios=usuarios,
        categorias=categorias,
        unidades=unidades
    )


# ===============================
# CONFIGURAÇÕES RESTRITAS (Usuários, Lojas, Máquinas)
# Acesso: usuários supervisores/master
# ===============================
@app.route('/config_restrito', methods=['GET','POST'])
@login_required
def config_restrito():
    uid = session.get('usuario_id')
    if not uid:
        flash("Sessão inválida, faça login novamente.", "warning")
        return redirect(url_for('login'))

    usuario = Usuario.query.get(uid)
    if not usuario:
        flash("Usuário não encontrado.", "danger")
        return redirect(url_for('login'))

    if request.method == 'POST':
        tipo_acao = request.form.get('tipo_acao')
        # ... seu código de POST permanece aqui ...

    # Buscar dados
    usuarios = Usuario.query.all()
    lojas = Loja.query.all()
    maquinas = Maquina.query.all()

    return render_template(
        'config_restrito.html',
        usuario=usuario,
        usuarios=usuarios,
        lojas=lojas,
        maquinas=maquinas
    )

# DECORATORS DE CONFIGURAÇÃO
# ===============================
def config_geral_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'usuario_id' not in session:
            flash("Faça login para acessar as configurações.", "warning")
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def config_restrito_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get('role') != 'admin':
            flash("Acesso restrito: apenas supervisores podem acessar.", "danger")
            return redirect(url_for('config'))
        return f(*args, **kwargs)
    return decorated_function

# ===============================
# ROTA CONFIGURAÇÃO RESTRITA
# ===============================

@app.route('/excluir/<string:alvo>/<int:id>')
@login_required
def excluir(alvo, id):
    mapa = {
        'insumo': Insumo, 'ficha': Ficha, 'base': Base,
        'categoria': Categoria, 'unidade': Unidade, 'usuario': Usuario
    }
    try:
        if alvo in mapa:
            obj = db.session.get(mapa[alvo], id)
            if not obj: return redirect(request.referrer or url_for('index'))

            # Proteção: só admin ou o dono exclui
            pode_excluir = session.get('role') == 'admin' or (hasattr(obj, 'user_id') and obj.user_id == session['usuario_id'])
            
            # CORREÇÃO: Permite excluir qualquer usuário que não seja você mesmo
            if alvo == 'usuario' and id == session.get('usuario_id'):
                flash("Você não pode excluir seu próprio usuário!", "danger")
                return redirect(url_for('config'))

            if obj and pode_excluir:
                db.session.delete(obj)
                db.session.commit()
                flash(f"{alvo.capitalize()} removido.", "success")
            else:
                flash("Acesso negado para exclusão.", "danger")
                
        return redirect(url_for('bases') if alvo == 'base' else (request.referrer or url_for('index')))
    except IntegrityError:
        db.session.rollback()
        flash("Não é possível excluir: Item vinculado.", "warning")
        return redirect(request.referrer or url_for('index'))
    
@app.route('/config/lojas', methods=['GET', 'POST'])
@login_required
@admin_required
def config_lojas():
    if request.method == 'POST':
        loja_id = request.form.get('loja_id')
        acao = request.form.get('acao')

        loja = db.session.get(Loja, loja_id)
        if loja:
            if acao == 'toggle':
                loja.ativo = not loja.ativo
            db.session.commit()

    lojas = Loja.query.order_by(Loja.nome).all()
    return render_template('config_lojas.html', lojas=lojas)


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/toggle/loja/<int:loja_id>')
def toggle_loja(loja_id):
    loja = Loja.query.get_or_404(loja_id)
    loja.ativo = not loja.ativo
    db.session.commit()
    flash('Status da loja atualizado.', 'info')
    return redirect(url_for('config'))

# ===============================
# ROTAS DE MÁQUINAS E LICENÇAS
# ===============================

@app.route('/maquinas')
@login_required
@admin_required
def listar_maquinas():
    maquinas = Maquina.query.order_by(Maquina.criada_em.desc()).all()
    return render_template('maquinas.html', maquinas=maquinas)

@app.route('/maquinas/nova', methods=['GET', 'POST'])
@login_required
@admin_required
def nova_maquina():
    lojas = Loja.query.filter_by(ativo=True).all()
    if request.method == 'POST':
        loja_id = request.form.get('loja_id')
        fingerprint = request.form.get('fingerprint').strip()
        dias_validos = int(request.form.get('dias_validos', 30))

        if Maquina.query.filter_by(fingerprint=fingerprint).first():
            flash("Máquina já cadastrada!", "warning")
            return redirect(url_for('nova_maquina'))

        maquina = Maquina(
            loja_id=loja_id,
            fingerprint=fingerprint,
            ativa=True,
            criada_em=datetime.utcnow(),
            expira_em=datetime.utcnow() + timedelta(days=dias_validos)
        )
        db.session.add(maquina)

        log = LogAcesso(
            loja_id=loja_id,
            usuario_id=session.get('usuario_id'),
            fingerprint=fingerprint,
            ip=request.remote_addr,
            motivo='MAQUINA_CADASTRADA_MANUAL'
        )
        db.session.add(log)

        db.session.commit()
        flash("Máquina cadastrada com sucesso!", "success")
        return redirect(url_for('listar_maquinas'))

    return render_template('maquinas_form.html', lojas=lojas, maquina=None)

@app.route('/maquinas/editar/<int:id>', methods=['GET', 'POST'])
@login_required
@admin_required
def editar_maquina(id):
    maquina = db.session.get(Maquina, id)
    if not maquina:
        flash("Máquina não encontrada.", "danger")
        return redirect(url_for('listar_maquinas'))

    lojas = Loja.query.filter_by(ativo=True).all()
    if request.method == 'POST':
        maquina.loja_id = request.form.get('loja_id')
        maquina.fingerprint = request.form.get('fingerprint').strip()
        maquina.ativa = True if request.form.get('ativa') == '1' else False
        dias_validos = int(request.form.get('dias_validos', 30))
        maquina.expira_em = datetime.utcnow() + timedelta(days=dias_validos)

        db.session.commit()
        flash("Máquina atualizada com sucesso!", "success")
        return redirect(url_for('listar_maquinas'))

    return render_template('maquinas_form.html', maquinas=lojas, maquina=maquina)

@app.route('/maquinas/toggle/<int:id>')
@login_required
@admin_required
def toggle_maquina(id):
    maquina = db.session.get(Maquina, id)
    if maquina:
        maquina.ativa = not maquina.ativa
        db.session.commit()
        flash(f"Máquina {'ativada' if maquina.ativa else 'desativada'}!", "info")
    return redirect(url_for('listar_maquinas'))

@app.route('/maquinas/historico/<int:id>')
@login_required
@admin_required
def historico_maquina(id):
    logs = LogAcesso.query.filter_by(fingerprint=Maquina.query.get(id).fingerprint).order_by(LogAcesso.data.desc()).all()
    return render_template('maquinas_historico.html', logs=logs)

def criar_maquina(loja_id, fingerprint):
    hoje = datetime.now().date()
    expira = hoje + timedelta(days=30)
    nova_maquina = Maquina(loja_id=loja_id, fingerprint=fingerprint, ativa=True, expira_em=expira)
    db.session.add(nova_maquina)
    db.session.commit()
    return nova_maquina



# ==============================================================================
# INICIALIZAÇÃO DO BANCO E APP
# ==============================================================================
def setup_database():
    with app.app_context():
        db.create_all()

        # ==== GARANTE LOJA PADRÃO ====
        loja = Loja.query.first()
        if not loja:
            loja = Loja(nome="Loja Principal", ativo=True)
            db.session.add(loja)
            db.session.commit()
            logger.info(">>> Loja padrão criada")

        # ==== GARANTE USUÁRIO MESTRE ====
        usuario = Usuario.query.filter_by(username='bpereira').first()
        if not usuario:
            usuario = Usuario(
                username='bpereira',
                password='chef@26',
                role='admin',
                loja_id=loja.id
            )
            db.session.add(usuario)
            db.session.commit()
            logger.info(">>> Usuário mestre criado")
        else:
            usuario.loja_id = loja.id
            usuario.role = 'admin'
            usuario.password = 'chef@26'
            db.session.commit()
            logger.info(">>> Usuário mestre ajustado")



if __name__ == '__main__':
    setup_database()
    app.run(debug=True)


