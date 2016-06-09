import json
import itertools

from django.conf import settings
from django.contrib import messages
from django.core.cache import cache
from django.forms import MediaDefiningClass
from django.http.request import QueryDict
from django.utils.safestring import mark_safe
from django.utils.text import re_camel_case
from django.utils.translation import gettext, gettext_lazy as _
import requests

from core.views import DashboardView


class DashboardModule(metaclass=MediaDefiningClass):
    template = 'core/dashboard/module.html'
    column_count = 1
    html_classes = ''
    title = _('Dashboard')
    show_stand_out = False
    enabled = True
    priority = 0
    cookie_key = None

    def __init__(self, dashboard_view):
        self.dashboard_view = dashboard_view
        self.cookie_data = QueryDict(dashboard_view.cookie_data.get(self.cookie_key)) or None

    @property
    def html_id(self):
        html_id = re_camel_case.sub(r'_\1', self.__class__.__name__)
        html_id = html_id.strip().lower()
        return 'id' + html_id


@DashboardView.register_dashboard
class ExternalDashboards(DashboardModule):
    template = 'core/dashboard/external-dashboards.html'
    column_count = 2
    title = _('External dashboards and logs')
    apps = [
        'api', 'cashbook', 'bank-admin', 'noms-ops',
        'transaction-uploader', 'send-money',
    ]
    grafana_host = None
    kibana_host = None
    sentry_url = None
    sensu_url = None
    kibana_params = '_g=(time:(from:now-24h,mode:quick,to:now))'  # last 24 hours

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        if settings.ENVIRONMENT == 'test':
            self.grafana_host = 'grafana-staging.service.dsd.io'
            self.kibana_host = 'kibana-staging.service.dsd.io'
            self.sentry_url = 'https://sentry.service.dsd.io/mojds/mtp-test-%(app)s/'
            self.sensu_url = 'https://sensu-staging.service.dsd.io/#/checks?q=moneytoprisoners'
        elif settings.ENVIRONMENT == 'prod':
            self.grafana_host = 'grafana.service.dsd.io'
            self.kibana_host = 'kibana.service.dsd.io'
            self.sentry_url = 'https://sentry.service.dsd.io/mojds/mtp-prod-%(app)s/'
            self.sensu_url = 'https://sensu.service.dsd.io/#/checks?q=moneytoprisoners'

        self.enabled = self.kibana_host or self.grafana_host or self.sentry_url or self.sensu_url

    def get_table(self):
        table = []
        if self.kibana_host:
            table.append({
                'title': _('Application dashboard'),
                'links': [
                    {
                        'title': _('All apps'),
                        'url': 'https://%s/#/dashboard/MTP?%s' % (self.kibana_host, self.kibana_params)
                    }
                ],
            })
            table.append({
                'title': _('Application logs'),
                'links': self.make_app_links('https://%(kibana_host)s/#/discover/MTP-%(app)s'
                                             '?%(kibana_params)s'),
            })
        if self.sentry_url:
            table.append({
                'title': _('Sentry error monitors'),
                'links': self.make_app_links(self.sentry_url),
            })
        if self.sensu_url:
            table.append({
                'title': _('Sensu monitoring checks'),
                'links': [
                    {
                        'title': _('All apps'),
                        'url': self.sensu_url
                    }
                ]
            })
        if self.grafana_host:
            table.append({
                'title': _('Host machine dashboards'),
                'links': self.make_app_links('https://%(grafana_host)s/dashboard/db/mtp'
                                             '?var-project=moneytoprisoners-%(app)s'),
            })
        return table

    def make_app_links(self, link_template):
        return [
            {
                'title': app,
                'url': link_template % {
                    'grafana_host': self.grafana_host,
                    'kibana_host': self.kibana_host,
                    'kibana_params': self.kibana_params,
                    'app': app,
                }
            }
            for app in self.apps
        ]


