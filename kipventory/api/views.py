from rest_framework import generics
from rest_framework import status
from rest_framework.response import Response
from rest_framework import authentication, permissions
from rest_framework.decorators import api_view, permission_classes
from rest_framework.exceptions import NotFound
from rest_framework.authtoken.models import Token
from rest_framework.views import APIView

from rest_framework.filters import BaseFilterBackend
from rest_framework.schemas import coreapi

from django.contrib.auth import authenticate, login
from django.contrib.auth.models import User
from django.shortcuts import redirect, render, get_object_or_404
from django.contrib import messages
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.db.models import Q, F

from . import models, serializers
from rest_framework import pagination
from datetime import datetime
from django.utils import timezone
from django.utils.crypto import get_random_string
from django.contrib.auth.forms import PasswordResetForm
from django.contrib.auth.views import password_reset, password_reset_confirm
from django.http import HttpResponse
import dateutil.parser
import json, requests, csv, os
from django.core.mail import EmailMultiAlternatives
from django.conf import settings

class CustomPagination(pagination.PageNumberPagination):
    page_query_param = 'page'
    page_size_query_param = 'itemsPerPage'

    def get_paginated_response(self, data):
        return Response({
             "count": self.page.paginator.count,
             "num_pages": self.page.paginator.num_pages,
             "results": data
            })

class ItemListFilter(BaseFilterBackend):
  def get_schema_fields(self, view):
    fields = [
      coreapi.Field(name="search", description="Filter by name or model no", required=False, location='query'),
      coreapi.Field(name="tags", description="Filter by tag (comma separated)", required=False, location='query'),
      coreapi.Field(name="excludeTags", description="Filter by excluding tags (comma separated)", required=False, location='query'),
      coreapi.Field(name="all", description="Set this to true to get all items instead of paginated.", required=False, location='query'),
    ]

    return fields

class ItemListCreate(generics.GenericAPIView):
    permission_classes = (permissions.IsAuthenticated,)
    pagination_class = CustomPagination
    filter_backends = (ItemListFilter,)

    def get_queryset(self):
        return models.Item.objects.all()

    def get_serializer_class(self):
        return serializers.ItemSerializer

    def filter_queryset(self, queryset, request):
        # Search and Tag Filtering
        search = self.request.query_params.get("search")
        include_tags = self.request.query_params.get("include_tags")
        exclude_tags = self.request.query_params.get("exclude_tags")
        low_stock = self.request.query_params.get("low_stock", False)
        low_stock = True if low_stock == "true" else False

        q_objs = Q()

        # Search filter
        if search is not None and search != '':
            q_objs &= (Q(name__icontains=search) | Q(model_no__icontains=search))
            queryset = queryset.filter(q_objs).order_by('name')

        # Tags filter
        if include_tags is not None and include_tags != '':
            tagsArray = include_tags.split(",")
            for tag in tagsArray:
                queryset = queryset.filter(tags__name=tag)

        # Exclude tags filter
        if exclude_tags is not None and exclude_tags != '':
            excludeTagsArray = exclude_tags.split(",")
            for tag in excludeTagsArray:
                queryset = queryset.exclude(tags__name=tag)

        # Low stock filter
        if low_stock:
            print(low_stock)
            queryset = queryset.filter(quantity__lte=F('minimum_stock'))


        return queryset

    def get(self, request, format=None):
        # CHECK PERMISSION
        queryset = self.get_queryset()

        all_items = request.query_params.get('all', False)
        if all_items:
            serializer = self.get_serializer(instance=queryset, many=True)
            d = {"count": len(serializer.data), 'num_pages': 1, "results": serializer.data}
            return Response(d)

        queryset = self.filter_queryset(queryset, request)

        # Pagination
        paginated_queryset = self.paginate_queryset(queryset)
        serializer = self.get_serializer(instance=paginated_queryset, many=True)
        response = self.get_paginated_response(serializer.data)
        return response

    # manager restricted
    def post(self, request, format=None):
        if not (request.user.is_staff or request.user.is_superuser):
            d = {"error": "Permission denied."}
            return Response(d, status=status.HTTP_403_FORBIDDEN)

        data = request.data.copy()

        serializer = self.get_serializer(data=data)
        if serializer.is_valid():
            serializer.save()
            itemCreationLog(serializer.data, request.user.pk)
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class ItemDetailModifyDelete(generics.GenericAPIView):
    permissions = (permissions.IsAuthenticated,)

    def get_instance(self, item_name):
        try:
            return models.Item.objects.get(name=item_name)
        except models.Item.DoesNotExist:
            raise NotFound('Item {} not found.'.format(item_name))

    def get_serializer_class(self):
        return serializers.ItemSerializer

    def get_queryset(self):
        return models.Item.objects.all()

    def get(self, request, item_name, format=None):
        item = self.get_instance(item_name=item_name)
        serializer = self.get_serializer(instance=item)
        return Response(serializer.data)

    # manager restricted
    def put(self, request, item_name, format=None):
        if not (request.user.is_staff or request.user.is_superuser):
            d = {"error": "Manager permissions required."}
            return Response(d, status=status.HTTP_403_FORBIDDEN)

        data = request.data.copy()
        item = self.get_instance(item_name=item_name)

        serializer = self.get_serializer(instance=item, data=data, partial=True)
        if serializer.is_valid():
            serializer.save()
            itemModificationLog(serializer.data, request.user.pk)
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    # manager restricted
    def delete(self, request, item_name, format=None):
        if not (request.user.is_superuser):
            d = {"error": "Administrator permissions required."}
            return Response(d, status=status.HTTP_403_FORBIDDEN)

        item = self.get_instance(item_name=item_name)
        item.delete()
        for r in models.Request.objects.all():
            if (r.requested_items.count() == 0):
                r.delete()
        itemDeletionLog(item_name, request.user.pk)
        return Response(status=status.HTTP_204_NO_CONTENT)

class AssetList(generics.GenericAPIView):
    permission_classes = (permissions.IsAuthenticated,)
    pagination_class = CustomPagination

    def get_queryset(self):
        item_name = self.kwargs['item_name']
        return models.Asset.objects.filter(item__name=item_name)

    def get_serializer_class(self):
        return serializers.AssetSerializer

    def get(self, request, item_name, format=None):
        try:
            item = models.Item.objects.get(name=item_name)
            if not item.has_assets:
                raise NotFound("Item '{}' has no tracked instances.".format(item_name))
        except models.Item.DoesNotExist:
            raise NotFound("Item '{}' not found.".format(item_name))

        # CHECK PERMISSION
        queryset = self.get_queryset()

        all_assets = request.query_params.get('all', False)
        if all_assets:
            serializer = self.get_serializer(instance=queryset, many=True)
            d = {"count": len(serializer.data), 'num_pages': 1, "results": serializer.data}
            return Response(d)

        tag_name = request.query_params.get('search', False)
        if tag_name:
            print(tag_name)
            queryset = queryset.filter(tag__icontains=tag_name)

        status = request.query_params.get('status', False)
        if status:
            status = status.lower().strip().replace(" ", "")
            if status == "instock":
                queryset = queryset.filter(status=models.IN_STOCK)
            elif status == "loaned":
                queryset = queryset.filter(status=models.LOANED)
            elif status == "disbursed":
                queryset = queryset.filter(status=models.DISBURSED)


        # Pagination
        paginated_queryset = self.paginate_queryset(queryset)
        serializer = self.get_serializer(instance=paginated_queryset, many=True)
        response = self.get_paginated_response(serializer.data)
        return response

class AssetDetailModifyDelete(generics.GenericAPIView):
    permissions = (permissions.IsAuthenticated,)

    def get_instance(self, asset_tag):
        try:
            return models.Asset.objects.get(tag=asset_tag)
        except models.Asset.DoesNotExist:
            raise NotFound('Asset {} not found.'.format(asset_tag))

    def get_serializer_class(self):
        return serializers.AssetSerializer

    def get_queryset(self):
        return models.Asset.objects.all()

    def get(self, request, item_name, asset_tag, format=None):
        try:
            item = models.Item.objects.get(name=item_name)
            if not item.has_assets:
                return Response({"item": ["Item '{}' has no tracked instances.".format(item_name)]}, status=status.HTTP_404_NOT_FOUND)
        except:
            raise NotFound("Item '{}' not found.".format(item_name))

        asset = self.get_instance(asset_tag=asset_tag)
        serializer = self.get_serializer(instance=asset)
        return Response(serializer.data)

    # manager restricted
    def put(self, request, item_name, asset_tag, format=None):
        if not (request.user.is_staff or request.user.is_superuser):
            d = {"error": "Manager permissions required."}
            return Response(d, status=status.HTTP_403_FORBIDDEN)

        try:
            item = models.Item.objects.get(name=item_name)
            if not item.has_assets:
                return Response({"item": ["Item '{}' has no tracked instances.".format(item_name)]}, status=status.HTTP_404_NOT_FOUND)
        except:
            raise NotFound("Item '{}' not found.".format(item_name))



        data = request.data.copy()
        asset = self.get_instance(asset_tag=asset_tag)

        print(data)
        print(asset)
        

        serializer = self.get_serializer(instance=asset, data=data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, item_name, asset_tag, format=None):
        if not (request.user.is_staff or request.user.is_superuser):
            d = {"error": "Manager permissions required."}
            return Response(d, status=status.HTTP_403_FORBIDDEN)

        try:
            item = models.Item.objects.get(name=item_name)
            if not item.has_assets:
                return Response({"item": ["Item '{}' has no tracked instances.".format(item_name)]}, status=status.HTTP_404_NOT_FOUND)
        except:
            raise NotFound("Item '{}' not found.".format(item_name))

        asset = self.get_instance(asset_tag=asset_tag)
        asset.delete()

        return Response(status=status.HTTP_204_NO_CONTENT)



class AddItemToCart(generics.GenericAPIView):
    permissions = (permissions.IsAuthenticated,)

    def get_item(self, item_name):
        try:
            return models.Item.objects.get(name=item_name)
        except models.Item.DoesNotExist:
            raise NotFound("Item '{}' not found.".format(item_name))

    def get_serializer_class(self):
        return serializers.CartItemSerializer

    def get_queryset(self):
        return models.CartItem.objects.filter(owner__pk=self.request.user.pk)

    # add an item to your cart
    # need to check if item already exists, and update if it does
    def post(self, request, item_name, format=None):
        item = self.get_item(item_name)

        data = request.data.copy()
        data.update({'owner': request.user})
        data.update({'item': item})

        cartitems = self.get_queryset().filter(item__name=item_name)
        if cartitems.count() > 0:
            serializer = self.get_serializer(instance=cartitems.first(), data=data)
        else:
            serializer = self.get_serializer(data=data)

        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class GetOutstandingRequestsByItemFilter(BaseFilterBackend):
  def get_schema_fields(self, view):
    fields = [
      coreapi.Field(name="user", description="Filter by user", required=False, location='query'),
      coreapi.Field(name="type", description="Filter by request type", required=False, location='query'),
    ]

    return fields

