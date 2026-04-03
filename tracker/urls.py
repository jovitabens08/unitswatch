from django.urls import path
from . import views

urlpatterns = [
    path('',                                        views.home,             name='home'),
    path('register/',                               views.register_view,    name='register'),
    path('login/',                                  views.login_view,       name='login'),
    path('logout/',                                 views.logout_view,      name='logout'),

    path('dashboard/',                              views.dashboard,        name='dashboard'),

    path('meters/',                                 views.meters_list,      name='meters'),
    path('meters/add/',                             views.add_meter,        name='add_meter'),
    path('meters/<str:meter_id>/',                  views.meter_detail,     name='meter_detail'),
    path('meters/<str:meter_id>/delete/',           views.delete_meter,     name='delete_meter'),
    path('meters/<str:meter_id>/readings/add/',     views.add_reading,      name='add_reading'),
    path('readings/<str:reading_id>/delete/',       views.delete_reading,   name='delete_reading'),

    path('billing/',                                views.billing_cycles,   name='billing_cycles'),
    path('billing/<str:meter_id>/close/',           views.close_cycle,      name='close_cycle'),

    path('recommendations/',                        views.recommendations,  name='recommendations'),
    path('history/',                                views.history,          name='history'),
    path('export/csv/',                             views.export_csv,       name='export_csv'),

    path('api/readings/<str:meter_id>/',            views.api_readings,     name='api_readings'),
]
