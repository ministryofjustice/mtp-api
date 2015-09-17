import mock
import urllib.parse

from django.core.urlresolvers import reverse
from django.utils.six.moves.urllib.parse import urlsplit

from rest_framework import status

from mtp_auth.models import PrisonUserMapping

from prison.models import Prison

from transaction.models import Transaction, Log
from transaction.constants import TRANSACTION_STATUS, LOCK_LIMIT, LOG_ACTIONS


from .test_base import BaseTransactionViewTestCase, \
    TransactionRejectsRequestsWithoutPermissionTestMixin


def get_prisons_for_user(user):
    return PrisonUserMapping.objects.get(user=user).prisons.all()


class CashbookTransactionRejectsRequestsWithoutPermissionTestMixin(
    TransactionRejectsRequestsWithoutPermissionTestMixin
):

    def _get_unauthorised_application_users(self):
        return [
            self.bank_admins[0], self.prisoner_location_admins[0]
        ]

    def _get_authorised_user(self):
        return self.prison_clerks[0]


class TransactionListTestCase(
    CashbookTransactionRejectsRequestsWithoutPermissionTestMixin,
    BaseTransactionViewTestCase
):

    def _get_url(self, **filters):
        url = reverse('cashbook:transaction-list')

        filters['limit'] = 1000
        return '{url}?{filters}'.format(
            url=url, filters=urllib.parse.urlencode(filters)
        )

    def _test_response_with_filters(self, filters={}):
        logged_in_user = self.prison_clerks[0]
        logged_in_user.prisonusermapping.prisons.add(*self.prisons)
        managing_prisons = list(get_prisons_for_user(logged_in_user))

        url = self._get_url(**filters)
        response = self.client.get(
            url, format='json',
            HTTP_AUTHORIZATION=self.get_http_authorization_for_user(logged_in_user)
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # check expected result
        status_checker = self.STATUS_FILTERS[filters.get('status', None)]
        if filters.get('prison'):
            prison_checker = lambda t: t.prison and t.prison.pk in filters['prison'].split(',')
        else:
            prison_checker = lambda t: True
        if filters.get('user'):
            user_checker = lambda t: t.owner and t.owner.pk == filters['user']
        else:
            user_checker = lambda t: True

        expected_ids = [
            t.pk for t in self.transactions if
                t.prison in managing_prisons and
                status_checker(t) and
                prison_checker(t) and
                user_checker(t)
        ]
        self.assertEqual(response.data['count'], len(expected_ids))
        self.assertListEqual(
            sorted([t['id'] for t in response.data['results']]),
            sorted(expected_ids)
        )


class TransactionListWithDefaultsTestCase(TransactionListTestCase):

    def test_returns_all_transactions(self):
        """
        Returns all transactions attached to all the prisons that
        the logged-in user can manage.
        """
        self._test_response_with_filters(filters={})


class TransactionListWithDefaultPrisonAndUserTestCase(TransactionListTestCase):

    def test_filter_by_status_available(self):
        """
        Returns available transactions attached to all the prisons
        that the logged-in user can manage.
        """
        self._test_response_with_filters(filters={
            'status': TRANSACTION_STATUS.AVAILABLE
        })

    def test_filter_by_status_locked(self):
        """
        Returns locked transactions attached to all the prisons
        that the logged-in user can manage.
        """
        self._test_response_with_filters(filters={
            'status': TRANSACTION_STATUS.LOCKED
        })

    def test_filter_by_status_credited(self):
        """
        Returns credited transactions attached to all the prisons
        that the logged-in user can manage.
        """
        self._test_response_with_filters(filters={
            'status': TRANSACTION_STATUS.CREDITED
        })


class TransactionListWithDefaultUserTestCase(TransactionListTestCase):

    def test_filter_by_status_available_and_prison(self):
        """
        Returns available transactions attached to the passed-in prison.
        """
        self._test_response_with_filters(filters={
            'prison': self.prisons[0].pk
        })

    def test_filter_by_status_locked_and_prison(self):
        """
        Returns locked transactions attached to the passed-in prison.
        """
        self._test_response_with_filters(filters={
            'status': TRANSACTION_STATUS.LOCKED,
            'prison': self.prisons[0].pk
        })

    def test_filter_by_status_credited_prison(self):
        """
        Returns crdited transactions attached to the passed-in prison.
        """
        self._test_response_with_filters(filters={
            'status': TRANSACTION_STATUS.CREDITED,
            'prison': self.prisons[0].pk
        })


class TransactionListWithDefaultPrisonTestCase(TransactionListTestCase):

    def test_filter_by_status_available_and_user(self):
        """
        Returns available transactions attached to all the prisons
        that the passed-in user can manage.
        """
        self._test_response_with_filters(filters={
            'user': self.prison_clerks[1].pk
        })

    def test_filter_by_status_locked_and_user(self):
        """
        Returns transactions locked by the passed-in user.
        """
        self._test_response_with_filters(filters={
            'status': TRANSACTION_STATUS.LOCKED,
            'user': self.prison_clerks[1].pk
        })

    def test_filter_by_status_credited_and_user(self):
        """
        Returns transactions credited by the passed-in user.
        """
        self._test_response_with_filters(filters={
            'status': TRANSACTION_STATUS.CREDITED,
            'user': self.prison_clerks[1].pk
        })


class TransactionListWithoutDefaultsTestCase(TransactionListTestCase):

    def test_filter_by_status_available_and_prison_and_user(self):
        """
        Returns available transactions attached to the passed-in prison.
        """
        self._test_response_with_filters(filters={
            'prison': self.prisons[0].pk,
            'user': self.prison_clerks[1].pk
        })

    def test_filter_by_status_locked_and_prison_and_user(self):
        """
        Returns transactions locked by the passed-in user and
        attached to the passed-in prison.
        """
        self._test_response_with_filters(filters={
            'status': TRANSACTION_STATUS.LOCKED,
            'prison': self.prisons[0].pk,
            'user': self.prison_clerks[1].pk
        })

    def test_filter_by_status_credited_and_prison_and_user(self):
        """
        Returns transactions credited by the passed-in user and
        attached to the passed-in prison.
        """
        self._test_response_with_filters(filters={
            'status': TRANSACTION_STATUS.CREDITED,
            'prison': self.prisons[0].pk,
            'user': self.prison_clerks[1].pk
        })


class TransactionListWithDefaultStatusAndUserTestCase(TransactionListTestCase):

    def test_filter_by_prison(self):
        """
        Returns all transactions attached to the passed-in prison.
        """
        self._test_response_with_filters(filters={
            'prison': self.prisons[0].pk
        })

    def test_filter_by_multiple_prisons(self):
        """
        Returns all transactions attached to the passed-in prisons.
        """

        # logged-in user managing all the prisons
        logged_in_user = self.prison_clerks[0]
        logged_in_user.prisonusermapping.prisons.add(*self.prisons)
        managing_prisons = list(get_prisons_for_user(logged_in_user))

        url = self._get_url(**{
            'prison[]': [p.pk for p in self.prisons]
        })
        response = self.client.get(
            url, format='json',
            HTTP_AUTHORIZATION=self.get_http_authorization_for_user(logged_in_user)
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        expected_ids = [
            t.pk for t in self.transactions if
                t.prison in managing_prisons
        ]
        self.assertEqual(response.data['count'], len(expected_ids))
        self.assertListEqual(
            sorted([t['id'] for t in response.data['results']]),
            sorted(expected_ids)
        )


class TransactionListWithDefaultStatusTestCase(TransactionListTestCase):

    def test_filter_by_prison_and_user(self):
        """
        Returns all transactions attached to the passed-in prison.
        """
        self._test_response_with_filters(filters={
            'prison': self.prisons[0].pk,
            'user': self.prison_clerks[1].pk
        })


class TransactionListWithDefaultStatusAndPrisonTestCase(TransactionListTestCase):

    def test_filter_by_user(self):
        """
        Returns all transactions managed by the passed-in user
        """
        self._test_response_with_filters(filters={
            'user': self.prison_clerks[1].pk
        })


class TransactionListInvalidValuesTestCase(TransactionListTestCase):

    def test_invalid_status_filter(self):
        logged_in_user = self.prison_clerks[0]
        url = self._get_url(status='invalid')
        response = self.client.get(
            url, format='json',
            HTTP_AUTHORIZATION=self.get_http_authorization_for_user(logged_in_user)
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 0)

    def test_invalid_user_filter(self):
        logged_in_user = self.prison_clerks[0]
        url = self._get_url(user='invalid')
        response = self.client.get(
            url, format='json',
            HTTP_AUTHORIZATION=self.get_http_authorization_for_user(logged_in_user)
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 0)

    def test_invalid_prison_filter(self):
        logged_in_user = self.prison_clerks[0]
        url = self._get_url(prison='invalid')
        response = self.client.get(
            url, format='json',
            HTTP_AUTHORIZATION=self.get_http_authorization_for_user(logged_in_user)
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 0)

    def test_prison_not_managed_by_loggedin_user(self):
        logged_in_user = self.prison_clerks[0]
        managing_prison_ids = get_prisons_for_user(logged_in_user).values_list('pk', flat=True)
        non_managing_prisons = Prison.objects.exclude(pk__in=managing_prison_ids)

        self.assertTrue(len(non_managing_prisons) > 0)

        url = self._get_url(prison=non_managing_prisons[0].pk)
        response = self.client.get(
            url, format='json',
            HTTP_AUTHORIZATION=self.get_http_authorization_for_user(logged_in_user)
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 0)

    def test_prison_not_managed_by_passed_in_user(self):
        # logged-in user managing all the prisons
        logged_in_user = self.prison_clerks[0]
        logged_in_user.prisonusermapping.prisons.add(*self.prisons)

        # passed-in user managing only prison #1
        passed_in_user = self.prison_clerks[1]
        passed_in_user.prisonusermapping.prisons.clear()
        Transaction.objects.filter(
            owner=passed_in_user, prison__isnull=False
        ).update(prison=self.prisons[1])
        passed_in_user.prisonusermapping.prisons.add(self.prisons[1])

        # filtering by prison #0, passed-in user doesn't manage that one so it should
        # return an empty list
        url = self._get_url(
            user=passed_in_user.pk,
            prison=self.prisons[0].pk
        )
        response = self.client.get(
            url, format='json',
            HTTP_AUTHORIZATION=self.get_http_authorization_for_user(logged_in_user)
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 0)

    def test_logged_in_user_not_managing_prison(self):
        # logged-in user managing only prison #1
        logged_in_user = self.prison_clerks[0]
        logged_in_user.prisonusermapping.prisons.clear()
        logged_in_user.prisonusermapping.prisons.add(self.prisons[1])

        # passed-in user managing all the prisons
        passed_in_user = self.prison_clerks[1]
        passed_in_user.prisonusermapping.prisons.add(*self.prisons)

        # filtering by prison #0, logged-in user doesn't manage that one so it should
        # return an empty list
        url = self._get_url(
            user=passed_in_user.pk,
            prison=self.prisons[0].pk
        )
        response = self.client.get(
            url, format='json',
            HTTP_AUTHORIZATION=self.get_http_authorization_for_user(logged_in_user)
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 0)


class LockTransactionTestCase(
    CashbookTransactionRejectsRequestsWithoutPermissionTestMixin,
    BaseTransactionViewTestCase
):
    ENDPOINT_VERB = 'post'
    transaction_batch = 500

    def _get_url(self):
        return reverse('cashbook:transaction-lock')

    def setUp(self):
        super(LockTransactionTestCase, self).setUp()

        self.logged_in_user = self.prison_clerks[0]
        self.logged_in_user.prisonusermapping.prisons.add(*self.prisons)

    def _test_lock(self, already_locked_count, available_count=LOCK_LIMIT):
        locked_qs = self._get_locked_transactions_qs(self.prisons, self.logged_in_user)
        available_qs = self._get_available_transactions_qs(self.prisons)

        # set nr of transactions locked by logged-in user to 'already_locked'
        locked = locked_qs.values_list('pk', flat=True)
        Transaction.objects.filter(
            pk__in=[-1]+list(locked[:locked.count() - already_locked_count])
        ).delete()

        self.assertEqual(locked_qs.count(), already_locked_count)

        # set nr of transactions available to 'available'
        available = available_qs.values_list('pk', flat=True)
        Transaction.objects.filter(
            pk__in=[-1]+list(available[:available.count() - available_count])
        ).delete()

        self.assertEqual(available_qs.count(), available_count)

        expected_locked = min(
            already_locked_count + available_qs.count(),
            LOCK_LIMIT
        )

        # make lock request
        url = self._get_url()
        response = self.client.post(
            url, format='json',
            HTTP_AUTHORIZATION=self.get_http_authorization_for_user(self.logged_in_user)
        )
        self.assertEqual(response.status_code, status.HTTP_303_SEE_OTHER)

        # check that expected_locked got locked
        self.assertEqual(locked_qs.count(), expected_locked)

        return locked_qs

    def test_lock_with_none_locked_already(self):
        locked_transactions = self._test_lock(already_locked_count=0)

        # check logs
        self.assertEqual(
            Log.objects.filter(
                user=self.logged_in_user,
                action=LOG_ACTIONS.LOCKED,
                transaction__id__in=locked_transactions.values_list('id', flat=True)
            ).count(),
            locked_transactions.count()
        )

    def test_lock_with_max_locked_already(self):
        self._test_lock(already_locked_count=LOCK_LIMIT)

    def test_lock_with_some_locked_already(self):
        self._test_lock(already_locked_count=(LOCK_LIMIT/2))

    def test_lock_with_some_locked_already_but_none_available(self):
        self._test_lock(already_locked_count=(LOCK_LIMIT/2), available_count=0)


class UnlockTransactionTestCase(
    CashbookTransactionRejectsRequestsWithoutPermissionTestMixin,
    BaseTransactionViewTestCase
):
    ENDPOINT_VERB = 'post'

    def _get_url(self):
        return reverse('cashbook:transaction-unlock')

    def test_can_unlock_somebody_else_s_transactions(self):
        logged_in_user = self.prison_clerks[0]
        logged_in_user.prisonusermapping.prisons.add(*self.prisons)
        locked_qs = self._get_locked_transactions_qs(self.prisons)

        to_unlock = list(locked_qs.values_list('id', flat=True))
        response = self.client.post(
            self._get_url(),
            {'transaction_ids': to_unlock},
            format='json',
            HTTP_AUTHORIZATION=self.get_http_authorization_for_user(logged_in_user)
        )

        self.assertEqual(response.status_code, status.HTTP_303_SEE_OTHER)
        self.assertEqual(
            urlsplit(response['Location']).path,
            reverse('cashbook:transaction-list')
        )

        self.assertEqual(locked_qs.count(), 0)

        # check logs
        self.assertEqual(
            Log.objects.filter(
                user=logged_in_user,
                action=LOG_ACTIONS.UNLOCKED,
                transaction__id__in=to_unlock
            ).count(),
            len(to_unlock)
        )

    def test_cannot_unlock_somebody_else_s_transactions_in_different_prison(self):
        # logged-in user managing prison #0
        logged_in_user = self.prison_clerks[0]
        logged_in_user.prisonusermapping.prisons.clear()
        logged_in_user.prisonusermapping.prisons.add(self.prisons[0])

        # other user managing prison #1
        other_user = self.prison_clerks[1]
        other_user.prisonusermapping.prisons.add(self.prisons[1])

        locked_qs = self._get_locked_transactions_qs(self.prisons, other_user)
        locked_qs.update(prison=self.prisons[1])

        to_unlock = locked_qs.values_list('id', flat=True)
        response = self.client.post(
            self._get_url(),
            {'transaction_ids': to_unlock},
            format='json',
            HTTP_AUTHORIZATION=self.get_http_authorization_for_user(logged_in_user)
        )

        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        errors = response.data['errors']
        self.assertEqual(len(errors), 1)
        self.assertEqual(errors[0]['msg'], 'Some transactions could not be unlocked.')
        self.assertEqual(errors[0]['ids'], sorted(to_unlock))

    def test_cannot_unlock_credited_transactions(self):
        logged_in_user = self.prison_clerks[0]
        managing_prisons = list(get_prisons_for_user(logged_in_user))

        locked_qs = self._get_locked_transactions_qs(managing_prisons, user=logged_in_user)
        credited_qs = self._get_credited_transactions_qs(managing_prisons, user=logged_in_user)

        locked_ids = list(locked_qs.values_list('id', flat=True))
        credited_ids = list(credited_qs.values_list('id', flat=True)[:1])

        response = self.client.post(
            self._get_url(),
            {'transaction_ids': locked_ids + credited_ids},
            format='json',
            HTTP_AUTHORIZATION=self.get_http_authorization_for_user(logged_in_user)
        )

        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        errors = response.data['errors']
        self.assertEqual(len(errors), 1)
        self.assertEqual(errors[0]['msg'], 'Some transactions could not be unlocked.')
        self.assertEqual(errors[0]['ids'], sorted(credited_ids))

    @mock.patch('transaction.api.cashbook.views.transaction_prisons_need_updating')
    def test_unlock_sends_transaction_prisons_need_updating_signal(
        self, mocked_transaction_prisons_need_updating
    ):
        logged_in_user = self.prison_clerks[0]
        logged_in_user.prisonusermapping.prisons.add(*self.prisons)
        locked_qs = self._get_locked_transactions_qs(self.prisons)

        response = self.client.post(
            self._get_url(),
            {'transaction_ids': list(locked_qs.values_list('id', flat=True))},
            format='json',
            HTTP_AUTHORIZATION=self.get_http_authorization_for_user(logged_in_user)
        )

        self.assertEqual(response.status_code, status.HTTP_303_SEE_OTHER)

        mocked_transaction_prisons_need_updating.send.assert_called_with(sender=Transaction)


class CreditTransactionTestCase(
    CashbookTransactionRejectsRequestsWithoutPermissionTestMixin,
    BaseTransactionViewTestCase
):
    ENDPOINT_VERB = 'patch'

    def _get_url(self, **filters):
        return reverse('cashbook:transaction-list')

    def test_credit_uncredit_transactions(self):
        logged_in_user = self.prison_clerks[0]
        managing_prisons = list(get_prisons_for_user(logged_in_user))

        locked_qs = self._get_locked_transactions_qs(managing_prisons, logged_in_user)
        credited_qs = self._get_credited_transactions_qs(managing_prisons, logged_in_user)

        self.assertTrue(locked_qs.count() > 0)
        self.assertTrue(credited_qs.count() > 0)

        to_credit = list(locked_qs.values_list('id', flat=True))
        to_uncredit = list(credited_qs.values_list('id', flat=True))

        data = [
            {'id': t_id, 'credited': True} for t_id in to_credit
        ] + [
            {'id': t_id, 'credited': False} for t_id in to_uncredit
        ]

        response = self.client.patch(
            self._get_url(), data=data,
            format='json',
            HTTP_AUTHORIZATION=self.get_http_authorization_for_user(logged_in_user)
        )

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

        # check db
        self.assertEqual(
            credited_qs.filter(id__in=to_credit).count(), len(to_credit)
        )
        self.assertEqual(
            locked_qs.filter(id__in=to_uncredit).count(), len(to_uncredit)
        )

        # check logs
        self.assertEqual(
            Log.objects.filter(
                user=logged_in_user,
                action=LOG_ACTIONS.CREDITED,
                transaction__id__in=to_credit
            ).count(),
            len(to_credit)
        )

        self.assertEqual(
            Log.objects.filter(
                user=logged_in_user,
                action=LOG_ACTIONS.UNCREDITED,
                transaction__id__in=to_uncredit
            ).count(),
            len(to_uncredit)
        )

    def test_cannot_credit_somebody_else_s_transactions(self):
        logged_in_user = self.prison_clerks[0]
        other_user = self.prison_clerks[1]

        locked_qs = self._get_locked_transactions_qs(self.prisons, logged_in_user)
        credited_qs = self._get_credited_transactions_qs(self.prisons, logged_in_user)
        locked_by_other_user_qs = self._get_locked_transactions_qs(self.prisons, other_user)

        credited = credited_qs.count()

        locked_by_other_user_ids = list(locked_by_other_user_qs.values_list('id', flat=True))
        data = [
            {'id': t_id, 'credited': True}
            for t_id in locked_qs.values_list('id', flat=True)
        ] + [
            {'id': t_id, 'credited': True}
            for t_id in locked_by_other_user_ids
        ]

        response = self.client.patch(
            self._get_url(), data=data,
            format='json',
            HTTP_AUTHORIZATION=self.get_http_authorization_for_user(logged_in_user)
        )

        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        errors = response.data['errors']
        self.assertEqual(len(errors), 1)
        self.assertEqual(errors[0]['msg'], 'Some transactions could not be credited.')
        self.assertEqual(errors[0]['ids'], sorted(locked_by_other_user_ids))

        # nothing changed in db
        self.assertEqual(credited_qs.count(), credited)

    def test_cannot_credit_non_locked_transactions(self):
        logged_in_user = self.prison_clerks[0]
        managing_prisons = list(get_prisons_for_user(logged_in_user))

        locked_qs = self._get_locked_transactions_qs(managing_prisons, logged_in_user)
        credited_qs = self._get_credited_transactions_qs(self.prisons, logged_in_user)
        available_qs = self._get_available_transactions_qs(managing_prisons)

        credited = credited_qs.count()

        available_ids = available_qs.values_list('id', flat=True)
        data = [
            {'id': t_id, 'credited': True}
            for t_id in locked_qs.values_list('id', flat=True)
        ] + [
            {'id': t_id, 'credited': True}
            for t_id in available_ids
        ]

        response = self.client.patch(
            self._get_url(), data=data,
            format='json',
            HTTP_AUTHORIZATION=self.get_http_authorization_for_user(logged_in_user)
        )

        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        errors = response.data['errors']
        self.assertEqual(len(errors), 1)
        self.assertEqual(errors[0]['msg'], 'Some transactions could not be credited.')
        self.assertEqual(errors[0]['ids'], sorted(available_ids))

        # nothing changed in db
        self.assertEqual(credited_qs.count(), credited)

    def test_invalid_format(self):
        logged_in_user = self.prison_clerks[0]

        response = self.client.patch(
            self._get_url(), data={},
            format='json',
            HTTP_AUTHORIZATION=self.get_http_authorization_for_user(logged_in_user)
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_missing_ids(self):
        logged_in_user = self.prison_clerks[0]

        response = self.client.patch(
            self._get_url(), data=[
                {'credited': True}
            ],
            format='json',
            HTTP_AUTHORIZATION=self.get_http_authorization_for_user(logged_in_user)
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_misspelt_credit(self):
        logged_in_user = self.prison_clerks[0]
        managing_prisons = list(get_prisons_for_user(logged_in_user))

        locked_qs = self._get_locked_transactions_qs(managing_prisons, logged_in_user)

        data = [
            {'id': t_id, 'credted': True}
            for t_id in locked_qs.values_list('id', flat=True)
        ]

        response = self.client.patch(
            self._get_url(), data=data,
            format='json',
            HTTP_AUTHORIZATION=self.get_http_authorization_for_user(logged_in_user)
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
