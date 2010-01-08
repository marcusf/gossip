from django.conf.urls.defaults import *
from django.contrib.comments.models import FreeComment

urlpatterns = patterns('',
	(r'^$', 'django.contrib.auth.views.login',{'template_name':'prefs_login.html'}),
	(r'^register/$', 'zoid.prefs.views.register'),
	(r'^login/$', 'django.contrib.auth.views.login',{'template_name':'prefs_login.html'}),
	(r'^logout/$', 'django.contrib.auth.views.logout'),
)
