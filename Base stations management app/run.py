from flask import Flask, render_template, abort, redirect, url_for, flash, request, session
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from flask_restful import Resource, Api, reqparse
from flask_marshmallow import Marshmallow
from flask_sqlalchemy import SQLAlchemy
import requests
import hashlib
import json

# App initialization
app = Flask(__name__)
api = Api(app)

# Database configuration
app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql://root:pass@192.168.0.2/addresses'
app.config['SQLALCHEMY_BINDS'] = {"users_database": "mysql://root:pass@192.168.0.2/users"}
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = "random string"
db = SQLAlchemy(app)
ma = Marshmallow(app)

# Logging manager configuration
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "home"
login_manager.login_message = "Please Logging To View Dashboard"

# Api ip address
kubeApiIpAddress = "localhost"


# Load user to logging manager
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


# Load base station mac address from mac_address file
def get_address():
    # Try to open file and return mac_address
    try:
        mac_address_file = open("mac_address.txt")
    except:
        mac_address_file = open("mac_address.txt", "w+")
    mac_address = mac_address_file.read()
    mac_address_file.close()
    return mac_address


# Active and inactive mac_addresses table
class Addresses(db.Model):
    __tablename__ = "mac_addresses"

    mac_address = db.Column(db.String(500), primary_key=True)
    status = db.Column(db.Boolean, default=0)


# Registered base stations mac addresses
class MacAddresses(db.Model):
    __bind_key__ = "users_database"
    __tablename__ = "base_stations"

    id = db.Column("id", db.Integer, primary_key=True)
    mac_address = db.Column(db.String(500), nullable=False)
    name = db.Column(db.String(500), nullable=False)
    user_id = db.Column(db.Integer, nullable=False)


# Users database table
class User(db.Model, UserMixin):
    __tablename__ = 'users'
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


# Model schemas for database tables for flask_marshamallow
class AddressSchema(ma.ModelSchema):
    class Meta:
        model = Addresses


class UsersSchema(ma.ModelSchema):
    class Meta:
        model = User


class MacAddressesSchema(ma.ModelSchema):
    class Meta:
        model = MacAddresses


# User management class with get class method only
class UserApi(Resource):
    def get(self):

        # parse arguments from requets
        parser = reqparse.RequestParser()
        parser.add_argument("email", type=str, help="Please enter a valid email address", required=True)
        args = parser.parse_args()
        user_data = User.query.filter_by(email=args['email']).first()

        # Dump users data to sql alchemy to get json format

        user_dictionary = UsersSchema().dump(user_data).data
        if user_dictionary != {}:
            return {"message": "User Exists", "code": 100}
        else:
            return {"message": "You are not registered. Register First", "code": 402}


# A method to check if the base station is register or not
def base_station_registered():

    # Request the base stations mac address from the registered bases stations table
    address = MacAddresses.query.filter_by(mac_address=get_address()).first()

    # Dup base station data to sql_alchemy to convert into json
    schema = MacAddressesSchema()
    results = schema.dump(address).data
    if results:
        return True
    else:
        return False


# Class to manage user login
class LogIn(Resource):
    def post(self):
        if base_station_registered():

            # parse arguments from request
            parser = reqparse.RequestParser()
            parser.add_argument("email", type=str, help="Please enter a valid email address", required=True)
            parser.add_argument("password", type=str, help="Please enter a valid Password", required=True)
            args = parser.parse_args()

            # Get user instance from database
            user = User.query.filter_by(email=args['email']).first()

            # Dump user data to get json response
            user_dictionary = UsersSchema().dump(user).data

            # Log a user in if their password mathces
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


# Get all database nodes
def get_nodes():
    # Return an error if no nodes are returned
    try:
        nodes = requests.get('http://{}:5000'.format(kubeApiIpAddress), data={'method': 'get_nodes'})

        # Load the api response into json
        json_nodes = json.loads(nodes.content)
        return json_nodes
    except Exception as e:
        print e
        if str(e) == "No JSON object could be decoded":
            return "Non_Json"
        else:
            return False