class GetOutstandingRequestsByItem(generics.GenericAPIView):
    permissions = (permissions.IsAuthenticated,)
    pagination_class = CustomPagination
    filter_backends = (GetOutstandingRequestsByItemFilter,)

    def get_queryset(self):
        return models.Request.objects.filter(status=models.OUTSTANDING)

    def get_serializer_class(self):
        return serializers.RequestSerializer

    def get(self, request, item_name, format=None):
        requests = self.get_queryset()
        if request.user.is_staff or request.user.is_superuser:
            requests = self.get_queryset().filter(requested_items__item__name=item_name)
        else:
            requests = self.get_queryset().filter(requested_items__item__name=item_name, requester=request.user.pk)

        # Filter by requester
        user = self.request.query_params.get("user", None)
        if user != None and user != "":
            requests = requests.filter(requester__username=user)

        # Filter by request type
        request_type = self.request.query_params.get("type", None)
        if request_type != None and request_type != "":
            requests = requests.filter(requested_items__request_type=request_type)

        # Pagination
        paginated_queryset = self.paginate_queryset(requests)
        serializer = self.get_serializer(instance=paginated_queryset, many=True)
        response = self.get_paginated_response(serializer.data)
        return response

class GetLoansByItemFilter(BaseFilterBackend):
  def get_schema_fields(self, view):
    fields = [
      coreapi.Field(name="user", description="Filter by user", required=False, location='query'),
    ]

    return fields

class GetLoansByItem(generics.GenericAPIView):
    permissions = (permissions.IsAuthenticated,)
    pagination_class = CustomPagination
    filter_backends = (GetLoansByItemFilter,)

    def get_queryset(self):
        return models.Loan.objects.filter(quantity_loaned__gt=F('quantity_returned'))

    def get_serializer_class(self):
        return serializers.LoanSerializer

    def get(self, request, item_name, format=None):
        loans = self.get_queryset()
        if request.user.is_staff or request.user.is_superuser:
            loans = loans.filter(item__name=item_name)
        else:
            loans = loans.filter(item__name=item_name, request__requester=request.user.pk)

        # Filter by loan owner
        user = self.request.query_params.get("user", None)
        if user != None and user != "":
            loans = loans.filter(request__requester__username=user)

        # Pagination
        paginated_queryset = self.paginate_queryset(loans)
        serializer = self.get_serializer(instance=paginated_queryset, many=True)
        response = self.get_paginated_response(serializer.data)
        return response

class GetTransactionsByItemFilter(BaseFilterBackend):
  def get_schema_fields(self, view):
    fields = [
      coreapi.Field(name="category", description="Filter by category (Acquisition, Loss)", required=False, location='query'),
      coreapi.Field(name="administrator", description="Filter by administrator username", required=False, location='query'),
    ]

    return fields

class GetTransactionsByItem(generics.GenericAPIView):
    permissions = (permissions.IsAuthenticated,)
    pagination_class = CustomPagination
    filter_backends = (GetTransactionsByItemFilter,)

    def get_queryset(self):
        return models.Transaction.objects.filter()

    def get_serializer_class(self):
        return serializers.TransactionSerializer

    def get(self, request, item_name, format=None):
        if not (request.user.is_staff or request.user.is_superuser):
            d = {"error": "Manager permissions required."}
            return Response(d, status=status.HTTP_403_FORBIDDEN)

        transactions = self.get_queryset()
        transactions = transactions.filter(item__name=item_name)

        # Filter by category (acquisition, loss)
        category = request.query_params.get('category', None)
        if category != None and category != "":
            if category in set([models.ACQUISITION, models.LOSS]):
                transactions = transactions.filter(category=category)

        administrator = request.query_params.get('administrator', None)
        if administrator != None and administrator != "":
            try:
                administrator = User.objects.get(username=administrator)
                transactions = transactions.filter(administrator=administrator)
            except User.DoesNotExist:
                pass


        # Pagination
        paginated_queryset = self.paginate_queryset(transactions)
        serializer = self.get_serializer(instance=paginated_queryset, many=True)
        response = self.get_paginated_response(serializer.data)
        return response

class GetItemStacks(generics.GenericAPIView):
    permissions = (permissions.IsAuthenticated,)
    pagination_class = CustomPagination

    def get_queryset(self):
        return models.Request.objects.all()

    def get_serializer_class(self):
        return serializers.RequestSerializer

    def get(self, request, item_name, format=None):
        item = None
        try:
            item = models.Item.objects.get(name=item_name)
        except models.Item.DoesNotExist:
            raise NotFound("Item '{}' not found.".format(item_name))

        requests = models.Request.objects.filter(status='O', requested_items__item__name=item_name)
        if not (request.user.is_staff or request.user.is_superuser):
            requests = requests.filter(requester=request.user.pk)
        rq = 0
        for r in requests.all():
            for ri in r.requested_items.all():
                if (ri.item.name == item_name):
                    rq += ri.quantity

        loans = models.Loan.objects.filter(item__name=item_name, quantity_loaned__gt=F('quantity_returned'))
        if not (request.user.is_staff or request.user.is_superuser):
            loans = loans.filter(request__requester=request.user.pk)
        lq = 0
        for l in loans.all():
            lq += (l.quantity_loaned - l.quantity_returned)

        disbursements = models.Disbursement.objects.filter(item__name=item_name)
        if not (request.user.is_staff or request.user.is_superuser):
            disbursements = disbursements.filter(request__requester=request.user.pk)
        dq = 0
        for d in disbursements.all():
            dq += d.quantity

        cart = models.CartItem.objects.filter(owner__pk=request.user.pk, item__name=item_name)
        cq = 0
        for c in cart.all():
            cq += c.quantity

        data = {
            "in_stock": item.quantity,
            "requested": rq,
            "loaned": lq,
            "disbursed": dq,
            "in_cart": cq,
        }
        return Response(data)


class CustomFieldListCreate(generics.GenericAPIView):
    permissions = (permissions.IsAuthenticated,)
    pagination_class = CustomPagination

    def get_serializer_class(self):
        return serializers.CustomFieldSerializer

    def get_queryset(self):
        return models.CustomField.objects.all()

    def get(self, request, format=None):
        queryset = self.get_queryset()

        if not (request.user.is_staff or request.user.is_superuser):
            queryset = queryset.filter(private=False)

        asset_tracked = request.query_params.get('asset_tracked', None)
        if asset_tracked:
            queryset = queryset.filter(asset_tracked=True)

        all_fields = request.query_params.get('all', None)
        if all_fields is not None:
            serializer = self.get_serializer(instance=queryset, many=True)
            return Response({"count": 1, "num_pages": 1, "results": serializer.data})

        paginated_queryset = self.paginate_queryset(queryset)
        serializer = self.get_serializer(instance=paginated_queryset, many=True)
        response = self.get_paginated_response(serializer.data)
        return response

    def post(self, request, format=None):
        if not (request.user.is_staff or request.user.is_superuser):
            d = {"error": "Manager permissions required."}
            return Response(d, status=status.HTTP_403_FORBIDDEN)

        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class CustomFieldDetailDelete(generics.GenericAPIView):
    permissions = (permissions.IsAuthenticated,)

    def get_instance(self, field_name):
        try:
            return models.CustomField.objects.get(name=field_name)
        except:
            raise NotFound("Field '{}' not found.".format(field_name))

    def get_serializer_class(self):
        return serializers.CustomFieldSerializer

    def get_queryset(self):
        return models.CustomField.objects.all()

    def get(self, request, field_name, format=None):
        if not (request.user.is_staff or request.user.is_superuser):
            d = {"error": "Manager permissions required."}
            return Response(d, status=status.HTTP_403_FORBIDDEN)
        custom_field = self.get_instance(field_name=field_name)
        serializer = self.get_serializer(instance=custom_field)
        return Response(serializer.data)

    def delete(self, request, field_name, format=None):
        if not (request.user.is_superuser):
            d = {"error": "Manager permissions required."}
            return Response(d, status=status.HTTP_403_FORBIDDEN)
        custom_field = self.get_instance(field_name=field_name)
        custom_field.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class CartItemList(generics.GenericAPIView):
    permission_classes = (permissions.IsAuthenticated,)

    def get_serializer_class(self):
        return serializers.CartItemSerializer

    # restrict this queryset - each user can only see his/her own cart items
    def get_queryset(self):
        return models.CartItem.objects.filter(owner__pk=self.request.user.pk)

    # view all items in your cart
    def get(self, request, format=None):
        queryset = self.get_queryset()
        serializer = self.get_serializer(instance=queryset, many=True)
        return Response(serializer.data)


