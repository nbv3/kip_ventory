from django.db import models
from django.contrib.auth.models import User


# Create your models here.
class Tag(models.Model):
    name = models.CharField(max_length=100)

    def __str__(self):
        return self.name


class Item(models.Model):
    name        = models.CharField(max_length=100, unique=True)
    location    = models.CharField(max_length=100)
    model       = models.CharField(max_length=100)
    quantity    = models.IntegerField(default=0)
    description = models.TextField(max_length=500)
    tags        = models.ManyToManyField(Tag, blank=True)

    def __str__(self):
        return self.name


class Request(models.Model):
    requester       = models.ForeignKey(User, on_delete=models.CASCADE)
    item            = models.ForeignKey(Item, on_delete=models.CASCADE)
    quantity        = models.IntegerField()
    date_open       = models.DateTimeField()
    open_reason     = models.TextField(max_length=500)
    date_closed     = models.DateTimeField()
    closed_comment  = models.TextField(max_length=500)
    administrator   = models.ForeignKey(User, on_delete=models.CASCADE, related_name='requests_administrated')

    OUTSTANDING = 'O'
    APPROVED = 'A'
    COMPLETE = 'C'
    ### Status Choices ###
    status_choices      = (
        (OUTSTANDING, 'Outstanding'),
        (APPROVED, 'Approved'),
        (COMPLETE, 'Complete'),
    )
    status          = models.CharField(max_length = 10, choices = status_choices, default = OUTSTANDING)


    def __str__(self):
        return "{} {}".format(self.requester, self.item)
