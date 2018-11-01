from django.db import models
from django.db.transaction import atomic
from rest_framework import serializers

from credit.models import Credit
from credit.serializers import SecurityCreditSerializer
from disbursement.models import Disbursement
from disbursement.serializers import DisbursementSerializer
from .models import Subscription, Parameter, Event


class ParameterSerializer(serializers.ModelSerializer):
    class Meta:
        model = Parameter
        fields = (
            'field',
            'value',
            'exclude',
        )


class SubscriptionSerializer(serializers.ModelSerializer):
    parameters = ParameterSerializer(many=True, required=False)

    class Meta:
        model = Subscription
        fields = (
            'id',
            'rule',
            'parameters',
        )

    @atomic
    def create(self, validated_data):
        user = self.context['request'].user
        validated_data['user'] = user
        parameters = validated_data.pop('parameters')
        subscription = super().create(validated_data)
        for parameter in parameters:
            Parameter.objects.create(
                subscription=subscription,
                **parameter
            )
        return subscription


class OrderedListSerializer(serializers.ListSerializer):
    def to_representation(self, data):
        data = data.all().order_by('-triggering') if isinstance(data, models.Manager) else data
        return super().to_representation(data)


class OrderedCreditSerializer(SecurityCreditSerializer):
    def to_representation(self, data):
        return super().to_representation(data.credit)

    class Meta:
        model = Credit
        fields = SecurityCreditSerializer.Meta.fields
        list_serializer_class = OrderedListSerializer


class OrderedDisbursementSerializer(DisbursementSerializer):
    def to_representation(self, data):
        return super().to_representation(data.disbursement)

    class Meta:
        model = Disbursement
        fields = DisbursementSerializer.Meta.fields
        list_serializer_class = OrderedListSerializer


class EventSerializer(serializers.ModelSerializer):
    credits = OrderedCreditSerializer(source='eventcredit_set', many=True)
    disbursements = OrderedDisbursementSerializer(source='eventdisbursement_set', many=True)
    rule = serializers.CharField(source='subscription.rule')

    class Meta:
        model = Event
        fields = (
            'ref_number',
            'credits',
            'disbursements',
            'created',
            'rule',
        )