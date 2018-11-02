from flask import Flask, render_template, abort, redirect, url_for, flash, request, session, jsonify
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from flask_cors import CORS, cross_origin
from datetime import *
from dateutil import parser
import requests
import logging


# App initialization
app = Flask(__name__)



cors = CORS(app)
app.config['CORS_HEADERS'] = 'Content-Type'

# logging.basicConfig(filename="app_log.log", level=logging.DEBUG)
app.config['SECRET_KEY'] = "secret"

# Logging manager configuration
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "home"
login_manager.login_message = "Please Log In To View Dashboard"

# Api ip address
kubeApiIpAddress = "192.168.0.119:8090"
blockChainApiIp = '192.168.0.119:5000'
cloudApi = '192.168.0.119:8080'


with open("/var/www/base_station_management_python3/mac_address.txt") as mac_address_file:
    mac_address = mac_address_file.read().strip()


class User(UserMixin):
    def __init__(self, user_id, pass_phrase, token):
        self.id = user_id
        self.pass_phrase = pass_phrase
        self.token = token


@login_manager.user_loader
def load_user(user_id):
    user = User(user_id=user_id, pass_phrase=session['pass_phrase'],
                token=session['token'])
    return user


@app.route("/get_mac_address")
def get_mac_address():
    print(mac_address)
    return jsonify({"mac_address": mac_address})\



@app.route("/rate", methods=["GET", "POST"])
def rate():
    if request.method == "POST":
        requests.post('http://{}'.format(cloudApi),
                      data={'method': 'set_rate', 'mac_address': mac_address,
                            'rate': request.form['rate']}).json()
        return redirect(url_for("rate"))
    return render_template("rates.html", title="Rates", current_rate=get_rate_local()['result'])


@app.route("/get_rate")
def get_rate():
    return jsonify(get_rate_local())


def get_rate_local():
    return requests.get('http://{}'.format(cloudApi),
                        data={'method': 'get_rate',
                              'mac_address': mac_address}).json()


# Home page view
@app.route('/')
def home():
    api_response = base_station_is_registered()
    registered = False
    if 'error' in api_response:
        registered = False
    else:
        if api_response['message'] == 'Registered':
            registered = True
    return render_template("home.html", title="Home", mac_address=mac_address, registered=registered)


def base_station_is_registered():
    return requests.post('http://{}'.format(blockChainApiIp),
                         data={'method': 'verify_base_station', 'mac_address': mac_address}).json()


@app.route('/user_exists')
def user_exists():
    api_response = requests.post('http://{}'.format(blockChainApiIp),
                                 data={'method': 'check_email', 'email': request.args['email']}).json()
    if api_response.get('result') == "Email is available":
        return jsonify({"message": "Email Not Found. Verify Input Or Register", "code": 402})
    else:
        if api_response.get('error') == "Email already exists":
            return jsonify({"message": "", "code": 100})


@app.route('/login', methods=["POST"])
def login():
    response = requests.post('http://{}'.format(blockChainApiIp),
                             data={'method': 'login', 'username': request.values['email'],
                                   'password': request.values['password']}).json()
    if ('error' in response) or (str(base_station_is_registered()['owner']) != str(response['uid'])):
        return jsonify({"message": "Invalid Email Or Password", "code": 401})
    else:
        session['user_id'] = response['uid']
        session['pass_phrase'] = response['passphrase']
        session['token'] = response['token']
        user_instance = User(user_id=response['uid'], pass_phrase=response['passphrase'],
                             token=response['token'])
        login_user(user_instance)
        flash("Login Successful")
        return jsonify({"message": "Login Successful", "code": 100})