# Get all the nodes of the base station
class Nodes(Resource):
    def get(self):
        # Only users logged in can see the base station nodes
        if current_user.is_authenticated:
            nodes = get_nodes()

            # Test if any nodes are presesnt
            if nodes:
                # Show that the cluster is still booting if no nodes are present
                if nodes == "Non_Json":
                    return {"message": "Please Wait While Cluster Is Booting Up", "code": 202}
                else:

                    # Filter the api response
                    data = {"data": []}
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
                            node[
                                'Activity'] = "<label><span style='color:red' class='fa fa-times-circle fa-2x'></span></label>"
                        data['data'].append(node)
                    return {"nodes": data, "code": 200}
            else:
                return {"message": "Establishing Connection...", "code": 202}
        else:
            return {"message": "Please Log in to access this resource", 'code': 202}


# Get base station deployed pods
def get_pods():
    try:
        owner = 0

        # Return 1 if the logged in  user is the onwer of the base station
        if current_user_is_owner():
            owner = 1
        pods = requests.get('http://{}:5000'.format(kubeApiIpAddress),
                            data={'method': 'get_pods', 'namespace': current_user.email, 'owner': owner})

        # Make the api response into json
        json_pods = json.loads(pods.content)
        return json_pods
    except Exception as e:
        print e
        return False


# Get all pods of the base station
class Pods(Resource):
    def get(self):
        # Only authenticated users can view the pods
        if current_user.is_authenticated:
            pods = get_pods()
            if pods:
                data = {'data': []}
                # Filter the pods for the data tables
                for pod in pods:
                    pod['Container Image'] = pod['Info'][0]['Container name']
                    pod['Container Name'] = pod['Info'][0]['Container name']
                    pod['Container Port'] = pod['Info'][0]['Ports'][0]['containerPort']
                    pod['Protocol'] = pod['Info'][0]['Ports'][0]['protocol']
                    if pod["Status"] == "Pending":
                        pod[
                            "Activity"] = '<label><span style="color:orange" class="fa fa-spinner fa-2x"></span></label>'
                    else:
                        if pod['Status'] == "Running":
                            pod[
                                "Activity"] = ' <label><span style="color:green" class="fa fa-check-circle fa-2x"></span></label>'
                        else:
                            pod[
                                "Activity"] = '  <label><span style="color:red" class="fa fa-times-circle fa-2x"></span></label>'
                    data['data'].append(pod)
                return {"pods": data, "code": 200}
            else:
                return {"message": "No Pods Found", "code": 202}
        else:
            return {"message": "Please Log in to access this resource", 'code': 202}


# Get the services of the base station
class Services(Resource):

    # method to delete a base station
    def delete(self):
        if current_user.is_authenticated:

            # Parse arguments from the api
            parser = reqparse.RequestParser()
            parser.add_argument("name", type=str, help="Please enter a valid service name", required=True)
            args = parser.parse_args()

            # send delete request to api
            response = delete_service(args['name'])
            if response['status'] == "Failure":
                return {"message": "Failed to delete service. {}".format(response['message']), "code": 500}
            if response['status'] == "Success":
                flash("{} service removed successfully".format(args['name']), 'success')
                return {"message": "Service removed successfully", "code": 200}
        else:
            abort(404)

    # Method to get all base stations
    def get(self):
        # Only authenticated suers can see their services
        if current_user.is_authenticated:
            try:
                owner = 0
                # The owner can see all the base stations
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

                # Sort the services for data tables
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
                        service[
                            'Delete'] = ''' <button onClick="delete_service('{}')" class="btn btn-danger btn-xs" data-toggle="modal"data-target="#confirmModal"><span class="fa fa-trash-o"></span>Delete</button>'''.format(
                            service["Name"])
                        data['data'].append(service)
                return {"services": data, "code": 200}
            else:
                return {"message": "No Services Found", "code": 202}
        else:
            return {"message": "Please Log in to access this resource", 'code': 202}


# Get deployments of the currently logged in user
def get_deployments():
    try:
        owner = 0
        # If a user is owner, the can see all base station deployments
        if current_user_is_owner():
            owner = 1
        deployments = requests.get('http://{}:5000'.format(kubeApiIpAddress),
                                   data={'method': 'get_deployments', 'namespace': current_user.email, "owner": owner})
        json_deployments = json.loads(deployments.content)
        return json_deployments
    except Exception as e:
        print e
        return False


