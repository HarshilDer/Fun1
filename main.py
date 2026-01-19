from flask import Flask, render_template, request, redirect, url_for, send_file
from flask_sqlalchemy import SQLAlchemy
import pandas as pd
import plotly.express as px
import plotly.io as pio
import os
from datetime import datetime
import io

app = Flask(__name__)

# --- ⚙️ SETTINGS ---
# SET THIS TO TRUE to fix your error (Wipes DB on start).
# SET TO FALSE later to keep your data.
RESET_DB_ON_START = True

# --- CONFIGURATION ---
# Hardcoded absolute path as requested
specific_path = "/Users/harshil/Desktop/grocery-app/grocery.db"
app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{specific_path}'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)


# --- DATABASE MODELS ---
class Member(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False, unique=True)


class GroceryItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    price = db.Column(db.Float, nullable=False)
    category = db.Column(db.String(50), nullable=False)
    assigned_to = db.Column(db.String(50), nullable=False)
    date_added = db.Column(db.String(20), default=datetime.now().strftime("%Y-%m-%d"))


# --- INITIALIZATION ---
with app.app_context():
    # 1. Check if we need to wipe the DB (Fixes schema errors)
    if RESET_DB_ON_START:
        try:
            db.drop_all()  # This deletes tables internally (bypasses file locks)
            print("⚠️ DATABASE WIPED: Started fresh as requested.")
        except Exception as e:
            print(f"Note: Could not drop tables (might be first run): {e}")

    # 2. Create the tables
    try:
        db.create_all()
        print(f"✅ Grocify Database Ready at: {specific_path}")
    except Exception as e:
        print(f"❌ Critical Error: {e}")


# --- ROUTES ---

@app.route('/', methods=['GET', 'POST'])
def index():
    # --- HANDLE FORMS ---
    if request.method == 'POST':
        # A. Add Member
        if 'add_member' in request.form:
            member_name = request.form.get('member_name')
            if member_name:
                exists = Member.query.filter_by(name=member_name).first()
                if not exists:
                    db.session.add(Member(name=member_name))
                    db.session.commit()

        # B. Add Item
        elif 'add_item' in request.form:
            name = request.form.get('name')
            price = request.form.get('price')
            category = request.form.get('category')
            assigned_to = request.form.get('assigned_to')

            if name and price:
                new_item = GroceryItem(
                    name=name,
                    price=float(price),
                    category=category,
                    assigned_to=assigned_to,
                    date_added=datetime.now().strftime("%Y-%m-%d")
                )
                db.session.add(new_item)
                db.session.commit()

        return redirect(url_for('index'))

    # --- FETCH DATA ---
    members = Member.query.all()
    items = GroceryItem.query.all()

    # --- CALCULATE SPLITS ---
    member_names = [m.name for m in members]
    member_totals = {name: 0.0 for name in member_names}
    total_cost = 0.0

    for item in items:
        total_cost += item.price

        if item.assigned_to == 'Shared':
            # Split logic: Divide price by ALL members
            if len(member_names) > 0:
                split_amount = item.price / len(member_names)
                for name in member_names:
                    member_totals[name] += split_amount
        elif item.assigned_to in member_totals:
            # Direct assignment
            member_totals[item.assigned_to] += item.price

    # --- GENERATE CHART ---
    chart_html = ""
    if items:
        data = [{'Category': i.category, 'Price': i.price} for i in items]
        df = pd.DataFrame(data)
        df_grouped = df.groupby('Category')['Price'].sum().reset_index()

        fig = px.pie(df_grouped, values='Price', names='Category',
                     color_discrete_sequence=px.colors.qualitative.Pastel)
        fig.update_layout(
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)',
            margin=dict(t=20, b=20, l=20, r=20),
            height=300,
            showlegend=False
        )
        fig.update_traces(textposition='inside', textinfo='percent+label')
        chart_html = pio.to_html(fig, full_html=False, config={'displayModeBar': False})

    return render_template('index.html',
                           items=items,
                           members=members,
                           total=total_cost,
                           member_totals=member_totals,
                           chart_html=chart_html)


@app.route('/delete_item/<int:id>')
def delete_item(id):
    item = GroceryItem.query.get(id)
    if item:
        db.session.delete(item)
        db.session.commit()
    return redirect(url_for('index'))


@app.route('/delete_member/<int:id>')
def delete_member(id):
    member = Member.query.get(id)
    if member:
        db.session.delete(member)
        db.session.commit()
    return redirect(url_for('index'))


@app.route('/export')
def export_csv():
    items = GroceryItem.query.all()
    # Create clean data dictionary
    data = [{
        'Date Added': i.date_added,
        'Item Name': i.name,
        'Price': i.price,
        'Category': i.category,
        'Assigned To': i.assigned_to
    } for i in items]

    df = pd.DataFrame(data)

    buffer = io.BytesIO()
    df.to_csv(buffer, index=False)
    buffer.seek(0)

    return send_file(buffer,
                     as_attachment=True,
                     download_name=f"grocify_list_{datetime.now().strftime('%Y-%m-%d')}.csv",
                     mimetype='text/csv')


if __name__ == '__main__':
    app.run(debug=True, port=5000)