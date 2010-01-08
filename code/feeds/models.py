import feedparser
import urllib2
import re
import datetime
from BeautifulSoup import BeautifulSoup, SoupStrainer

from django.db import models
from zoid.music.models import Track
from zoid.helpers.utils import canonical_url, uniq, flatten

##############################################################################
class IllegalFeedException(Exception):
	"""Is raised when we try to open a feed which is invalid in some
	spectacular way, such as that the feed url does not exist or has been
	moved without having a new location specified. """
	def __init__(self, str):
		self.str = str
	def __str__(self):
		return self.str

##############################################################################
class FeedUpdater(models.Manager):
	"""Manages refreshing feeds and fetching hot new music."""
	
	def update(self):
		feeds = Feed.feeds.all()
		for feed in feeds:
			print "== Refreshing " + feed.url
			feed.update()
		

##############################################################################
class NewFeedManager(models.Manager):
	"""Manages the creation of new feeds"""

	def update_or_create(self, current_feed, soup):
		"""Does the right thing, i.e. creates a new feed object 
		if required, or returns the current one if not."""
		if not current_feed:
			return self.find_and_create_from_soup(soup)
		new_feed_url = self._feed_url(soup)
		if new_feed_url and new_feed_url != current_feed.url:
			current_feed.delete()
			return self.create_from_url(new_feed_url)
		return current_feed

	def find_and_create_from_soup(self, soup):
		"""Finds a feed in parsed HTML and creates it"""
		feed_url = self.__feed_url(soup)
		if feed_url:
			return self.create_from_url(feed_url)
		else:
			raise IllegalFeedException("No feed found for blog.")

	def create_from_url(self, url):
		"""Fetches a feed from a URL and creates a feed object."""
		feed = self.model(url=url, etag=None, modified=None)
		feed.detect_music()
		feed.save()
		return feed

	def __feed_url(self, soup):
		"""Tries to locate the URL of a feed, first checks for an Atom
		feed, and then checks for an RSS feed. Pretty simple logic, so
		will probably break down in fringe cases."""
		atom_feed = soup.find('link',rel='alternate', \
		 type='application/atom+xml')
		if atom_feed: return atom_feed['href']
		rss_feed = soup.find('link',rel='alternate', \
		 type='application/rss+xml')
		if rss_feed: return rss_feed['href']
		xml_feed = soup.find('link', rel='alternate', \
		 type='text/xml')
		if xml_feed: return xml_feed['href']


