from flask import Flask, render_template, request, redirect, url_for, send_file, jsonify
from flask_sqlalchemy import SQLAlchemy
import pandas as pd
import plotly.express as px
import plotly.io as pio
import os, io, json
from datetime import datetime

app = Flask(__name__)

# --- CONFIGURATION ---
DB_PATH = "/Users/harshil/Desktop/grocery-app/grocery.db"
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
    payer_name = db.Column(db.String(50), nullable=False)  # Who paid the cash
    assignees = db.Column(db.String(255), nullable=False)  # JSON string of names who share it
    date_added = db.Column(db.String(20), default=datetime.now().strftime("%Y-%m-%d"))


# --- MODULAR FUNCTIONS ---

def init_db(reset=False):
    """Initializes the database. If reset=True, wipes all data."""
    with app.app_context():
        if reset:
            db.drop_all()
        db.create_all()
        print(f"🚀 Database Synchronized at {DB_PATH}")


def calculate_balances(items, members):
    """The Math Engine: Calculates how much everyone owes relative to each other."""
    # Initialize: everyone starts at 0
    balances = {m.name: 0.0 for m in members}

    for item in items:
        # 1. Payer gets credit for the full amount they spent
        if item.payer_name in balances:
            balances[item.payer_name] += item.price

        # 2. Assignees get debited their share
        try:
            assignee_list = json.loads(item.assignees)
        except:
            assignee_list = [m.name for m in members]  # Default to all if error

        if assignee_list:
            share = item.price / len(assignee_list)
            for name in assignee_list:
                if name in balances:
                    balances[name] -= share
    return balances


def get_chart_data(items):
    """Generates an interactive Plotly Pie Chart of expenses by category."""
    if not items: return ""
    df = pd.DataFrame([{'Cat': i.category, 'Price': i.price} for i in items])
    df = df.groupby('Cat')['Price'].sum().reset_index()
    fig = px.pie(df, values='Price', names='Cat', hole=0.4,
                 color_discrete_sequence=px.colors.qualitative.Vivid)
    fig.update_layout(showlegend=False, margin=dict(t=0, b=0, l=0, r=0), height=250,
                      paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')
    return pio.to_html(fig, full_html=False, config={'displayModeBar': False})


# --- ROUTES ---

@app.route('/', methods=['GET'])
def index():
    members = Member.query.all()
    items = GroceryItem.query.all()
    balances = calculate_balances(items, members)
    chart_html = get_chart_data(items)
    return render_template('index.html', items=items, members=members,
                           balances=balances, chart_html=chart_html)


@app.route('/add_member', methods=['POST'])
def add_member():
    name = request.form.get('member_name')
    if name and not Member.query.filter_by(name=name).first():
        db.session.add(Member(name=name))
        db.session.commit()
    return redirect(url_for('index'))


@app.route('/add_item', methods=['POST'])
def add_item():
    assignees = request.form.getlist('assignees')
    new_item = GroceryItem(
        name=request.form.get('name'),
        price=float(request.form.get('price')),
        category=request.form.get('category'),
        payer_name=request.form.get('payer_name'),
        assignees=json.dumps(assignees)
    )
    db.session.add(new_item)
    db.session.commit()
    return redirect(url_for('index'))


@app.route('/edit_item', methods=['POST'])
def edit_item():
    item_id = request.form.get('item_id')
    item = GroceryItem.query.get(item_id)
    if item:
        item.name = request.form.get('name')
        item.price = float(request.form.get('price'))
        item.category = request.form.get('category')
        item.payer_name = request.form.get('payer_name')
        item.assignees = json.dumps(request.form.getlist('assignees'))
        db.session.commit()
    return redirect(url_for('index'))


@app.route('/delete_item/<int:id>')
def delete_item(id):
    item = GroceryItem.query.get(id)
    if item:
        db.session.delete(item)
        db.session.commit()
    return redirect(url_for('index'))


if __name__ == '__main__':
    init_db(reset=False)  # Change to True once if you get errors
    app.run(debug=True, port=5000)