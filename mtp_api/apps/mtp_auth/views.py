import collections
import datetime
import logging
from urllib.parse import urlsplit, urlunsplit, urlencode, parse_qs

from django.contrib.auth import password_validation, get_user_model
from django.contrib.auth.password_validation import get_default_password_validators
from django.core.exceptions import NON_FIELD_ERRORS
from django.db import connection, models
from django.db.transaction import atomic
from django.forms import ValidationError
from django.http import Http404
from django.utils.decorators import method_decorator
from django.utils.timezone import now
from django.utils.translation import gettext, gettext_lazy as _
from django.views.decorators.debug import sensitive_post_parameters, sensitive_variables
from django.views.generic import TemplateView
from mtp_common.tasks import send_email
from oauth2_provider.models import Application
from rest_framework import viewsets, generics, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from core.views import AdminViewMixin
from mtp_auth.forms import LoginStatsForm
from mtp_auth.models import FailedLoginAttempt, PrisonUserMapping, Role, PasswordChangeRequest
from mtp_auth.permissions import UserPermissions, AnyAdminClientIDPermissions
from mtp_auth.serializers import (
    RoleSerializer, UserSerializer, ChangePasswordSerializer, ResetPasswordSerializer,
    ChangePasswordWithCodeSerializer
)
from prison.models import Prison

User = get_user_model()

logger = logging.getLogger('mtp')


class RoleViewSet(viewsets.mixins.ListModelMixin, viewsets.GenericViewSet):
    queryset = Role.objects.all()
    permission_classes = (IsAuthenticated,)
    serializer_class = RoleSerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        if 'managed' in self.request.query_params:
            user = self.request.user
            managed_roles = Role.objects.get_managed_roles_for_user(user)
            queryset = queryset.filter(pk__in=set(role.pk for role in managed_roles))
        return queryset


class UserViewSet(viewsets.ModelViewSet):
    lookup_field = 'username__iexact'
    lookup_url_kwarg = 'username'
    lookup_value_regex = '[^/]+'

    queryset = User.objects.none()
    permission_classes = (IsAuthenticated, UserPermissions)
    serializer_class = UserSerializer

    def get_queryset(self):
        """
        Set of users for user account management AND looking up details of self.
        Set is determined by matching set of prisons if some exist OR by key group as determined by Role models.
        If a user falls into multiple roles, they can only edit themselves.
        """
        user = self.request.user
        queryset = User.objects.filter(is_superuser=user.is_superuser).order_by('username')

        prisons = list(PrisonUserMapping.objects.get_prison_set_for_user(user).values_list('pk', flat=True))
        if prisons:
            for prison in prisons:
                queryset = queryset.filter(prisonusermapping__prisons=prison)
            return queryset

        key_groups = set(Role.objects.values_list('key_group', flat=True))
        user_groups = set(user.groups.values_list('pk', flat=True))
        user_key_groups = list(key_groups.intersection(user_groups))
        if len(user_key_groups) == 1:
            queryset = queryset.filter(prisonusermapping__isnull=True)
            return queryset.filter(models.Q(groups=user_key_groups[0]) | models.Q(pk=user.pk)).distinct()

        return User.objects.filter(pk=user.pk)

    def get_object(self):
        """
        Make sure that you can only access your own user data,
        unless the user is a UserAdmin.
        """
        lookup_url_kwarg = self.lookup_url_kwarg or self.lookup_field
        lookup = self.kwargs.get(lookup_url_kwarg, None)

        if (lookup.lower() == self.request.user.username.lower() or
                self.request.user.has_perm('auth.change_user')):
            return super().get_object()
        else:
            raise Http404()

    def perform_create_or_update(self, serializer):
        kwargs = {
            key: self.request.data[key]
            for key in ('user_admin', 'is_locked_out', 'role')
            if key in self.request.data
        }
        serializer.save(**kwargs)

    def perform_create(self, serializer):
        self.perform_create_or_update(serializer)

    def perform_update(self, serializer):
        self.perform_create_or_update(serializer)

    def destroy(self, request, *args, **kwargs):
        user = self.get_object()
        if user != request.user:
            self.perform_destroy(user)
            return Response(status=status.HTTP_204_NO_CONTENT)
        else:
            return Response(
                status=status.HTTP_400_BAD_REQUEST,
                data={
                    '__all__': [_('You cannot disable yourself')]
                },
            )

    def perform_destroy(self, instance):
        instance.is_active = False
        instance.save()


