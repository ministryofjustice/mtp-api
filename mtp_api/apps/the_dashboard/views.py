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
    yearly_data = requests.get('https://www.performance.service.gov.uk/data/send-prisoner-money/customer-satisfaction?flatten=true&duration=1&period=year&collect=rating_1%3Asum&collect=rating_2%3Asum&collect=rating_3%3Asum&collect=rating_4%3Asum&collect=rating_5%3Asum&collect=total%3Asum&format=json').json()
    yearly_data = yearly_data["data"][0]

    this_year = {}

    def ratings_data(time_span, ratings):
        ratings['rating_1'] = time_span['rating_1:sum']
        ratings['rating_2'] = time_span['rating_2:sum']
        ratings['rating_3'] = time_span['rating_3:sum']
        ratings['rating_4'] = time_span['rating_4:sum']
        ratings['rating_5'] = time_span['rating_5:sum']
        return ratings


    yearly_ratings = ratings_data(yearly_data, this_year)

    total_satisfied_each_year = yearly_ratings['rating_4'] + yearly_ratings['rating_5']
    total_not_satisfied_each_year = yearly_ratings['rating_1'] + yearly_ratings['rating_2'] + yearly_ratings['rating_3']


    def percentage(total_satisfied, total_not_satisfied):
        total = total_satisfied + total_not_satisfied
        try:
            return round((total_satisfied/total) * 100, 2)
        except:
            return 'No rating'


    yearly_satisfaction_percentage = percentage(total_satisfied_each_year, total_not_satisfied_each_year)

    return {
        'yearly_satisfaction_ratings': yearly_satisfaction_percentage,
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
            month += 1

        next_month = month + 1
        this_month = month - 1

        current_month = today.replace(month=this_month, day=1)

        start_of_current_month = today.replace(month=this_month, day=1)
        start_of_next_month = today.replace(month=next_month, day=1)

        start_of_current_month_last_year = today.replace(year=last_year, month=this_month, day=1)
        start_of_next_month_last_year = today.replace(year=last_year, month=next_month, day=1)

        starting_day_of_current_year = today.replace(month=1, day=1)

        queryset_total_number_of_digital_transactions_this_month = Credit.objects.filter(received_at__range=(start_of_current_month, start_of_next_month))
        queryset_total_amount_of_digital_transactions_this_month = Credit.objects.filter(received_at__range=(start_of_current_month, start_of_next_month)).aggregate(Sum('amount'))
        queryset_total_number_of_digital_transactions_this_year = Credit.objects.filter(received_at__range=(starting_day_of_current_year, today))
        queryset_total_amount_of_digital_transactions_this_year = Credit.objects.filter(received_at__range=(starting_day_of_current_year, today)).aggregate(Sum('amount'))
        queryset_total_number_of_digital_transactions_previous_week = Credit.objects.filter(received_at__range=(start_of_week, end_of_week))
        queryset_amount_of_digital_transactions_previous_week = Credit.objects.filter(received_at__range=(start_of_week, end_of_week)).aggregate(Sum('amount'))

        queryset_number_of_disbursement_this_year = Disbursement.objects.filter(created__range=(starting_day_of_current_year, today))
        queryset_number_of_disbursement_previous_week = Disbursement.objects.filter(created__range=(start_of_week, end_of_week))
        queryset_disbursement_amount_this_year = Disbursement.objects.filter(created__range=(starting_day_of_current_year, today)).aggregate(Sum('amount'))
        queryset_disbursement_amount_this_week = Disbursement.objects.filter(created__range=(start_of_week, end_of_week)).aggregate(Sum('amount'))

        takeup_queryset = DigitalTakeup.objects.filter(date__range=(starting_day_of_current_year, today))

        queryset_debit_for_current_month = Credit.objects.filter(payment__isnull=False).filter(received_at__range=(start_of_current_month, start_of_next_month))
        queryset_debit_for_current_month_last_year = Credit.objects.filter(payment__isnull=False).filter(received_at__range=(start_of_current_month_last_year, start_of_next_month_last_year))


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

        total_credit_this_month = queryset_debit_for_current_month.exclude(resolution=CREDIT_RESOLUTION.INITIAL)
        error_credit_this_month = total_credit_this_month.filter(transaction__isnull=False)
        total_credit_this_month_last_year = queryset_debit_for_current_month_last_year.exclude(resolution=CREDIT_RESOLUTION.INITIAL)
        error_credit_last_year = total_credit_this_month_last_year.filter(transaction__isnull=False)
        percent_of_errors_this_month = error_percentage(error_credit_this_month.count(), total_credit_this_month.count())
        percent_of_errors_this_month_last_year = error_percentage(error_credit_last_year.count(), total_credit_this_month_last_year.count())

        formated_current_month_and_year = '{:%B %Y}'.format(current_month)
        formated_current_month_last_year = '{:%B %Y}'.format(start_of_current_month_last_year)

        context['total_number_of_digital_transactions_this_month'] = queryset_total_number_of_digital_transactions_this_month.count()
        context['total_amount_of_digital_transactions_this_month'] = queryset_total_amount_of_digital_transactions_this_month['amount__sum']
        context['formated_current_month_and_year'] = formated_current_month_and_year
        context['formated_current_month_last_year'] = formated_current_month_last_year
        context['percent_of_errors_last_month'] = percent_of_errors_this_month
        context['percent_of_errors_last_month_last_year'] = percent_of_errors_this_month_last_year
        context['savings_made'] = round(savings_made)
        context['number_of_disbursement_the_previous_week']= queryset_number_of_disbursement_previous_week.count()
        context['number_of_disbursement_this_year']= queryset_number_of_disbursement_previous_week.count()
        context['disbursement_amount_previous_week'] = queryset_disbursement_amount_this_week['amount__sum']
        context['disbursement_amount_this_year'] = queryset_disbursement_amount_this_year['amount__sum']
        context['total_number_of_digital_transactions_this_year'] = queryset_total_number_of_digital_transactions_this_year.count()
        context['total_amount_of_digital_transactions_this_year'] = queryset_total_amount_of_digital_transactions_this_year['amount__sum']
        context['total_digital_transactions_recent_week']= queryset_total_number_of_digital_transactions_previous_week.count()
        context['total_digital_amount_recent_week'] = queryset_amount_of_digital_transactions_previous_week['amount__sum']

        transaction_by_post_current_month = None
        bank_transfer_count_current_month = None
        debit_card_count_current_month = None
        disbursement_amount_current_month = None
        disbursement_count_current_month = None
        digital_transactions_count_current_month = None
        digital_transactions_amount_current_month = None


        for _ in range(5):
            end_of_month = datetime.datetime(year=year, month=month, day=1)

            month -= 1
            if month == 0:
                month = 12
                year -= 1
                last_year -= 1

            start_of_month = datetime.datetime(year=year, month=month, day=1)
            start_of_month = tz.localize(start_of_month)
            end_of_month = tz.localize(end_of_month)

            takeup_queryset = DigitalTakeup.objects.filter(date__range=(start_of_month, end_of_month))
            queryset_total_number_of_digital_transactions_in_month = Credit.objects.filter(received_at__range=(start_of_month, end_of_month))

            digital_take_up = takeup_queryset.mean_digital_takeup()
            if digital_take_up:
                transaction_by_post = (1 - digital_take_up) * queryset_total_number_of_digital_transactions_in_month.count()
            else:
                transaction_by_post = 0


            queryset_bank_transfer = Credit.objects.filter(transaction__isnull=False).filter(received_at__range=(start_of_month, end_of_month))
            queryset_bank_transfer_amount = Credit.objects.filter(transaction__isnull=False).filter(received_at__range=(start_of_month, end_of_month)).aggregate(Sum('amount'))
            queryset_debit = Credit.objects.filter(payment__isnull=False).filter(received_at__range=(start_of_month, end_of_month))
            queryset_debit_amount = Credit.objects.filter(payment__isnull=False).filter(received_at__range=(start_of_month, end_of_month)).aggregate(Sum('amount'))
            queryset_amount_of_digital_transactions = Credit.objects.filter(received_at__range=(start_of_month, end_of_month)).aggregate(Sum('amount'))

            queryset_disbursement_bank_transfer_count = Disbursement.objects.filter(method=DISBURSEMENT_METHOD.BANK_TRANSFER).filter(created__range=(start_of_month, end_of_month))
            queryset_disbursement_cheque_count = Disbursement.objects.filter(method=DISBURSEMENT_METHOD.CHEQUE).filter(created__range=(start_of_month, end_of_month))
            queryset_disbursement_bank_transfer_amount = Disbursement.objects.filter(method=DISBURSEMENT_METHOD.BANK_TRANSFER).filter(created__range=(start_of_month, end_of_month)).aggregate(Sum('amount'))
            queryset_disbursement_cheque_amount = Disbursement.objects.filter(method=DISBURSEMENT_METHOD.CHEQUE).filter(created__range=(start_of_month, end_of_month)).aggregate(Sum('amount'))
            queryset_disbursement_count_all = Disbursement.objects.filter(created__range=(start_of_month, end_of_month))
            queryset_disbursement_amount_all = Disbursement.objects.filter(created__range=(start_of_month, end_of_month)).aggregate(Sum('amount'))

            bank_transfer_amount = queryset_bank_transfer_amount['amount__sum'] or 0
            debit_amount = queryset_debit_amount['amount__sum'] or 0
            disbursement_bank_transfer_amount = queryset_disbursement_bank_transfer_amount['amount__sum'] or 0
            disbursement_amount_all = queryset_disbursement_amount_all['amount__sum'] or 0
            amount_of_digital_transactions = queryset_amount_of_digital_transactions['amount__sum'] or 0


            if(transaction_by_post_current_month == None):
                transaction_by_post_current_month = transaction_by_post

            if(bank_transfer_count_current_month == None):
                bank_transfer_count_current_month = queryset_bank_transfer.count()

            if(debit_card_count_current_month == None):
                debit_card_count_current_month = queryset_debit.count()

            if(disbursement_amount_current_month == None):
                disbursement_amount_current_month = disbursement_amount_all

            if(disbursement_count_current_month == None):
                disbursement_count_current_month = queryset_disbursement_count_all.count()


            data.append({
            'disbursement_bank_transfer_count': queryset_disbursement_bank_transfer_count.count(),
            'disbursement_bank_transfer_amount': disbursement_bank_transfer_amount,
            'disbursement_cheque_count': queryset_disbursement_cheque_count.count(),
            'disbursement_cheque_amount':queryset_disbursement_cheque_amount['amount__sum'] or 0,
            'transaction_by_post':transaction_by_post,
            'transaction_count': queryset_bank_transfer.count(),
            'credit_count': queryset_debit.count(),
            'queryset_credit_amount': debit_amount,
            'queryset_transaction_amount': bank_transfer_amount,
            'start_of_month': start_of_month,
            'end_of_month': end_of_month,
            })

        context['disbursement_count_current_month'] = disbursement_count_current_month
        context['disbursement_amount_current_month'] = disbursement_amount_current_month
        context['this_months_transaction_by_post'] = transaction_by_post_current_month
        context['this_months_bank_transfers'] =  bank_transfer_count_current_month
        context['this_month_debit'] = debit_card_count_current_month
        context['user_satisfaction'] = get_user_satisfaction()
        return context




