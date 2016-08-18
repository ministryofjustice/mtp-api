import datetime
from functools import partial
from itertools import cycle
from math import ceil
import random
import warnings

from django.core.exceptions import FieldDoesNotExist
from django.utils import timezone
from django.utils.crypto import get_random_string
from faker import Faker

from core.tests.utils import MockModelTimestamps
from credit.constants import CREDIT_RESOLUTION, CREDIT_STATUS
from credit.models import Credit
from credit.tests.utils import (
    get_owner_and_status_chooser, create_credit_log, random_amount
)
from prison.models import PrisonerLocation
from transaction.models import Transaction
from transaction.constants import (
    TRANSACTION_CATEGORY, TRANSACTION_SOURCE
)

fake = Faker(locale='en_GB')


def random_sender_name():
    name = []
    # < 5% have a title
    if random.random() < 0.05:
        name.insert(0, random.choice(['MISS', 'MR', 'MRS']))
    # > 60% have an initial
    if random.random() > 0.6:
        name.append(random.choice('ABCDEFGHIJKLMNOPQRSTUVWXYZ'))
    else:
        name.append(fake.first_name().upper())
    surname = fake.last_name().upper()
    if random.random() > 0.5:
        name.append(surname)
    else:
        name.insert(0, surname)
    return ' '.join(name)


def random_reference(prisoner_number=None, prisoner_dob=None):
    if not prisoner_number or not prisoner_dob:
        return get_random_string(length=15)
    return '%s %s' % (
        prisoner_number.upper(),
        prisoner_dob.strftime('%d/%m/%Y'),
    )


def get_midnight(dt):
    return dt.tzinfo.localize(dt.replace(hour=0, minute=0, second=0, microsecond=0, tzinfo=None))


def latest_transaction_date():
    latest_transaction_date = timezone.now().replace(microsecond=0) - datetime.timedelta(days=1)
    while latest_transaction_date.weekday() > 4:
        latest_transaction_date = latest_transaction_date - datetime.timedelta(days=1)
    return timezone.localtime(latest_transaction_date)


def get_sender_prisoner_pairs():
    number_of_prisoners = PrisonerLocation.objects.all().count()
    number_of_senders = number_of_prisoners
    number_of_sort_codes = ceil(number_of_senders/5)

    sort_codes = [
        get_random_string(6, '1234567890') for _ in range(number_of_sort_codes)
    ]
    senders = [
        {
            'sender_name': random_sender_name(),
            'sender_sort_code': sort_codes[n % number_of_sort_codes],
            'sender_account_number': get_random_string(8, '1234567890')
        } for n in range(number_of_senders)
    ]
    for i, sender in enumerate(senders):
        if i % 20 == 0:
            sender['sender_roll_number'] = get_random_string(15, '1234a567890')

    prisoners = list(PrisonerLocation.objects.all())

    sender_prisoner_pairs = []
    for i in range(number_of_senders*3):
        prisoner_fraction = number_of_prisoners
        if i <= number_of_senders:
            sender_fraction = number_of_senders
            if i % 3 == 1:
                prisoner_fraction = ceil(number_of_prisoners/2)
            elif i % 3 == 2:
                prisoner_fraction = ceil(number_of_prisoners/15)
        elif i <= number_of_senders*2:
            sender_fraction = ceil(number_of_senders/2)
        else:
            sender_fraction = ceil(number_of_senders/15)

        sender_prisoner_pairs.append(
            (senders[i % sender_fraction], prisoners[i % prisoner_fraction])
        )
    return cycle(sender_prisoner_pairs)


