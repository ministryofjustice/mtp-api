from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _

from model_utils.models import TimeStampedModel


class Prison(TimeStampedModel):
    nomis_id = models.CharField(max_length=3, primary_key=True, verbose_name='NOMIS id')
    general_ledger_code = models.CharField(max_length=3)
    name = models.CharField(max_length=500)
    region = models.CharField(max_length=255, blank=True)
    gender = models.CharField(max_length=1, blank=True, choices=(('m', _('Male')), ('f', _('Female'))))

    def __str__(self):
        return self.name


class PrisonerLocation(TimeStampedModel):
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)

    prisoner_name = models.CharField(blank=True, max_length=250)
    prisoner_number = models.CharField(max_length=250)  # TODO: shouldn't this be unique?
    prisoner_dob = models.DateField()

    prison = models.ForeignKey(Prison, on_delete=models.CASCADE)

    class Meta:
        index_together = (
            ('prisoner_number', 'prisoner_dob'),
        )

    def __str__(self):
        return '%s (%s)' % (self.prisoner_name, self.prisoner_number)
