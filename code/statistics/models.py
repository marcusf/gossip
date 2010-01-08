from django.db import models
from zoid.music.models import Track, Artist
from zoid.feeds.models import Enclosure, Post
from datetime import datetime
from urllib import quote_plus
import time
from zoid.helpers.utils import *
from django.db.models import Q


def get_similar(artist_name):
	artist = Artist.objects.filter(name__icontains=artist_name)
	if not artist: return []
	artist = artist[0]
	if len(SoundsLike.objects.filter(artist_one=artist)) == 0: 
		get_similar_lastfm(artist)
	a1 = SoundsLike.objects.filter(Q(artist_one=artist)|Q(artist_two=artist))
	similars = []
	for similar in a1:
		if similar.artist_one == artist: similars.append((similar.artist_two, similar.strength))
		else: similars.append((similar.artist_one, similar.strength))

	titles = uniq([a[0].name for a in similars])
	uniq_similars = []
	for sim in similars:
		if sim[0].name in titles:
			titles = [t for t in titles if t != sim[0].name]
			uniq_similars.append(sim)
	
	uniq_similars.sort(lambda x,y: x[1] > y[1])
	
	return uniq_similars
	

def get_similar_lastfm(artist):
	url = 'http://ws.audioscrobbler.com/1.0/artist/%s/similar.txt' % (quote_plus(artist.name))
	
	data, url = get_data_from_url(url)
	if re.match('^No artist exists with this name:.*', data): return
	
	matches = [(p.group(2), p.group(1)) for p in \
	  [re.match('([^,]+),[a-z0-9\-]*,(.+)',line) for line in data.split('\n')]\
	 if p]
	
	for match in matches:
		artist2 = Artist.artist_manager.find_or_create(match[0])
		SoundsLike.manager.similar_lastfm(artist, artist2, match[1])
		
class SoundsLikeManager(models.Manager):
	def similar_lastfm(self, artist1, artist2, strength):
		try:
			obj = SoundsLike.objects.get(artist_one=artist1,artist2=artist2, type=SoundsLike.LAST_FM)
			return obj
		except:
			try:
				obj = SoundsLike.objects.get(artist_one=artist1,artist2=artist2, type=SoundsLike.LAST_FM)
				return obj
			except: pass
		obj = self.model(artist_one=artist1,artist_two=artist2, type=SoundsLike.LAST_FM, strength=strength)
		obj.save()
		return obj


class SoundsLike(models.Model):
	LAST_FM  = 0
	INTERNAL = 1
	artist_one = models.ForeignKey(Artist, related_name='soundslike_one')
	artist_two = models.ForeignKey(Artist, related_name='soundslike_two')
	type = models.IntegerField(default=0)
	strength = models.FloatField(default=0.0)
	
	objects = models.Manager()
	manager = SoundsLikeManager()

class TrackStatisticsManager(models.Manager):
	def create_from_track(self, track):
		"""Creates a new statistic from a given track."""
		stat = TrackStatistics(track=track)
		stat.update_date()
		stat.update_importance()
		stat.update()
		stat.save()
		return stat
		
	def find_all(self):
		tracks = self.update_all_nosave()
		return tracks

	def update_all_nosave(self):
		tracks = []
		for track in Track.objects.all():
			try: track.trackstatistics.update()
			except: self.create_from_track(track)
			tracks.append(track)
		return tracks

	def update_all_tracks(self):
		for track in Track.objects.all():
			try: 
				track.trackstatistics.update_date()
				track.trackstatistics.update_importance()
				track.trackstatistics.update()
			except: self.create_from_track(track)
			else: track.trackstatistics.save()
	
	def update_all(self):
		for stat in TrackStatistics.objects.all():
			stat.update_date()
			stat.update_importance()
			stat.update()
			stat.save()

class TrackStatistics(models.Model):
	"""Contains statistics on the popularity of a track."""
	track = models.OneToOneField(Track)
	global_score = models.FloatField(default=0)
	published = models.DateTimeField()
	last_seen = models.DateTimeField()
	
	objects = models.Manager()
	manager = TrackStatisticsManager()
	
	sort_score = 0
	
	WEIGHT_FRESH 	= 2
	WEIGHT_BLOG 	= 1
	
	def __unicode__(self):
		try: name = self.track.artist.name
		except: name = "<unknown>"
		return "'%s' rating" % (name)
		
	def update_date(self):
		# First, compute the date
		self.published = datetime.today()
		self.last_seen = datetime(1985, 04, 06, 0, 0, 0)
		enclosures =  self.track.enclosure_set.all()
		for enclosure in enclosures:
			date = enclosure.post.published
			if date < self.published:
				actual_date = True
				self.published = date
			if date > self.last_seen:
				self.last_seen = date
				
	def update_importance(self):
		self.global_score = self.importance(self.track)
	
	def update(self):
		"""Recomputes the statistics for a given track."""
		# Then, magic sauce all around!
		self.sort_score = self.WEIGHT_BLOG*self.global_score
		freshness = self.freshness(self.published)
		if self.sort_score != 0:
			self.sort_score += self.WEIGHT_FRESH*freshness
		
	def importance(self, track):
		"""Calculates some measure of the tracks importance as a sum of the 
		ranks of the blogs that posted it, somewhat normalized."""
		rank = 0.0
		# This is amazingly ineffective and should be replaced with a nice,
		# joined query in production. But no time to figure out how to do that clean
		# today.
		for enclosure in track.enclosure_set.all():
			rank += enclosure.post.feed.blog.rank
		return rank
	
	def freshness(self, date):
		"""Returns a measure of the freshness of a certain track. The fresher,
		the higher the number."""
		today = time.mktime(datetime.today().timetuple())
		the_date = time.mktime(date.timetuple())
		return 100000*1/(abs(today-the_date)+0.01)
		