def generate_initial_transactions_data(
        tot=50,
        prisoner_location_generator=None,
        include_debits=True,
        include_administrative_credits=True,
        include_unidentified_credits=True,
        days_of_history=7):
    data_list = []
    sender_prisoner_pairs = get_sender_prisoner_pairs()

    for transaction_counter in range(1, tot + 1):
        include_prisoner_info = transaction_counter % 5 != 0
        omit_sender_details = (
            include_unidentified_credits and transaction_counter % 23 == 0
        )
        make_debit_transaction = (
            include_debits and transaction_counter % 21 == 0
        )
        make_administrative_credit_transaction = (
            include_administrative_credits and transaction_counter % 41 == 0
        )

        random_date = latest_transaction_date() - datetime.timedelta(
            minutes=random.randint(0, 1440*days_of_history)
        )
        random_date = timezone.localtime(random_date)
        midnight_random_date = get_midnight(random_date)
        data = {
            'category': TRANSACTION_CATEGORY.CREDIT,
            'amount': random_amount(),
            'received_at': midnight_random_date,
            'owner': None,
            'credited': False,
            'refunded': False,
            'created': random_date,
            'modified': random_date,
        }

        sender, prisoner = next(sender_prisoner_pairs)
        data.update(sender)

        if make_administrative_credit_transaction:
            data['source'] = TRANSACTION_SOURCE.ADMINISTRATIVE
            data['incomplete_sender_info'] = True
            data['processor_type_code'] = 'RA'
            del data['sender_sort_code']
            del data['sender_account_number']
        elif make_debit_transaction:
            data['source'] = TRANSACTION_SOURCE.ADMINISTRATIVE
            data['category'] = TRANSACTION_CATEGORY.DEBIT
            data['processor_type_code'] = '03'
            data['reference'] = 'Payment refunded'
        else:
            data['source'] = TRANSACTION_SOURCE.BANK_TRANSFER
            data['processor_type_code'] = '99'

            if include_prisoner_info:
                data['prisoner_name'] = prisoner.prisoner_name
                data['prisoner_number'] = prisoner.prisoner_number
                data['prisoner_dob'] = prisoner.prisoner_dob
                data['prison'] = prisoner.prison

            if omit_sender_details:
                data['incomplete_sender_info'] = True
                del data['sender_name']
                if data.get('sender_roll_number'):
                    del data['sender_roll_number']
                else:
                    del data['sender_account_number']
                    if transaction_counter % 2 == 0:
                        del data['sender_sort_code']

            data['reference'] = random_reference(
                data.get('prisoner_number'), data.get('prisoner_dob')
            )
        data_list.append(data)
    return data_list


def generate_predetermined_transactions_data():
    """
    Uses test NOMIS prisoner locations to create some transactions
    that are pre-determined for user testing with specific scenarios

    Currently, only one transaction is created:
        NICHOLAS FINNEY (A1450AE, dob. 30/12/1986) @ HMP BIRMINGHAM
        Mary Stevenson sent £72.30, 8 days ago
        Payment is still uncredited
    """
    prisoner_number = 'A1450AE'
    try:
        prisoner_location = PrisonerLocation.objects.get(
            prisoner_number=prisoner_number
        )
    except PrisonerLocation.DoesNotExist:
        warnings.warn('Could not find prisoner %s, '
                      'was test NOMIS data loaded?' % prisoner_number)
        return []

    now = timezone.now().replace(microsecond=0)
    over_a_week_ago = now - datetime.timedelta(days=8)
    over_a_week_ago = timezone.localtime(over_a_week_ago)
    a_week_ago = over_a_week_ago + datetime.timedelta(days=1)
    a_week_ago = timezone.localtime(a_week_ago)
    data = {
        'received_at': get_midnight(over_a_week_ago),
        'created': over_a_week_ago,
        'modified': a_week_ago,
        'owner': None,
        'credited': True,
        'refunded': False,

        'sender_name': 'Mary Stevenson',
        'amount': 7230,
        'category': TRANSACTION_CATEGORY.CREDIT,
        'source': TRANSACTION_SOURCE.BANK_TRANSFER,
        'sender_sort_code': '680966',
        'sender_account_number': '75823963',

        'prison': prisoner_location.prison,
        'prisoner_name': prisoner_location.prisoner_name,
        'prisoner_number': prisoner_location.prisoner_number,
        'prisoner_dob': prisoner_location.prisoner_dob,
    }
    data['reference'] = random_reference(
        data.get('prisoner_number'), data.get('prisoner_dob')
    )
    data_list = [data]
    return data_list


