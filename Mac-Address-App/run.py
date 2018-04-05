from flask import Flask, render_template, abort, redirect, url_for, flash, request
from flask_restful import Resource, Api, reqparse
from flask_marshmallow import Marshmallow
from flask_sqlalchemy import SQLAlchemy
import requests
import hashlib
import json


app = Flask(__name__)
api = Api(app)
app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql://root:pass@192.168.0.2/addresses'
app.config['SQLALCHEMY_BINDS'] = {"users_database": "mysql://root:pass@192.168.0.2/users"}
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = "random string"
db = SQLAlchemy(app)
ma = Marshmallow(app)

kubeApiIpAddress = "localhost"

class Addresses(db.Model):
    __tablename__ = "mac_addresses"

    mac_address = db.Column(db.String(500), primary_key=True)
    status = db.Column(db.Boolean, default=0)


class MacAddresses(db.Model):
    __bind_key__ = "users_database"
    __tablename__ = "base_stations"

    id = db.Column("id", db.Integer, primary_key=True)
    mac_address = db.Column(db.String(500), nullable=False)
    name = db.Column(db.String(500), nullable=False)
    user_id = db.Column(db.Integer, nullable=False)


class User(db.Model):
    __tablename__  = 'users'
    __bind_key__ = "users_database"

    id = db.Column('id', db.Integer, primary_key=True)
    name = db.Column(db.String(500), index=True, nullable=False)
    surname = db.Column(db.String(500), index=True, nullable=False)
    contact = db.Column(db.String(500), nullable=False)
    acc_num = db.Column(db.String(500), nullable=False)
    address = db.Column(db.String(500), nullable=False)
    email = db.Column(db.String(500), unique=True, nullable=False)
    password = db.Column(db.String(500), nullable=False)
    block_addr = db.Column(db.String(500), nullable=False)
    active = db.Column(db.Boolean, default=0)
    type = db.Column(db.String(5), nullable=False)


class AddressSchema(ma.ModelSchema):
    class Meta:
        model = Addresses


class UsersSchema(ma.ModelSchema):
    class Meta:
        model = User


class MacAddressesSchema(ma.ModelSchema):
    class Meta:
        model = MacAddresses


class UserApi(Resource):
    def get(self):
        parser = reqparse.RequestParser()
        parser.add_argument("email", type=str, help="Please enter a valid email address", required=True)
        args = parser.parse_args()
        data = User.query.filter_by(email=args['email']).first()
        schema = UsersSchema()
        re = schema.dump(data).data
        if re != {}:
            return {"message": "User Exists", "code": 100}
        else:
            return {"message": "You are not registered. Register First", "code": 402}


class Address(Resource):
    def post(self):
        parser = reqparse.RequestParser()
        parser.add_argument("address", type=str, help="Please enter a valid Mac Address", required=True)
        parser.add_argument("email", type=str, help="Please enter a valid email address", required=True)
        parser.add_argument("password", type=str, help="Please enter a valid password", required=True)
        parser.add_argument("name", type=str, help="Please enter base station name", required=True)
        args = parser.parse_args()
        data = User.query.filter_by(email=args['email']).first()
        schema = UsersSchema()
        re = schema.dump(data).data
        if re != {}:
            if re['password'] == hashlib.sha256(args['password']).hexdigest():
                data = Addresses.query.filter_by(mac_address=args['address']).first()
                schema = AddressSchema()
                results = schema.dump(data).data
                if results != {}:
                    if results["status"] == 0:
                        data.status = 1
                        db.session.add(MacAddresses(user_id=re['id'], mac_address=results['mac_address'], name=args['name']))
                        try:
                            db.session.commit()
                            return {"message": "Mac Address {} Successfully Assigned to "
                                               "{}".format(results['mac_address'], re["name"] + " " + re["surname"]), "code": 200}
                        except Exception as e:
                            print e
                            db.session.rollback()
                            return {"message": "Failed to assign Mac_address. Try again", "code": 500}
                    else:
                        return {"message": "Mac Address Already Assigned to Another User", "code": 401}
                else:
                    return {"message": "Mac Address Not Found", "code": 404}
            else:
                return {"message": "Please Verify Your Credentials", "code": 401}
        else:
            return {"message": "Please Verify Your Credentials", "code": 401}


