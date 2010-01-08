from django.conf.urls.defaults import *
from django.contrib.comments.models import FreeComment

urlpatterns = patterns('',
	(r'^music/', 		include('zoid.music.urls')),
	(r'^blogs/',		include('zoid.blogs.urls')),
	(r'^feeds/',		include('zoid.feeds.urls')),
	(r'^prefs/',		include('zoid.prefs.urls')),
    (r'^admin/', 		include('django.contrib.admin.urls')),	
	(r'^comments/', 	include('django.contrib.comments.urls.comments')),
	(r'^$', 			'zoid.music.views.default_index'),
)
