from flask import Flask, request
import json
from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.sql import text



# Flask constructor takes the name of 
# current module (__name__) as argument.
app = Flask(__name__)
# this variable, db, will be used for all SQLAlchemy commands
db = SQLAlchemy()
db_name = 'main.db'
class Car(db.Model):
    __tablename__ = 'cars'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String)
    desc = db.Column(db.String)
    json = db.Column(db.String)
    sold = db.Column(db.Integer)
    price = db.Column(db.Integer)
    uuid = db.Column(db.String)
    lot_time = db.Column(db.String)    # when the lot first appeared
    price_time = db.Column(db.String)  # when the price was last updated

    def __init__(self, name, desc, json, sold, price, uuid):
        self.name = name
        self.desc = desc
        self.json = json
        self.sold = sold
        self.price = price
        self.uuid = uuid

app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + db_name

app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = True

# initialize the app with Flask-SQLAlchemy
db.init_app(app)
with app.app_context():
    db.create_all()
    # Add new columns to existing databases that predate this change
    for col in ('lot_time', 'price_time'):
        try:
            db.session.execute(text(f'ALTER TABLE cars ADD COLUMN {col} TEXT'))
            db.session.commit()
        except Exception:
            db.session.rollback()

@app.route('/dbtest')
def testdb():
    try:
        db.session.query(text('1')).from_statement(text('SELECT 1')).all()
        return '<h1>It works.</h1>'
    except Exception as e:
        # e holds description of the error
        error_text = "<p>The error:<br>" + str(e) + "</p>"
        hed = '<h1>Something is broken.</h1>'
        return hed + error_text
# The route() function of the Flask class is a decorator, 
# which tells the application which URL should call 
# the associated function.
@app.route('/',methods=[ 'GET','POST'])
# ‘/’ URL is bound with hello_world() function.
def hello_world():
    if request.method == 'POST':
        data = request.get_json(force=True)
        logdata(data)
        return 'Hello World'
    else:
        photos = request.args.get('photos') is not None
        q = (request.args.get('q') or '').strip().lower()

        stmt = db.select(Car).order_by(Car.lot_time.desc(), Car.name)
        if q:
            stmt = stmt.where(
                db.or_(
                    Car.name.ilike(f'%{q}%'),
                    Car.lot_time.ilike(f'%{q}%'),
                    Car.price_time.ilike(f'%{q}%'),
                )
            )
        socks = db.session.execute(stmt).scalars()

        photo_toggle = '<a href="/?photos' + (f'&q={q}' if q else '') + '">Photos</a>' if not photos else '<a href="/' + (f'?q={q}' if q else '') + '">No Photos</a>'
        search_box = f'''<form style="text-align:center;margin:8px">
            <input name="q" value="{q}" placeholder="Search name, date or time..." style="width:300px;padding:4px">
            {"<input type='hidden' name='photos' value=''>" if photos else ""}
            <button type="submit">Search</button>
            {"<a href='/?photos'>&nbsp;Clear</a>" if q else ""}
        </form>'''
        sock_text = f'<style>table {{margin-left: auto;margin-right: auto;}}table, th, td {{margin:2px;border: 1px solid black;border-collapse: collapse;}}</style>{photo_toggle}{search_box}<table><tr>{"<th>photo</th>" if photos else ""}<th>Name</th><th>Last Price</th><th>Price Updated</th><th>Lot Time</th><th>Reserve Met</th><th>Reference</th></tr>'
        for sock in socks:
            ph = json.loads(sock.json)[0]['Url']
            photo_tag = f'<td><img src="{ph}" height="100px"></img></td>'
            ref_link = f'<a href="https://www.turners.co.nz/Cars/Used-Cars-for-Sale/?searchfor={sock.uuid}" target="_blank">{sock.uuid}</a>'#https://www.turners.co.nz/Cars/Used-Cars-for-Sale/?searchfor={sock.uuid}
            sock_text += f'<tr>{photo_tag if photos else ""}<td>{sock.name}</td><td>${str(sock.price)}</td><td>{sock.price_time or ""}</td><td>{sock.lot_time or ""}</td><td>{sock.sold==1}</td><td>{ref_link}</td></tr>'
        sock_text += '</table>'
        return sock_text


def _now():
    return datetime.now().strftime('%Y-%m-%d %H:%M:%S')

def ws(data,gid):
    lid = str(gid)
    now = _now()
    if data["type"] == 8:
        bid = 0
        for x in data["obj"]:
            newbid = int(x["cbid"].split('.')[0])
            if newbid > bid:
                bid = newbid
        db.session.execute(text("UPDATE cars SET price = :bid, price_time = :now WHERE uuid = :lid"), {'bid':bid,'now':now,'lid':lid})
    elif data["type"] == 9:
        db.session.execute(text("UPDATE cars SET sold = 1, price_time = :now WHERE uuid = :lid"), {'now':now,'lid':lid})
    elif data["type"] == 7:
        db.session.execute(text("UPDATE cars SET price = :ask, price_time = :now WHERE uuid = :lid"), {'ask':int(data['obj']['abid'].split('.')[0]),'now':now,'lid':lid})
    db.session.commit()

def lot(data,gid):
    uid = gid
    data = data['data']['Result']
    imgs = data['imagesGoodModel']['ApiGoodImages']
    name = data['goodName']
    d = {'name':str(name), 'imgs':json.dumps(imgs),'price':0,'sold':0,'uuid':str(uid),'now':_now()}
    db.session.execute(text('INSERT INTO cars (name, json, sold, price, uuid, lot_time) VALUES (:name, :imgs, :sold, :price, :uuid, :now)'),d)
    db.session.commit()



def logdata(data):
    if data["logtype"] == "ws":
        ws(data["data"],data['id'])
    elif data["logtype"] == "lot":
        lot(data["data"],data['id'])
    

@app.route('/heartbeat')
def heartbeat():
    return 'ok'

# main driver function
if __name__ == '__main__':
    app.run()