# Get all deployments of the base station
class Deployments(Resource):
    def delete(self):

        # Check if the user is authenticated
        if current_user.is_authenticated:

            # parse arguments from the request
            parser = reqparse.RequestParser()
            parser.add_argument("name", type=str, help="Please enter a valid deployment name", required=True)
            args = parser.parse_args()

            # Send delete request to the api
            response = delete_deployment(args['name'])
            if response['status'] == "Failure":
                return {"message": "Failed to delete deployment. {}".format(response["message"]), "code": 500}
            if response['status'] == "Success":
                flash("Deployment {} removed successfully".format(args['name']))
                return {"message": "Deployment removed successfully", "code": 200}
        else:
            return {"message": "Please Log in to access this resource", 'code': 202}

    # Method to get the apps deployed by the user
    def get(self):

        # Check if the user is authenticed
        if current_user.is_authenticated:
            try:
                owner = 0

                # Only the owner can see all deployments
                if current_user_is_owner():
                    owner = 1

                #Send api request to get deployments
                deployments = requests.get('http://{}:5000'.format(kubeApiIpAddress),
                                           data={'method': 'get_deployments', 'namespace': current_user.email,
                                                 "owner": owner})

                # Make the deployments objet json
                json_deployments = json.loads(deployments.content)
            except Exception as e:
                print e
                json_deployments = False

            # Start looping if there are deployments
            if json_deployments:
                deployments = {'data': []}
                for deployment in json_deployments:
                    iterator = 0

                    # Filter deployments for data tables
                    while iterator < len(deployment['Info']['conditions']):
                        filtered_deployment = {}
                        filtered_deployment['Name'] = deployment["Name"]
                        filtered_deployment['Age'] = deployment['Age']
                        filtered_deployment['Type'] = deployment['Info']['conditions'][iterator]['type']
                        filtered_deployment['Replicas'] = deployment['Info']['replicas']
                        filtered_deployment['Last Update Time'] = deployment['Info']['conditions'][iterator][
                            'lastUpdateTime']
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


# Register a base staition
class Register(Resource):
    def post(self):

        # parse the argumnets from the requets
        parser = reqparse.RequestParser()
        parser.add_argument("address", type=str, help="Please enter a valid Mac Address", required=True)
        parser.add_argument("email", type=str, help="Please enter a valid email address", required=True)
        parser.add_argument("password", type=str, help="Please enter a valid password", required=True)
        parser.add_argument("name", type=str, help="Please enter base station name", required=True)
        args = parser.parse_args()

        # Authenticate the user
        user = User.query.filter_by(email=args['email']).first()
        user_json = UsersSchema().dump(user).data
        if user_json != {}:
            if user_json['password'] == hashlib.sha256(args['password']).hexdigest():

                # Check if the mac_address is not already used
                mac_address = Addresses.query.filter_by(mac_address=args['address']).first()
                mac_address_json = AddressSchema().dump(mac_address).data
                if mac_address_json != {}:

                    # Change the mac_address status to used
                    if mac_address_json["status"] == 0:
                        mac_address.status = 1
                        db.session.add(MacAddresses(user_id=user_json['id'],
                                                    mac_address=mac_address_json['mac_address'], name=args['name']))
                        try:

                            # Write the mac_address into the mac address file
                            mac_address_file = open("mac_address.txt", "w+")
                            mac_address_file.write(args['address'])
                            mac_address_file.close()

                            # Save the changes to the database
                            db.session.commit()
                            flash("Mac Address {} Successfully Assigned to {}"
                                  .format(mac_address_json['mac_address'],
                                          user_json["name"] + " " + user_json["surname"]))
                            return {"message": "Mac Address {} Successfully Assigned to "
                                               "{}".format(mac_address_json['mac_address'],
                                                           user_json["name"] + " " + user_json["surname"]), "code": 200}
                        except Exception as e:
                            print e

                            # Roll back all changse if there is an error in one of the requests
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


# Home page view
@app.route('/')
def home():
    # Clear the user from session
    logout_user()
    return render_template("home.html", title="Home", global_mac_address=get_address(),
                           registered=base_station_registered())


# Function to check if the user owns the base station
def current_user_is_owner():

    # Get the base station and the user registed in the dataabse
    address = MacAddresses.query.filter_by(mac_address=get_address()).first()
    schema = MacAddressesSchema()
    results = schema.dump(address).data
    if results:
        # Verify if the user owns it
        if current_user.id == results['user_id']:
            return True
        else:
            return False
    else:
        return False