@method_decorator(sensitive_post_parameters('old_password', 'new_password'), name='dispatch')
class ChangePasswordView(generics.GenericAPIView):
    permission_classes = (IsAuthenticated, AnyAdminClientIDPermissions)
    serializer_class = ChangePasswordSerializer

    @atomic
    @method_decorator(sensitive_variables('old_password', 'new_password'))
    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid():
            old_password = serializer.validated_data['old_password']
            new_password = serializer.validated_data['new_password']

            try:
                if not FailedLoginAttempt.objects.is_locked_out(
                        request.user, request.auth.application):
                    if request.user.check_password(old_password):
                        FailedLoginAttempt.objects.delete_failed_attempts(
                            request.user, request.auth.application)
                        password_validation.validate_password(new_password, request.user)
                        request.user.set_password(new_password)
                        request.user.save()
                        return Response(status=status.HTTP_204_NO_CONTENT)
                    else:
                        FailedLoginAttempt.objects.add_failed_attempt(
                            request.user, request.auth.application)
                errors = {'old_password': [_('You’ve entered an incorrect password')]}
            except ValidationError as e:
                errors = {'new_password': e.error_list}
        else:
            errors = serializer.errors
        return Response(
            data={'errors': errors},
            status=status.HTTP_400_BAD_REQUEST,
        )


@method_decorator(sensitive_post_parameters('new_password'), name='dispatch')
class ChangePasswordWithCodeView(generics.GenericAPIView):
    permission_classes = ()
    serializer_class = ChangePasswordWithCodeSerializer

    @atomic
    @method_decorator(sensitive_variables('new_password'))
    def post(self, request, code):
        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid():
            new_password = serializer.validated_data['new_password']

            try:
                user = PasswordChangeRequest.objects.get(code=code).user
                password_validation.validate_password(new_password, user)
                user.set_password(new_password)
                user.save()
                return Response(status=status.HTTP_204_NO_CONTENT)
            except PasswordChangeRequest.DoesNotExist:
                return Response(status=status.HTTP_404_NOT_FOUND)
            except ValidationError as e:
                errors = {'new_password': e.error_list}
        else:
            errors = serializer.errors
        return Response(
            data={'errors': errors},
            status=status.HTTP_400_BAD_REQUEST,
        )


class ResetPasswordView(generics.GenericAPIView):
    permission_classes = ()
    serializer_class = ResetPasswordSerializer
    immutable_users = ['transaction-uploader', 'send-money']

    error_messages = {
        'generic': _('There has been a system error. Please try again later'),
        'not_found': _('Username doesn’t match any user account'),
        'locked_out': _('Your account is locked, '
                        'please contact the person who set it up'),
        'no_email': _('We don’t have your email address, '
                      'please contact the person who set up the account'),
        'multiple_found': _('That email address matches multiple user accounts, '
                            'please enter your unique username'),
    }

    @classmethod
    def generate_new_password(cls):
        validators = get_default_password_validators()
        for __ in range(5):
            password = User.objects.make_random_password(length=10)
            try:
                for validator in validators:
                    validator.validate(password)
            except ValidationError:
                continue
            return password

    def failure_response(self, errors, field=NON_FIELD_ERRORS):
        if isinstance(errors, str):
            errors = {
                field: [self.error_messages[errors]]
            }
        return Response(
            data={'errors': errors},
            status=status.HTTP_400_BAD_REQUEST,
        )

    @atomic
    @method_decorator(sensitive_variables('password'))
    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid():
            user_identifier = serializer.validated_data['username']
            try:
                user = User.objects.get_by_natural_key(user_identifier)
            except User.DoesNotExist:
                users = User.objects.filter(email__iexact=user_identifier)
                user_count = users.count()
                if user_count == 0:
                    return self.failure_response('not_found', field='username')
                elif user_count > 1:
                    return self.failure_response('multiple_found', field='username')
                user = users[0]
            if user.username in self.immutable_users:
                return self.failure_response('not_found', field='username')
            if user.is_locked_out:
                return self.failure_response('locked_out', field='username')
            if not user.email:
                return self.failure_response('no_email', field='username')

            if serializer.validated_data.get('create_password'):
                change_request, _ = PasswordChangeRequest.objects.get_or_create(user=user)
                change_password_url = urlsplit(
                    serializer.validated_data['create_password']['password_change_url']
                )
                query = parse_qs(change_password_url.query)
                query.update({
                    serializer.validated_data['create_password']['reset_code_param']: str(change_request.code)
                })
                change_password_url = list(change_password_url)
                change_password_url[3] = urlencode(query)
                change_password_url = urlunsplit(change_password_url)
                send_email(
                    user.email, 'mtp_auth/create_new_password.txt',
                    gettext('Create a new Prisoner Money password'),
                    context={
                        'change_password_url': change_password_url,
                    },
                    html_template='mtp_auth/create_new_password.html'
                )
                return Response(status=status.HTTP_204_NO_CONTENT)
            else:
                password = self.generate_new_password()
                if not password:
                    logger.error('Password could not be generated; have validators changed?')
                    return self.failure_response('generic')

                user.set_password(password)
                user.save()

                send_email(
                    user.email, 'mtp_auth/reset_password.txt',
                    gettext('Your new Prisoner Money password'),
                    context={'username': user.username, 'password': password},
                    html_template='mtp_auth/reset_password.html'
                )

                return Response(status=status.HTTP_204_NO_CONTENT)
        else:
            return self.failure_response(serializer.errors)


