import os, io, json
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, send_file, jsonify
from flask_sqlalchemy import SQLAlchemy
import pandas as pd
import plotly.express as px
import plotly.io as pio

app = Flask(__name__)

# --- CONFIGURATION ---
DB_PATH = os.path.join(os.getcwd(), "grocery.db")
app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{DB_PATH}'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)


# --- MODELS ---
class Member(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False, unique=True)


class GroceryItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    price = db.Column(db.Float, nullable=False)
    category = db.Column(db.String(50), nullable=False)
    payer_name = db.Column(db.String(50), nullable=False)
    assignees = db.Column(db.String(500), nullable=False)
    date_added = db.Column(db.String(20), default=datetime.now().strftime("%Y-%m-%d"))


# --- 1. MATH UNIT (SETTLEMENT & SIMPLIFICATION) ---

def calculate_settlements(members, items):
    balances = {m.name: 0.0 for m in members}
    for item in items:
        if item.payer_name in balances:
            balances[item.payer_name] += item.price
        try:
            a_list = json.loads(item.assignees)
            if a_list:
                share = item.price / len(a_list)
                for person in a_list:
                    if person in balances:
                        balances[person] -= share
        except:
            continue
    return balances


def simplify_debts(balances):
    """Greedy Algorithm to find the most efficient payments."""
    debtors = [[n, a] for n, a in balances.items() if a < -0.01]
    creditors = [[n, a] for n, a in balances.items() if a > 0.01]

    # Sort by amount to optimize transactions
    debtors.sort(key=lambda x: x[1])
    creditors.sort(key=lambda x: x[1], reverse=True)

    transactions = []
    while debtors and creditors:
        d_name, d_amt = debtors[0]
        c_name, c_amt = creditors[0]

        pay_amt = min(abs(d_amt), c_amt)
        if pay_amt > 0.01:
            transactions.append({'from': d_name, 'to': c_name, 'amount': round(pay_amt, 2)})

        debtors[0][1] += pay_amt
        creditors[0][1] -= pay_amt

        if abs(debtors[0][1]) < 0.01: debtors.pop(0)
        if abs(creditors[0][1]) < 0.01: creditors.pop(0)
    return transactions


# --- 2. DATA UNIT ---

def db_update_item(item_id, data, assignees):
    item = db.session.get(GroceryItem, item_id)
    if item:
        item.name = data.get('name')
        item.price = float(data.get('price'))
        item.category = data.get('category')
        item.payer_name = data.get('payer_name')
        item.assignees = json.dumps(assignees)
        db.session.commit()


# --- ROUTES ---

@app.route('/')
def index():
    members = Member.query.all()
    items = GroceryItem.query.all()
    balances = calculate_settlements(members, items)
    simplified_debts = simplify_debts(balances)

    chart_html = ""
    if items:
        df = pd.DataFrame([{'Cat': i.category, 'Val': i.price, 'Payer': i.payer_name} for i in items])
        df_g = df.groupby(['Cat', 'Payer'])['Val'].sum().reset_index()
        fig = px.bar(df_g, x="Cat", y="Val", color="Payer", barmode="group", template="plotly_dark")
        fig.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', height=300,
                          margin=dict(t=10, b=10, l=10, r=10), font=dict(size=10))
        chart_html = pio.to_html(fig, full_html=False, config={'displayModeBar': False})

    categories = ["Veg/Fruit", "Dairy", "Meat", "Snacks", "Grains", "Beverages", "Household", "Frozen"]
    return render_template('index.html', members=members, items=items,
                           balances=balances, debts=simplified_debts,
                           chart_html=chart_html, categories=categories)


@app.route('/add_item', methods=['POST'])
def add_item():
    new_item = GroceryItem(
        name=request.form.get('name'),
        price=float(request.form.get('price')),
        category=request.form.get('category'),
        payer_name=request.form.get('payer_name'),
        assignees=json.dumps(request.form.getlist('assignees'))
    )
    db.session.add(new_item)
    db.session.commit()
    return redirect(url_for('index'))


@app.route('/edit_item', methods=['POST'])
def edit_item():
    db_update_item(request.form.get('item_id'), request.form, request.form.getlist('assignees'))
    return redirect(url_for('index'))


@app.route('/get_item/<int:id>')
def get_item(id):
    item = db.session.get(GroceryItem, id)
    return jsonify({
        'name': item.name, 'price': item.price, 'category': item.category,
        'payer': item.payer_name, 'assignees': json.loads(item.assignees)
    })


@app.route('/settle_up', methods=['POST'])
def settle_up():
    db.session.query(GroceryItem).delete()
    db.session.commit()
    return redirect(url_for('index'))


@app.route('/export')
def export_csv():
    members = Member.query.all()
    items = GroceryItem.query.all()
    balances = calculate_settlements(members, items)
    output = io.StringIO()
    output.write("--- ITEM HISTORY ---\n")
    pd.DataFrame(
        [{'Date': i.date_added, 'Item': i.name, 'Price': i.price, 'Payer': i.payer_name} for i in items]).to_csv(output,
                                                                                                                 index=False)
    output.write("\n--- FINAL BALANCES ---\n")
    for n, b in balances.items(): output.write(f"{n},{b}\n")
    output.seek(0)
    return send_file(io.BytesIO(output.getvalue().encode()), mimetype='text/csv', as_attachment=True,
                     download_name="Grocify_Report.csv")


@app.route('/add_member', methods=['POST'])
def add_member():
    name = request.form.get('member_name')
    if name:
        db.session.add(Member(name=name))
        db.session.commit()
    return redirect(url_for('index'))


@app.route('/delete_item/<int:id>')
def delete_item(id):
    item = db.session.get(GroceryItem, id)
    if item:
        db.session.delete(item)
        db.session.commit()
    return redirect(url_for('index'))


if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True, port=5001)