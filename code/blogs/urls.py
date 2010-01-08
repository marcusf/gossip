from django.conf.urls.defaults import *

urlpatterns = patterns('',
	(r'^$', 'zoid.blogs.views.index'),
	(r'^list/(?P<pno>\d+)?/?', 'zoid.blogs.views.list'),
	(r'^listing/', 'zoid.blogs.views.listing'),
	(r'^(?P<pno>\d+)/refresh/$', 'zoid.blogs.views.refresh'),
	(r'^(?P<blog_id>\d+)/$', 'zoid.blogs.views.details'),
)