from django.conf.urls.defaults import *

urlpatterns = patterns('',
	(r'^(?P<pno>\d+)?/?', 'zoid.feeds.views.show'),
)