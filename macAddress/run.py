from flask import Flask, render_template, abort, redirect, url_for, flash, request, session
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
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
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "home"
login_manager.login_message = "Please Logging First"

kubeApiIpAddress = "localhost"


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


def get_address():
    try:
        mac_address_file = open("mac_address.txt")
    except:
        mac_address_file = open("mac_address.txt", "w+")
    mac_address = mac_address_file.read()
    mac_address_file.close()
    return mac_address


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


class User(db.Model, UserMixin):
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


#Check if the base station is registerd
def base_station_registered():
    address = MacAddresses.query.filter_by(mac_address=get_address()).first()
    schema = MacAddressesSchema()
    results = schema.dump(address).data
    if results:
        return True
    else:
        return False


class LogIn(Resource):
    def post(self):
        parser = reqparse.RequestParser()
        parser.add_argument("email", type=str, help="Please enter a valid email address", required=True)
        parser.add_argument("password", type=str, help="Please enter a valid Password", required=True)
        args = parser.parse_args()
        data = User.query.filter_by(email=args['email']).first()
        schema = UsersSchema()
        re = schema.dump(data).data
        if re:
            if (re['email'] == args['email']) and (re['password'] == hashlib.sha256(args['password']).hexdigest()):
                login_user(data)
                return {"message": "Login Successful", "code": 100}
            else:
                return {"message": "Invalid username or password", "code": 401}
        else:
            return {"message": "Invalid username or password", "code": 401}


class Services(Resource):
    def post(self):
        parser = reqparse.RequestParser()
        parser.add_argument("name", type=str, help="Please enter a valid service name", required=True)
        args = parser.parse_args()
        response = delete_service(args['name'])
        if response['status'] == "Failure":
            return {"message": "Failed to delete service. Try again", "code": 500}
        if response['status'] == "Success":
            return {"message": "Service removed successfully", "code": 200}


class Deployments(Resource):
    def post(self):
        parser = reqparse.RequestParser()
        parser.add_argument("name", type=str, help="Please enter a valid deployment name", required=True)
        args = parser.parse_args()
        response = delete_deployment(args['name'])
        if response['status'] == "Failure":
            return {"message": "Failed to delete deployment. Try again", "code": 500}
        if response['status'] == "Success":
            return {"message": "Deployment removed successfully", "code": 200}


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
                            mac_address_file = open("mac_address.txt", "w+")
                            mac_address_file.write(args['address'])
                            mac_address_file.close()
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
    logout_user()
    session.clear()
    return render_template("home.html", title="Home", global_mac_address=get_address())


def get_nodes():
    try:
        nodes = requests.get('http://{}:5000'.format(kubeApiIpAddress), data={'method': 'get_nodes'})
        json_nodes = json.loads(nodes.content)
        return json_nodes
    except Exception as e:
        print e
        if str(e) == "No JSON object could be decoded":
            return "Non_Json"
        else:
            return False


def current_user_is_owner():
    address = MacAddresses.query.filter_by(mac_address=get_address()).first()
    schema = MacAddressesSchema()
    results = schema.dump(address).data
    if results:
        if current_user.id == results['user_id']:
            return True
        else:
            return False
    else:
        return False


def get_pods():
    try:
        owner = 0
        if current_user_is_owner():
            owner = 1
        pods = requests.get('http://{}:5000'.format(kubeApiIpAddress), data={'method': 'get_pods', 'namespace': current_user.email,'owner':owner})
        json_pods = json.loads(pods.content)
        return json_pods
    except Exception as e:
        print e
        return False


def get_services():
    try:
        owner = 0
        if current_user_is_owner():
            owner = 1
        services = requests.get('http://{}:5000'.format(kubeApiIpAddress), data={'method': 'get_services', 'namespace': current_user.email, "owner":owner})
        json_services = json.loads(services.content)
        return json_services
    except Exception as e:
        print e
        return False


def get_deployments():
    try:
        owner = 0
        if current_user_is_owner():
            owner = 1
        deployments = requests.get('http://{}:5000'.format(kubeApiIpAddress), data={'method': 'get_deployments', 'namespace': current_user.email, "owner":owner})
        json_deployments = json.loads(deployments.content)
        return json_deployments
    except Exception as e:
        print e
        return False


def deploy_app(name, image, port, replicas):
    try:
        owner = 0
        if current_user_is_owner():
            owner = 1
        deploy = requests.post('http://{}:5000'.format(kubeApiIpAddress),
                               data={'method': 'deploy', 'namespace': current_user.email, 'name': name, "image": image, "replicas": replicas, "port": port, "owner":owner})
        deploy_json = json.loads(deploy.content)
        return deploy_json
    except Exception as e:
        print e
        return False


def update_deployment(name, image, port, replicas):
    try:
        owner = 0
        if current_user_is_owner():
            owner = 1
        deploy = requests.post('http://{}:5000'.format(kubeApiIpAddress),
                               data={'method': 'update_deployment', 'namespace': current_user.email, 'name': name, "image": image, "replicas": replicas, "port": port, "owner":owner})
        deploy_json = json.loads(deploy.content)
        return deploy_json
    except Exception as e:
        print e
        return False


def delete_deployment(name):
    try:
        owner = 0
        if current_user_is_owner():
            owner = 1
        delete = requests.post('http://{}:5000'.format(kubeApiIpAddress),
                               data={'method': 'delete_deployment', 'namespace': current_user.email, 'name': name, "owner":owner})
        print delete.content
        delete_json = json.loads(delete.content)
        return delete_json
    except Exception as e:
        print e
        return False


