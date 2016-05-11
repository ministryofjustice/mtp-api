from django.db import models, connection

from .constants import LOG_ACTIONS, CREDIT_STATUS


class CreditQuerySet(models.QuerySet):

    def available(self):
        return self.filter(**self.model.STATUS_LOOKUP[CREDIT_STATUS.AVAILABLE])

    def locked(self):
        return self.filter(**self.model.STATUS_LOOKUP[CREDIT_STATUS.LOCKED])

    def credited(self):
        return self.filter(**self.model.STATUS_LOOKUP[CREDIT_STATUS.CREDITED])

    def refunded(self):
        return self.filter(**self.model.STATUS_LOOKUP[CREDIT_STATUS.REFUNDED])

    def refund_pending(self):
        return self.filter(**self.model.STATUS_LOOKUP[CREDIT_STATUS.REFUND_PENDING])

    def locked_by(self, user):
        return self.filter(owner=user)


class CreditManager(models.Manager):

    def update_prisons(self):
        cursor = connection.cursor()

        cursor.execute(
            "UPDATE credit_credit "
            "SET prison_id = pl.prison_id, prisoner_name = pl.prisoner_name "
            "FROM credit_credit AS c LEFT OUTER JOIN prison_prisonerlocation AS pl "
            "ON c.prisoner_number = pl.prisoner_number AND c.prisoner_dob = pl.prisoner_dob "
            "WHERE c.owner_id IS NULL AND c.resolution = 'pending' "
            "AND c.reconciled is False AND credit_credit.id = c.id "
        )


class LogManager(models.Manager):

    def credit_created(self, credit, by_user=None):
        self.create(
            credit=credit,
            action=LOG_ACTIONS.CREATED,
            user=by_user
        )

    def credit_locked(self, credit, by_user):
        self.create(
            credit=credit,
            action=LOG_ACTIONS.LOCKED,
            user=by_user
        )

    def credit_unlocked(self, credit, by_user):
        self.create(
            credit=credit,
            action=LOG_ACTIONS.UNLOCKED,
            user=by_user
        )

    def credit_credited(self, credit, by_user, credited=True):
        action = LOG_ACTIONS.CREDITED if credited else LOG_ACTIONS.UNCREDITED
        self.create(
            credit=credit,
            action=action,
            user=by_user
        )

    def credit_refunded(self, credit, by_user):
        self.create(
            credit=credit,
            action=LOG_ACTIONS.REFUNDED,
            user=by_user
        )

    def credit_reconciled(self, credit, by_user):
        self.create(
            credit=credit,
            action=LOG_ACTIONS.RECONCILED,
            user=by_user
        )