# Deploy app to base station function
def deploy_app(name, image, port, replicas):
    try:
        owner = 0

        #Check if this user is the owner of the base station
        if current_user_is_owner():
            owner = 1

        # Send deployments request to base station
        deploy = requests.post('http://{}:5000'.format(kubeApiIpAddress),
                               data={'method': 'deploy', 'namespace': current_user.email, 'name': name, "image": image,
                                     "replicas": replicas, "port": port, "owner": owner})
        deploy_json = json.loads(deploy.content)
        return deploy_json
    except Exception as e:
        print e
        return False


# Update deployments function
def update_deployment(name, image, port, replicas):
    try:
        owner = 0
        # Check if the logged in user is the owner of the base station
        if current_user_is_owner():
            owner = 1
        deploy = requests.post('http://{}:5000'.format(kubeApiIpAddress),
                               data={'method': 'update_deployment', 'namespace': current_user.email, 'name': name,
                                     "image": image, "replicas": replicas, "port": port, "owner": owner})
        # load theresponse from api into json
        deploy_json = json.loads(deploy.content)
        return deploy_json
    except Exception as e:
        print e
        return False


# delete a deployment from database
def delete_deployment(name):
    try:
        owner = 0
        # Check if the user is onwer
        if current_user_is_owner():
            owner = 1

        # Send request to API
        delete = requests.post('http://{}:5000'.format(kubeApiIpAddress),
                               data={'method': 'delete_deployment',
                                     'namespace': current_user.email, 'name': name, "owner": owner})

        # Transale response to json
        delete_json = json.loads(delete.content)
        return delete_json
    except Exception as e:
        print e
        return False


# Create a service for a deployment
def create_service(name, port):
    try:
        owner = 0
        if current_user_is_owner():
            owner = 1

        # send deployment request to api
        check_deployment = requests.post('http://{}:5000'.format(kubeApiIpAddress),
                                         data={'method': 'check_deployment', 'namespace': current_user.email,
                                               'name': name})

        # Check if the deployment exists before trying to create a service
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


# Update a service
def update_service(name, port):
    try:
        owner = 0
        if current_user_is_owner():
            owner = 1

        # Send update request to APi
        service = requests.post('http://{}:5000'.format(kubeApiIpAddress),
                                data={'method': 'update_service', 'namespace': current_user.email,
                                      'name': name, "port": port, "owner": owner})

        # Laod updare into json
        create_service_json = json.loads(service.content)
        return create_service_json
    except Exception as e:
        print e
        return False


# Delete a service from the api
def delete_service(name):
    try:
        owner = 0
        if current_user_is_owner():
            owner = 1

        # Call to api
        delete_service_call = requests.post('http://{}:5000'.format(kubeApiIpAddress),
                                            data={'method': 'delete_service',
                                                  'namespace': current_user.email, 'name': name, "owner": owner})

        # Load service to api
        delete_service_json = json.loads(delete_service_call.content)
        return delete_service_json
    except Exception as e:
        print e
        return False


# show the dashboard of all the tables link
@app.route('/dashboard/<string:method>', methods=["get", "post"])
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

        # Deploy an app to the base station

        if request.method == "POST":
            name = request.values.get("name")
            image = request.values.get("image")
            port = request.values.get("port")
            replicas = request.values.get("replicas")

            # The api returns a json response

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

    # Create a service ethod
    elif method == "create_service":
        if request.method == "POST":

            # Request values from the form

            name = request.values.get("name")
            port = request.values.get("port")
            deploy_json = create_service(name, port)

            # If there is a response from the api
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

    # Update deployment method
    elif method == "update_deployment":
        if request.method == "POST":

            # Get values from the form

            name = request.values.get("name")
            image = request.values.get("image")
            port = request.values.get("port")
            replicas = request.values.get("replicas")
            update_deployment_json = update_deployment(name, image, port, replicas)

            # Get a json response from the API
            if update_deployment_json:
                if update_deployment_json['status'] != "Failure":
                    flash("App Successfully Deployed", 'success')
                    return redirect(url_for("dashboard", method="deployments"))
                else:
                    flash("Failed to update App. {}".format(update_deployment_json['reason']), 'danger')
            else:
                flash("Failed to update App. {}".format("Failed to establish Connection"), 'danger')
        return render_template("updateDeployment.html", title="Dashboard")

    # Update a service method
    elif method == "update_service":
        if request.method == "POST":

            # request values from the form
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


# Clear session and logout user
@app.route('/log_out')
@login_required
def logout():
    logout_user()
    session.clear()
    return redirect(url_for("home"))


# Add the resources to the link
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
