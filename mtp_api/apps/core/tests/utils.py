from django.contrib.auth.models import User
from mtp_auth.tests.mommy_recipes import create_prison_user_mapping
from oauth2_provider.models import Application
from prison.models import Prison


def make_test_users(users_per_prison=1):
    users = []
    for prison in Prison.objects.all():
        for index in range(users_per_prison):
            pu = create_prison_user_mapping(prison)
            users.append(pu.user)
    return users


def make_test_oauth_applications():
    Application.objects.get_or_create(
        client_id='cashbook',
        client_type='confidential',
        authorization_grant_type='password',
        client_secret='cashbook',
        name='cashbook',
        user=User.objects.first())
