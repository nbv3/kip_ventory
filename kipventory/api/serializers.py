from rest_framework import serializers, pagination
from rest_framework.exceptions import ValidationError
from . import models
from django.contrib.auth.models import User
from django.utils import timezone
import re, json


class CustomFieldSerializer(serializers.ModelSerializer):
    name = serializers.CharField(required=True)
    private = serializers.BooleanField(default=False)
    field_type = serializers.ChoiceField(choices=models.FIELD_TYPES)

    class Meta:
        model = models.CustomField
        fields = ('name', 'private', 'field_type',)

    def validate(self, data):
        name = data.get('name')
        field_exists = (models.CustomField.objects.filter(name=name).count() > 0)
        if field_exists:
            raise ValidationError({"name": ["A field with name \'{}\' already exists.".format(request.data['name'])]})
        return data

class CustomValueSerializer(serializers.ModelSerializer):
    field = serializers.SlugRelatedField(read_only=True, slug_field="name")
    value = serializers.CharField(max_length=None, min_length=None, required=True, source='*', allow_blank=True)

    class Meta:
        model = models.CustomValue
        fields = ('field', 'value',)

    def to_representation(self, cv):
        d = {'name': cv.field.name, 'value': cv.get_value(), 'field_type': cv.field.field_type}
        return d

    def to_internal_value(self, data):
        validated_data = {}
        errors = {}
        # get value type specified in CustomField
        name = data.get('name')
        ft = models.CustomField.objects.get(name=name).field_type
        # convert value to correct type
        try:
            value = data.get('value')
            validated_data['value'] = models.FIELD_TYPE_DICT[ft](value)
        except:
            errors.update({'value': ['Field \'{}\' requires values of type \'{}\'.'.format(name, type(value).__name__)]})

        if errors:
            raise ValidationError(errors)

        return validated_data

    def update(self, instance, validated_data):
        ft = instance.field.field_type
        setattr(instance, ft, validated_data.get('value', getattr(instance, ft)))
        instance.save()
        return instance

class ItemSerializer(serializers.ModelSerializer):
    name          = serializers.CharField(max_length=None, min_length=None)
    quantity      = serializers.IntegerField(min_value=0, max_value=None)
    model_no      = serializers.CharField(max_length=None, min_length=None, allow_blank=True)
    description   = serializers.CharField(max_length=None, min_length=None, allow_blank=True)
    tags          = serializers.SlugRelatedField(slug_field="name", read_only=False, many=True, queryset=models.Tag.objects.all())
    custom_fields = serializers.SerializerMethodField(method_name="get_custom_fields_by_permission")
    in_cart       = serializers.SerializerMethodField(method_name="is_item_in_cart")

    class Meta:
        model  = models.Item
        fields = ['name', 'quantity', 'model_no', 'description', 'tags', 'custom_fields', 'in_cart']

    def get_custom_fields_by_permission(self, item):
        user = self.context['request'].user
        if user.is_staff:
            return [{"name": cv.field.name, "value": cv.get_value(), "field_type": cv.field.field_type, "private": cv.field.private} for cv in item.values.all()]
        else:
            return [{"name": cv.field.name, "value": cv.get_value(), "field_type": cv.field.field_type} for cv in item.values.all().filter(field__private=False)]

    def is_item_in_cart(self, item):
        user = self.context['request'].user
        is_in_cart = (models.CartItem.objects.filter(owner__pk=user.pk, item__name=item.name).count() > 0)
        return is_in_cart

    def to_internal_value(self, data):
        errors = {}
        clean_data = {}

        # Validate any custom field definitions - only accept name, value pairs
        custom_field_data = data.pop('custom_fields', [])

        custom_field_list = []
        existing_fields = models.CustomField.objects.all()

        for index, field_dict_json in enumerate(custom_field_data):
            # convert from JSON
            field_dict = json.loads(field_dict_json)

            name = field_dict.get('name', None)
            value = field_dict.get('value', None)
            index_error = {index: {}}

            if name is None:
                index_error[index].update({"name": ["This field is required."]})
            if value is None:
                index_error[index].update({"value": ["This field is required."]})
            try:
                cf = existing_fields.get(name=name)
                try:
                    value = models.FIELD_TYPE_DICT[cf.field_type](value)
                    custom_field_list.append({"field": cf, "value": value})
                except:
                    index_error[index].update({"value": ['Field \'{}\' requires values of type \'{}\'.'.format(name, type(value).__name__)]})
            except models.CustomField.DoesNotExist:
                index_error[index].update({"name": ["Custom field with name '{}' does not exist.".format(name)]})
            if (index_error[index]):
                if 'custom_fields' not in errors.keys():
                    errors['custom_fields'] = {}
                errors['custom_fields'].update(index_error)

        if errors:
            raise ValidationError(errors)

        item_dict = super(ItemSerializer, self).to_internal_value(data)

        clean_data.update(item_dict)
        clean_data['custom_fields'] = custom_field_list
        return clean_data

    def validate(self, clean_data):
        errors = {}
        # Check if the item name conflicts with an existing item
        name = clean_data.get('name', None)
        if name is not None:
            item_exists = (models.Item.objects.filter(name=name).count() > 0)
            if item_exists:
                # if we're making a PUT request, we should have an instance.
                if self.instance:
                    if not (self.instance.name == name):
                        errors.update({"name": ["An item with this name already exists."]})
                # This must be a POST request, in which case we know the operation is invalid
                else:
                    errors.update({"name": ["An item with this name already exists."]})

        quantity = clean_data.get('quantity', None)
        if self.instance:
            if (quantity != self.instance.quantity) and not self.context['request'].user.is_superuser:
                errors.update({'quantity': ['Administrator privileges required to directly modify quantity.']})

        if errors:
            raise ValidationError(errors)

        return clean_data

    def modify_fields(self, item, custom_fields):
        # there will be a complete set of blank CustomValues associated with this Item
        # as a result of the Item.save() method.
        item_values = item.values.all()

        # iterate through the name/value pairs we were passed in data
        for i, fd in enumerate(custom_fields):
            field = fd.get('field')
            value = fd.get('value')
            cv = item_values.get(field__pk=field.pk)
            setattr(cv, field.field_type, value)
            cv.save()

    def create(self, validated_data):
        # custom field - list of name/value pairs (dicts)
        custom_fields = validated_data.pop('custom_fields')
        # item data - everything else
        item_data = validated_data
        # Create the item instance
        item = super(ItemSerializer, self).create(item_data)
        # Set Custom Fields on the item
        self.modify_fields(item, custom_fields)

        item.save()
        return item

    def update(self, instance, validated_data):
        # custom field - list of name/value pairs (dicts)
        custom_fields = validated_data.pop('custom_fields')
        # item data - everything else
        item_data = validated_data
        # Create the item instance
        item = super(ItemSerializer, self).update(instance, item_data)

        if item_data.get('tags', None) is None:
            for tag in item.tags.all():
                item.tags.remove(tag)

        # Set Custom Fields on the item
        self.modify_fields(item, custom_fields)

        item.save()
        return item

