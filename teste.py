from FoodCost_Ultimate_ERP_v8.app1 import app, db, Ficha, Insumo, Base

with app.app_context():
    fichas = Ficha.query.all()
    print(f"--- Diagnóstico de {len(fichas)} Fichas ---")
    for f in fichas:
        # Simulação do cálculo que injetaremos no app.py
        total = sum(it.qtd * (db.session.get(Insumo, it.item_id).custo_un if it.tipo == 'ins' else db.session.get(Base, it.item_id).custo_por_kg_litro) for it in f.itens)
        print(f"Ficha: {f.nome} | Custo Total: R$ {total:.2f} | Preço Venda: R$ {f.preco_venda:.2f}")