def generate_transactions(
    transaction_batch=50,
    predetermined_transactions=False,
    consistent_history=False,
    include_debits=True,
    include_administrative_credits=True,
    include_unidentified_credits=True,
    days_of_history=7
):
    data_list = generate_initial_transactions_data(
        tot=transaction_batch,
        include_debits=include_debits,
        include_administrative_credits=include_administrative_credits,
        include_unidentified_credits=include_unidentified_credits,
        days_of_history=days_of_history
    )

    owner_status_chooser = get_owner_and_status_chooser()
    transactions = []
    if consistent_history:
        create_transaction = partial(
            setup_historical_transaction,
            owner_status_chooser,
            latest_transaction_date()
        )
    else:
        create_transaction = partial(
            setup_transaction,
            owner_status_chooser
        )
    for transaction_counter, data in enumerate(data_list, start=1):
        new_transaction = create_transaction(transaction_counter, data)
        transactions.append(new_transaction)

    if predetermined_transactions:
        for data in generate_predetermined_transactions_data():
            with MockModelTimestamps(data['created'], data['modified']):
                new_transaction = save_transaction(data)
            transactions.append(new_transaction)

    generate_transaction_logs(transactions)

    return transactions


def setup_historical_transaction(owner_status_chooser,
                                 end_date, transaction_counter, data):
    if (data['category'] == TRANSACTION_CATEGORY.CREDIT and
            data['source'] == TRANSACTION_SOURCE.BANK_TRANSFER):
        is_valid = data.get('prison', None) and not data.get('incomplete_sender_info')
        is_most_recent = data['received_at'].date() == end_date.date()
        if is_valid:
            owner, status = owner_status_chooser(data['prison'])
            if is_most_recent:
                data.update({
                    'owner': None,
                    'credited': False
                })
            else:
                data.update({
                    'owner': owner,
                    'credited': True
                })
        else:
            if is_most_recent or data.get('incomplete_sender_info'):
                data.update({'refunded': False})
            else:
                data.update({'refunded': True})

    with MockModelTimestamps(data['created'], data['modified']):
        new_transaction = save_transaction(data)

    return new_transaction


def setup_transaction(owner_status_chooser,
                      transaction_counter, data):
    if data['category'] == TRANSACTION_CATEGORY.CREDIT:
        is_valid = data.get('prison', None) and not data.get('incomplete_sender_info')

        if is_valid:
            owner, status = owner_status_chooser(data['prison'])
            if status == CREDIT_STATUS.LOCKED:
                data.update({
                    'owner': owner,
                    'credited': False
                })
            elif status == CREDIT_STATUS.AVAILABLE:
                data.update({
                    'owner': None,
                    'credited': False
                })
            elif status == CREDIT_STATUS.CREDITED:
                data.update({
                    'owner': owner,
                    'credited': True
                })
        else:
            if transaction_counter % 2 == 0 or data.get('incomplete_sender_info'):
                data.update({'refunded': False})
            else:
                data.update({'refunded': True})

    with MockModelTimestamps(data['created'], data['modified']):
        new_transaction = save_transaction(data)

    return new_transaction


def save_transaction(data):
    if data.pop('credited', False):
        resolution = CREDIT_RESOLUTION.CREDITED
    elif data.pop('refunded', False):
        resolution = CREDIT_RESOLUTION.REFUNDED
    else:
        resolution = CREDIT_RESOLUTION.PENDING

    prisoner_dob = data.pop('prisoner_dob', None)
    prisoner_number = data.pop('prisoner_number', None)
    prisoner_name = data.pop('prisoner_name', None)
    prison = data.pop('prison', None)
    reconciled = data.pop('reconciled', False)
    owner = data.pop('owner', None)

    if (data['category'] == TRANSACTION_CATEGORY.CREDIT and
            data['source'] == TRANSACTION_SOURCE.BANK_TRANSFER):
        credit = Credit(
            amount=data['amount'],
            prisoner_dob=prisoner_dob,
            prisoner_number=prisoner_number,
            prisoner_name=prisoner_name,
            prison=prison,
            reconciled=reconciled,
            owner=owner,
            received_at=data['received_at'],
            resolution=resolution
        )
        credit.save()
        data['credit'] = credit

    return Transaction.objects.create(**data)


def generate_transaction_logs(transactions):
    for new_transaction in transactions:
        if new_transaction.credit:
            create_credit_log(new_transaction.credit,
                              new_transaction.modified,
                              new_transaction.modified)


def filters_from_api_data(data):
    filters = {}
    for field in data:
        try:
            Transaction._meta.get_field(field)
            filters[field] = data[field]
            if (data['category'] == TRANSACTION_CATEGORY.CREDIT and
                    data['source'] == TRANSACTION_SOURCE.BANK_TRANSFER):
                Credit._meta.get_field(field)
                filters['credit__%s' % field] = data[field]
        except FieldDoesNotExist:
            pass
    return filters