# Method to Log splash user In
@app.route('/splash_auth_login', methods=["POST"])
@cross_origin()
def splash_login():
    if request.method == "POST":

        # Send api request to get token for user and verify credentials
        login_response = requests.post('http://{}'.format(blockChainApiIp),
                                 data={'method': 'login', 'username': request.values['log_in_email'],
                                       'password': request.values['log_in_password']}).json()
        print("User logged in")
        if 'error' in login_response:
            return jsonify({"code": 401})
        else:
            session['email'] = request.values['log_in_email']
            user_balance = requests.post('http://{}'.format(blockChainApiIp),
                                         data={'method': 'balance', 'user_id': login_response['uid'],
                                               'token': login_response['token'],
                                               'passphrase': login_response['passphrase']}).json()
            rate = get_rate_local()['result']
            if float(user_balance['balance']) < rate*float(request.values['data_bundle']):
                return jsonify({"code": 412})
            owner_id = base_station_is_registered()['owner']
            print(request.values['client_mac'])
            charge_user_response = requests.post('http://{}'.format(blockChainApiIp),
                                                 data={'method': 'send_to_riot_wallet',
                                                       'user_id': login_response['uid'],
                                                       'token': login_response['token'],
                                                       'password': request.values['log_in_password'],
                                                       'qty': rate * float(request.values['data_bundle']), 'receiver_id': owner_id,
                                                       'passphrase': login_response['passphrase'], 'rate': rate,
                                                       'device_mac_address': request.values['client_mac'],
                                                       'base_station_mac_address': mac_address}).json()
            if charge_user_response['result'] == "Success":
                print("Login user in")
                return jsonify({"code": 200})


@app.route('/register_base_station', methods=['POST'])
def register_base_station():
    print(mac_address)
    api_response = requests.post('http://{}'.format(cloudApi),
                                 data={'method': 'check_mac_address',  'mac_address': mac_address}).json()
    print(api_response)
    if 'error' in api_response:
        return jsonify({"code": "401", "message": "Invalid Mac Address"})
    else:
        api_response = requests.post('http://{}'.format(blockChainApiIp),
                                     data={'method': 'register_base_station', 'email': request.values['email'],
                                           'password': request.values['password'], 'mac_address': mac_address,
                                           'name': request.values['name']}).json()
        print(api_response)
        if 'error' in api_response:
            return jsonify({"code": "401", "message": "Invalid Email Or Password"})
        else:
            api_response = requests.get('http://{}'.format(cloudApi),
                                        data={'method': 'activate_mac_address', 'mac_address': mac_address, 'rate': request.values['rate']}).json()
            if api_response.get('result') == "Mac address has been activated":
                return jsonify({"code": "200", "message": "Base Station Registered"})
            else:
                return jsonify({"code": "401", "message": "This Base Station Is Already Registered"})


@app.route('/nodes')
@login_required
def nodes():
    api_response = requests.get('http://{}'.format(kubeApiIpAddress), data={'method': 'get_nodes'}).json()

    # Test if any nodes are present
    if api_response:
            # Filter the api response
            data = {"data": []}
            for node in api_response:
                node['Disk'] = node["Info"][0]
                node['Memory'] = node["Info"][1]
                node['Disk Pressure'] = node["Info"][2]
                time_stamp = parser.parse(node["Created"])
                time_stamp = time_stamp.replace(tzinfo=None)
                age = datetime.now() - time_stamp
                age = str(age).split(":")
                age = age[0] + "h " + age[1] + "m"
                node["Age"] = str(age)
                if node['Ready'] == "True":
                    node['Activity'] = '<label class="">' \
                                       '<span style="color:green" class="fa fa-check-circle fa-2x"></span></label>'
                    node['Status'] = "Ready"
                else:
                    node['Status'] = "Dead"
                    node[
                        'Activity'] = "<label><span style='color:red' class='fa fa-times-circle fa-2x'></span></label>"
                data['data'].append(node)
            return jsonify({"nodes": data, "code": 200})
    else:
        return jsonify({"message": "Please Wait While Cluster Is Booting Up", "code": 202})


