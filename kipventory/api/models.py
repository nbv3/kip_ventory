from django.db import models
from django.contrib.auth.models import User


# Create your models here.
class Tag(models.Model):
    name = models.CharField(max_length=100)

    def __str__(self):
        return self.name


class Item(models.Model):
    name        = models.CharField(max_length=100, unique=True)
    photo_src   = models.ImageField(upload_to='items')
    location    = models.CharField(max_length=100)
    model       = models.CharField(max_length=100)
    quantity    = models.IntegerField(default=0)
    description = models.TextField(max_length=500)
    tags        = models.ManyToManyField(Tag, blank=True)

    def __str__(self):
        return self.name


class CartItem(models.Model):
    item     = models.ForeignKey(Item, on_delete=models.CASCADE)
    owner    = models.ForeignKey(User, on_delete=models.CASCADE)
    quantity = models.IntegerField(default=1)

    def __str__(self):
        return "Item: {}, Owner: {}, Quantity: {}".format(self.item, self.owner, self.quantity)


class Request(models.Model):
    requester       = models.ForeignKey(User, on_delete=models.CASCADE)
    item            = models.ForeignKey(Item, on_delete=models.CASCADE)
    quantity        = models.IntegerField()
    date_open       = models.DateTimeField(blank=True)
    open_reason     = models.TextField(max_length=500, blank=True)

    def __str__(self):
        return "{} {}".format(self.requester, self.item)

class RequestResponse(models.Model):
    request         = models.ForeignKey(Request, on_delete=models.CASCADE)
    date_closed     = models.DateTimeField(blank=True, null=True)
    closed_comment  = models.TextField(max_length=500, blank=True, null=True)
    administrator   = models.ForeignKey(User, on_delete=models.CASCADE, related_name='requests_administrated', blank=True, null=True)
    APPROVED = 'A'
    DENIED = 'D'
    ### Status Choices ###
    status_choices      = (
        (APPROVED, 'Approved'),
        (DENIED, 'Denied'),
    )
    status          = models.CharField(max_length = 10, choices=status_choices, default=DENIED)