@app.route('/')
def home():
    return render_template("home.html", title="Home")


def get_nodes():
    try:
        x = requests.get('http://{}:5000'.format(kubeApiIpAddress), data={'method': 'get_nodes'})
        return x
    except Exception as e:
        print e
        return "Internal Server Error. Try again"


def get_pods():
    try:
        x = requests.get('http://{}:5000'.format(kubeApiIpAddress), data={'method': 'get_pods', 'namespace': 'default'})
        return x
    except Exception as e:
        print e
        return "Internal Server Error. Try again"


def get_services():
    try:
        x = requests.get('http://{}:5000'.format(kubeApiIpAddress), data={'method': 'get_services', 'namespace': 'default'})
        return x
    except Exception as e:
        print e
        return "Internal Server Error. Try again"

def get_deployments():
    try:
        x = requests.get('http://{}:5000'.format(kubeApiIpAddress), data={'method': 'get_deployments', 'namespace': 'default'})
        return x
    except Exception as e:
        print e
        return "Internal Server Error. Try again"

def deploy_app(name, image, port, replicas):
    try:
        deploy = requests.post('http://{}:5000'.format(kubeApiIpAddress),
                               data={'method': 'deploy', 'namespace': 'default', 'name': name, "image": image, "replicas": replicas, "port": port})
        deploy_json = json.loads(deploy.content)
        return deploy_json
    except Exception as e:
        print e
        return "Internal Server Error. Try again"

def create_service(name, port):
    try:
        service = requests.post('http://{}:5000'.format(kubeApiIpAddress),
                               data={'method': 'service', 'namespace': 'default', 'name': name, "port": port})
        deploy_json = json.loads(service.content)
        return deploy_json
    except Exception as e:
        print e
        return "Internal Server Error. Try again"

@app.route('/dashboard/<string:method>', methods=["get","post"])
def dashboard(method):
    if method == "nodes":
        data = json.loads(get_nodes().content)
        return render_template("nodes.html", data=data, title="Dashboard")
    elif method == "pods":
        data =  json.loads(get_pods().content)
        return render_template("pods.html", data=data, title="Dashboard")
    elif method == "services":
        data = json.loads(get_services().content)
        return render_template("services.html", data=data, title="Dashboard")
    elif method == "deployments":
        data =  json.loads(get_deployments().content)
        return render_template("deployments.html", data=data, title="Dashboard")
    elif method == "deploy":
        if request.method == "POST":
            name = request.values.get("name")
            image = request.values.get("image")
            port = request.values.get("port")
            replicas = request.values.get("replicas")
            deploy_json = deploy_app(name, image, port, replicas)
            if deploy_json['status'] != "Failure":
                flash("App Successfully Deployed")
                return redirect(url_for("dashboard", method="deployments"))
            else:
                flash("Failed to deploy App. {}".format(deploy_json['reason']))
        return render_template("deploy.html", title="Dashboard")
    elif method == "create_service":
        if request.method == "POST":
            name = request.values.get("name")
            port = request.values.get("port")
            deploy_json = create_service(name, port)
            if deploy_json['status'] != "Failure":
                flash("Service Successfully Created")
                return redirect(url_for("dashboard", method="services"))
            else:
                flash("Failed to create service. {}".format(deploy_json['reason']))
        return render_template("create_service.html", title="Dashboard")
    else:
        abort(404)


api.add_resource(UserApi, '/user_exists')
api.add_resource(Address, '/register_address')


if __name__ == "__main__":
    db.create_all()
    app.run(port=5001)
