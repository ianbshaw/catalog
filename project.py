from flask import Flask, render_template, request, redirect, url_for, flash
from flask import session as login_session, jsonify, make_response
from oauth2client.client import flow_from_clientsecrets
from oauth2client.client import FlowExchangeError
import httplib2
import requests
import json
import random
import string
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from database_setup import Base, Restaurant, MenuItem, User
from functools import wraps


""" loads client secrets from local file """
CLIENT_ID = json.loads(
    open('client_secrets.json', 'r').read())['web']['client_id']


""" create flask object and database session """
app = Flask(__name__)

engine = create_engine('sqlite:///restaurantmenuuserspython.db')
Base.metadata.bind = engine

DBSession = sessionmaker(bind=engine)
session = DBSession()


""" helper functions to get user info """


def createUser(login_session):
    newUser = User(name=login_session['username'], email=login_session[
                   'email'], picture=login_session['picture'])
    session.add(newUser)
    session.commit()
    user = session.query(User).filter_by(email=login_session['email']).one()
    return user.id


def getUserInfo(user_id):
    user = session.query(User).filter_by(id=user_id).one()
    return user


def getUserID(email):
    try:
        user = session.query(User).filter_by(email=email).one()
        return user.id
    except:
        return None


def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'username' not in login_session:
            return redirect('/login')
        return f(*args, **kwargs)
    return decorated_function


""" routes to the web pages to view, add, edit, and delete menus/items """


@app.route('/')
@app.route('/restaurants/')
def restaurantMain():
    restaurants = session.query(Restaurant).all()
    if 'username' in login_session:
        return render_template('mainmenu.html', restaurants=restaurants,
                               login_session=login_session)
    else:
        return render_template('publicrestaurants.html',
                               restaurants=restaurants)


@app.route('/restaurants/new/', methods=['GET', 'POST'])
@login_required
def newRestaurant():
    if request.method == 'POST':
        newRestaurant = Restaurant(name=request.form['name'],
                                   user_id=login_session['user_id'])
        session.add(newRestaurant)
        session.commit()
        flash("New Restaurant Created!!!")
        return redirect(url_for('restaurantMain'))
    else:
        return render_template('newrestaurant.html')


@app.route('/restaurants/<int:restaurant_id>/edit/', methods=['GET', 'POST'])
@login_required
def editRestaurant(restaurant_id):
    restaurant = session.query(Restaurant).filter_by(id=restaurant_id).one()
    if restaurant.user_id == login_session['user_id']:
        if request.method == 'POST':
            restaurant.name = request.form['name']
            session.commit()
            flash("Restaurant Edited Successfully!!")
            return redirect(url_for('restaurantMain'))
        else:
            return render_template('editrestaurant.html', r=restaurant)
    else:
        return redirect(url_for('restaurantMain'))


@app.route('/restaurants/<int:restaurant_id>/delete/', methods=['GET', 'POST'])
@login_required
def deleteRestaurant(restaurant_id):
    restaurant = session.query(Restaurant).filter_by(id=restaurant_id).one()
    if restaurant.user_id == login_session['user_id']:
        if request.method == 'POST':
            session.delete(restaurant)
            session.commit()
            flash("Restaurant Deleted Successfully!!")
            return redirect(url_for('restaurantMain'))
        else:
            return render_template('deleterestaurant.html', r=restaurant)
    else:
        return redirect(url_for('restaurantMain'))


@app.route('/restaurants/<int:restaurant_id>/')
def restaurantMenu(restaurant_id):
    restaurant = session.query(Restaurant).filter_by(id=restaurant_id).one()
    items = session.query(MenuItem).filter_by(restaurant_id=restaurant.id)
    if 'username' in login_session:
        return render_template('menu.html', restaurant=restaurant, items=items,
                               login_session=login_session)
    else:
        return render_template('publicmenu.html', restaurant=restaurant,
                               items=items)


@app.route('/restaurants/<int:restaurant_id>/new/', methods=['GET', 'POST'])
@login_required
def newMenuItem(restaurant_id):
    if request.method == 'POST':
        newItem = MenuItem(
            name=request.form['name'], restaurant_id=restaurant_id,
            user_id=login_session['user_id'])
        session.add(newItem)
        session.commit()
        flash("New Menu Item Created!!!")
        return redirect(url_for('restaurantMenu', restaurant_id=restaurant_id))
    else:
        return render_template('newmenuitem.html', restaurant_id=restaurant_id)


@app.route('/restaurants/<int:restaurant_id>/<int:menu_id>/edit/',
           methods=['GET', 'POST'])
@login_required
def editMenuItem(restaurant_id, menu_id):
    item = session.query(MenuItem).filter_by(id=menu_id).one()
    if item.user_id == login_session['user_id']:
        if request.method == 'POST':
            item.name = request.form['name']
            session.commit()
            flash("Menu Item Edited Successfully!!")
            return redirect(url_for('restaurantMenu',
                                    restaurant_id=restaurant_id))
        else:
            return render_template('editmenuitem.html', menu_id=menu_id,
                                   restaurant_id=restaurant_id, item=item)
    else:
        return redirect(url_for('restaurantMenu', restaurant_id=restaurant_id))


@app.route('/restaurants/<int:restaurant_id>/<int:menu_id>/delete/',
           methods=['GET', 'POST'])
@login_required
def deleteMenuItem(restaurant_id, menu_id):
    item = session.query(MenuItem).filter_by(id=menu_id).one()
    if item.user_id == login_session['user_id']:
        if request.method == 'POST':
            session.delete(item)
            session.commit()
            flash("Menu Item Deleted Successfully!!")
            return redirect(url_for('restaurantMenu',
                                    restaurant_id=restaurant_id))
        else:
            return render_template('deletemenuitem.html', menu_id=menu_id,
                                   restaurant_id=restaurant_id, item=item)
    else:
        return redirect(url_for('restaurantMenu', restaurant_id=restaurant_id))


