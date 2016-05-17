from django.db import transaction

from rest_framework import serializers

from credit.signals import credit_prisons_need_updating

from .models import PrisonerLocation, Prison


class PrisonSerializer(serializers.ModelSerializer):

    class Meta:
        model = Prison
        fields = (
            'nomis_id',
            'general_ledger_code',
            'name',
            'region',
            'gender',
        )


class PrisonerLocationListSerializer(serializers.ListSerializer):

    @transaction.atomic
    def create(self, validated_data):
        locations = [
            PrisonerLocation(**item) for item in validated_data
        ]

        # delete all current records and insert new batch
        PrisonerLocation.objects.all().delete()
        objects = PrisonerLocation.objects.bulk_create(locations)

        credit_prisons_need_updating.send(sender=PrisonerLocation)

        return objects


class PrisonerLocationSerializer(serializers.ModelSerializer):

    class Meta:
        model = PrisonerLocation
        list_serializer_class = PrisonerLocationListSerializer
        fields = (
            'prisoner_name',
            'prisoner_number',
            'prisoner_dob',
            'prison',
        )


class PrisonerValiditySerializer(serializers.ModelSerializer):
    class Meta:
        model = PrisonerLocation
        fields = (
            'prisoner_number',
            'prisoner_dob',
        )
