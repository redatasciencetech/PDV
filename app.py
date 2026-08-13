from flask import Flask, render_template, jsonify, request
import sqlite3
import os

app = Flask(__name__)
DATABASE = 'conveniencia.db'

def get_db_connection():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA foreign_keys = ON;')
    return conn

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.executescript('''
        CREATE TABLE IF NOT EXISTS categorias (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT UNIQUE NOT NULL
        );

        CREATE TABLE IF NOT EXISTS produtos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            codigo_barras TEXT UNIQUE NOT NULL,
            nome TEXT NOT NULL,
            categoria_id INTEGER,
            preco_custo REAL DEFAULT 0.0,
            preco_venda REAL NOT NULL,
            estoque_atual INTEGER NOT NULL DEFAULT 0,
            estoque_minimo INTEGER DEFAULT 5,
            FOREIGN KEY (categoria_id) REFERENCES categorias(id) ON DELETE SET NULL
        );

        CREATE TABLE IF NOT EXISTS vendas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            data_hora DATETIME DEFAULT CURRENT_TIMESTAMP,
            subtotal REAL NOT NULL,
            desconto REAL DEFAULT 0.0,
            total REAL NOT NULL,
            valor_pago REAL DEFAULT 0.0,
            troco REAL DEFAULT 0.0,
            forma_pagamento TEXT NOT NULL,
            status TEXT DEFAULT 'CONCLUIDA'
        );

        CREATE TABLE IF NOT EXISTS itens_venda (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            venda_id INTEGER NOT NULL,
            produto_id INTEGER NOT NULL,
            quantidade INTEGER NOT NULL,
            preco_unitario REAL NOT NULL,
            FOREIGN KEY (venda_id) REFERENCES vendas(id) ON DELETE CASCADE,
            FOREIGN KEY (produto_id) REFERENCES produtos(id)
        );
    ''')

    # Inserir dados de teste caso as tabelas estejam vazias
    cursor.execute('SELECT COUNT(*) FROM categorias')
    if cursor.fetchone()[0] == 0:
        categorias_iniciais = ['Cervejas', 'Destilados', 'Sem Álcool', 'Gelo & Carvão', 'Petiscos']
        for cat in categorias_iniciais:
            cursor.execute('INSERT INTO categorias (nome) VALUES (?)', (cat,))
        
        cursor.execute('''
            INSERT INTO produtos (codigo_barras, nome, categoria_id, preco_custo, preco_venda, estoque_atual, estoque_minimo)
            VALUES 
            ('78912345', 'Heineken Long Neck 330ml', 1, 4.50, 8.50, 48, 12),
            ('78912346', 'Vodka Absolut 1L', 2, 65.00, 98.90, 15, 3),
            ('78912347', 'Saco de Gelo 5kg', 4, 4.00, 12.00, 30, 8),
            ('78912348', 'Coca-Cola 2L Original', 3, 6.20, 10.00, 24, 6),
            ('78912349', 'Energético Red Bull 250ml', 3, 7.50, 12.90, 36, 10),
            ('78912350', 'Carvão Vegetal 3kg', 4, 10.00, 18.00, 10, 4)
        ''')
    
    conn.commit()
    conn.close()

@app.route('/')
def index():
    return render_template('index.html')

# --- API CATEGORIAS ---
@app.route('/api/categorias', methods=['GET', 'POST'])
def manage_categorias():
    conn = get_db_connection()
    if request.method == 'POST':
        data = request.get_json()
        nome = data.get('nome', '').strip()
        if not nome:
            conn.close()
            return jsonify({'error': 'Nome da categoria é obrigatório'}), 400
        try:
            conn.execute('INSERT INTO categorias (nome) VALUES (?)', (nome,))
            conn.commit()
            conn.close()
            return jsonify({'message': 'Categoria cadastrada com sucesso!'}), 201
        except sqlite3.IntegrityError:
            conn.close()
            return jsonify({'error': 'Categoria já existe'}), 400
    
    cats = conn.execute('SELECT * FROM categorias ORDER BY nome').fetchall()
    conn.close()
    return jsonify([dict(c) for c in cats])

