from rest_framework import mixins, viewsets, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.decorators import list_route
from rest_framework.exceptions import ParseError

from mtp_auth.permissions import BankAdminClientIDPermissions
from transaction.models import Transaction
from .permissions import TransactionPermissions
from .serializers import CreateTransactionSerializer, \
    UpdateRefundedTransactionSerializer, TransactionSerializer, \
    ReconcileTransactionSerializer


class TransactionView(mixins.CreateModelMixin, mixins.UpdateModelMixin,
                      mixins.ListModelMixin, viewsets.GenericViewSet):

    permission_classes = (
        IsAuthenticated, BankAdminClientIDPermissions,
        TransactionPermissions
    )

    def get_queryset(self):
        queryset = Transaction.objects.all()

        status = self.request.query_params.get('status', None)
        if status:
            values = [v.lower() for v in status.split(',')]

            if len(values) > 0:
                try:
                    queryset = Transaction.objects.filter(
                        **Transaction.STATUS_LOOKUP[values[0]])
                    for value in values[1:]:
                        queryset = queryset | Transaction.objects.filter(
                            **Transaction.STATUS_LOOKUP[value])
                except KeyError:
                    raise ParseError()

        return queryset

    @list_route(methods=['patch'])
    def patch_refunded(self, request, *args, **kwargs):
        try:
            return self.partial_update(request, *args, **kwargs)
        except Transaction.DoesNotExist as e:
            return Response(
                data={
                    'errors': [
                        {
                            'msg': 'Some transactions could not be refunded',
                            'ids': sorted(e.args[0])
                        }
                    ]
                },
                status=status.HTTP_409_CONFLICT
            )

    def get_serializer(self, *args, **kwargs):
        many = kwargs.pop('many', True)
        return super(TransactionView, self).get_serializer(many=many,
                                                           *args, **kwargs)

    def get_object(self):
        """Return dummy object to allow for mass patching"""
        return Transaction()

    def get_serializer_class(self):
        if self.request.method == 'POST':
            return CreateTransactionSerializer
        elif self.request.method == 'PATCH':
            return UpdateRefundedTransactionSerializer
        elif self.request.method == 'GET':
            if self.request.user.has_perm(
                    'transaction.view_bank_details_transaction'):
                return TransactionSerializer
            else:
                return ReconcileTransactionSerializer
