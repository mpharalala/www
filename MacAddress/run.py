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
login_manager.login_message = "Please Logging To View Dashboard"

kubeApiIpAddress = "localhost"


#Flash an error if there is no connection to database before making a request
@app.before_request
def database_connection():
    try:
        db.create_all()
    except Exception as e:
        flash("Lost Connection To Database. Please Try Again Or Contact Support")
        print e


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
        user_data = User.query.filter_by(email=args['email']).first()
        user_schema = UsersSchema()
        user_dictionary = user_schema.dump(user_data).data
        if user_dictionary != {}:
            return {"message": "User Exists", "code": 100}
        else:
            return {"message": "You are not registered. Register First", "code": 402}


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
        if base_station_registered():
            parser = reqparse.RequestParser()
            parser.add_argument("email", type=str, help="Please enter a valid email address", required=True)
            parser.add_argument("password", type=str, help="Please enter a valid Password", required=True)
            args = parser.parse_args()
            user = User.query.filter_by(email=args['email']).first()
            user_dictionary = UsersSchema().dump(user).data
            if (user_dictionary.get('email') == args['email']) \
                    and (user_dictionary.get('password') == hashlib.sha256(args['password']).hexdigest()):
                login_user(user)
                flash("Login Successful")
                return {"message": "Login Successful", "code": 100}
            else:
                return {"message": "Invalid username or password", "code": 401}
        else:
            flash("This Base Station Is Not Registered. Please Register Base Station First")
            return {"message": "This Base Station Is Not Registered. Please Register Base Station", "code": 403}


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


class Nodes(Resource):
    def get(self):
        if current_user.is_authenticated:
            nodes = get_nodes()
            if nodes:
                if nodes == "Non_Json":
                    return {"message": "Please Wait While Cluster Is Booting Up", "code": 202}
                else:
                    data = {"data":[]}
                    for node in nodes:
                        node['Disk'] = node["Info"][0]
                        node['Memory'] = node["Info"][1]
                        node['Disk Pressure'] = node["Info"][2]
                        if node['Ready'] == "True":
                            node['Activity'] = '<label class="">' \
                                               '<span style="color:green" class="fa fa-check-circle fa-2x"></span></label>'
                            node['Status'] = "Ready"
                        else:
                            node['Status'] = "Dead"
                            node['Activity'] = "<label><span style='color:red' class='fa fa-times-circle fa-2x'></span></label>"
                        data['data'].append(node)
                    return {"nodes": data, "code": 200}
            else:
                return {"message": "Establishing Connection...", "code": 202}
        else:
            return {"message": "Please Log in to access this resource", 'code': 202}


def get_pods():
    try:
        owner = 0
        if current_user_is_owner():
            owner = 1
        pods = requests.get('http://{}:5000'.format(kubeApiIpAddress),
                            data={'method': 'get_pods', 'namespace': current_user.email, 'owner': owner})
        json_pods = json.loads(pods.content)
        return json_pods
    except Exception as e:
        print e
        return False


class Pods(Resource):
    def get(self):
        if current_user.is_authenticated:
            pods = get_pods()
            if pods:
                    data = {'data': []}
                    for pod in pods:
                        pod['Container Image'] = pod['Info'][0]['Container name']
                        pod['Container Name'] = pod['Info'][0]['Container name']
                        pod['Container Port'] = pod['Info'][0]['Ports'][0]['containerPort']
                        pod['Protocol'] = pod['Info'][0]['Ports'][0]['protocol']
                        if pod["Status"] == "Pending":
                            pod["Activity"] = '<label><span style="color:orange" class="fa fa-spinner fa-2x"></span></label>'
                        else:
                            if pod['Status'] == "Running":
                                pod["Activity"] = ' <label><span style="color:green" class="fa fa-check-circle fa-2x"></span></label>'
                            else:
                                pod["Activity"] = '  <label><span style="color:red" class="fa fa-times-circle fa-2x"></span></label>'
                        data['data'].append(pod)
                    return {"pods": data, "code": 200}
            else:
                return {"message": "No Pods Found", "code": 202}
        else:
            return {"message": "Please Log in to access this resource", 'code': 202}