##############################################################################
class Feed(models.Model):
	"""Represents a feed for a particular blog."""
	url = models.URLField(verify_exists=False, max_length=500)
	etag = models.CharField(max_length=150, null=True, blank=True)
	modified = models.DateTimeField(null=True, blank=True)

	feeds = models.Manager()
	new_feed = NewFeedManager()
	updater = FeedUpdater()
	_providers = None

	MUSIC_PROVIDERS = [".*zshare\.net.*",".*yousendit\.com.*",\
		".*speedyshare\.com.*",".*?\.mp3$"]
		
	def __unicode__(self):
		return self.url
	#	return self.blog.

	def _get_music_providers(self):
		"""The music providers property, containing information about
		URLs we suspect contain music."""
		if not self._providers:
			self._providers = \
			 [re.compile(l, re.IGNORECASE) for l in self.MUSIC_PROVIDERS]
		return self._providers

	music_providers = property(_get_music_providers)
	
	def title(self):
		try: return self.blog.title
		except: return self.url

	def detect_music(self):
		"""Tries to detect if a feed contains any music."""
		try: self.feed = feedparser.parse(self.url)
		except: raise IllegalFeedException("Cannot find feed")
		if not self.is_mp3_feed():
			raise IllegalFeedException("Not a feed for an MP3 blog")

	def is_mp3_feed(self):
		"""Checks if a blog is an MP3 blog by inspecting 
		entries in the feed"""
		posts_mp3, posts_total = (0,0)
		for entry in self.feed.entries:
			posts_total+=1
			if (entry.has_key('content') or entry.has_key('links') \
			or entry.has_key('summary_detail')) and self.is_mp3_entry(entry):
				posts_mp3 +=1
		# If more than 40% of the posts contain mp3s, then go for it
		# print "mp3: %d, total: %d" % (posts_mp3, posts_total)
		if posts_total == 0: return False
 		return ((1.0*posts_mp3)/posts_total >= 0.4)

	def is_mp3_entry(self, entry):
		"""Checks if an entry contains any mp3 links"""
		return len(self.get_mp3_links(entry)) > 0

	feed_updated = None

	def update(self):
		"""Updates the current feed by trying to fetch a new one, and then
		iterating over the feeds."""
		feed = feedparser.parse(self.url)
		#feed = feedparser.parse(self.url, \
		# modified=self.modified, etag=self.etag)
		if feed.has_key('status'):
			if feed.status in [200, 301, 302, 307]:
				# Permanent redirect, update URL
				if feed.status == 301: self.url = feed.url
				if feed.has_key('updated_parsed'):
					self.feed_updated = feed['updated_parsed']
				# We probably have new contents
				for entry in feed.entries:
					self.update_post(entry)
			else:
				print "Odd feed status: %d" % (feed.status)

	def update_post(self, entry):
		"""Updates a single (as of now unknown) post from a feed."""
		title, url, date = self.__entry_meta(entry)
		files = self.__enclosure_list(entry)
		if not url: url = self.blog.url
		post = Post.from_feed.create_or_update(self, title, url, date, files)

	def get_mp3_links(self, entry):
		"""Gets the MP3 links from a post."""
		mp3_links = []
		# First gather contents
		contents = []
		if entry.has_key('content'): contents.extend(entry['content'])

		for content in contents:
			code = BeautifulSoup(content.value)
			mp3_links.extend([song_obj(a) \
			for a in code.findAll('a') \
			if a.has_key('href') and vars(a).has_key('string') and \
			 self.is_mp3_link(a['href'])])

		# Then gather from the links
		if entry.has_key('links'):
			music = [(link['title'],link['href']) for link in entry.links\
			 if link.has_key('rel') and link['rel'] == 'related' and \
				link.has_key('href') and link.has_key('title')]
			mp3_links.extend([song_obj_from_data(a[0],a[1]) \
			 for a in music if self.is_mp3_link(a[1])])

		# If we don't have anything, check the extended summary
		if not mp3_links and entry.has_key('summary_detail'): 
			content = entry['summary_detail']
			code = BeautifulSoup(content.value)
			mp3_links.extend([song_obj(a) \
			 for a in code.findAll('a') \
			 if a.has_key('href') and vars(a).has_key('string') and \
			  self.is_mp3_link(a['href'])])
			
		# ...and done!
		return mp3_links

	def is_mp3_link(self, link):
		"""Checks if a link points to an MP3 file"""
		return [True for host in self.music_providers if host.match(link)]

	def __entry_meta(self, entry):
		"""Gets the title, link and date"""
		title, link, date = ('No title', '', self.__get_date(entry))
		if entry.has_key('title'): title = entry['title']
		if entry.has_key('link'): link = entry['link']
		return (title,link, date)
		
	def __get_date(self, entry):
		if entry.has_key('published_parsed'): 
			return datetime.datetime(*entry['published_parsed'][:6])
		elif entry.has_key('created_parsed'): 
			return datetime.datetime(*entry['created_parsed'][:6])        
		elif entry.has_key('updated_parsed'): 
			return datetime.datetime(*entry['updated_parsed'][:6])
		elif self.feed_updated: 
			return datetime.datetime(*self.feed_updated[:6])

	def __enclosure_list(self, entry):
		links = self.get_mp3_links(entry)
		encl=[]
		for link in links:
			artist = ''
			if link.has_key('artist'): artist = link['artist']
			if link.has_key('title'): title = link['title']
			else: title = link['string']
			if title:
				track = Track.track_manager.find_or_create(artist,title)
				encl.append([track,link['href']])
				# Earlier, we only added tracks we didn't already have,
				# but I find this more natural. If someone double-posts
				# something, we should notice it.
				# Old code below for reference:
				#already_got = self.post_set.filter(enclosure__track=track)
				#if not already_got: 
			
		return encl

