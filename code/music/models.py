"""
	music.models
	Defines classes directly related to tracks, and the parsing of them,
	especially artist metadata and track metadata (including popularity).
"""

from django.db import models
from django.contrib.auth.models import User
from zoid.helpers.utils import get_data_from_url
#from zoid.statistics.models import TrackStatistics

class ArtistManager(models.Manager):
	"""Manages overarching responsibilites for the artist class."""
	
	def find_or_create(self, artist_name):
		"""Finds or creates and returns an artist object given its name.
		Case insensitive."""
		artist = Artist.objects.filter(name__iexact=artist_name)
		if artist: return artist[0]
		artist = Artist(name=artist_name)
		artist.save()
		return artist

class Artist(models.Model):
	"""An artist identifier, eg. 'MSTRKRFT'"""
	name = models.CharField(max_length=200)
	description = models.TextField(blank=True, null=True)
	
	objects = models.Manager()
	artist_manager = ArtistManager()
	
	def __unicode__(self): return self.name
		
		
	class Admin: 
		pass

class TrackManager(models.Manager):
	"""Manages track related things."""
	
	def find_or_create(self, artist, title):
		"""This looks especially nasty, thanks to alot of bug fixing.
		Due for a cleanup."""
		if artist and title:
			artistobj = Artist.artist_manager.find_or_create(artist)
			track = self.find_by_artist_model_and_title(artistobj, title)
		else: track = None
		if not track:
			if artist:
				artistobj = Artist.artist_manager.find_or_create(artist)
				track = Track(artist=artistobj, title=title)
			else:
				track = Track(title=title)
			track.save()
			#TrackStatistics.manager.create_from_track(track)
		return track

	def find_by_artist_model_and_title(self, artist, title):
		track = Track.objects.filter(artist=artist).filter(title__iexact=title)
		if track: return track[0]
		
	def find_by_artist_and_title(self, artist, title):
		track = Track.objects.filter(artist__name__iexact=artist).filter(title__iexact=title)
		if track: return track[0]

class Track(models.Model):
	"""A track identifier, i.e. 'MSTRKRFT - The Looks'"""
	artist = models.ForeignKey(Artist, null=True, blank=True)
	title = models.CharField(max_length=300)
	slug = models.SlugField(prepopulate_from=("artist","title"))
	
	user_for_relation = None
	
	objects = models.Manager()
	track_manager = TrackManager()
	
	def set_user_for_relation(self,user):
		self.user_for_relation = user
	
	def user_relation(self):
		return Popularity.popper.state(self.user_for_relation, self)

	def __unicode__(self):
		return '%(artist)s - %(title)s' % \
		{'artist': self.artist, 'title': self.title}
		
	class Meta:
		unique_together = (("artist", "title"),)
	# Admin stuff	
	class Admin:
		pass


class PopularityManager(models.Manager):
	"""Manages track popularity, i.e. if a user loves or hates a track."""
	def love(self, user, track):
		"""Makes user love track."""
		trackpop = self.__get(user, track)
		if trackpop:
			trackpop.love()
			trackpop.save()
			return sum([t.score for t in Popularity.objects.filter(track=track)])

	def hate(self, user, track):
		"""Makes user hate track."""
		trackpop = self.__get(user, track)
		if trackpop:
			trackpop.hate()
			trackpop.save()
			return sum([t.score for t in Popularity.objects.filter(track=track)])

	def state(self, user, track):
		"Returns either -1 == hate, or 1 == love."
		trackpop = self.__get(user, track)
		if trackpop: return trackpop.score

	def __get(self, user, track):
		"Returns a popularity for a track. Creates a new pop object if none exists."
		try: 
			trackpop = Popularity.objects.get(track=track, user=user)
		except:
			 trackpop = Popularity(user=user, track=track)
		return trackpop

class Popularity(models.Model):
	"""Likability scheme to use for slope one predictors."""
	user = models.ForeignKey(User, related_name='voted_tracks')
	track = models.ForeignKey(Track, related_name='predictions')
	score = models.IntegerField(default=0)

	objects = models.Manager()
	popper = PopularityManager()

	class Meta:
		unique_together = (("user", "track"),)

	def love(self):
		"""Loves and saves a track."""
		self.score = 1
		self.save()

	def hate(self):
		"""Loves and saves a track."""
		self.score = -1
		self.save()