""" JSON endpoints for menu list, individual menus, menu items """


@app.route('/restaurants/JSON')
def restaurantJSON():
    restaurants = session.query(Restaurant).all()
    return jsonify(Restaurants=[r.serialize for r in restaurants])


@app.route('/restaurants/<int:restaurant_id>/JSON')
def restaurantMenuJSON(restaurant_id):
    restaurant = session.query(Restaurant).filter_by(id=restaurant_id).one()
    items = session.query(MenuItem).filter_by(restaurant_id=restaurant.id)
    return jsonify(MenuItems=[i.serialize for i in items])


@app.route('/restaurants/<int:restaurant_id>/<int:menu_id>/JSON')
def restaurantMenuItemJSON(restaurant_id, menu_id):
    item = session.query(MenuItem).filter_by(id=menu_id).one()
    return jsonify(MenuItems=[item.serialize])


""" functions to handle user login """


@app.route('/login')
def showLogin():
    state = ''.join(random.choice(string.ascii_uppercase + string.digits)
                    for x in xrange(32))
    login_session['state'] = state
    # return "The current session state is %s" % login_session['state']
    return render_template('login.html', STATE=state)


@app.route('/gconnect', methods=['POST'])
def gconnect():
    # Validate state token
    if request.args.get('state') != login_session['state']:
        response = make_response(json.dumps('Invalid state parameter.'), 401)
        response.headers['Content-Type'] = 'application/json'
        return response
    # Obtain authorization code
    code = request.data

    try:
        # Upgrade the authorization code into a credentials object
        oauth_flow = flow_from_clientsecrets('client_secrets.json', scope='')
        oauth_flow.redirect_uri = 'postmessage'
        credentials = oauth_flow.step2_exchange(code)
    except FlowExchangeError:
        response = make_response(
            json.dumps('Failed to upgrade the authorization code.'), 401)
        response.headers['Content-Type'] = 'application/json'
        return response

    # Check that the access token is valid.
    access_token = credentials.access_token
    url = ('https://www.googleapis.com/oauth2/v1/tokeninfo?access_token=%s'
           % access_token)
    h = httplib2.Http()
    result = json.loads(h.request(url, 'GET')[1])
    # If there was an error in the access token info, abort.
    if result.get('error') is not None:
        response = make_response(json.dumps(result.get('error')), 500)
        response.headers['Content-Type'] = 'application/json'
        return response

    # Verify that the access token is used for the intended user.
    gplus_id = credentials.id_token['sub']
    if result['user_id'] != gplus_id:
        response = make_response(
            json.dumps("Token's user ID doesn't match given user ID."), 401)
        response.headers['Content-Type'] = 'application/json'
        return response

    # Verify that the access token is valid for this app.
    if result['issued_to'] != CLIENT_ID:
        response = make_response(
            json.dumps("Token's client ID does not match app's."), 401)
        print "Token's client ID does not match app's."
        response.headers['Content-Type'] = 'application/json'
        return response

    stored_access_token = login_session.get('access_token')
    stored_gplus_id = login_session.get('gplus_id')
    if stored_access_token is not None and gplus_id == stored_gplus_id:
        response = make_response(json.dumps('Current user is already connected.'),
                                 200)
        response.headers['Content-Type'] = 'application/json'
        return response

    # Store the access token in the session for later use.
    login_session['access_token'] = credentials.access_token
    login_session['gplus_id'] = gplus_id

    # Get user info
    userinfo_url = "https://www.googleapis.com/oauth2/v1/userinfo"
    params = {'access_token': credentials.access_token, 'alt': 'json'}
    answer = requests.get(userinfo_url, params=params)

    data = answer.json()

    login_session['username'] = data['name']
    login_session['picture'] = data['picture']
    login_session['email'] = data['email']

    user_id = getUserID(login_session['email'])
    if not user_id:
        user_id = createUser(login_session)

    login_session['user_id'] = user_id

    output = ''
    output += '<h1>Welcome, '
    output += login_session['username']
    output += '!</h1>'
    output += '<img src="'
    output += login_session['picture']
    output += ' " style = "width: 300px; height: 300px;border-radius: 150px;-webkit-border-radius: 150px;-moz-border-radius: 150px;"> '
    flash("you are now logged in as %s" % login_session['username'])
    print "done!"
    return output


@app.route('/gdisconnect')
def gdisconnect():
    access_token = login_session['access_token']
    print 'In gdisconnect access token is %s', access_token
    print 'User name is: '
    print login_session['username']
    if access_token is None:
        print 'Access Token is None'
        response = make_response(json.dumps('Current user not connected.'),
                                 401)
        response.headers['Content-Type'] = 'application/json'
        return response
    url = 'https://accounts.google.com/o/oauth2/revoke?token=%s' % login_session['access_token']
    h = httplib2.Http()
    result = h.request(url, 'GET')[0]
    print 'result is '
    print result
    if result['status'] == '200':
        del login_session['access_token']
        del login_session['gplus_id']
        del login_session['username']
        del login_session['email']
        del login_session['picture']
        response = make_response(json.dumps('Successfully disconnected.'), 200)
        response.headers['Content-Type'] = 'application/json'
        return redirect(url_for('restaurantMain'))
    else:
        response = make_response(json.dumps('Failed to revoke token for ' +
                                 'given user.', 400))
        response.headers['Content-Type'] = 'application/json'
        return response


if __name__ == '__main__':
    app.secret_key = 'muaddib'
    app.debug = True
    app.run(host='0.0.0.0', port=5000)