############################################################################
# Parsing routines for link names.
# Routines for trying to extract the artist and title from a souped
# up <a>-tag object.

class ParseSongAnchor(object):
	"""This is a refactored version of the song_obj(a) below.
	Not tested enough, so we keep the old one for reference."""
	def parse_simple(a_tag):
		"""<a>artist - title</a>"""
		song = re.match('(.+)-(.+)', a_tag.string)
		if song: 
			return (song.group(1),song.group(2))
		
	def parse_separate_title(a_tag):
		"""<a href='myspace'>artist</a> - <a>title</a>"""
		if a_tag.previous and a_tag.previous.string and \
		 a_tag.previous.string == ' - ' and \
		 a_tag.previous.previous and a_tag.previous.previous.string and \
		 len(a_tag.previous.previous.string) < 57:
			return (a_tag.previous.previous.string, a_tag.string)
	
	def parse_only_title(a_tag):
		"""artist - <a>title</a>"""
		if a_tag.previous and a_tag.previous.string:
			prev = a_tag.previous.string
			just_artist = re.match('(.+) - ', prev)
			if just_artist: return(just_artist.group(1),a_tag.string)
	
	def parse_download_link(a_tag):
		"""artist - title <a>(download)</a>"""
		if a.previous and a.previous.string:
			prev = a.previous.string
			# Check first if it's of artist - song <a>(download)</a> type
			song_artist = re.match('(.+)-([^\s].+)',prev, re.IGNORECASE)
			if song_artist:
				return (song_artist.group(1), song_artist.group(2))
	
	def get_title(a):
		parse_methods = [h[1] for h in inspect(self).members \
			if h[0].count('parse_') > 0]
		songs = [y for y in [f(a) for f in parse_methods] if y]
		if songs:
			song = songs[0]
			song[0] = song[0].strip()
			song[1] = self.strip_title(song[1].strip)
			return (song[0],song[1])
		return (None,None)
		
##############################################################################
def song_obj(a):
	"""This one transforms a song string found in a souped up a-tag to
	a full fledged hash containing title and artist for a link, if it 
	can find it.
	
	It is extremely messy, due to the messy nature of people posting to
	the web."""
	artist, title = (None,None)
	# Basic case -- song and title in the link
	song = re.match('(.+)-(.+)',a.string)
	if song:
		artist = song.group(1).strip()
		title = strip_title(song.group(2).strip())

	elif a.previous and a.previous.string:
		# Start with the music.for-robots behaviour of linking
		# to the band as the first string.
		if a.previous.string == ' - ' and \
		 a.previous.previous and a.previous.previous.string and \
		 len(a.previous.previous.string) < 57:
			artist = a.previous.previous.string.strip()
			title = strip_title(a.string).strip()
		# Elsewise, is it in righte before the link?
		elif a.previous and a.previous.string:
			prev = a.previous.string
			# Check first if it's of artist - song <a>(download)</a> type
			song_artist = re.match('(.+)-([^\s].+)',prev, re.IGNORECASE)
			if song_artist:
				artist = song_artist.group(1).strip()
				title = song_artist.group(2).strip()
				# Then if the blog author just wrote artist - <a>song</a>
			else:
				just_artist = re.match('(.+) - ', prev)
				if just_artist:
					artist = just_artist.group(1).strip()
					title = strip_title(a.string).strip()
	# Try finding any remix string
	if a.next.next and a.next.next.string:
		remix = re.match('.*(\(.*(mix|version|edit|refix).*\)).*',a.next.next.string, re.IGNORECASE)
		if remix: title = ("%s %s" %(title, remix.group(1).strip())).strip()
	# Just in case we've fetched shit, such as the string below, we
	# kill it if there is too much shit.
	# 'Efter en intensiv vecka som bade inneburit for tidiga dodsfall, storm, 
	#  ett ohalsosamt lyssnande pa Sven-Bertil Taube och insikt att det ar 
	#  alldeles for fa timmar pa dygnet var det just det har jag behovde for 
	#  att fortsatta, en ny eurodiscohit. <a>"Trippin on you"</a>'
	#                                  ^--- Notice the dash
	if artist and len(artist) > 57:
		artist = None
	if title and len(title) > 100:
		title = None
	# Let's be extra catious
	if title: title = title.strip()
	if artist: 
		extra_dash = re.match('(.*)\s*-$', artist)
		if extra_dash: artist = extra_dash.group(1)
		artist = artist.strip()
	#str = ("%s - %s" % (artist, title)).encode('ascii','ignore')
	#print str
	return {'artist': artist, 'title': title,'href': a['href'], 'string': a.string}
	