class Services(Resource):
    def delete(self):
        if current_user.is_authenticated:
            parser = reqparse.RequestParser()
            parser.add_argument("name", type=str, help="Please enter a valid service name", required=True)
            args = parser.parse_args()
            response = delete_service(args['name'])
            if response['status'] == "Failure":
                return {"message": "Failed to delete service. {}".format(response['message']), "code": 500}
            if response['status'] == "Success":
                flash("{} service removed successfully".format(args['name']), 'success')
                return {"message": "Service removed successfully", "code": 200}
        else:
            abort(404)

    def get(self):
        if current_user.is_authenticated:
            try:
                owner = 0
                if current_user_is_owner():
                    owner = 1
                services = requests.get('http://{}:5000'.format(kubeApiIpAddress),
                                        data={'method': 'get_services', 'namespace': current_user.email,
                                              "owner": owner})
                json_services = json.loads(services.content)
            except Exception as e:
                print e
                json_services = False
            services = json_services
            if services:
                    data = {'data': []}
                    for service in services:
                        if service["Name"] != "kubernetes":
                            service['Cluster IP'] = service['Info']['clusterIP']
                            service['Node Port'] = service['Info']['ports'][0]['nodePort']
                            service['Port'] = service['Info']['ports'][0]['port']
                            service['Protocol'] = service['Info']['ports'][0]['protocol']
                            service['Target Port'] = service['Info']['ports'][0]['targetPort']
                            service['Type'] = service['Info']['type']
                            service['Type'] = service['Info']['type']
                            service['Delete'] = ''' <button onClick="delete_service('{}')" class="btn btn-danger btn-xs" data-toggle="modal"data-target="#confirmModal"><span class="fa fa-trash-o"></span>Delete</button>'''.format(service["Name"])
                            data['data'].append(service)
                    return {"services": data, "code": 200}
            else:
                return {"message": "No Services Found", "code": 202}
        else:
            return {"message": "Please Log in to access this resource", 'code': 202}


def get_deployments():
    try:
        owner = 0
        if current_user_is_owner():
            owner = 1
        deployments = requests.get('http://{}:5000'.format(kubeApiIpAddress),
                                   data={'method': 'get_deployments', 'namespace': current_user.email, "owner": owner})
        json_deployments = json.loads(deployments.content)
        return json_deployments
    except Exception as e:
        print e
        return False

