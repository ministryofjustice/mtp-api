import datetime
from django.shortcuts import render
from django.http import HttpResponse
from transaction.models import Transaction, TRANSACTION_CATEGORY, TRANSACTION_SOURCE, TRANSACTION_STATUS
from django.views.generic import FormView, TemplateView
from django.utils import timezone
from credit.models import Credit
from payment.models import Payment
from disbursement.models import Disbursement
from disbursement.constants import DISBURSEMENT_METHOD
from model_utils.models import TimeStampedModel
from performance.models import DigitalTakeupQueryset, DigitalTakeup
from django.db.models import Sum
import pytz
import functools
import urllib.request as ur
import json
import requests
from django.db import models
from credit.models import Credit, CREDIT_RESOLUTION, CREDIT_STATUS


TRANSACTION_ERROR_FILTERS = (
    models.Q(transaction__source=TRANSACTION_SOURCE.BANK_TRANSFER,
             prison__isnull=True) |
    models.Q(transaction__source=TRANSACTION_SOURCE.BANK_TRANSFER,
             blocked=True)
)

def get_user_satisfaction():
    monthly_data = requests.get('https://www.performance.service.gov.uk/data/send-prisoner-money/customer-satisfaction?flatten=true&duration=1&period=month&collect=rating_1%3Asum&collect=rating_2%3Asum&collect=rating_3%3Asum&collect=rating_4%3Asum&collect=rating_5%3Asum&collect=total%3Asum&format=json').json()
    monthly_data = monthly_data["data"][0]
    weekly_data = requests.get('https://www.performance.service.gov.uk/data/send-prisoner-money/customer-satisfaction?flatten=true&duration=1&period=week&collect=rating_1%3Asum&collect=rating_2%3Asum&collect=rating_3%3Asum&collect=rating_4%3Asum&collect=rating_5%3Asum&collect=total%3Asum&format=json').json()
    weekly_data = weekly_data["data"][0]
    yearly_data = requests.get('https://www.performance.service.gov.uk/data/send-prisoner-money/customer-satisfaction?flatten=true&duration=1&period=year&collect=rating_1%3Asum&collect=rating_2%3Asum&collect=rating_3%3Asum&collect=rating_4%3Asum&collect=rating_5%3Asum&collect=total%3Asum&format=json').json()
    yearly_data = yearly_data["data"][0]

    this_week = {}
    this_month = {}
    this_year = {}

    def ratings_data(time_span, ratings):
        ratings['rating_1'] = time_span['rating_1:sum']
        ratings['rating_2'] = time_span['rating_2:sum']
        ratings['rating_3'] = time_span['rating_3:sum']
        ratings['rating_4'] = time_span['rating_4:sum']
        ratings['rating_5'] = time_span['rating_5:sum']
        return ratings

    weekly_ratings = ratings_data(weekly_data, this_week)
    monthly_ratings = ratings_data(monthly_data, this_month)
    yearly_ratings = ratings_data(yearly_data, this_year)

    total_satisfied_each_week = weekly_ratings['rating_4'] + weekly_ratings['rating_5']
    total_satisfied_each_month =  monthly_ratings['rating_4'] + monthly_ratings['rating_5']
    total_satisfied_each_year = yearly_ratings['rating_4'] + yearly_ratings['rating_5']
    total_not_satisfied_each_week = weekly_ratings['rating_3'] + weekly_ratings['rating_2'] + weekly_ratings['rating_1']
    total_not_satisfied_each_month = monthly_ratings['rating_3'] + monthly_ratings['rating_2'] + monthly_ratings['rating_1']
    total_not_satisfied_each_year = yearly_ratings['rating_1'] + yearly_ratings['rating_2'] + yearly_ratings['rating_3']


    def percentage(total_satisfied, total_not_satisfied):
        total = total_satisfied + total_not_satisfied
        try:
            return round((total_satisfied/total) * 100, 2)
        except:
            return 'No rating'


    weekly_satisfaction_percentage = percentage(total_satisfied_each_week, total_not_satisfied_each_week)
    monthly_satisfaction_percentage = percentage(total_satisfied_each_month, total_not_satisfied_each_month)
    yearly_satisfaction_percentage = percentage(total_satisfied_each_year, total_not_satisfied_each_year)

    return {
        'weekly_ratings': weekly_satisfaction_percentage,
        'monthly_ratings': monthly_satisfaction_percentage,
        'yearly_ratings': yearly_satisfaction_percentage,
    }