class CartItemDetailModifyDelete(generics.GenericAPIView):
    permission_classes = (permissions.IsAuthenticated,)

    def get_instance(self, item_name):
        try:
            return self.get_queryset().get(item__name=item_name)
        except models.CartItem.DoesNotExist:
            raise NotFound('Cart item {} not found.'.format(item_name))

    def get_serializer_class(self):
        return serializers.CartItemSerializer

    # restrict this queryset - each user can only see his/her own cart items
    def get_queryset(self):
        return models.CartItem.objects.filter(owner__pk=self.request.user.pk)

    # view all items in your cart
    def get(self, request, item_name, format=None):
        cartitem = self.get_instance(item_name=item_name)
        serializer = self.get_serializer(instance=cartitem)
        return Response(serializer.data)

    # modify quantity of an item in your cart
    def put(self, request, item_name, format=None):
        cartitem = self.get_instance(item_name=item_name)
        data = request.data.copy()

        data.update({'owner': request.user})
        data.update({'item': cartitem.item})

        serializer = self.get_serializer(instance=cartitem, data=data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    # remove an item from your cart
    def delete(self, request, item_name, format=None):
        cartitem = self.get_instance(item_name=item_name)
        cartitem.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

class RequestListAllFilter(BaseFilterBackend):
  def get_schema_fields(self, view):
    fields = [
      coreapi.Field(name="status", description="Filter by status (Outstanding, Approved, Denied)", required=False, location='query'),
    ]

    return fields

class RequestListAll(generics.GenericAPIView):
    authentication_classes = (authentication.SessionAuthentication,)
    permissions = (permissions.IsAuthenticated,)
    pagination_class = CustomPagination
    filter_backends = (RequestListAllFilter,)

    def get_queryset(self):
        return models.Request.objects.all()

    def get_serializer_class(self):
        return serializers.RequestSerializer

    def get(self, request, format=None):
        if not (request.user.is_staff or request.user.is_superuser):
            d = {"error": ["Manager permissions required."]}
            return Response(d, status=status.HTTP_403_FORBIDDEN)

        queryset = self.get_queryset()
        status = request.GET.get('status')
        if not (status is None or status=="All" or status==""):
            queryset = models.Request.objects.filter(status=status)

        paginated_queryset = self.paginate_queryset(queryset)
        serializer = self.get_serializer(instance=paginated_queryset, many=True)
        response = self.get_paginated_response(serializer.data)
        return response

class RequestListCreateFilter(BaseFilterBackend):
  def get_schema_fields(self, view):
    fields = [
      coreapi.Field(name="status", description="Filter by status (Outstanding, Approved, Denied)", required=False, location='query'),
    ]

    return fields

class RequestListCreate(generics.GenericAPIView):
    authentication_classes = (authentication.SessionAuthentication,)
    permission_classes = (permissions.IsAuthenticated,)
    pagination_class = CustomPagination
    filter_backends = (RequestListCreateFilter,)

    # restrict this queryset - each user can only see his/her own Requests
    def get_queryset(self):
        return models.Request.objects.filter(requester__pk=self.request.user.pk)

    def get_serializer_class(self):
        return serializers.RequestSerializer

    def get(self, request, format=None):
        queryset = self.get_queryset()

        status = request.GET.get('status')
        if not (status is None or status=="All" or status==""):
            queryset = queryset.filter(status=status)

        # Pagination
        paginated_queryset = self.paginate_queryset(queryset)
        data = []
        for req in paginated_queryset:
            data.append(self.get_serializer(instance=req).data)

        # serializer = self.get_serializer(instance=paginated_queryset, many=True)
        response = self.get_paginated_response(data)
        return response

    # generate a request that contains all items currently in your cart.
    def post(self, request, format=None):
        data = request.data.copy()
        data.update({'requester': request.user})

        cart_items = models.CartItem.objects.filter(owner__pk=self.request.user.pk)
        if cart_items.count() <= 0:
            d = {"error": ["There are no items in your cart. Add an item to your cart in order to request it."]}
            return Response(d, status=status.HTTP_400_BAD_REQUEST)

        serializer = self.get_serializer(data=data)
        if serializer.is_valid():
            request_instance = serializer.save()

        for ci in cart_items:
            req_item = models.RequestedItem.objects.create(request=request_instance,
                                                           item=ci.item,
                                                           quantity=ci.quantity,
                                                           request_type=ci.request_type)
            # Insert Create Log
            # Need {serializer.data, initiating_user_pk, 'Request Created'}
            req_item.save()
            requestItemCreation(req_item, request.user.pk, request_instance)
            ci.delete()

        #todo maybe combine this with the requsetItemCreationLog method (involves refactoring of logs)
        sendEmailForNewRequest(request_instance)

        serializer = self.get_serializer(instance=request_instance)
        return Response(serializer.data)

class RequestDetailModifyDelete(generics.GenericAPIView):
    authentication_classes = (authentication.SessionAuthentication,)
    permission_classes = (permissions.IsAuthenticated,)

    def get_instance(self, request_pk):
        try:
            return models.Request.objects.get(pk=request_pk)
        except models.Request.DoesNotExist:
            raise NotFound('Request with ID {} not found.'.format(request_pk))

    def get_queryset(self):
        return models.Request.objects.filter(requester__pk=self.request.user.pk)

    def get_serializer_class(self):
        if self.request.method == 'PUT':
            return serializers.RequestPUTSerializer
        return serializers.RequestSerializer

    # MANAGER/OWNER LOCKED
    def get(self, request, request_pk, format=None):
        instance = self.get_instance(request_pk)
        # if admin, see any request.
        # if user, only see your requests
        is_owner = (instance.requester.pk == request.user.pk)
        if not (request.user.is_staff or request.user.is_superuser or is_owner):
            d = {"error": ["Manager or owner permissions required."]}
            return Response(d, status=status.HTTP_403_FORBIDDEN)

        serializer = self.get_serializer(instance=instance)
        return Response(serializer.data)

    # MANAGER LOCKED - only admins may change the fields on a request
    def put(self, request, request_pk, format=None):
        if not (request.user.is_staff or request.user.is_superuser):
            d = {"error": ["Manager permissions required."]}
            return Response(d, status=status.HTTP_403_FORBIDDEN)

        instance = self.get_instance(request_pk)
        data = request.data.copy()
        data.update({'administrator': request.user})

        if not (instance.status == 'O'):
            return Response({"status": ["Only outstanding requests may be modified."]})

        serializer = self.get_serializer(instance=instance, data=data, partial=True)

        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    # OWNER LOCKED
    def delete(self, request, request_pk, format=None):
        instance = self.get_instance(request_pk)
        is_owner = (request.user.pk == instance.requester.pk)
        if not (is_owner):
            d = {"error": ["Owner permissions required"]}
            return Response(d, status=status.HTTP_403_FORBIDDEN)

        if not (instance.status == 'O'):
            d = {"error": ["Cannot delete an approved/denied request."]}
            return Response(d, status=status.HTTP_403_FORBIDDEN)

        instance.delete()
        #sendEmailForDeletedOutstandingRequest? Probably not
        # Don't post log here since its as if it never happened
        return Response(status=status.HTTP_204_NO_CONTENT)


class GetBackfillsByRequest(generics.GenericAPIView):
    permissions = (permissions.IsAuthenticated,)
    pagination_class = CustomPagination

    def get_instance(self, request_pk):
        try:
            return models.Request.objects.get(pk=request_pk)
        except models.Request.DoesNotExist:
            raise NotFound('Request with ID {} not found.'.format(request_pk))

    def get_queryset(self):
        return models.Backfill.objects.all()

    def get_serializer_class(self):
        return serializers.BackfillGETSerializer

    def get(self, request, request_pk, format=None):
        instance = self.get_instance(request_pk)
        if (instance.status != models.APPROVED):
            d = {"error": ["Request with ID {} is not approved.".format(request_pk)]}
            return Response(d, status=status.HTTP_204_NO_CONTENT)

        is_owner = (instance.requester.pk == request.user.pk)
        if not (request.user.is_staff or request.user.is_superuser or is_owner):
            d = {"error": ["Manager or owner permissions required."]}
            return Response(d, status=status.HTTP_403_FORBIDDEN)

        backfills = self.get_queryset().filter(request__pk=instance.pk).distinct()

        # filter by status
        backfill_status = request.query_params.get('status', "")
        if backfill_status != "":
            if (backfill_status == models.AWAITING_ITEMS):
                backfills = backfills.filter(status=models.AWAITING_ITEMS).distinct()
            elif (backfill_status == models.SATISFIED):
                backfills = backfills.filter(status=models.SATISFIED).distinct()

        # Pagination
        paginated_queryset = self.paginate_queryset(backfills)
        serializer = self.get_serializer(instance=paginated_queryset, many=True)
        response = self.get_paginated_response(serializer.data)
        return response

class GetBackFillRequestsByRequest(generics.GenericAPIView):
    permissions = (permissions.IsAuthenticated,)
    pagination_class = CustomPagination

    def get_instance(self, request_pk):
        try:
            return models.Request.objects.get(pk=request_pk)
        except models.Request.DoesNotExist:
            raise NotFound('Request with ID {} not found.'.format(request_pk))

    def get_queryset(self):
        return models.BackfillRequest.objects.all()

    def get_serializer_class(self):
        return serializers.BackfillRequestGETSerializer

    def get(self, request, request_pk, format=None):
        instance = self.get_instance(request_pk)
        if (instance.status != models.APPROVED):
            d = {"error": ["Request with ID {} is not approved.".format(request_pk)]}
            return Response(d, status=status.HTTP_204_NO_CONTENT)

        is_owner = (instance.requester.pk == request.user.pk)
        if not (request.user.is_staff or request.user.is_superuser or is_owner):
            d = {"error": ["Manager or owner permissions required."]}
            return Response(d, status=status.HTTP_403_FORBIDDEN)

        backfill_requests = self.get_queryset().filter(loan__request__pk=instance.pk).distinct()

        # filter by status
        status = request.query_params.get('status', "")
        if status != "":
            if (status == models.OUTSTANDING):
                backfill_requests = backfill_requests.filter(status=models.OUTSTANDING).distinct()
            elif (status == models.APPROVED):
                backfill_requests = backfill_requests.filter(status=models.APPROVED).distinct()
            elif (status == models.DENIED):
                backfill_requests = backfill_requests.filter(status=models.DENIED).distinct()

        # Pagination
        paginated_queryset = self.paginate_queryset(backfill_requests)
        serializer = self.get_serializer(instance=paginated_queryset, many=True)
        response = self.get_paginated_response(serializer.data)
        return response

class GetLoansByRequest(generics.GenericAPIView):
    permissions = (permissions.IsAuthenticated,)
    pagination_class = CustomPagination
    filter_backends = (GetLoansByItemFilter,)

    def get_instance(self, request_pk):
        try:
            return models.Request.objects.get(pk=request_pk)
        except models.Request.DoesNotExist:
            raise NotFound('Request with ID {} not found.'.format(request_pk))

    def get_queryset(self):
        return models.Loan.objects.all()

    def get_serializer_class(self):
        return serializers.LoanSerializerNoRequest

    def get(self, request, request_pk, format=None):
        instance = self.get_instance(request_pk)
        if (instance.status != models.APPROVED):
            d = {"error": ["Request with ID {} is not approved.".format(request_pk)]}
            return Response(d, status=status.HTTP_204_NO_CONTENT)

        is_owner = (instance.requester.pk == request.user.pk)
        if not (request.user.is_staff or request.user.is_superuser or is_owner):
            d = {"error": ["Manager or owner permissions required."]}
            return Response(d, status=status.HTTP_403_FORBIDDEN)

        loans = self.get_queryset().filter(request__pk=instance.pk)

        status = request.query_params.get('status', "").lower().strip()
        if status != "":
            if (status == "outstanding"):
                loans = loans.filter(quantity_loaned__gt=F('quantity_returned')).distinct()
            elif (status == "returned"):
                loans = loans.filter(quantity_loaned=F('quantity_returned')).distinct()

        item = request.query_params.get('item', "")
        if item != "":
            loans = loans.filter(item__name__icontains=item).distinct()

        # Pagination
        paginated_queryset = self.paginate_queryset(loans)
        serializer = self.get_serializer(instance=paginated_queryset, many=True)
        response = self.get_paginated_response(serializer.data)
        return response

class GetDisbursementsByRequest(generics.GenericAPIView):
    permissions = (permissions.IsAuthenticated,)
    pagination_class = CustomPagination
    filter_backends = (GetLoansByItemFilter,)

    def get_instance(self, request_pk):
        try:
            return models.Request.objects.get(pk=request_pk)
        except models.Request.DoesNotExist:
            raise NotFound('Request with ID {} not found.'.format(request_pk))

    def get_queryset(self):
        return models.Disbursement.objects.all()

    def get_serializer_class(self):
        return serializers.DisbursementSerializerNoRequest

    def get(self, request, request_pk, format=None):
        instance = self.get_instance(request_pk)
        if (instance.status != models.APPROVED):
            d = {"error": ["Request with ID {} is not approved.".format(request_pk)]}
            return Response(d, status=status.HTTP_204_NO_CONTENT)

        is_owner = (instance.requester.pk == request.user.pk)
        if not (request.user.is_staff or request.user.is_superuser or is_owner):
            d = {"error": ["Manager or owner permissions required."]}
            return Response(d, status=status.HTTP_403_FORBIDDEN)

        disbursements = self.get_queryset().filter(request__pk=instance.pk)

        item = request.query_params.get('item', "")
        if item != "":
            disbursements = disbursements.filter(item__name__icontains=item).distinct()

        # Pagination
        paginated_queryset = self.paginate_queryset(disbursements)
        serializer = self.get_serializer(instance=paginated_queryset, many=True)
        response = self.get_paginated_response(serializer.data)
        return response







class LoanListAllFilter(BaseFilterBackend):
  def get_schema_fields(self, view):
    fields = [
      coreapi.Field(name="user", description="Filter by requester's username", required=False, location='query'),
      coreapi.Field(name="status", description="Filter by loan status (Outstanding, Returned)", required=False, location='query'),      coreapi.Field(name="status", description="Filter by loan status (Outstanding, Returned)", required=False, location='query'),
      coreapi.Field(name="item", description="Filter by item", required=False, location='query'),
    ]

    return fields

class LoanListAll(generics.GenericAPIView):
    authentication_classes = (authentication.SessionAuthentication,)
    permission_classes = (permissions.IsAuthenticated,)
    pagination_class = CustomPagination
    filter_backends = (LoanListAllFilter,)

    def get_queryset(self):
        return models.Request.objects.filter(status=models.APPROVED);

    def get_serializer_class(self):
        return serializers.RequestLoanDisbursementSerializer

    def get(self, request, format=None):
        if not (request.user.is_staff or request.user.is_superuser):
            return Response({"error": ["Manager permissions required."]}, status=status.HTTP_403_FORBIDDEN)

        requests = self.get_queryset()

        item_search = request.query_params.get('item', "")
        if item_search != "":
            requests = requests.filter(loans__item__name__icontains=item_search).distinct()

        status = request.query_params.get('status', "")
        if status != "":
            if (status.lower().strip() == "returned"):
                requests = requests.exclude(loans__quantity_loaned__gt=F('loans__quantity_returned')).distinct()
            elif (status.lower().strip() == "outstanding"):
                requests = requests.exclude(loans__quantity_loaned__lte=F('loans__quantity_returned')).distinct()

        user = request.query_params.get('user', "")
        if user != "":
            requests = requests.filter(requester__username=user).distinct()

        requests = self.paginate_queryset(requests)
        serializer = self.get_serializer(instance=requests, many=True)
        response = self.get_paginated_response(serializer.data)
        return response

class LoanListFilter(BaseFilterBackend):
  def get_schema_fields(self, view):
    fields = [
      coreapi.Field(name="status", description="Filter by loan status (Outstanding, Returned)", required=False, location='query'),      coreapi.Field(name="status", description="Filter by loan status (Outstanding, Returned)", required=False, location='query'),
      coreapi.Field(name="item", description="Filter by item", required=False, location='query'),
    ]

    return fields

class LoanList(generics.GenericAPIView):
    authentication_classes = (authentication.SessionAuthentication,)
    permission_classes = (permissions.IsAuthenticated,)
    pagination_class = CustomPagination
    filter_backends = (LoanListFilter,)

    def get_queryset(self):
        return models.Request.objects.filter(requester=self.request.user, status=models.APPROVED);

    def get_serializer_class(self):
        return serializers.RequestLoanDisbursementSerializer

    def get(self, request, format=None):
        queryset = self.get_queryset()

        item_search = request.query_params.get('item', "")
        if item_search != "":
            queryset = queryset.filter(loans__item__name__icontains=item_search).distinct()

        status = request.query_params.get('status', "")
        if status != "":
            if (status.lower().strip() == "returned"):
                queryset = queryset.filter(loans__quantity_loaned__lte=F('loans__quantity_returned')).distinct()
            elif (status.lower().strip() == "outstanding"):
                queryset = queryset.filter(loans__quantity_loaned__gt=F('loans__quantity_returned')).distinct()

        user = request.query_params.get('user', "")
        if user != "":
            queryset = queryset.filter(requester__username=user).distinct()

        queryset = self.paginate_queryset(queryset)
        serializer = self.get_serializer(instance=queryset, many=True)
        response = self.get_paginated_response(serializer.data)
        return response


class LoanDetailModify(generics.GenericAPIView):
    authentication_classes = (authentication.SessionAuthentication,)
    permission_classes = (permissions.IsAuthenticated,)

    def get_queryset(self):
        queryset = models.Loan.objects.all()
        if not (self.request.user.is_staff or self.request.user.is_superuser):
            queryset = queryset.filter(request__requester=self.request.user)
        return queryset

    def get_serializer_class(self):
        return serializers.LoanSerializer

    def get_instance(self, pk):
        try:
            return models.Loan.objects.get(pk=pk)
        except models.Loan.DoesNotExist:
            raise NotFound('Loan {} not found.'.format(pk))

    def get(self, request, pk, format=None):
        loan = self.get_instance(pk=pk)
        serializer = self.get_serializer(instance=loan)
        return Response(serializer.data)

    def put(self, request, pk, format=None):
        if not (request.user.is_superuser or request.user.is_staff):
            d = {"error": "Manager permissions required."}
            return Response(d, status=status.HTTP_403_FORBIDDEN)
        loan = self.get_instance(pk=pk)
        data = request.data.copy()
        data.update({"loan": loan})
        serializer = self.get_serializer(instance=loan, data=data, partial=True)
        if serializer.is_valid():
            serializer.save()
            # send email that loan was returned
            sendEmailForLoanModification(loan)
            # Log the loan being returned
            requestItemLoanModify(loan, request.user.pk)

            if loan.quantity_loaned == 0:
                loan.delete()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class ConvertLoanToDisbursement(generics.GenericAPIView):
    authentication_classes = (authentication.SessionAuthentication,)
    permission_classes = (permissions.IsAuthenticated,)

    def get_queryset(self):
        queryset = models.Loan.objects.all()
        if not (self.request.user.is_staff or self.request.user.is_superuser):
            queryset = queryset.filter(request__requester=self.request.user)
        return queryset

    def get_serializer_class(self):
        return serializers.ConversionSerializer

    def get_instance(self, pk):
        try:
            return models.Loan.objects.get(pk=pk)
        except models.Loan.DoesNotExist:
            raise NotFound('Loan {} not found.'.format(pk))

    def post(self, request, pk, format=None):
        if not (request.user.is_superuser or request.user.is_staff):
            d = {"error": "Manager permissions required."}
            return Response(d, status=status.HTTP_403_FORBIDDEN)

        loan = self.get_instance(pk=pk)

        data = request.data.copy()
        data.update({"loan": loan})

        serializer = self.get_serializer(data=data)
        if serializer.is_valid():
            data = serializer.data
            quantity = data.get('quantity')
            convertLoanToDisbursement(loan, quantity)
            sendEmailForLoanToDisbursementConversion(loan)
            requestItemLoantoDisburse(loan, request.user, quantity)
            if loan.quantity_loaned == 0:
                loan.delete()

            return Response(serializer.data)
        else:
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

def approveBackfillRequest(backfill_request):
    loan = backfill_request.loan
    quantity = loan.quantity_loaned - loan.quantity_returned # change this if want to implement partial backfills
    convertLoanToBackfill(loan, backfill_request, quantity)
    convertLoanToDisbursement(loan, quantity)
    #todo send email

    #todo what happens if some of the loan was already returned before it was requested backfilled? - loan remains, but backfill requests still deleted
    if loan.quantity_loaned == 0:
        loan.delete() # also deletes backfill_request
    else:
        backfill_request.delete()

def convertLoanToBackfill(loan, backfill_request, quantity):
    backfill = models.Backfill.objects.create(request=loan.request, item=loan.item, quantity=quantity, requester_comment=backfill_request.requester_comment, receipt=backfill_request.receipt, admin_comment=backfill_request.admin_comment)

def convertLoanToDisbursement(loan, quantity):
    # Standard loan - no asset to handle
    if (loan.asset == None and loan.item.has_assets == False):
        loan.quantity_loaned -= quantity

        disbursements = loan.request.disbursements.filter(item__name=loan.item.name)
        # add to existing disbursement or create a new one
        if disbursements.count() > 0:
            disbursement = disbursements.first()
            disbursement.quantity += quantity
            disbursement.save()
        else:
            disbursement = models.Disbursement.objects.create(item=loan.item, request=loan.request, quantity=quantity)
            disbursement.save()
        loan.save()

    # loan with asset, item has assets
    else:
        disbursement = models.Disbursement.objects.create(item=loan.item, asset=loan.asset, request=loan.request, quantity=quantity)
        disbursement.save()
        loan.quantity_loaned -= quantity
        loan.save()


@api_view(['POST'])
@permission_classes((permissions.AllowAny,))
def post_user_login(request, format=None):
    username = request.data.get('username', None)
    password = request.data.get('password', None)
    next_url = request.data.get('next', None)

    user = authenticate(username=username, password=password)

    if hasattr(user, 'kipventory_user'):
        if user.kipventory_user.is_duke_user:
            messages.add_message(request._request, messages.ERROR, 'login-via-duke-authentication')
            return redirect('/')

    if user is not None:
        login(request, user)
        if len(next_url) > 0:
            return redirect(next_url)
        return redirect('/app/inventory/')
    else:
        # Return an 'invalid login' error message.
        messages.add_message(request._request, messages.ERROR, 'invalid-login-credentials')
        return redirect('/')

class UserList(generics.GenericAPIView):
    authentication_classes = (authentication.SessionAuthentication,)
    permission_classes = (permissions.IsAuthenticated,)

    def get_queryset(self):
        return User.objects.all().order_by("username")

    def get_serializer_class(self):
        return serializers.UserGETSerializer

    def get(self, request, format=None):
        users = self.get_queryset()
        serializer = self.get_serializer(instance=users, many=True)
        return Response(serializer.data)

class UserCreate(generics.GenericAPIView):
    authentication_classes = (authentication.SessionAuthentication,)
    permission_classes = (permissions.IsAuthenticated,)
    pagination_class = CustomPagination

    def get_queryset(self):
        return User.objects.all()

    def get_serializer_class(self):
        return serializers.UserPOSTSerializer

    def post(self, request, format=None):
        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid():
            # serializer.save()
            user = User.objects.create_user(**serializer.validated_data)
            #todo do we log this for net id creations?
            userCreationLog(serializer.data, request.user.pk)
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class GetCurrentUser(generics.GenericAPIView):
    queryset = None
    permission_classes = (permissions.IsAuthenticated,)
    serializer_class = serializers.UserGETSerializer

    def get(self, request, format=None):
        serializer = self.get_serializer(instance=request.user)
        return Response(serializer.data)
        user = request.user
        return Response({
            "username": user.username,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "email": user.email,
            "is_staff": user.is_staff,
            "is_superuser": user.is_superuser,
            "profile" : user.profile
        })

class EditUser(generics.GenericAPIView):
    permission_classes = (permissions.IsAuthenticated,)
    serializer_class = serializers.UserPUTSerializer

    def get_instance(self, username):
        return models.User.objects.get(username=username)

    def put(self, request, username, format=None):
        # Only managers can edit users
        if not request.user.is_staff: #and not (request.user.username == username): #todo fix this. users should be able to edit any of their attributes except permissions
            d = {"error": "Manager permissions required."}
            return Response(d, status=status.HTTP_403_FORBIDDEN)

        jsonData = request.data.copy()
        user = self.get_instance(username)

         # Only admins can change privilege
        if not request.user.is_superuser and (jsonData["is_staff"] != user.is_staff or jsonData["is_superuser"] != user.is_superuser):
            d = {"error": "Admin permissions required to change privilege."}
            return Response(d, status=status.HTTP_403_FORBIDDEN)

        serializer = self.get_serializer(instance=user, data=jsonData, partial=True)
        if serializer.is_valid():
            print("saving user serializer")
            serializer.save()
            return Response(serializer.data)
        print("error saving user {} ".format(serializer.errors))
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class GetNetIDTokenFilter(BaseFilterBackend):
  def get_schema_fields(self, view):
    fields = [
      coreapi.Field(name="code", description="Authorization code", required=False, location='query'),
    ]

    return fields

class GetNetIDToken(generics.GenericAPIView):
    queryset = None
    permission_classes = (permissions.AllowAny,)
    serializer_class = None
    filter_backends = (GetNetIDTokenFilter, )

    def get(self, request, format=None):
        code = request.query_params.get('code')

        p = {'grant_type' : 'authorization_code',
             'code' : code,
             'redirect_uri' : "https://colab-sbx-277.oit.duke.edu/api/netidtoken/",
             'client_id' : 'ece458kipventory',
             'client_secret' : '%Y1S@xJm8VUSp*LZL!hgdgv5IWdVl7gugIpb*vXNrnKLzL1dQd'}

        token_request = requests.post('https://oauth.oit.duke.edu/oauth/token.php', data=p)
        token_json = token_request.json()

        headers = {'Accept' : 'application/json', 'x-api-key' : 'ece458kipventory', 'Authorization' : 'Bearer '+token_json['access_token']}

        identity = requests.get('https://api.colab.duke.edu/identity/v1/', headers= headers)
        identity_json = identity.json()

        netid = identity_json['netid']
        email = identity_json['eduPersonPrincipalName']
        first_name = identity_json['firstName']
        last_name = identity_json['lastName']

        user_count = User.objects.filter(username=netid).count()
        if user_count == 1:
            user = User.objects.get(username=netid)
            login(request, user)
            return redirect('/app/inventory/')
        elif user_count == 0:
            user = User.objects.create_user(username=netid, email=email, password=None, first_name=first_name, last_name=last_name)
            login(request, user)
            return redirect('/app/inventory/')
        else:
            print("Multiple NetId Users this is big time wrong need to throw an error")
            return redirect('/app/inventory/')

class TagListFilter(BaseFilterBackend):
  def get_schema_fields(self, view):
    fields = [
      coreapi.Field(name="all", description="Set all=true to get all tags instead of paginated", required=False, location='query'),
    ]

    return fields

class TagListCreate(generics.GenericAPIView):
    permission_classes = (permissions.IsAuthenticated,)
    serializer_class = serializers.TagSerializer
    pagination_class = CustomPagination
    filter_backends = (TagListFilter,)

    def get_queryset(self):
        return models.Tag.objects.all()

    def get(self, request, format=None):
        tags = self.get_queryset()

        if(request.query_params.get("all") == "true"):
            serializer = self.get_serializer(instance=tags, many=True)
            return Response(serializer.data)
        else:
            paginated_tags = self.paginate_queryset(tags)
            serializer = self.get_serializer(instance=paginated_tags, many=True)
            response = self.get_paginated_response(serializer.data)
            return response

        # return response

    def post(self, request, format=None):
        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class TagDelete(generics.GenericAPIView):
    permission_classes = (permissions.IsAuthenticated,)

    def get_instance(self, tag_name):
        try:
            return models.Tag.objects.get(name=tag_name)
        except models.Tag.DoesNotExist:
            raise NotFound('Tag {} not found.'.format(tag_name))

    # Maybe put into its own view? Seems like a lot for now
    # manager restricted
    def delete(self, request, tag_name, format=None):
        if not (request.user.is_staff):
            d = {"error": "Administrator permissions required."}
            return Response(d, status=status.HTTP_403_FORBIDDEN)

        tag = self.get_instance(tag_name=tag_name)
        tag.delete()
        # Insert Delete Log
        # Need {serializer.data, initiating_user_pk, 'Item Changed'}
        # itemDeletionLog(item_name, request.user.pk)
        #TODO NEED TO LOG DELETION HERE
        return Response(status=status.HTTP_204_NO_CONTENT)

class LogListFilter(BaseFilterBackend):
  def get_schema_fields(self, view):
    fields = [
      coreapi.Field(name="user", description="Filter by affected user or initiating user's username", required=False, location='query'),
      coreapi.Field(name="item", description="Filter by item name", required=False, location='query'),
      coreapi.Field(name="endDate", description="Filter by start date/end date", required=False, location='query'),
      coreapi.Field(name="startDate", description="Filter by start date/end date", required=False, location='query'),

    ]

    return fields

class LogList(generics.GenericAPIView):
    permission_classes = (permissions.IsAuthenticated,)
    pagination_class = CustomPagination
    filter_backends = (LogListFilter,)

    def get_queryset(self):
        return models.Log.objects.all()

    def get_serializer_class(self):
        return serializers.LogSerializer

    def get(self, request, format=None):
        if not (request.user.is_staff or request.user.is_superuser):
            # Not allowed to see logs if not manager/admin
            return Response(status=status.HTTP_403_FORBIDDEN)

        user = request.query_params.get("user")
        item = request.query_params.get("item")
        endDate = request.query_params.get("endDate")
        startDate = request.query_params.get("startDate")

        # Create Datetimes from strings
        logs = self.get_queryset()
        q_objs = Q()
        if user is not None and user != '':
            q_objs &= (Q(affected_user__username=user) | Q(initiating_user__username=user))
        logs = logs.filter(q_objs).distinct()
        if item is not None and item != '':
            logs = logs.filter(item__name=item)
        if startDate is not None and startDate != '' and endDate is not None and endDate != '':
            startDate, endDate = startDate.split(" "), endDate.split(" ")
            stimeZone, etimeZone = startDate[5], endDate[5]
            stimeZone, etimeZone = stimeZone.split('-'), etimeZone.split('-')
            startDate, endDate = startDate[:5], endDate[:5]
            startDate, endDate = " ".join(startDate), " ".join(endDate)
            startDate, endDate = startDate + " " + stimeZone[0], endDate + " " + etimeZone[0]

            startDate = datetime.strptime(startDate, "%a %b %d %Y %H:%M:%S %Z").date()
            endDate = datetime.strptime(endDate, "%a %b %d %Y %H:%M:%S %Z").date()
            startDate = datetime.combine(startDate, datetime.min.time())
            endDate = datetime.combine(endDate, datetime.max.time())
            startDate = timezone.make_aware(startDate, timezone.get_current_timezone())
            endDate = timezone.make_aware(endDate, timezone.get_current_timezone())

            logs = logs.filter(date_created__range=[startDate, endDate])

        queryset = logs
        paginated_queryset = self.paginate_queryset(queryset)
        serializer = self.get_serializer(instance=paginated_queryset, many=True)
        response = self.get_paginated_response(serializer.data)
        return response


class TransactionListFilter(BaseFilterBackend):
  def get_schema_fields(self, view):
    fields = [
      coreapi.Field(name="category", description="Filter by category(Acquisition, Loss)", required=False, location='query'),
    ]

    return fields

class TransactionListCreate(generics.GenericAPIView):
    permission_classes = (permissions.IsAuthenticated,)
    pagination_class = CustomPagination
    filter_backends = (TransactionListFilter,)

    def get_queryset(self):
        return models.Transaction.objects.all()

    def get_serializer_class(self):
        return serializers.TransactionSerializer

    def get(self, request, format=None):
        queryset = self.get_queryset()

        category = request.query_params.get('category', None)
        if category != None and category != "":
            if category in set(['Acquisition', 'Loss']):
                queryset = queryset.filter(category=category)

        # Pagination
        paginated_queryset = self.paginate_queryset(queryset)
        serializer = self.get_serializer(instance=paginated_queryset, many=True)
        response = self.get_paginated_response(serializer.data)
        return response


    def post(self, request, format=None):
        #todo django recommends doing this in middleware
        data = request.data.copy()
        data['administrator'] = request.user

        serializer = self.get_serializer(data=data)
        if serializer.is_valid(): #todo could move the validation this logic into serializer's validate method
            quantity = serializer.validated_data.get('quantity', 0)
            try:
                item = models.Item.objects.get(name=serializer.validated_data.get('item'))
                category = serializer.validated_data.get('category')
                if category.lower() == "acquisition":
                    item.quantity += quantity
                elif category.lower() == "loss":
                    item.quantity -= quantity
                item.save()
            except:
                return Response({"name": ["Item with name '{}' does not exist.".format(serializer.validated_data.get('name', None))]})
            transactionCreationLog(item, request.user.pk, request.data['category'], quantity)
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class TokenPoint(generics.GenericAPIView):
    permission_classes = (permissions.IsAuthenticated,)

    def get(self, request, format=None):
        if Token.objects.filter(user=request.user).count() > 0:
            #User has a token, return created token
            print(Token.objects.get(user=request.user).key)
            return Response({"token": Token.objects.get(user=request.user).key})
        else:
            token = Token.objects.create(user=request.user)
            print(token.key)
            return Response({"token": token.key})


class BulkImportTemplate(APIView):
    permissions = (permissions.IsAuthenticated,)

    def get(self, request, format=None):
        schema = ["name", "model_no", "quantity", "description", "tags", "has_assets", "minimum_stock"]
        for cf in models.CustomField.objects.all():
            schema.append(cf.name)

        # construct a blank csv file template
        with open('template.csv', 'w') as template:
            wr = csv.writer(template)
            wr.writerow(schema)

        template = open('template.csv', 'rb')
        response = HttpResponse(content=template)
        response['Content-Type'] = 'text/csv'
        response['Content-Disposition'] = 'attachment; filename="import_template.csv"'
        os.remove('template.csv')
        return response

class BulkImport(generics.GenericAPIView):
    permission_classes = (permissions.IsAuthenticated,)


    def post(self, request, format=None):
        if not request.user.is_superuser:
            d = {"error": "Administrator permissions required."}
            return Response(d, status=status.HTTP_403_FORBIDDEN)

        data = request.data.copy()
        data.update({"administrator": request.user})
        serializer = self.get_serializer(data=data)

        if serializer.is_valid():
            inputfile = request.FILES['data']
            fout = open('importtempfile.csv', 'wb')
            for chunk in inputfile.chunks():
                fout.write(chunk)
            fout.close()

            header = []
            contents = []
            firstRow = True
            numRows = 0
            errors = {}

            with open('importtempfile.csv', 'r') as f:
                reader = csv.reader(f)
                for row in reader:
                    if len("".join(row)) == 0:
                        continue
                    else:
                        if firstRow:
                            header = [x for x in row]
                            firstRow = False
                        else:
                            contents.append([x for x in row])
                            numRows += 1

            os.remove('importtempfile.csv')
            indices = {}
            name_index = 0
            model_no_index = 0
            quantity_index = 0
            description_index = 0
            tags_index = 0

            columns_present = set(['name', 'model_no', 'quantity', 'description', 'tags', 'has_assets', 'minimum_stock'])
            for (i, column_name) in enumerate(header):
                indices[column_name] = i
                if column_name in columns_present:
                    columns_present.remove(column_name)
            if len(columns_present) > 0:
                error = {'error': ['Invalid header schema. Missing required columns {}'.format(', '.join(columns_present))]}
                return Response(error, status=status.HTTP_400_BAD_REQUEST)


            # Parse all known item fields (intrinsic)
            name_index = indices['name']
            names = [row[name_index] for row in contents]
            indices.pop('name')

            model_no_index = indices['model_no']
            model_nos = [row[model_no_index] for row in contents]
            indices.pop('model_no')

            quantity_index = indices['quantity']
            quantities = [row[quantity_index] for row in contents]
            indices.pop('quantity')

            description_index = indices['description']
            descriptions = [row[description_index] for row in contents]
            indices.pop('description')

            tags_index = indices['tags']
            tags = [row[tags_index] for row in contents]
            indices.pop('tags')

            has_assets_index = indices['has_assets']
            have_assets = [row[has_assets_index] for row in contents]
            indices.pop('has_assets')

            minimum_stock_index = indices['minimum_stock']
            minimum_stocks = [row[minimum_stock_index] for row in contents]
            indices.pop('minimum_stock')

            # Now, indices contains only custom field headers

            custom_field_errors = []
            for field_name, index in indices.items():
                try:
                    cf = models.CustomField.objects.get(name=field_name)
                    values = [row[index] for row in contents]
                    cf_errors = []
                    for i, val in enumerate(values):
                        try:
                            val = models.FIELD_TYPE_DICT[cf.field_type](val)
                            contents[i][index] = val
                        except:
                            cf_errors.append("Value '{}' is not of type '{}' (row {}).".format(val, models.FIELD_TYPE_DICT[cf.field_type].__name__, i))

                    if cf_errors:
                        custom_field_errors.append({field_name: cf_errors})

                except models.CustomField.DoesNotExist:
                    custom_field_errors.append({field_name: ["Custom field '{}' does not exist (column {}).".format(field_name, i)]})
            # check type of has_assets
            has_assets_errors = []
            for i, has_assets in enumerate(have_assets):
                print(has_assets)
                if (has_assets != "") and (has_assets.lower() != "true") and (has_assets.lower() != "false"):
                    print((has_assets.lower() != "true"))
                    print("HERE1")
                    has_assets_errors.append("has_assets field must be empty or of type boolean (row {}).".format(i))
                if has_assets.lower() == 'true':
                    print("HERE2")
                    have_assets[i] = True
                if has_assets.lower() == 'false' or has_assets.lower() == '':
                    print("HERE3")
                    have_assets[i] = False
            minimum_stock_errors = []
            for i, minimum_stock in enumerate(minimum_stocks):
                if minimum_stock == "" or minimum_stock == None:
                    minimum_stock_errors.append("Minimum stock must not be blank (row {}).".format(i))
                try:
                    minimum_stock = int(minimum_stock)
                    minimum_stocks[i] = minimum_stock
                except:
                    minimum_stock_errors.append("Minimum stock must be an integer (row {}).".format(i))
            # check unique names
            nameset = set()
            name_errors = []
            for i, name in enumerate(names):
                if name == "" or name == None:
                    name_errors.append("Name must not be blank (row {}).".format(i))
                if name in nameset:
                    name_errors.append("Name '{}' appears multiple times.".format(name))
                try:
                    other_item = models.Item.objects.get(name=name)
                    name_errors.append("An item with name '{}' (row {}) already exists.".format(name, i))
                except models.Item.DoesNotExist:
                    pass
                nameset.add(name)

            # check valid (positive) integer quantities
            quantity_errors = []
            for i, q in enumerate(quantities):
                if q == None or q == "":
                    quantity_errors.append("Quantity must not be blank (row {}).".format(i))
                else:
                    try:
                        q = int(q)
                        quantities[i] = q
                        if q < 0:
                            quantity_errors.append("Negative quantity {} (row {}).".format(q, i))
                    except:
                            quantity_errors.append("Value '{}' is not an integer (row {}).".format(q, i))

            if name_errors:
                errors.update({"name": name_errors})
            if quantity_errors:
                errors.update({"quantity": quantity_errors})
            if custom_field_errors:
                for e in custom_field_errors:
                    errors.update(e)
            if has_assets_errors:
                errors.update({"has_assets": has_assets_errors})
            if minimum_stock_errors:
                errors.update({"minimum_stock": minimum_stock_errors})
            if errors:
                return Response(errors, status=status.HTTP_400_BAD_REQUEST)

            # we know we've passed the validation check - go ahead and make all the items
            created_items = []
            created_tags  = []
            for i in range(numRows):
                # create the base item
                item = models.Item(name=names[i], model_no=model_nos[i], quantity=quantities[i], description=descriptions[i], minimum_stock=minimum_stocks[i], has_assets=have_assets[i])
                item.save()
                itemCreationBILog(item, request.user)
                # parse and create tags
                tag_string = tags[i]
                # remove empty tags (ie. a blank cell)
                tag_list = [x.strip() for x in tag_string.split(",") if len(x) > 0]
                for tag in tag_list:
                    try:
                        tag = models.Tag.objects.get(name=tag)
                    except models.Tag.DoesNotExist:
                        tag = models.Tag.objects.create(name=tag)
                        created_tags.append(tag.name)
                    item.tags.add(tag)
                item.save()

                # set custom field values on created item
                for custom_value in item.values.all():
                    field_index = indices[custom_value.field.name]
                    val = contents[i][field_index]
                    setattr(custom_value, custom_value.field.field_type, val)
                    custom_value.save()
                item.save()
                created_items.append(item.name)

            d = {
                    "items" : [name for name in created_items],
                    "tags"  : [tag  for tag  in created_tags]
                }

            return Response(d)
        else:
            return Response({"no_file": ["Please select a .csv file."]}, status=status.HTTP_400_BAD_REQUEST)

    def get_serializer_class(self):
        return serializers.BulkImportSerializer

    def get_queryset(self):
        return models.BulkImport.Objects.all()

# class DisburseFilter(BaseFilterBackend):
#   def get_schema_fields(self, view):
#     fields = [
#       coreapi.Field(name="requester", description="Request username", required=True, location='body'),
#       coreapi.Field(name="closed_comment", description="Admin comment", required=True, location='body'),
#       coreapi.Field(name="items", description="list of disbursed items", required=True, location='body'),
#       coreapi.Field(name="types", description="index correlated request type", required=True, location='body'),
#       coreapi.Field(name="quantities", description="index correlated item quantity", required=True, location='body'),
#     ]
#
#     return fields

class DisburseCreate(generics.GenericAPIView):
    permission_classes = (permissions.IsAuthenticated,)
    # filter_backends = (DisburseFilter,)
    queryset = models.Request.objects.all()

    def get_serializer_class(self):
        return serializers.RequestSerializer

    def post(self, request, format=None):
        # check that all item names and quantities are valid
        errors = {}

        # validate user input
        data = {}
        data.update(request.data)
        requester = data.get('requester')
        closed_comment = data.get('closed_comment')
        items = data['items']
        quantities = data['quantities']
        types = data['types']

        print(data)

        try:
            requester = User.objects.get(username=requester)
        except User.DoesNotExist:
            return Response({"error": "Could not find user with username '{}'".format(requester)})

        data = {}
        data.update({'requester': requester, 'open_comment': "Administrative disbursement to user '{}'".format(requester.username)})

        # Verify that the disbursement quantities are valid (ie. less than or equal to inventory stock)
        for i in range(len(items)):
            item = None
            try:
                item = models.Item.objects.get(name=items[i])
            except models.Item.DoesNotExist:
                return Response({"error": "Item '{}' not found.".format(items[i])})
            items[i] = item
            # convert to int
            quantity = int(quantities[i])
            quantities[i] = quantity
            if quantity > item.quantity:
                errors.update({'error': "Request for {} instances of '{}' exceeds current stock of {}.".format(quantity, item.name, item.quantity)})

        if errors:
            return Response(errors, status=status.HTTP_400_BAD_REQUEST)

        # if we made it here, we know we can go ahead and create the request, all the request items, and approve it
        serializer = self.get_serializer(data=data)
        if serializer.is_valid():
            print("MADE IT")
            request_instance = serializer.save()

            data = {}
            data.update({'administrator': request.user})
            data.update({'closed_comment': closed_comment})
            data.update({'status': 'A'})

            request_instance.administrator = request.user
            request_instance.closed_comment = closed_comment
            request_instance.status = 'A'
            request_instance.save()

            for item, quantity, request_type in zip(items, quantities, types):
                # Create request item
                req_item = models.ApprovedItem.objects.create(item=item, quantity=quantity, request_type=request_type, request=request_instance)
                req_item.save()

                # Decrement the quantity remaining on the Item
                item.quantity -= quantity
                item.save()

                # Logging
                print("Rq Instance", request_instance)
                requestItemCreation(req_item, request.user.pk, request_instance)
                requestItemApprovalDisburse(req_item, request.user.pk, request_instance)

            sendEmailForNewDisbursement(requester, request_instance)
            return Response(serializer.data)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


def itemCreationLog(data, initiating_user_pk):
    item = None
    initiating_user = None
    quantity = None
    affected_user = None
    try:
        item = models.Item.objects.get(name=data['name'])
    except models.Item.DoesNotExist:
        raise NotFound('Item {} not found.'.format(data['name']))
    try:
        initiating_user = User.objects.get(pk=initiating_user_pk)
    except User.DoesNotExist:
        raise NotFound('User not found.')
    quantity = data['quantity']
    message = 'Item {} created by {}'.format(data['name'], initiating_user)
    log = models.Log(item=item, initiating_user=initiating_user, quantity=quantity, category='Item Creation', message=message, affected_user=affected_user)
    log.save()

def itemCreationBILog(item, initiating_user):
    message = 'Item {} created by {}'.format(item.name, initiating_user)
    log = models.Log(item=item, initiating_user=initiating_user, quantity=item.quantity, category='Item Creation', message=message, affected_user=None)
    log.save()

def itemModificationLog(data, initiating_user_pk):
    item = None
    initiating_user = None
    quantity = None
    affected_user = None
    try:
        item = models.Item.objects.get(name=data['name'])
    except models.Item.DoesNotExist:
        raise NotFound('Item {} not found.'.format(data['name']))
    try:
        initiating_user = User.objects.get(pk=initiating_user_pk)
    except User.DoesNotExist:
        raise NotFound('User not found.')
    quantity = data['quantity']
    message = 'Item {} modified by {}'.format(data['name'], initiating_user)
    log = models.Log(item=item, initiating_user=initiating_user, quantity=quantity, category='Item Modification', message=message, affected_user=affected_user)
    log.save()

def itemDeletionLog(item_name, initiating_user_pk):
    item = None
    initiating_user = None
    quantity = None
    affected_user = None
    try:
        initiating_user = User.objects.get(pk=initiating_user_pk)
    except User.DoesNotExist:
        raise NotFound('User not found.')
    message = 'Item {} deleted by {}'.format(item_name, initiating_user)
    log = models.Log(item=item, initiating_user=initiating_user, quantity=quantity, category='Item Deletion', message=message, affected_user=affected_user)
    log.save()

def requestItemCreation(request_item, initiating_user_pk, requestObj):
    item = request_item.item
    initiating_user = None
    quantity = request_item.quantity
    affected_user = None
    request = requestObj
    try:
        initiating_user = User.objects.get(pk=initiating_user_pk)
    except User.DoesNotExist:
        raise NotFound('User not found.')
    message = 'Request Item for item {} created by {}'.format(request_item.item.name, initiating_user)
    log = models.Log(item=item, initiating_user=initiating_user, request=request, quantity=quantity, category='Request Item Creation', message=message, affected_user=affected_user)
    log.save()

DOMAIN = "https://colab-sbx-277.oit.duke.edu/"
REQUESTS_URL = "{}{}".format(DOMAIN, "app/requests/")

def sendEmailForLoanToDisbursementConversion(loan):
    user = User.objects.get(username=loan.request.requester)
    subject = "Loan To Disbursement"
    request_url = "{}{}".format(REQUESTS_URL, loan.request.id)
    text_content = "One of your loans has been converted to a disbursement. Check {} for details.".format(request_url)
    html_content = "One of your loans has been converted to a disbursement. Check <a href='{}'>{}</a> for details.".format(request_url, request_url)
    to_emails = [user.email]
    sendEmail(subject, text_content, html_content, to_emails)

def sendEmailForLoanModification(loan):
    #todo make something more specific for loan returns
    #are there any other loan modificaations besides marking as returned? i don't think so
    user = User.objects.get(username=loan.request.requester)
    subject = "Loan Returned" #"Loan Modified"
    request_url = "{}{}".format(REQUESTS_URL, loan.request.id)
    text_content = "One of your loans has been marked as returned. Check {} for details.".format(request_url)
    html_content = "One of your loans has been marked as returned. Check <a href='{}'>{}</a> for details.".format(request_url, request_url)
    to_emails = [user.email]
    sendEmail(subject, text_content, html_content, to_emails)

def sendEmailForNewDisbursement(user, request):
    subject = "New Disbursement"
    request_url = "{}{}".format(REQUESTS_URL, request.id)
    text_content = "An administrator has disbursed one or more item(s) to you. Check {} for details.".format(request_url)
    html_content = "An administrator has disbursed one or more item(s) to you. Check <a href='{}'>{}</a> for details.".format(request_url, request_url)
    to_emails = [user.email]
    sendEmail(subject, text_content, html_content, to_emails)

def sendEmailForRequestStatusUpdate(request):
    user = request.requester
    subject = "Request Status Update"
    request_url = "{}{}".format(REQUESTS_URL, request.id)
    text_content = "The status of one of your requests has changed. Go to {} to view the request".format(request_url)
    html_content = "The status of one of your requests has changed. Go to <a href='{}'>{}</a> to view the request".format(request_url, request_url)
    to_emails = [user.email]
    sendEmail(subject, text_content, html_content, to_emails)

def sendEmailForNewRequest(request):
    user = request.requester
    request_items = models.RequestedItem.objects.filter(request=request)
    subscribed_managers = User.objects.filter(is_staff=True).filter(profile__subscribed=True)

    # Send email to all subscribed managers
    subject = "New User Request"
    request_url = "{}{}".format(REQUESTS_URL, request.id)
    text_content = "User {} initiated a new request for one or more item(s). Go to {} to view and/or respond to this request.".format(user.username, request_url)
    html_content = "User <b>{}</b> initiated a new request for one or more item(s). Go to <a href='{}'>{}</a> to view and/or respond to this request.".format(user.username, request_url, request_url)
    to_emails = []
    bcc_emails = [subscribed_manager.email for subscribed_manager in subscribed_managers]
    sendEmail(subject, text_content, html_content, to_emails, bcc_emails)

    # Send email to requesting user
    subject = "Request Confirmation"
    text_content = "This email is to confirm that you have made a new request for one or more item(s). Go to {} to view your request. An email will be sent when the status of your request changes.".format(request_url)
    html_content = "This email is to confirm that you have made a new request for one or more item(s). Go to <a href='{}'>{}</a> to view your request. An email will be sent when the status of your request changes.".format(request_url, request_url)
    to_emails = [user.email]
    bcc_emails = []
    sendEmail(subject, text_content, html_content, to_emails, bcc_emails)

def sendEmail(subject, text_content, html_content, to_emails, bcc_emails=[]):
    from_email = settings.EMAIL_HOST_USER
    x = None
    try:
        x = models.SubjectTag.objects.get()
    except models.SubjectTag.DoesNotExist:
        x = models.SubjectTag.objects.create(text='[kipventory]')
    subject = "{} {}".format(x.text, subject)
    msg = EmailMultiAlternatives(subject, text_content, from_email, to_emails, bcc_emails)
    msg.attach_alternative(html_content, "text/html")
    msg.send()

def requestItemDenial(request_item, initiating_user_pk, requestObj):
    item = request_item.item
    initiating_user = None
    quantity = request_item.quantity
    affected_user = request_item.request.requester
    request = requestObj
    try:
        initiating_user = User.objects.get(pk=initiating_user_pk)
    except User.DoesNotExist:
        raise NotFound('User not found.')
    message = 'Request Item for item {} denied by {}'.format(request_item.item.name, initiating_user.username)
    log = models.Log(item=item, request=request, initiating_user=initiating_user, quantity=quantity, category='Request Item Denial', message=message, affected_user=affected_user)
    log.save()

# def requestItemApproval(request_item, initiating_user_pk, requestObj):
#     item = request_item.item
#     initiating_user = None
#     quantity = request_item.quantity
#     affected_user = request_item.request.requester
#     request = requestObj
#     try:
#         initiating_user = User.objects.get(pk=initiating_user_pk)
#     except User.DoesNotExist:
#         raise NotFound('User not found.')
#     message = 'Request Item for item {} approved by {}'.format(request_item.item.name, initiating_user.username)
#     log = models.Log(item=item, request=request, initiating_user=initiating_user, quantity=quantity, category='Request Item Approval', message=message, affected_user=affected_user)
#     log.save()

def requestItemApprovalLoan(request_item, initiating_user_pk, requestObj):
    item = request_item.item
    initiating_user = None
    quantity = request_item.quantity
    affected_user = requestObj.requester
    request = requestObj
    category = 'Request Item Approval: Loan'
    try:
        initiating_user = User.objects.get(pk=initiating_user_pk)
    except User.DoesNotExist:
        raise NotFound('User not found.')
    message = 'Request Item for item {} approved by {} as a {}'.format(item.name, initiating_user.username, category)
    log = models.Log(item=item, request=request, initiating_user=initiating_user, quantity=quantity, category=category, message=message, affected_user=affected_user)
    log.save()

def requestItemLoanModify(loan, initiating_user_pk):
    item = loan.item
    initiating_user = None
    quantity = loan.quantity_returned
    request = loan.request
    affected_user = request.requester
    category = 'Request Item Loan Modify'
    try:
        initiating_user = User.objects.get(pk=initiating_user_pk)
    except User.DoesNotExist:
        raise NotFound('User not found.')
    message = 'Loan for item {} modified. The number of items returned by {} is now {}. The total number loaned is {}'.format(item.name, initiating_user.username, quantity, loan.quantity_loaned)
    log = models.Log(item=item, request=request, initiating_user=initiating_user, quantity=quantity, category=category, message=message, affected_user=affected_user)
    log.save()

def requestItemLoantoDisburse(loan, user, num_disbursed):
    item = loan.item
    initiating_user = user
    quantity = num_disbursed
    loaned_quantity = loan.quantity_loaned
    request = loan.request
    affected_user = request.requester
    category = 'Request Item Loan Changed to Disburse'
    message = 'Loan for item {} modified. {} items have been disbursed from a loan by {}. The number still loaned is {}.'.format(item.name, quantity, initiating_user.username, loaned_quantity)
    log = models.Log(item=item, request=request, initiating_user=initiating_user, quantity=quantity, category=category, message=message, affected_user=affected_user)
    log.save()

def requestItemApprovalDisburse(request_item, initiating_user_pk, requestObj):
    item = request_item.item
    initiating_user = None
    quantity = request_item.quantity
    affected_user = requestObj.requester
    request = requestObj
    category = 'Request Item Approval: Disburse'
    try:
        initiating_user = User.objects.get(pk=initiating_user_pk)
    except User.DoesNotExist:
        raise NotFound('User not found.')
    message = 'Request Item for item {} approved by {} as a {}'.format(item.name, initiating_user.username, category)
    log = models.Log(item=item, request=request, initiating_user=initiating_user, quantity=quantity, category=category, message=message, affected_user=affected_user)
    log.save()


def userCreationLog(data, initiating_user_pk):
    item = None
    initiating_user = None
    quantity = None
    affected_user = None
    try:
        initiating_user = User.objects.get(pk=initiating_user_pk)
    except User.DoesNotExist:
        raise NotFound('User not found.')
    try:
        affected_user = User.objects.get(username=data['username'])
    except User.DoesNotExist:
        raise NotFound('User not found.')
    message = "User {} was created by {}".format(affected_user, initiating_user)
    log = models.Log(item=item, initiating_user=initiating_user, quantity=quantity, category='User Creation', message=message, affected_user=affected_user)
    log.save()

def transactionCreationLog(item, initiating_user_pk, category, amount):
    item = item
    initiating_user = None
    quantity = amount
    affected_user = None
    try:
        initiating_user = User.objects.get(pk=initiating_user_pk)
    except User.DoesNotExist:
        raise NotFound('User not found.')
    message = "User {} created a {} transaction on item {} of quantity {} and it now has a quantity of {}".format(initiating_user, category, item, quantity, item.quantity)
    log = models.Log(item=item, initiating_user=initiating_user, quantity=quantity, category='Transaction Creation', message=message, affected_user=affected_user)
    log.save()


class GetSubscribedManagers(generics.GenericAPIView):
    permission_classes = (permissions.IsAuthenticated,)

    def get_queryset(self):
        return User.objects.filter(is_staff=True).filter(profile__subscribed=True)

    def get_serializer_class(self):
        return serializers.UserGETSerializer

    def get(self, request, format=None):
        if not (request.user.is_staff):
            d = {"error": "Permission denied."}
            return Response(d, status=status.HTTP_403_FORBIDDEN)
        subscribed_managers = self.get_queryset()
        serializer = self.get_serializer(instance=subscribed_managers, many=True)
        return Response(serializer.data)

class LoanReminderListFilter(BaseFilterBackend):
  def get_schema_fields(self, view):
    fields = [
      coreapi.Field(name="sent", description="Filter by sent or not sent (true/false)", required=False, location='query'),
    ]

    return fields

class LoanReminderListCreate(generics.GenericAPIView):
    authentication_classes = (authentication.SessionAuthentication,)
    permission_classes = (permissions.IsAuthenticated,)
    pagination_class = CustomPagination
    filter_backends = (LoanReminderListFilter,)

    def get_queryset(self):
        return models.LoanReminder.objects.all().order_by("date")

    def get_serializer_class(self):
        return serializers.LoanReminderSerializer

    def get(self, request, format=None):
        queryset = self.get_queryset()
        sent = json.loads(request.query_params.get("sent", "false"))
        queryset = queryset.filter(sent=sent)
        # Pagination
        paginated_queryset = self.paginate_queryset(queryset)
        serializer = self.get_serializer(instance=paginated_queryset, many=True)
        response = self.get_paginated_response(serializer.data)
        return response

    def post(self, request, format=None):
        data = request.data
        serializer = self.get_serializer(data=data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class LoanReminderModifyDelete(generics.GenericAPIView):
    permission_classes = (permissions.IsAuthenticated,)

    def get_instance(self, id):
        return models.LoanReminder.objects.get(id=id)

    def get_serializer_class(self):
        return serializers.LoanReminderSerializer

    def put(self, request, id, format=None):
        data = request.data
        loan_reminder = self.get_instance(id=id)
        serializer = self.get_serializer(instance=loan_reminder, data=data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, id, format=None):
        #todo do i need to deal with DoNotExist?
        loan_reminder = self.get_instance(id=id)
        loan_reminder.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

class SubjectTagGetModify(generics.GenericAPIView):
    permission_classes = (permissions.IsAuthenticated,)

    def get_instance(self):
        try:
            subject_tag = models.SubjectTag.objects.get()
            return subject_tag
        except models.SubjectTag.DoesNotExist:
            subject_tag = models.SubjectTag(text='[kipventory]')
            subject_tag.save()
            return subject_tag

    def get_serializer_class(self):
        return serializers.SubjectTagSerializer

    def get(self, request, format=None):
        subject_tag = self.get_instance()
        serializer = self.get_serializer(instance=subject_tag)
        return Response(serializer.data)

    def put(self, request, format=None):
        subject_tag = self.get_instance()
        serializer = self.get_serializer(instance=subject_tag, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class BackupEmailFilter(BaseFilterBackend):
  def get_schema_fields(self, view):
    fields = [
      coreapi.Field(name="status", description="Status of backup (success/failure)", required=True, location='query'),
    ]

    return fields

class BackupEmail(generics.GenericAPIView):
    permission_classes = (permissions.IsAuthenticated,)
    filter_backends = (BackupEmailFilter,)
    def get_queryset(self):
        return User.objects.filter(is_superuser=True)

    def get(self, request, format=None):
        admins = self.get_queryset()
        bcc_emails = []
        for admin in admins:
            bcc_emails.append(admin.email)
        backup_status = request.query_params.get("status", "")

        try:
            if backup_status == "success":
                subject = "Backup Successful"
                text_content = "Backup was successful."
                html_content = text_content
                to_emails = []
                sendEmail(subject, text_content, html_content, to_emails, bcc_emails)
                return Response(data={"backup" : "success"}, status=status.HTTP_200_OK)
            elif backup_status == "failure":
                subject = "Backup Failure"
                text_content = "ERROR Backup was a failure."
                html_content = text_content
                to_emails = []
                sendEmail(subject, text_content, html_content, to_emails, bcc_emails)
                return Response(data={"backup" : "failure"}, status=status.HTTP_200_OK)
            else:
                return Response(data={"backup" : "incorrect status code"}, status=status.HTTP_400_BAD_REQUEST)
        except:
            return Response(data={"backup" : "exception raised"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class BackfillDetailModify(generics.GenericAPIView):
    authentication_classes = (authentication.SessionAuthentication,)
    permission_classes = (permissions.IsAuthenticated,)

    def get_instance(self, pk):
        try:
            return models.Backfill.objects.get(pk=pk)
        except models.Backfill.DoesNotExist:
            raise NotFound('Backfill with ID {} not found.'.format(pk))

    def get_serializer_class(self):
        if self.request.method == 'PUT':
            return serializers.BackfillPUTSerializer
        return serializers.BackfillGETSerializer

    # MANAGER/OWNER LOCKED
    def get(self, request, pk, format=None):
        instance = self.get_instance(pk)
        # if manager, see any backfill.
        # if user, only see your backfill.
        is_owner = (instance.request.requester.pk == request.user.pk)
        if not (request.user.is_staff or request.user.is_superuser or is_owner):
            d = {"error": ["Manager or owner permissions required."]}
            return Response(d, status=status.HTTP_403_FORBIDDEN)

        serializer = self.get_serializer(instance=instance)
        return Response(serializer.data)

    # MANAGER LOCKED
    #  - only managers may change the status of a Backfill
    def put(self, request, pk, format=None):
        instance = self.get_instance(pk)
        is_owner = (instance.request.requester.pk == request.user.pk)
        if not (request.user.is_staff or request.user.is_superuser or is_owner):
            d = {"error": ["Manager or owner permissions required."]}
            return Response(d, status=status.HTTP_403_FORBIDDEN)

        data = request.data.copy()

        if not (instance.status == models.AWAITING_ITEMS):
            return Response({"status": ["Only backfills with status 'Awaiting Items' can be modified."]})

        serializer = self.get_serializer(instance=instance, data=data, partial=True)

        if serializer.is_valid():
            serializer.save()

            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class BackfillRequestCreate(generics.GenericAPIView):
    authentication_classes = (authentication.SessionAuthentication,)
    permission_classes = (permissions.IsAuthenticated,)

    def get_loan(self, pk):
        try:
            return models.Loan.objects.get(pk=pk)
        except models.Loan.DoesNotExist:
            raise NotFound('Loan with ID {} not found.'.format(pk))

    def get_serializer_class(self):
        return serializers.BackfillRequestPOSTSerializer

    def post(self, request, pk, format=None):
        loan = self.get_loan(pk=pk)

        data = request.data.copy()
        data.update({"loan" : loan})
        serializer = self.get_serializer(data=data)
        if serializer.is_valid():
            serializer.save()

        return Response(serializer.data)

class BackfillRequestDetailModifyCancel(generics.GenericAPIView):
    authentication_classes = (authentication.SessionAuthentication,)
    permission_classes = (permissions.IsAuthenticated,)

    def get_instance(self, pk):
        try:
            return models.BackfillRequest.objects.get(pk=pk)
        except models.BackfillRequest.DoesNotExist:
            raise NotFound('BackfillRequest with ID {} not found.'.format(pk))

    def get_serializer_class(self):
        if self.request.method == 'PUT':
            return serializers.BackfillRequestPUTSerializer
        return serializers.BackfillRequestGETSerializer

    # MANAGER/OWNER LOCKED
    def get(self, request, pk, format=None):
        instance = self.get_instance(pk)
        # if manager, see any backfill request.
        # if user, only see your backfill requests
        is_owner = (instance.loan.request.requester.pk == request.user.pk)
        if not (request.user.is_staff or request.user.is_superuser or is_owner):
            d = {"error": ["Manager or owner permissions required."]}
            return Response(d, status=status.HTTP_403_FORBIDDEN)

        serializer = self.get_serializer(instance=instance)
        return Response(serializer.data)

    # MANAGER/OWNER LOCKED
    #  - only admins may change the status or admin_comment fields on a BackfillRequest
    #  - only owners may change the receipt on a BackfillRequests
    def put(self, request, pk, format=None):
        instance = self.get_instance(pk)
        is_owner = (instance.loan.request.requester.pk == request.user.pk)
        if not (request.user.is_staff or request.user.is_superuser or is_owner):
            d = {"error": ["Manager or owner permissions required."]}
            return Response(d, status=status.HTTP_403_FORBIDDEN)

        data = request.data.copy()
        #data.update({'user': request.user}) # add back in to deal with permissioning on a field-level basis in serializer

        if not (instance.status == 'O'):
            return Response({"status": ["Only outstanding backfill requests may be modified."]})

        serializer = self.get_serializer(instance=instance, data=data, partial=True)

        if serializer.is_valid():
            serializer.save()
            if serializer.data.get('status', None) == "A":
                approveBackfillRequest(instance)

            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    # OWNER LOCKED
    def delete(self, request, request_pk, format=None):
        instance = self.get_instance(pk)
        is_owner =  (instance.loan.request.requester.pk == request.user.pk)
        if not (is_owner):
            d = {"error": ["Owner permissions required"]}
            return Response(d, status=status.HTTP_403_FORBIDDEN)

        if not (instance.status == 'O'):
            d = {"error": ["Cannot delete an approved/denied request."]}
            return Response(d, status=status.HTTP_403_FORBIDDEN)

        instance.delete()
        #sendEmailForDeletedOutstandingBackfillRequest? Probably not
        # Don't post log here since its as if it never happened?
        return Response(status=status.HTTP_204_NO_CONTENT)
