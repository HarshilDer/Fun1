from flask import Flask, render_template, request, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
import pandas as pd
import plotly.express as px
import plotly.io as pio
import os

app = Flask(__name__)

# --- DATABASE CONFIGURATION ---
# We explicitly set the absolute path you requested.
# The 4 slashes (sqlite:////) are required for absolute paths on macOS/Linux.
specific_path = "/Users/harshil/Desktop/grocery-app/grocery.db"
app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{specific_path}'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

print(f"✅ Database configured to: {specific_path}")

db = SQLAlchemy(app)


# --- DATABASE MODEL ---
class GroceryItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    price = db.Column(db.Float, nullable=False)
    category = db.Column(db.String(50), nullable=False)


# --- CREATE TABLES ---
with app.app_context():
    # Check if the folder actually exists before trying to create the DB
    folder_path = os.path.dirname(specific_path)
    if not os.path.exists(folder_path):
        print(f"⚠️ Warning: The folder '{folder_path}' does not exist.")
        print("Please create the folder 'grocery-app' on your Desktop first.")
    else:
        try:
            db.create_all()
            print("✅ Database connected and tables ready.")
        except Exception as e:
            print(f"❌ Error creating database: {e}")
            print(
                "Tip: Check 'System Settings > Privacy & Security > Files and Folders' to ensure Terminal/PyCharm has access.")


# --- ROUTES ---

@app.route('/', methods=['GET', 'POST'])
def index():
    # 1. Handle Adding Items
    if request.method == 'POST':
        name = request.form.get('name')
        price = request.form.get('price')
        category = request.form.get('category')

        if name and price:
            try:
                new_item = GroceryItem(name=name, price=float(price), category=category)
                db.session.add(new_item)
                db.session.commit()
                print(f"Added item: {name}")
            except Exception as e:
                print(f"Error adding item: {e}")
        return redirect(url_for('index'))

    # 2. Fetch Items
    try:
        items = GroceryItem.query.all()
    except Exception as e:
        print(f"Error fetching data: {e}")
        items = []

    # 3. Handle Empty State
    if not items:
        return render_template('index.html', items=[], chart_html="", total=0)

    # 4. Process Data with Pandas
    data = [{'id': i.id, 'name': i.name, 'price': i.price, 'category': i.category} for i in items]
    df = pd.DataFrame(data)

    # Calculate Total
    total_cost = df['price'].sum()

    # 5. Generate Plotly Chart
    if not df.empty:
        df_grouped = df.groupby('category')['price'].sum().reset_index()

        fig = px.pie(df_grouped, values='price', names='category',
                     title='Expenses by Category',
                     color_discrete_sequence=px.colors.qualitative.Pastel)

        fig.update_traces(textposition='inside', textinfo='percent+label')
        fig.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')

        chart_html = pio.to_html(fig, full_html=False)
    else:
        chart_html = ""

    return render_template('index.html', items=items, chart_html=chart_html, total=total_cost)


@app.route('/delete/<int:id>')
def delete_item(id):
    try:
        item = GroceryItem.query.get(id)
        if item:
            db.session.delete(item)
            db.session.commit()
    except Exception as e:
        print(f"Error deleting item: {e}")
    return redirect(url_for('index'))


if __name__ == '__main__':
    app.run(debug=True, port=5000)