class Deployments(Resource):
    def delete(self):
        if current_user.is_authenticated:
            parser = reqparse.RequestParser()
            parser.add_argument("name", type=str, help="Please enter a valid deployment name", required=True)
            args = parser.parse_args()
            response = delete_deployment(args['name'])
            if response['status'] == "Failure":
                return {"message": "Failed to delete deployment. {}".format(response["message"]), "code": 500}
            if response['status'] == "Success":
                flash("Deployment {} removed successfully".format(args['name']))
                return {"message": "Deployment removed successfully", "code": 200}
        else:
            return {"message": "Please Log in to access this resource", 'code': 202}

    def get(self):
        if current_user.is_authenticated:
            try:
                owner = 0
                if current_user_is_owner():
                    owner = 1
                deployments = requests.get('http://{}:5000'.format(kubeApiIpAddress),
                                           data={'method': 'get_deployments', 'namespace': current_user.email,
                                                 "owner": owner})
                json_deployments = json.loads(deployments.content)
            except Exception as e:
                print e
                json_deployments = False
            if json_deployments:
                    deployments = {'data': []}
                    for deployment in json_deployments:
                        iterator = 0
                        while iterator < len(deployment['Info']['conditions']):
                            filtered_deployment = {}
                            filtered_deployment['Name'] = deployment["Name"]
                            filtered_deployment['Age'] = deployment['Age']
                            filtered_deployment['Type'] = deployment['Info']['conditions'][iterator]['type']
                            filtered_deployment['Replicas'] = deployment['Info']['replicas']
                            filtered_deployment['Last Update Time'] = deployment['Info']['conditions'][iterator]['lastUpdateTime']
                            filtered_deployment['Reason'] = deployment['Info']['conditions'][iterator]['reason']
                            filtered_deployment['Type'] = deployment['Info']['conditions'][iterator]['type']
                            if deployment['Info']['conditions'][iterator]['status'] == "True":
                                filtered_deployment['Status'] = """  <label class="">
                                                                <span style="color:green" class="fa fa-check-circle fa-2x">
                                                                </span>
                                                            </label>"""
                            else:
                                filtered_deployment['Status'] = """  <label class="">
                                                                <span style="color:red" class="fa fa-times-circle fa-2x">
                                                                </span>
                                                            </label>"""

                            filtered_deployment['Delete'] = """<button onclick="delete_deployment('{}')"
                                                        class="btn btn-danger btn-xs" data-toggle="modal"
                                                        data-target="#confirmModal">
                                                        <span class="fa fa-trash-o"></span>Delete
                                                        </button>""".format(deployment["Name"])
                            deployments['data'].append(filtered_deployment)
                            iterator = iterator + 1
                    return {"deployments": deployments, "code": 200}
            else:
                return {"message": "No deployments Found", "code": 202}
        else:
            return {"message": "Please Log in to access this resource", 'code': 202}


class Register(Resource):
    def post(self):
        parser = reqparse.RequestParser()
        parser.add_argument("address", type=str, help="Please enter a valid Mac Address", required=True)
        parser.add_argument("email", type=str, help="Please enter a valid email address", required=True)
        parser.add_argument("password", type=str, help="Please enter a valid password", required=True)
        parser.add_argument("name", type=str, help="Please enter base station name", required=True)
        args = parser.parse_args()
        user = User.query.filter_by(email=args['email']).first()
        user_json = UsersSchema().dump(user).data
        if user_json != {}:
            if user_json['password'] == hashlib.sha256(args['password']).hexdigest():
                mac_address = Addresses.query.filter_by(mac_address=args['address']).first()
                mac_address_json = AddressSchema().dump(mac_address).data
                if mac_address_json != {}:
                    if mac_address_json["status"] == 0:
                        mac_address.status = 1
                        db.session.add(MacAddresses(user_id=user_json['id'],
                                                    mac_address=mac_address_json['mac_address'], name=args['name']))
                        try:
                            mac_address_file = open("mac_address.txt", "w+")
                            mac_address_file.write(args['address'])
                            mac_address_file.close()
                            db.session.commit()
                            flash("Mac Address {} Successfully Assigned to {}"
                                  .format(mac_address_json['mac_address'],
                                          user_json["name"] + " " + user_json["surname"]))
                            return {"message": "Mac Address {} Successfully Assigned to "
                                               "{}".format(mac_address_json['mac_address'],
                                                           user_json["name"] + " " + user_json["surname"]), "code": 200}
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
    return render_template("home.html", title="Home", global_mac_address=get_address(),
                           registered=base_station_registered())


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









def deploy_app(name, image, port, replicas):
    try:
        owner = 0
        if current_user_is_owner():
            owner = 1
        deploy = requests.post('http://{}:5000'.format(kubeApiIpAddress),
                               data={'method': 'deploy', 'namespace': current_user.email, 'name': name, "image": image,
                                     "replicas": replicas, "port": port, "owner": owner})
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
                               data={'method': 'update_deployment', 'namespace': current_user.email, 'name': name,
                                     "image": image, "replicas": replicas, "port": port, "owner": owner})
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
                               data={'method': 'delete_deployment',
                                     'namespace': current_user.email, 'name': name, "owner":owner})
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
        if check_deployment.text == "1":
            service = requests.post('http://{}:5000'.format(kubeApiIpAddress),
                                   data={'method': 'service', 'namespace': current_user.email,
                                         'name': name, "port": port, "owner": owner})
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
                                data={'method': 'update_service', 'namespace': current_user.email,
                                      'name': name, "port": port, "owner": owner})
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
        delete_service_call = requests.post('http://{}:5000'.format(kubeApiIpAddress),
                                            data={'method': 'delete_service',
                                                  'namespace': current_user.email, 'name': name, "owner": owner})
        delete_service_json = json.loads(delete_service_call.content)
        return delete_service_json
    except Exception as e:
        print e
        return False