class LoginStatsView(AdminViewMixin, TemplateView):
    title = _('Login stats')
    template_name = 'admin/mtp_auth/login-stats.html'
    required_permissions = ['transaction.view_dashboard']
    excluded_nomis_ids = {'ZCH'}

    def get_context_data(self, **kwargs):
        context_data = super().get_context_data(**kwargs)
        form = LoginStatsForm(data=self.request.GET.dict())
        if not form.is_valid():
            form = LoginStatsForm(data={})
            assert form.is_valid(), 'Empty form should be valid'

        context_data['form'] = form
        context_data['prisons'] = self.get_prisons()
        months = list(self.get_months())
        current_month_progress = months.pop(0)
        context_data['months'] = months
        context_data['login_counts'] = self.get_login_counts(
            form.cleaned_data['application'],
            current_month_progress,
            months,
        )
        return context_data

    def get_prisons(self):
        prisons = list(Prison.objects.exclude(
            nomis_id__in=self.excluded_nomis_ids
        ).order_by('nomis_id').values_list('nomis_id', 'name'))
        prisons.append((None, _('Prison not specified')))
        return prisons

    def get_months(self):
        today = now()
        month_start = today.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        month = month_start.month + 1
        if month > 12:
            next_month = month_start.replace(year=month_start.year + 1, month=1)
        else:
            next_month = month_start.replace(month=month)
        month_end = next_month - datetime.timedelta(days=1)
        yield today.day / month_end.day

        for _ in range(4):  # noqa: F402
            yield month_start
            month = month_start.month - 1
            if month < 1:
                month_start = month_start.replace(year=month_start.year - 1, month=12)
            else:
                month_start = month_start.replace(month=month)

    def get_login_counts(self, application, current_month_progress, months):
        login_count_query = '''
            WITH users AS (
              SELECT user_id, COUNT(*) AS login_count
              FROM mtp_auth_login
              WHERE application_id = %(application_id)s AND date_trunc('month', created) = %(month)s
              GROUP BY user_id
            )
            SELECT prison_id, SUM(login_count)::integer AS login_count
            FROM users
            LEFT OUTER JOIN mtp_auth_prisonusermapping ON mtp_auth_prisonusermapping.user_id = users.user_id
            LEFT OUTER JOIN mtp_auth_prisonusermapping_prisons ON
              mtp_auth_prisonusermapping_prisons.prisonusermapping_id = mtp_auth_prisonusermapping.id
            GROUP BY prison_id
        '''
        try:
            application = Application.objects.get(client_id=application)
        except Application.DoesNotExist:
            return
        login_counts = collections.defaultdict(int)
        for i, month in enumerate(months):
            scale = current_month_progress if i == 0 else 1
            with connection.cursor() as cursor:
                cursor.execute(login_count_query, {
                    'application_id': application.id,
                    'month': month.date(),
                })
                for prison_id, login_count in cursor.fetchall():
                    login_counts[(prison_id, month)] = round(login_count / scale)
        return login_counts
