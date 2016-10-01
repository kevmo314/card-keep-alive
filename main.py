from flask import Flask, redirect, render_template, request
from google.appengine.api import mail, users
from google.appengine.ext import ndb
import datetime
import stripe
import threading

stripe.api_key = 'sk_live_4wQzFgbzMf4LhkYVhHzMlYW4'

app = Flask(__name__)

class Customer(ndb.Model):
    email = ndb.StringProperty()
    stripe_id = ndb.StringProperty()
    
    @classmethod
    @ndb.transactional
    def find(cls, user):
        key = ndb.Key(cls, user.user_id())
        ent = key.get()
        if ent is not None:
            return ent
        ent = cls()
        ent.key = key
        ent.email = user.email()
        ent.stripe_id = stripe.Customer.create(email=user.email()).id
        ent.put()
        return ent

@app.template_filter('get_date')
def get_date(timestamp):
    return datetime.datetime.fromtimestamp(timestamp).strftime('%m/%d')

def get_all_subscriptions(customer_id, starting_after=None):
    subscriptions = stripe.Subscription.all(customer=customer_id,
                                             starting_after=starting_after)
    data = subscriptions['data']
    if subscriptions['has_more']:
        data += get_all_subscriptions(customer_id, subscriptions['data'][-1])
    return data
    
@app.route('/')
def main():
    return render_template('home.html')

@app.route('/login', methods=['GET'])
def login():
    return redirect(users.create_login_url('/subscriptions'))
    
@app.route('/subscriptions/<id>', methods=['GET'])
def cancel(id):
    customer = Customer.find(users.get_current_user())
    subscription = stripe.Subscription.retrieve('sub_%s' % id)
    if subscription and subscription.customer != customer.stripe_id:
        # Something went wrong, the id's don't match
        return redirect('/subscriptions', code=403)
    if subscription:
        subscription.delete()
    return redirect('/subscriptions', code=302)
    
@app.route('/subscriptions', methods=['POST'])
def create():
    """Create a subscription then redirect to the index page."""
    customer = Customer.find(users.get_current_user())
    try:
        subscription = stripe.Subscription.create(customer=customer.stripe_id,
                                                  plan="50c/qtr",
                                                  source=request.form.get('token'),
                                                  metadata={'description': request.form.get('description')})
        customer = Customer.find(users.get_current_user())
        return render_template('subscriptions.html',
                               active=subscription['id'],
                               subscriptions=get_all_subscriptions(customer.stripe_id),
                               email=customer.email,
                               stripe_id=customer.stripe_id[4:])
    except:
        return redirect('/subscriptions', code=302)

@app.route('/subscriptions', methods=['GET'])
def index():
    customer = Customer.find(users.get_current_user())
    return render_template('subscriptions.html',
                           active=None,
                           subscriptions=get_all_subscriptions(customer.stripe_id),
                           email=customer.email,
                           stripe_id=customer.stripe_id[4:])