def create_service(name, port):
    try:
        owner = 0
        if current_user_is_owner():
            owner = 1
        check_deployment = requests.post('http://{}:5000'.format(kubeApiIpAddress),
                               data={'method': 'check_deployment', 'namespace': current_user.email, 'name': name})
        print check_deployment.text
        if check_deployment.text == "1":
            service = requests.post('http://{}:5000'.format(kubeApiIpAddress),
                                   data={'method': 'service', 'namespace': current_user.email, 'name': name, "port": port, "owner":owner})
        else:
            return "NotAvailable"
        create_service_json = json.loads(service.content)
        return create_service_json
    except Exception as e:
        print e
        return False


def update_service(name, port):
    try:
        owner = 0
        if current_user_is_owner():
            owner = 1
        service = requests.post('http://{}:5000'.format(kubeApiIpAddress),
                               data={'method': 'update_service', 'namespace': current_user.email, 'name': name, "port": port, "owner":owner})
        create_service_json = json.loads(service.content)
        return create_service_json
    except Exception as e:
        print e
        return False


def delete_service(name):
    try:
        owner = 0
        if current_user_is_owner():
            owner = 1
        delete_service = requests.post('http://{}:5000'.format(kubeApiIpAddress),
                               data ={'method': 'delete_service', 'namespace': current_user.email, 'name': name, "owner":owner})
        delete_service_json = json.loads(delete_service.content)
        return delete_service_json
    except Exception as e:
        print e
        return False


@app.route('/dashboard/<string:method>', methods=["get","post"])
@login_required
def dashboard(method):
    if method == "nodes":
        nodes = get_nodes()
        if nodes == {} or nodes == [] or nodes == "Non_Json":
            flash("Please wait while cluster is booting up", 'info')
            nodes = {}
        else:
            if nodes == False:
                flash("Establishing Connection ...", 'info')
                nodes = {}
        return render_template("nodes.html", data=nodes, title="Dashboard")
    elif method == "pods":
        data = get_pods()
        if not data:
            if data == {} or data == []:
                flash("Could not find any pods", 'danger')
            else:
                flash("Failed to connect to API. Try Again",'danger')
                data = {}
        return render_template("pods.html", data=data, title="Dashboard")
    elif method == "services":
        data = get_services()
        if not data:
            if data == {} or data == []:
                flash("No services found",'danger')
            else:
                flash("Failed to connect to API. Try Again", 'danger')
                data = {}
        return render_template("services.html", data=data, title="Dashboard")
    elif method == "deployments":
        data = get_deployments()
        if not data:
            if data == {} or data == []:
                flash("There are no apps currently deployed", 'danger')
            else:
                flash("Failed to connect to API. Try Again", 'danger')
                data = {}
        return render_template("deployments.html", data=data, title="Dashboard")
    elif method == "deploy":
        if request.method == "POST":
            name = request.values.get("name")
            image = request.values.get("image")
            port = request.values.get("port")
            replicas = request.values.get("replicas")
            deploy_json = deploy_app(name, image, port, replicas)
            if deploy_json['status'] != "Failure":
                flash("App Successfully Deployed", 'success')
                return redirect(url_for("dashboard", method="deployments"))
            else:
                flash("Failed to deploy App. {}".format(deploy_json['reason'], 'danger'))
        return render_template("deploy.html", title="Dashboard")
    elif method == "create_service":
        if request.method == "POST":
            name = request.values.get("name")
            port = request.values.get("port")
            deploy_json = create_service(name, port)
            if deploy_json == "NotAvailable":
                flash("Deployment Not Available", "danger")
            else:
                if deploy_json['status'] != "Failure":
                    flash("Service Successfully Created", 'success')
                    return redirect(url_for("dashboard", method="services"))
                else:
                    flash("Failed to create service. {}".format(deploy_json['reason']), 'danger')
        return render_template("create_service.html", title="Dashboard")
    elif method == "update_deployment":
        if request.method == "POST":
            name = request.values.get("name")
            image = request.values.get("image")
            port = request.values.get("port")
            replicas = request.values.get("replicas")
            update_deployment_json = update_deployment(name, image, port, replicas)
            if update_deployment_json['status'] != "Failure":
                flash("App Successfully Deployed", 'success')
                return redirect(url_for("dashboard", method="deployments"))
            else:
                flash("Failed to update App. {}".format(update_deployment_json['reason']), 'danger')
        return render_template("updateDeployment.html", title="Dashboard")
    elif method == "update_service":
        if request.method == "POST":
            name = request.values.get("name")
            port = request.values.get("port")
            update_json = update_service(name, port)
            if update_json['status'] != "Failure":
                flash("Service Successfully Created", 'success')
                return redirect(url_for("dashboard", method="services"))
            else:
                flash("Failed to update service. {}".format(update_json['reason']), 'danger')
        return render_template("updateService.html", title="Dashboard")
    else:
        abort(404)


@app.route('/log_out')
@login_required
def logout():
    logout_user()
    session.clear()
    return redirect(url_for("home"))

api.add_resource(UserApi, '/user_exists')
api.add_resource(LogIn, '/login')
api.add_resource(Address, '/register_address')
api.add_resource(Deployments, '/delete/deployment/')
api.add_resource(Services, '/delete/service/')


if __name__ == "__main__":
    db.create_all()
    app.run(port=5001, debug=True)