@app.route('/pods')
@login_required
def pods():
    api_response = requests.get('http://{}'.format(kubeApiIpAddress),
                                data={'method': 'get_pods'}).json()
    if api_response:
        data = {'data': []}
        print(api_response)
        # Filter the pods for the data tables
        for pod in api_response:
            pod['Container Image'] = pod['Info'][0]['Container image']
            pod['Container Name'] = pod['Info'][0]['Container name']
            pod['Container Port'] = pod['Info'][0]['Ports'][0]['containerPort']
            pod['Protocol'] = pod['Info'][0]['Ports'][0]['protocol']
            time_stamp = parser.parse(pod["Created"])
            time_stamp = time_stamp.replace(tzinfo=None)
            age = datetime.now() - time_stamp
            age = str(age).split(":")
            age = age[0] + "h " + age[1] + "m"
            pod['Age'] = str(age)
            if pod["Status"] == "Pending":
                pod[
                    "Activity"] = '<label><span style="color:orange" class="fa fa-spinner fa-2x"></span></label>'
            else:
                if pod['Status'] == "Running":
                    pod["Activity"] =\
                        ' <label><span style="color:green" class="fa fa-check-circle fa-2x"></span></label>'
                else:
                    pod["Activity"] = \
                        '  <label><span style="color:red" class="fa fa-times-circle fa-2x"></span></label>'
            data['data'].append(pod)
        return jsonify({"pods": data, "code": 200})
    else:
        return jsonify({"message": "No Pods Found", "code": 202})


@app.route('/services')
@login_required
def services():
    api_response = requests.get('http://{}'.format(kubeApiIpAddress),
                                data={'method': 'get_services'}).json()
    if api_response:

        # Sort the services for data tables
        data = {'data': []}
        for service in api_response:
            if service["Name"] != "kubernetes":
                service['Cluster IP'] = service['Info']['clusterIP']
                service['Node Port'] = service['Info']['ports'][0]['nodePort']
                service['Port'] = service['Info']['ports'][0]['port']
                time_stamp = parser.parse(service["Created"])
                time_stamp = time_stamp.replace(tzinfo=None)
                age = datetime.now() - time_stamp
                age = str(age).split(":")
                age = age[0] + "h " + age[1] + "m"
                service['Age'] = str(age)
                service['Protocol'] = service['Info']['ports'][0]['protocol']
                service['Target Port'] = service['Info']['ports'][0]['targetPort']
                service['Type'] = service['Info']['type']
                data['data'].append(service)
        return jsonify({"services": data, "code": 200})
    else:
        return jsonify({"message": "No Services Found", "code": 202})


@app.route('/deployments')
@login_required
def deployments():
    json_deployments = requests.get('http://{}'.format(kubeApiIpAddress),
                                    data={'method': 'get_deployments'}).json()
    if json_deployments:
        filtered_deployments = {'data': []}
        for deployment in json_deployments:
            iterator = 0

            # Filter deployments for data tables
            filtered_deployment = {
                'Name': deployment["Name"]
            }
            time_stamp = parser.parse(deployment["Created"])
            time_stamp = time_stamp.replace(tzinfo=None)
            age = datetime.now() - time_stamp
            age = str(age).split(":")
            age = age[0] + "h " + age[1] + "m"
            filtered_deployment['Age'] = str(age)
            filtered_deployment['Type'] = deployment['Status']['conditions'][iterator]['type']
            filtered_deployment['Replicas'] = deployment['Status']['replicas']
            filtered_deployment['Last Update Time'] = deployment['Status']['conditions'][iterator][
                'lastUpdateTime']
            filtered_deployment['Reason'] = deployment['Status']['conditions'][iterator]['reason']
            filtered_deployment['Type'] = deployment['Status']['conditions'][iterator]['type']
            if deployment['Status']['conditions'][iterator]['status'] == "True":
                filtered_deployment['Status'] = """  <label class="">
                                                            <span style="color:green" class="fa fa-check-circle fa-2x">
                                                                </span>
                                                            </label>"""
            else:
                filtered_deployment['Status'] = """  <label class="">
                                                            <span style="color:red" class="fa fa-times-circle fa-2x">
                                                                </span>
                                                            </label>"""
            filtered_deployments['data'].append(filtered_deployment)
        return jsonify({"deployments": filtered_deployments, "code": 200})
    else:
        return jsonify({"message": "No deployments Found", "code": 202})


# Clear session and logout user
@app.route('/log_out')
@login_required
def logout():
    logout_user()
    session.clear()
    return redirect(url_for("home"))


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


if __name__ == "__main__":
    app.run(port=5001, host="0.0.0.0", debug=True)