@app.route('/dashboard/<string:method>', methods=["get","post"])
@login_required
def dashboard(method):
    if method == "nodes":
        return render_template("nodes_ajax.html", title="Dashboard")
    elif method == "pods":
        return render_template("pods_ajax.html", title="Dashboard")
    elif method == "services":
        return render_template("services_ajax.html", title="Dashboard")
    elif method == "deployments":
        return render_template("deployments.html", title="Dashboard")
    elif method == "deploy":
        if request.method == "POST":
            name = request.values.get("name")
            image = request.values.get("image")
            port = request.values.get("port")
            replicas = request.values.get("replicas")
            deploy_json = deploy_app(name, image, port, replicas)
            if deploy_json:
                if deploy_json['status'] != "Failure":
                    flash("App Successfully Deployed", 'success')
                    return redirect(url_for("dashboard", method="deployments"))
                else:
                    flash("Failed to deploy App. {}".format(deploy_json['reason']), 'danger')
            else:
                flash("Failed to deploy App. {}".format("Failed to establish Connection"), 'danger')
        return render_template("deploy.html", title="Dashboard")
    elif method == "create_service":
        if request.method == "POST":
            name = request.values.get("name")
            port = request.values.get("port")
            deploy_json = create_service(name, port)
            if deploy_json:
                if deploy_json == "NotAvailable":
                    flash("Deployment Not Found", "danger")
                else:
                    if deploy_json['status'] != "Failure":
                        flash("Service Successfully Created", 'success')
                        return redirect(url_for("dashboard", method="services"))
                    else:
                        flash("Failed to create service. {}".format(deploy_json['reason']), 'danger')
            else:
                flash("Failed to create service. {}".format("Failed to establish Connection"), 'danger')
        return render_template("create_service.html", title="Dashboard")
    elif method == "update_deployment":
        if request.method == "POST":
            name = request.values.get("name")
            image = request.values.get("image")
            port = request.values.get("port")
            replicas = request.values.get("replicas")
            update_deployment_json = update_deployment(name, image, port, replicas)
            if update_deployment_json:
                if update_deployment_json['status'] != "Failure":
                    flash("App Successfully Deployed", 'success')
                    return redirect(url_for("dashboard", method="deployments"))
                else:
                    flash("Failed to update App. {}".format(update_deployment_json['reason']), 'danger')
            else:
                flash("Failed to update App. {}".format("Failed to establish Connection"), 'danger')
        return render_template("updateDeployment.html", title="Dashboard")
    elif method == "update_service":
        if request.method == "POST":
            name = request.values.get("name")
            port = request.values.get("port")
            update_json = update_service(name, port)
            if update_json:
                if update_json['status'] != "Failure":
                    flash("Service Successfully Created", 'success')
                    return redirect(url_for("dashboard", method="services"))
                else:
                    flash("Failed to update service. {}".format(update_json['reason']), 'danger')
            else:
                flash("Failed to update service. {}".format("Failed to establish Connection"), 'danger')
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
api.add_resource(Register, '/register_address')
api.add_resource(Nodes, '/nodes')
api.add_resource(Pods, '/pods')
api.add_resource(Services, '/services')
api.add_resource(Deployments, '/deployments')


if __name__ == "__main__":
    db.create_all()
    app.run(port=5001, debug=True, threaded=True)