# --- API PRODUTOS ---
@app.route('/api/produtos', methods=['GET', 'POST'])
def manage_produtos():
    conn = get_db_connection()
    if request.method == 'POST':
        data = request.get_json()
        codigo_barras = data.get('codigo_barras', '').strip()
        nome = data.get('nome', '').strip()
        categoria_id = data.get('categoria_id')
        preco_custo = float(data.get('preco_custo', 0.0))
        preco_venda = float(data.get('preco_venda', 0.0))
        estoque_atual = int(data.get('estoque_atual', 0))
        estoque_minimo = int(data.get('estoque_minimo', 5))

        if not codigo_barras or not nome or preco_venda <= 0:
            conn.close()
            return jsonify({'error': 'Preencha código de barras, nome e preço válido'}), 400

        try:
            conn.execute('''
                INSERT INTO produtos (codigo_barras, nome, categoria_id, preco_custo, preco_venda, estoque_atual, estoque_minimo)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (codigo_barras, nome, categoria_id, preco_custo, preco_venda, estoque_atual, estoque_minimo))
            conn.commit()
            conn.close()
            return jsonify({'message': 'Produto cadastrado com sucesso!'}), 201
        except sqlite3.IntegrityError:
            conn.close()
            return jsonify({'error': 'Código de barras já cadastrado'}), 400

    query = '''
        SELECT p.*, c.nome as categoria_nome 
        FROM produtos p 
        LEFT JOIN categorias c ON p.categoria_id = c.id 
        ORDER BY p.nome
    '''
    produtos = conn.execute(query).fetchall()
    conn.close()
    return jsonify([dict(p) for p in produtos])

@app.route('/api/produtos/<int:prod_id>', methods=['PUT', 'DELETE'])
def update_delete_produto(prod_id):
    conn = get_db_connection()
    if request.method == 'DELETE':
        try:
            conn.execute('DELETE FROM produtos WHERE id = ?', (prod_id,))
            conn.commit()
            conn.close()
            return jsonify({'message': 'Produto removido com sucesso'})
        except Exception:
            conn.close()
            return jsonify({'error': 'Não é possível excluir produto vinculado a vendas'}), 400

    data = request.get_json()
    conn.execute('''
        UPDATE produtos 
        SET codigo_barras = ?, nome = ?, categoria_id = ?, preco_custo = ?, preco_venda = ?, estoque_atual = ?, estoque_minimo = ?
        WHERE id = ?
    ''', (
        data['codigo_barras'], data['nome'], data.get('categoria_id'),
        float(data.get('preco_custo', 0)), float(data['preco_venda']),
        int(data['estoque_atual']), int(data.get('estoque_minimo', 5)), prod_id
    ))
    conn.commit()
    conn.close()
    return jsonify({'message': 'Produto atualizado com sucesso!'})

# --- API VENDAS ---
@app.route('/api/vendas', methods=['GET', 'POST'])
def manage_vendas():
    conn = get_db_connection()
    if request.method == 'POST':
        data = request.get_json()
        items = data.get('items', [])
        subtotal = float(data.get('subtotal', 0.0))
        desconto = float(data.get('desconto', 0.0))
        total = float(data.get('total', 0.0))
        valor_pago = float(data.get('valor_pago', total))
        troco = float(data.get('troco', 0.0))
        forma_pagamento = data.get('forma_pagamento', 'PIX')

        if not items:
            conn.close()
            return jsonify({'error': 'Carrinho vazio'}), 400

        try:
            # Validar disponibilidade do estoque de todos os itens antes de gravar
            for item in items:
                prod = conn.execute('SELECT estoque_atual, nome FROM produtos WHERE id = ?', (item['id'],)).fetchone()
                if not prod or prod['estoque_atual'] < item['qty']:
                    conn.close()
                    nome = prod['nome'] if prod else 'Produto'
                    return jsonify({'error': f'Estoque insuficiente para o produto: {nome}'}), 400

            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO vendas (subtotal, desconto, total, valor_pago, troco, forma_pagamento)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (subtotal, desconto, total, valor_pago, troco, forma_pagamento))
            venda_id = cursor.lastrowid

            for item in items:
                cursor.execute('''
                    INSERT INTO itens_venda (venda_id, produto_id, quantidade, preco_unitario)
                    VALUES (?, ?, ?, ?)
                ''', (venda_id, item['id'], item['qty'], item['price']))

                # Baixa automática de estoque
                cursor.execute('''
                    UPDATE produtos SET estoque_atual = estoque_atual - ? WHERE id = ?
                ''', (item['qty'], item['id']))

            conn.commit()
            conn.close()
            return jsonify({'message': 'Venda finalizada com sucesso!', 'venda_id': venda_id}), 201

        except Exception as e:
            conn.rollback()
            conn.close()
            return jsonify({'error': f'Erro de transação ao salvar venda: {str(e)}'}), 500

    # Histórico de Vendas
    vendas = conn.execute('SELECT * FROM vendas ORDER BY id DESC').fetchall()
    result = []
    for v in vendas:
        v_dict = dict(v)
        itens = conn.execute('''
            SELECT iv.*, p.nome as produto_nome, p.codigo_barras 
            FROM itens_venda iv 
            JOIN produtos p ON iv.produto_id = p.id 
            WHERE iv.venda_id = ?
        ''', (v['id'],)).fetchall()
        v_dict['itens'] = [dict(i) for i in itens]
        result.append(v_dict)
    
    conn.close()
    return jsonify(result)

# --- CANCELAR VENDA E REPOR ESTOQUE ---
@app.route('/api/vendas/<int:venda_id>/cancelar', methods=['POST'])
def cancelar_venda(venda_id):
    conn = get_db_connection()
    venda = conn.execute('SELECT * FROM vendas WHERE id = ?', (venda_id,)).fetchone()
    
    if not venda:
        conn.close()
        return jsonify({'error': 'Venda não encontrada'}), 404
    
    if venda['status'] == 'CANCELADA':
        conn.close()
        return jsonify({'error': 'Esta venda já está cancelada'}), 400

    try:
        cursor = conn.cursor()
        itens = cursor.execute('SELECT * FROM itens_venda WHERE venda_id = ?', (venda_id,)).fetchall()
        
        # Devolver quantidades de volta ao estoque
        for item in itens:
            cursor.execute('UPDATE produtos SET estoque_atual = estoque_atual + ? WHERE id = ?', 
                           (item['quantidade'], item['produto_id']))
        
        cursor.execute("UPDATE vendas SET status = 'CANCELADA' WHERE id = ?", (venda_id,))
        conn.commit()
        conn.close()
        return jsonify({'message': 'Venda cancelada e estoque estornado com sucesso!'})
    except Exception as e:
        conn.rollback()
        conn.close()
        return jsonify({'error': str(e)}), 500

# --- DASHBOARD & INDICADORES ---
@app.route('/api/dashboard', methods=['GET'])
def get_dashboard():
    conn = get_db_connection()
    
    hoje_total = conn.execute('''
        SELECT COALESCE(SUM(total), 0) as total_hoje, COUNT(*) as qtd_vendas 
        FROM vendas 
        WHERE DATE(data_hora) = DATE('now', 'localtime') AND status = 'CONCLUIDA'
    ''').fetchone()

    pagamentos = conn.execute('''
        SELECT forma_pagamento, SUM(total) as total 
        FROM vendas 
        WHERE DATE(data_hora) = DATE('now', 'localtime') AND status = 'CONCLUIDA'
        GROUP BY forma_pagamento
    ''').fetchall()

    estoque_baixo = conn.execute('''
        SELECT COUNT(*) as baixos FROM produtos WHERE estoque_atual <= estoque_minimo
    ''').fetchone()

    top_produtos = conn.execute('''
        SELECT p.nome, SUM(iv.quantidade) as total_vendido, SUM(iv.quantidade * iv.preco_unitario) as faturamento
        FROM itens_venda iv
        JOIN produtos p ON iv.produto_id = p.id
        JOIN vendas v ON iv.venda_id = v.id
        WHERE v.status = 'CONCLUIDA'
        GROUP BY p.id
        ORDER BY total_vendido DESC
        LIMIT 5
    ''').fetchall()

    conn.close()
    return jsonify({
        'total_hoje': hoje_total['total_hoje'],
        'qtd_vendas_hoje': hoje_total['qtd_vendas'],
        'ticket_medio': (hoje_total['total_hoje'] / hoje_total['qtd_vendas']) if hoje_total['qtd_vendas'] > 0 else 0,
        'estoque_baixo_count': estoque_baixo['baixos'],
        'pagamentos': [dict(p) for p in pagamentos],
        'top_produtos': [dict(tp) for tp in top_produtos]
    })

if __name__ == '__main__':
    init_db()
    print("Servidor rodando em http://127.0.0.1:5000")
    app.run(debug=True, port=5000)