@DashboardView.register_dashboard
class SatisfactionDashboard(DashboardModule):
    template = 'core/dashboard/satisfaction-results.html'
    column_count = 1
    title = _('User satisfaction')
    cache_lifetime = 60 * 60  # 1 hour
    survey_id = '2527768'
    survey_url = 'http://data.surveygizmo.com/r/413845_57330cc99681a7.27709426'
    questions = [
        # NB: all questions must have 6 options, ending with "Not applicable"
        {'id': '13', 'title': _('Easy'), 'reverse': False},
        {'id': '14', 'title': _('Unreasonably slow'), 'reverse': True},
        {'id': '15', 'title': _('Cheap'), 'reverse': False},
        {'id': '70', 'title': _('Rating'), 'reverse': False},
    ]
    weightings = [-2, -1, 0, 1, 2, 0]

    class Media:
        css = {
            'all': ('core/css/satisfaction-results.css',)
        }
        js = (
            'https://www.gstatic.com/charts/loader.js',
            'core/js/google-charts.js',
            'core/js/satisfaction-results.js',
        )

    def __init__(self, dashboard_view):
        super().__init__(dashboard_view)
        self.enabled = bool(settings.SURVEY_GIZMO_API_KEY)
        self.cache_key = 'satisfaction_results'

        self.max_response_count = 0

    @classmethod
    def get_modal_responses(cls, responses):
        responses = sorted(responses, key=lambda response: (response['count'], response['.index']), reverse=True)
        modal_responses = [(responses[0]['.index'], responses[0]['count'])]
        last_index = 0
        for index in range(1, len(cls.weightings)):
            if responses[last_index]['count'] == responses[index]['count']:
                modal_responses.append((responses[index]['.index'], responses[index]['count']))
        return modal_responses

    def get_satisfaction_results(self):
        response = cache.get(self.cache_key)
        if not response:
            url_prefix = 'https://restapi.surveygizmo.com/v4/survey/%s' % self.survey_id

            response = []
            for question in self.questions:
                question_id = question['id']
                question_response = requests.get('%(url_prefix)s/surveyquestion/%(question)s' % {
                    'url_prefix': url_prefix,
                    'question': question_id,
                }, params={
                    'api_token': settings.SURVEY_GIZMO_API_KEY,
                }).json()['data']
                statistics_response = requests.get('%(url_prefix)s/surveystatistic' % {
                    'url_prefix': url_prefix,
                }, params={
                    'api_token': settings.SURVEY_GIZMO_API_KEY,
                    'surveyquestion': question_id,
                }).json()['data']
                response.append({
                    'id': question_id,
                    'question': question_response,
                    'statistics': statistics_response,
                    'reverse': question['reverse'],
                })

            cache.set(self.cache_key, response, timeout=self.cache_lifetime)

        return response

    @property
    def columns(self):
        return [
            {'type': 'string', 'label': gettext('Response'), 'role': 'domain'},
            {'type': 'number', 'label': gettext('Money by post'), 'role': 'data'},
            {'type': 'string', 'role': 'style'},
            {'type': 'string', 'role': 'annotation'},
            {'type': 'number', 'label': gettext('MTP service'), 'role': 'data'},
            {'type': 'string', 'role': 'style'},
            {'type': 'string', 'role': 'annotation'},
        ]

    def make_chart_rows(self, question, statistics, reverse=False):
        options = question['options']
        if len(options) != len(self.weightings):
            messages.error(
                self.dashboard_view.request,
                _('Satisfaction survey question %s has unexpected number of options' % question['id'])
            )
            return []
        if options[-1]['value'] != 'Not applicable':
            messages.error(
                self.dashboard_view.request,
                _('Satisfaction survey question %s does not have "Not applicable" option' % question['id'])
            )
            return
        if reverse:
            options = itertools.chain(reversed(options[:-1]), [options[-1]])

        # connect responses with questions
        self.max_response_count = 0
        mean_response = 0
        rows = []
        row_index = dict()
        for index, option in enumerate(options):
            title = option['value']
            rows.append([title, 0, '', None, 0, '', None])
            row_index[title] = index
        for response in statistics['Breakdown']:
            index = row_index[response['label']]
            response['.index'] = index
            response_count = int(response['count'])
            response['count'] = response_count
            rows[index][1] = response_count
            if response_count > self.max_response_count:
                self.max_response_count = response_count
            mean_response += response_count * self.weightings[index]
        mean_response /= rows[0][1] + rows[1][1] + rows[3][1] + rows[4][1]

        # annotate modal responses
        modal_responses = self.get_modal_responses(statistics['Breakdown'])
        for modal_response_index, modal_response_count in modal_responses:
            rows[modal_response_index][3] = str(modal_response_count)

        return rows, mean_response

    def get_chart_data(self):
        responses = self.get_satisfaction_results()
        questions = []
        for source_data in responses:
            question = source_data['question']
            statistics = source_data['statistics']
            reverse = source_data['reverse']
            rows, mean_response = self.make_chart_rows(question, statistics, reverse)
            questions.append({
                'id': source_data['id'],
                'rows': rows,
                'mean': mean_response,
            })

        return mark_safe(json.dumps({
            'columns': self.columns,
            'questions': questions,
            'max': self.max_response_count,
        }))