class DashboardView(TemplateView):
    """
    Django admin view which presents an overview report for MTP
    """
    template_name = 'the_dashboard/the_dashboard.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        data = []
        context['data'] = data

        tz = timezone.get_current_timezone()
        today = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
        weekday = today.weekday()
        start_delta = datetime.timedelta(days=weekday, weeks=1)
        start_of_week = today - start_delta
        end_delta = datetime.timedelta(days=weekday)
        end_of_week = today - end_delta

        year = today.year
        last_year = today.year -1
        month = today.month

        if month == 12:
            month = 1
            year += 1
        else:
            month

        last_month = month - 1
        if last_month == 0:
            last_month = 12
            year -= 1
        else:
            last_month

        last_month = month - 1

        start_of_previous_month = today.replace(month=last_month, day=1)
        start_of_current_month = today.replace(month=month, day=1)

        start_of_previous_month_last_year = today.replace(year=last_year, month=last_month, day=1)
        start_of_current_month_last_year = today.replace(year=last_year, month=month, day=1)

        starting_day_of_current_year = today.replace(month=1, day=1)

        queryset_total_number_of_digital_transactions_this_year = Credit.objects.filter(received_at__range=(starting_day_of_current_year, today))
        queryset_total_amount_of_digital_transactions_this_year = Credit.objects.filter(received_at__range=(starting_day_of_current_year, today)).aggregate(Sum('amount'))
        queryset_total_number_of_digital_transactions_previous_week = Credit.objects.filter(received_at__range=(start_of_week, end_of_week))
        queryset_amount_of_digital_transactions_previous_week = Credit.objects.filter(received_at__range=(start_of_week, end_of_week)).aggregate(Sum('amount'))

        queryset_number_of_disbursement_this_year = Disbursement.objects.filter(created__range=(starting_day_of_current_year, today))
        queryset_number_of_disbursement_previous_week = Disbursement.objects.filter(created__range=(start_of_week, end_of_week))
        queryset_disbursement_amount_this_year = Disbursement.objects.filter(created__range=(starting_day_of_current_year, today)).aggregate(Sum('amount'))
        queryset_disbursement_amount_this_week = Disbursement.objects.filter(created__range=(start_of_week, end_of_week)).aggregate(Sum('amount'))

        takeup_queryset = DigitalTakeup.objects.filter(date__range=(starting_day_of_current_year, today))

        queryset_debit_for_previous_month = Credit.objects.filter(payment__isnull=False).filter(received_at__range=(start_of_previous_month, start_of_current_month))
        queryset_debit_for_previous_month_last_year = Credit.objects.filter(payment__isnull=False).filter(received_at__range=(start_of_previous_month_last_year, start_of_current_month_last_year))


        digital_take_up = takeup_queryset.mean_digital_takeup()
        if digital_take_up:
            transaction_by_post = 1 - digital_take_up * queryset_total_number_of_digital_transactions_this_year.count()
        else:
            transaction_by_post = 0


        transaction_by_digital = queryset_total_number_of_digital_transactions_this_year.filter(resolution=CREDIT_RESOLUTION.CREDITED).count()
        COST_PER_TRANSACTION_BY_POST = 5.73
        COST_PER_TRANSACTION_BY_DIGITAL = 2.22

        total_cost_of_transaction_by_post = transaction_by_post * COST_PER_TRANSACTION_BY_POST
        total_cost_of_transaction_by_digital = transaction_by_digital * COST_PER_TRANSACTION_BY_DIGITAL
        total_cost_if_it_was_only_by_post = (transaction_by_post + transaction_by_digital) * COST_PER_TRANSACTION_BY_POST
        actual_cost = total_cost_of_transaction_by_post + total_cost_of_transaction_by_digital
        savings_made = total_cost_if_it_was_only_by_post - actual_cost

        def error_percentage(error, total ):
            try:
                return round((error/total) * 100, 2)
            except:
                return 0

        total_credit_last_month = queryset_debit_for_previous_month.exclude(resolution=CREDIT_RESOLUTION.INITIAL)
        error_credit_last_month = total_credit_last_month.filter(transaction__isnull=False)
        total_credit_last_month_last_year = queryset_debit_for_previous_month_last_year.exclude(resolution=CREDIT_RESOLUTION.INITIAL)
        error_credit_last_year = total_credit_last_month_last_year.filter(transaction__isnull=False)
        percent_of_errors_last_month = error_percentage(error_credit_last_month.count(), total_credit_last_month.count())
        percent_of_errors_last_month_last_year = error_percentage(error_credit_last_year.count(), total_credit_last_month_last_year.count())
        formated_month_and_year = '{:%B %Y}'.format(start_of_previous_month)
        formated_months_last_year = '{:%B %Y}'.format(start_of_previous_month_last_year)
        print("MONTH AND YEAR", formated_month_and_year)
        print("MONTH AND YEAR LAST YEAR", formated_months_last_year)

        context['formated_month_and_year'] = formated_month_and_year
        context['formated_months_last_year'] = formated_months_last_year
        context['percent_of_errors_last_month'] = percent_of_errors_last_month
        context['percent_of_errors_last_month_last_year'] = percent_of_errors_last_month_last_year
        context['savings_made'] = round(savings_made)
        context['number_of_disbursement_the_previous_week']= queryset_number_of_disbursement_previous_week.count()
        context['number_of_disbursement_this_year']= queryset_number_of_disbursement_previous_week.count()
        context['disbursement_amount_previous_week'] = queryset_disbursement_amount_this_week['amount__sum']
        context['disbursement_amount_this_year'] = queryset_disbursement_amount_this_year['amount__sum']
        context['total_number_of_digital_transactions_this_year'] = queryset_total_number_of_digital_transactions_this_year.count()
        context['total_amount_of_digital_transactions_this_year'] = queryset_total_amount_of_digital_transactions_this_year['amount__sum']
        context['total_digital_transactions_recent_week']=  queryset_total_number_of_digital_transactions_previous_week.count()
        context['total_digital_amount_recent_week'] = queryset_amount_of_digital_transactions_previous_week['amount__sum']

        list_of_transactions_by_post = []
        list_of_bank_transfer_count = []
        list_of_bank_transfer_amount = []
        list_of_debit_count = []
        list_of_debit_amount = []
        # list_of_formated_months = []
        # list_of_formated_months_last_year = []
        list_of_disbursement_in_months_amount = []
        list_of_disbursement_in_months_count = []

        for _ in range(5):
            end_of_month = datetime.datetime(year=year, month=month, day=1)
            end_of_month_last_year = datetime.datetime(year=last_year, month=month, day=1)
            month -= 1
            if month == 0:
                month = 12
                year -= 1
                last_year -= 1

            start_of_month_last_year = datetime.datetime(year=last_year, month=month, day=1)
            start_of_month = datetime.datetime(year=year, month=month, day=1)
            start_of_month = tz.localize(start_of_month)
            end_of_month = tz.localize(end_of_month)
            start_of_month_last_year = tz.localize(start_of_month_last_year)
            end_of_month_last_year = tz.localize(end_of_month_last_year)
            # formated_month_and_year = '{:%B %Y}'.format(start_of_month)
            # formated_months_last_year = '{:%B %Y}'.format(start_of_month_last_year)

            queryset_bank_transfer = Credit.objects.filter(transaction__isnull=False).filter(received_at__range=(start_of_month, end_of_month))
            queryset_bank_transfer_amount = Credit.objects.filter(transaction__isnull=False).filter(received_at__range=(start_of_month, end_of_month)).aggregate(Sum('amount'))
            queryset_debit = Credit.objects.filter(payment__isnull=False).filter(received_at__range=(start_of_month, end_of_month))
            queryset_debit_amount = Credit.objects.filter(payment__isnull=False).filter(received_at__range=(start_of_month, end_of_month)).aggregate(Sum('amount'))
            # queryset_debit_last_year = Credit.objects.filter(payment__isnull=False).filter(received_at__range=(start_of_month_last_year, end_of_month_last_year))

            queryset_number_of_all_digital_transactions = Credit.objects.filter(received_at__range=(start_of_month_last_year, end_of_month_last_year))
            queryset_amount_of_digital_transactions = Credit.objects.filter(received_at__range=(start_of_month_last_year, end_of_month_last_year)).aggregate(Sum('amount'))

            queryset_disbursement_bank_transfer_count = Disbursement.objects.filter(method=DISBURSEMENT_METHOD.BANK_TRANSFER).filter(created__range=(start_of_month, end_of_month))
            queryset_disbursement_cheque_count = Disbursement.objects.filter(method=DISBURSEMENT_METHOD.CHEQUE).filter(created__range=(start_of_month, end_of_month))
            queryset_disbursement_bank_transfer_amount = Disbursement.objects.filter(method=DISBURSEMENT_METHOD.BANK_TRANSFER).filter(created__range=(start_of_month, end_of_month)).aggregate(Sum('amount'))
            queryset_disbursement_cheque_amount = Disbursement.objects.filter(method=DISBURSEMENT_METHOD.CHEQUE).filter(created__range=(start_of_month, end_of_month)).aggregate(Sum('amount'))
            queryset_disbursement_count_all = Disbursement.objects.filter(created__range=(start_of_month, end_of_month))
            queryset_disbursement_amount_all = Disbursement.objects.filter(created__range=(start_of_month, end_of_month)).aggregate(Sum('amount'))

            list_of_transactions_by_post.append(transaction_by_post)
            list_of_bank_transfer_count.append(queryset_bank_transfer.count())
            list_of_debit_count.append(queryset_debit.count())
            # list_of_formated_months.append(formated_month_and_year)
            # list_of_formated_months_last_year.append(formated_months_last_year)
            list_of_debit_amount.append(queryset_debit_amount['amount__sum'])
            list_of_bank_transfer_amount.append(queryset_bank_transfer_amount['amount__sum'])
            list_of_disbursement_in_months_count.append(queryset_disbursement_count_all.count())
            list_of_disbursement_in_months_amount.append(queryset_disbursement_amount_all['amount__sum'])


            data.append({
            'disbursement_bank_transfer_count':queryset_disbursement_bank_transfer_count.count(),
            'disbursement_bank_transfer_amount': queryset_disbursement_bank_transfer_amount['amount__sum'],
            'disbursement_cheque_count': queryset_disbursement_cheque_count.count(),
            'disbursement_cheque_amount':queryset_disbursement_cheque_amount['amount__sum'],
            'transaction_by_post':transaction_by_post,
            'transaction_count': queryset_bank_transfer.count(),
            'credit_count': queryset_debit.count(),
            'queryset_credit_amount': queryset_debit_amount['amount__sum'],
            'queryset_transaction_amount': queryset_bank_transfer_amount['amount__sum'],
            'start_of_month': start_of_month,
            'end_of_month': end_of_month,
            })


        current_month_transaction_amount = list_of_bank_transfer_amount[0]
        current_month_credit_amount = list_of_debit_amount[0]

        context['this_months_disbursement_in_months_amount'] = list_of_disbursement_in_months_amount[0]
        context['this_months_disbursement_in_months_count'] = list_of_disbursement_in_months_count[0]
        context['total_digital_amount_this_month'] = queryset_amount_of_digital_transactions['amount__sum']
        context['total_digital_transactions_this_month'] = queryset_number_of_all_digital_transactions.count()
        # context['current_month_previous_year'] = list_of_formated_months_last_year[0]
        # context['current_formated_month']= list_of_formated_months[0]
        context['this_months_transaction_by_post'] = list_of_transactions_by_post[0]
        context['this_months_bank_transfers'] = list_of_bank_transfer_count[0]
        context['this_month_debit'] = list_of_debit_count[0]
        context['user_satisfaction'] = get_user_satisfaction()
        return context




