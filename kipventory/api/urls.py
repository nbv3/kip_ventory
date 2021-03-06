from django.conf.urls import url, include
from rest_framework.urlpatterns import format_suffix_patterns

from . import views
from django.contrib.auth import views as auth_views


urlpatterns = [

    # ITEM ENDPOINTS
    url(r'^items/?$',                                               views.ItemListCreate.as_view()),
    url(r'^items/(?P<item_name>.+?)/assets/(?P<asset_tag>.+?)/?$',  views.AssetDetailModify.as_view()),
    url(r'^assets/(?P<asset_tag>.+?)/?$',  views.AssetDetail.as_view()),
    url(r'^items/(?P<item_name>.+?)/assets/?$',                     views.AssetList.as_view()),
    url(r'^items/(?P<item_name>.+?)/requests/?$',                   views.GetOutstandingRequestsByItem.as_view()),
    url(r'^items/(?P<item_name>.+?)/stacks/?$',                     views.GetItemStacks.as_view()),
    url(r'^items/(?P<item_name>.+?)/loans/?$',                      views.GetLoansByItem.as_view()),
    url(r'^items/(?P<item_name>.+?)/transactions/?$',               views.GetTransactionsByItem.as_view()),
    url(r'^items/(?P<item_name>.+?)/addtocart/?$',                  views.AddItemToCart.as_view()),
    url(r'^items/(?P<item_name>.+?)/?$',                            views.ItemDetailModifyDelete.as_view()),

    url(r'^import/?$',          views.BulkImport.as_view()),
    url(r'^import/template/?$', views.BulkImportTemplate.as_view()),

    url(r'^tags/?$', views.TagListCreate.as_view()),
    url(r'^tags/(?P<tag_name>.+?)/$', views.TagDelete.as_view()),


    url(r'^fields/?$',                     views.CustomFieldListCreate.as_view()),
    url(r'^fields/(?P<field_name>.+?)/?$', views.CustomFieldDetailDelete.as_view()),

    url(r'^cart/?$',                     views.CartItemList.as_view()),
    url(r'^cart/?(?P<item_name>.+?)/?$', views.CartItemDetailModifyDelete.as_view()),


    url(r'^loans/?$',                        views.LoanList.as_view()),
    url(r'^loans/all/?$',                    views.LoanListAll.as_view()),
    url(r'^loans/(?P<pk>[\d]+?)/?$',         views.LoanDetailModify.as_view()),
    url(r'^loans/(?P<pk>[\d]+?)/convert/?$', views.ConvertLoanToDisbursement.as_view()),
    url(r'^loans/(?P<loan_id>[\d]+?)/requestforbackfill/?$', views.BackfillRequestCreate.as_view()),

    #url(r'^backfillrequests/all/?$',                    views.BackfillRequestListAll.as_view()),
    url(r'^backfillrequests/(?P<pk>[\d]+?)/?$', views.BackfillRequestDetailModifyCancel.as_view()),

    url(r'^backfills/(?P<pk>[\d]+?)/?$', views.BackfillDetailModify.as_view()),

    # url(r'^disbursements/?$',                views.DisbursementList.as_view()),
    # url(r'^disbursements/(?P<pk>[\d]+?)/?$', views.DisbursementDetail.as_view()),

    url(r'^loanreminders/?$', views.LoanReminderListCreate.as_view()),
    url(r'^loanreminders/(?P<id>[\d]+?)/?$', views.LoanReminderModifyDelete.as_view()),

    url(r'^subjecttag/?$', views.SubjectTagGetModify.as_view()),


    url(r'^transactions/?$', views.TransactionListCreate.as_view()),

    url(r'^disburse/?$', views.DisburseCreate.as_view()),

    url(r'^requests/?$',                                            views.RequestListCreate.as_view()),
    url(r'^requests/all/?$',                                        views.RequestListAll.as_view()),
    url(r'^requests/(?P<request_pk>[0-9]+?)/?$',                    views.RequestDetailModifyDelete.as_view()),
    url(r'^requests/(?P<request_pk>[0-9]+?)/backfills/?$',          views.GetBackfillsByRequest.as_view()),
    url(r'^requests/(?P<request_pk>[0-9]+?)/backfills/requests/?$', views.GetBackFillRequestsByRequest.as_view()),
    url(r'^requests/(?P<request_pk>[0-9]+?)/loans/?$',              views.GetLoansByRequest.as_view()),
    url(r'^requests/(?P<request_pk>[0-9]+?)/disbursements/?$',      views.GetDisbursementsByRequest.as_view()),

    url(r'^login/?$',  views.post_user_login),
    url(r'^logout/?$', auth_views.logout),
    url(r'^apitoken/?$', views.TokenPoint.as_view()),

    url(r'^logs/?$', views.LogList.as_view()),

    url(r'^users/?$',         views.UserList.as_view()),
    url(r'^users/current/?$', views.GetCurrentUser.as_view()),
    url(r'^users/edit/(?P<username>[\w\s]+)/?$',         views.EditUser.as_view()),
    url(r'^users/create/?$',         views.UserCreate.as_view()),
    url(r'^users/managers/subscribed/?$', views.GetSubscribedManagers.as_view()),

    url(r'^netidtoken/?$',    views.GetNetIDToken.as_view()),

    url(r'^backupemail/?$', views.BackupEmail.as_view()),
]

urlpatterns = format_suffix_patterns(urlpatterns)