def strip_title(str):
	has_download = re.match('(.*)\((download|ysi|zshare)\)',str, re.IGNORECASE)
	if has_download: return has_download.group(1)
	else: return str

def song_obj_from_data(title, href):
	"""Returns a track hash from a string"""
	song = re.match('(.+)-(.+)',title)
	if song:
		return {'artist': song.group(1), 'title': song.group(2),\
		 'href': href, 'string':title}
	else:
		return {'artist': None, 'title': title, 'href': href, 'string': title}
		
##############################################################################
class PostCreator(models.Manager):
	"""Methods for creating posts."""

	def create_or_update(self, my_feed, title, my_url, date, files):
		"""Either returns a post matching the criteria, or create
		a new one, giving it.
		
		Notice that the parameter ``file'' is of the sort (Track, url)
		"""
		post = Post.objects.filter(url=my_url)
		if post:

			if post[0].published > date: 
				print my_url
				return post[0]
			else:
				enclosures=post[0].enclosure_set.all()
				for e in enclosures: e.delete()
				post.delete()
		
		if date:
			new_post = self.model(feed=my_feed, title=title,url=my_url,published=date)
		else:
			new_post = self.model(feed=my_feed, title=title,url=my_url)
		print "I've made it this far!"
		new_post.save()
		if files:
			for file in files:
				e = Enclosure(post=new_post, track=file[0],url=file[1]) 
				try: e.save()
				except: pass
		return post

##############################################################################
class Post(models.Model):
	"""A blog post, i.e. 'New track' from Discobelle."""
	feed = models.ForeignKey(Feed)
	title = models.CharField(max_length=200, null=True)
	url = models.URLField(unique=True)
	published = models.DateTimeField(null=True)
	
	objects = models.Manager()
	from_feed = PostCreator()
	
	def __unicode__(self):
		return '%(title)s (%(url)s)' % \
		{'title': self.title, 'url': self.url}
		
	def enclosures(self):
		return self.enclosure_set.all()
		
		
	def published_date(self):
		return self.published.strftime('%d %B %Y %H:%M')

	# Admin stuff	
	class Admin:
		pass
		
##############################################################################
class Enclosure(models.Model):
	""" Models a posting of a track in a blog post, i.e.
	an annotated many-to-many relation between post
	and track. Also contains the URL of the enclosure."""
	url = models.URLField(verify_exists=False)
	post = models.ForeignKey(Post)
	track = models.ForeignKey(Track)
	def __unicode__(self):
		return self.url
		
	class Meta:
		""" Ensures that we only have one track per post, since eg
		Discobelle.net often posts one YSI-link and one zShare."""
		unique_together = (("track","post"),)		
		
	# Admin stuff	
	class Admin:
		pass
