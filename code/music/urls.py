from django.conf.urls.defaults import *
from django.contrib.comments.models import FreeComment

urlpatterns = patterns('',
	(r'^(?P<pno>\d+)?$', 			'zoid.music.views.index'),
	(r'^love/(?P<tid>\d+)?/?', 		'zoid.music.views.love'),
	(r'^hate/(?P<tid>\d+)?/?', 		'zoid.music.views.hate'),
	(r'^explore/(?P<id>\d+)/?', 	'zoid.music.views.explore'),
	(r'^track/(?P<id>\d+)/?', 		'zoid.music.views.track'),
	(r'^explore/(?P<query>.+)/?', 	'zoid.music.views.explore_string'),
	(r'^similar/(?P<id>\d+)/?', 	'zoid.music.views.similar'),
)