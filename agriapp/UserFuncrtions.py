from django.contrib.auth.models import User
import datetime

import os
# from twilio.rest import Client
from . models import ColumnName, ColumnData


def create_user(username, email):
    x = datetime.datetime.now()
    current_year = x.year
    current_year = str(current_year)
    password = username + 'P' + current_year + '_$'
    User.objects.create_user(username, email, password)

def send_message(to, body):
    # Find your Account SID and Auth Token at twilio.com/console
    # and set the environment variables. See http://twil.io/secure
    account_sid = "AC1760a99b2ff30278ae4f925a71eb8d30"
    auth_token = "3abe370f1ab25cfaeeb6047bb5d8d235"
    client = Client(account_sid, auth_token)

    message = client.messages \
                    .create(
                        body=body,
                        from_='+14094032838',
                        to=f"+919986168736"
                    )

def change_password(username, password):
    user = User.objects.get(username=username)
    user.set_password(password)
    user.save()

def get_all_dynamic_fields():
    return ColumnName.objects.all()

def get_all_dynamic_field_value(api, field):
    return ColumnData.objects.filter(api=api, field=field).first()