class CartItemSerializer(serializers.ModelSerializer):
    def __init__(self, *args, **kwargs):
        super(CartItemSerializer, self).__init__(*args, **kwargs)
        self.fields['item'].context = self.context

    item         = ItemSerializer(read_only=True, many=False)
    quantity     = serializers.IntegerField(min_value=0, max_value=None, required=True)
    request_type = serializers.ChoiceField(choices=models.ITEM_REQUEST_TYPES, default=models.DISBURSEMENT)
    due_date     = serializers.DateTimeField(allow_null=True, required=False)

    class Meta:
        model = models.CartItem
        fields = ['item', 'quantity', 'request_type', 'due_date']

    def is_future_date(self, date):
        now = timezone.now()
        return date > now

    def to_internal_value(self, data):
        item = data.get('item', None)
        owner = data.get('owner', None)
        data = super(CartItemSerializer, self).to_internal_value(data)
        data.update({"item": item, 'owner': owner})
        return data

    def validate(self, data):
        request_type = data.get('request_type', None)
        due_date = data.get('due_date', None)
        if request_type == models.LOAN:
            if due_date is None:
                raise ValidationError({"due_date": ["Must provide a due date for a loan request."]})
            else:
                if not self.is_future_date(due_date):
                    raise ValidationError({"due_date": ["Only future dates are allowed."]})
        return data

    def create(self, validated_data):
        ci = super(CartItemSerializer, self).create(validated_data)
        if ci.request_type == models.DISBURSEMENT:
            ci.due_date = None
        ci.save()
        return ci

    def update(self, ci, validated_data):
        ci = super(CartItemSerializer, self).update(ci, validated_data)
        if ci.request_type == models.DISBURSEMENT:
            ci.due_date = None
        ci.save()
        return ci



class TagSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.Tag
        fields = ["id", 'name']

class TransactionSerializer(serializers.ModelSerializer):
    item          = serializers.SlugRelatedField(queryset=models.Item.objects.all(), slug_field="name")
    administrator = serializers.SlugRelatedField(queryset=User.objects.filter(is_staff=True), slug_field="username")

    class Meta:
        model = models.Transaction
        fields = ["id", 'item', 'category', 'quantity', 'date', 'comment', 'administrator']

class UserGETSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'first_name', 'last_name', 'email', 'is_staff', 'is_superuser']

def validate_username(instance, value):
    netid_regex = re.compile(r'[a-z]{2,3}[0-9]{1,3}')
    if netid_regex.fullmatch(value):
        raise serializers.ValidationError("Username cannot be the same form as Duke NetID.")
    username_taken = (User.objects.filter(username=value).count() > 0)
    if username_taken:
        # POST REQUEST - We know instance is None
        if instance is None:
            raise ValidationError({"username": ["Username '{}' is already taken.".format(username)]})
        # PUT REQUEST - We must check and make sure that we're not changing our username to itself (ie. Brody -> Brody)
        else:
            if not (instance.username == value):
                raise ValidationError({"username": ["Username '{}' is already taken.".format(username)]})
    return value

class UserPOSTSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'password', 'first_name', 'last_name', 'email']

    def validate_username(self, value):
        return validate_username(self.instance, value)

    # add unique email when we add user signup back in
    '''
    def validate_email(self, value):
        email_taken = (User.objects.filter(email=email).count() > 0)

        if email_taken:
            raise serializers.ValidationError("Email is already taken.")
        return value
    '''

class UserPUTSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'password', 'first_name', 'last_name', 'email', 'is_staff', 'is_superuser']

    def validate_username(self, value):
        #todo make sure you can't change username to somebody else's.
        return validate_username(self.instance, value)

class RequestedItemSerializer(serializers.ModelSerializer):
    item         = serializers.SlugRelatedField(read_only=True, slug_field="name")
    quantity     = serializers.IntegerField(required=True)
    request_type = serializers.ChoiceField(choices=models.ITEM_REQUEST_TYPES)
    due_date     = serializers.DateTimeField(allow_null=True, required=False)

    class Meta:
        model = models.RequestedItem
        fields = ['item', 'quantity', 'request_type', 'due_date']

    def is_future_date(self, date):
        return True

    def to_representation(self, ri):
        d = {"item": ri.item.name, "quantity": ri.quantity, "request_type": ri.request_type}
        if ri.due_date is not None and ri.request_type == models.LOAN:
            d.update({"due_date": ri.due_date})
        return d

    def validate(self, data):
        request_type = data.get('request_type', None)
        due_date = data.get('due_date', None)
        if request_type == models.LOAN:
            if due_date is None:
                raise ValidationError({"due_date": ["Must provide a due date for a loan request."]})
            else:
                if not self.is_future_date(due_date):
                    raise ValidationError({"due_date": ["Only future dates are allowed."]})
        return data

    def create(self, validated_data):
        ri = super(RequestedItemSerializer, self).create(validated_data)
        if ri.request_type == models.DISBURSEMENT:
            ri.due_date = None
        ri.save()
        return ri

    def update(self, ri, validated_data):
        ri = super(RequestedItemSerializer, self).update(ri, validated_data)
        if ri.request_type == models.DISBURSEMENT:
            ri.due_date = None
        ri.save()
        return ri


class RequestSerializer(serializers.ModelSerializer):
    request_id       = serializers.ReadOnlyField(source='id')
    requester        = serializers.SlugRelatedField(read_only=True, slug_field="username")
    requested_items  = RequestedItemSerializer(read_only=True, many=True)
    date_open        = serializers.ReadOnlyField()
    open_comment     = serializers.CharField(max_length=500, default='', allow_blank=True)
    date_closed      = serializers.ReadOnlyField()
    closed_comment   = serializers.ReadOnlyField()
    administrator    = serializers.SlugRelatedField(read_only=True, slug_field="username")
    status           = serializers.ChoiceField(read_only=True, choices=models.STATUS_CHOICES)

    class Meta:
        model = models.Request
        fields = ['request_id', 'requester', 'requested_items', 'date_open', 'open_comment', 'date_closed', 'closed_comment', 'administrator', 'status']

    def to_internal_value(self, data):
        requester = data.get('requester', None)
        validated_data = super(RequestSerializer, self).to_internal_value(data)
        validated_data.update({"requester": requester})
        return validated_data

class RequestPUTSerializer(serializers.ModelSerializer):
    request_id      = serializers.ReadOnlyField(source='id')
    requester       = serializers.SlugRelatedField(read_only=True, slug_field="username")
    requested_items = RequestedItemSerializer(read_only=True, many=True)
    date_open       = serializers.DateTimeField(read_only=True)
    open_comment    = serializers.CharField(read_only=True)
    administrator   = serializers.SlugRelatedField(read_only=True, slug_field="username")
    date_closed     = serializers.DateTimeField(read_only=True)
    closed_comment  = serializers.CharField(max_length=500, allow_blank=True, default="")
    status          = serializers.ChoiceField(choices=((models.APPROVED, 'Approved'), (models.DENIED, 'Denied')))

    class Meta:
        model = models.Request
        fields = ['request_id', 'requester', 'requested_items', 'date_open', 'open_comment', 'date_closed', 'closed_comment', 'administrator', 'status']

    def to_internal_value(self, data):
        date_closed = timezone.now()
        administrator = data.get('administrator', None)

        validated_data = super(RequestPUTSerializer, self).to_internal_value(data)

        validated_data.update({"date_closed": date_closed, "administrator": administrator})
        return validated_data

class LogSerializer(serializers.ModelSerializer):
    item            = serializers.SlugRelatedField(slug_field="name",     read_only=True)
    initiating_user = serializers.SlugRelatedField(slug_field="username", read_only=True)
    affected_user   = serializers.SlugRelatedField(slug_field="username", read_only=True)

    class Meta:
        model = models.Log
        fields = ['id', "item", "request", "quantity", "date_created", "initiating_user", 'message', 'affected_user', "category", "default_item", "default_affected_user", "default_initiating_user"]
