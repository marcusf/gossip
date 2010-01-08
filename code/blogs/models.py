import feedparser
import urllib2
import re
import socket
import networkx as NX

from numpy import linalg, ones, dot, array, abs, size, sum, allclose
from scipy import sparse
from math import log
from urlparse import urlparse
from BeautifulSoup import BeautifulSoup, SoupStrainer

from zoid.feeds.models import Feed, IllegalFeedException
from zoid.music.models import Track
from zoid.helpers.pagerank import Pagerank
from zoid.helpers.utils import canonical_url, www_url, uniq, flatten, get_data_from_url, IllegalBlogException

from django.db import models, connection


##############################################################################
class BlogRank(models.Manager):
	"""Calculates the page rank for a nest of blogs."""
	
	graph = NX.DiGraph()
	max_id = 0
	normal_matrix = None
	invalid = True
	index_to_id = {}
	
	def rank(self):
		"""Computes the page rank for a link graph, by first
		inserting all the blogs and blog relations, and then
		calculating the graph and returning it."""
		relations = BlogRelation.objects.all()
		if len(relations) == 0: return False
		blogs = Blog.objects.all()
		# Sets up the rank graph
		for blog in blogs:
			self.insert(blog.id)
		for anchor in relations: 
			self.link(anchor.source.id,anchor.destination.id)
		# Calculate the page rank
		rank_vector = self.get_rank()
		# And update the database
		for rank in rank_vector:
			blog = Blog.objects.filter(id=rank[0])
			if blog:
				blog[0].rank = rank[1]
				blog[0].save()

	def insert(self, id):
		"""Inserts a URL in to the pagerank graph. Returns the ID
		of the inserted URL. If the URL is in the graph already,
		return that ID instead."""
		self.graph.add_node(id)
		self.index_to_id[self.max_id] = id
		self.max_id+=1
		self.invalidate()
		return id
    
	def invalidate(self):
		"""Marks the pagerank as invalid for the current setup."""
		self.invalid = True
		if self.normal_matrix: self.normal_matrix = None
    
    
	def link(self, from_id, to_id):
		"""Inserts a link in the graph from from_id to to_id."""
		self.invalidate()
		self.graph.add_edge((from_id, to_id))
    
	def normalize_graph(self):
		"""Creates a normalized graph, i.e. makes a new graph for actually
		calculating the pagrank in, and gives columns equal values,
		and adds constant noise (the damping factor)"""
		# 1 - The damping factor of the graph
		DAMP = 0.85
		adj = NX.adj_matrix(self.graph)#.transpose()
		idx_max = len(adj)
		self.normal_matrix = sparse.lil_matrix(adj)
		for i in range(0,idx_max):
			col = self.normal_matrix[i,:].todense()
			col_nonzero = size(col[col>0])
			if col_nonzero > 0: col[col>0] = DAMP*1.0/col_nonzero
			else: col = DAMP*1/len(col)
			col = col + (1.0-DAMP)/idx_max
			self.normal_matrix[i,:] = col

		# We want the _transpose_ of the adjacency matrix!
		self.normal_matrix = self.normal_matrix.transpose()
    
	def get_rank(self):
		"""Calculates the pagerank."""
		# Get ourself a decent graph
		if self.invalid:
			self.normalize_graph()
		# Find the dominant eigenvector
		Vn = self.find_dominant(self.normal_matrix)
		# Process the result afterwards
		result = [float(x) for x in Vn]
		indexes = [self.index_to_id[index] for index in range(0,len(result))]
		result = zip(indexes,result)
		#print result
		result.sort(lambda a,b: int(100000*(b[1]-a[1])))
		self.invalid = False
		return result
    
	def find_dominant(self, A):
		"""Finds the dominant eigenvector of matrix A.
		Since no method currently exist in SciPack for iteratively 
		finding	the dominant eigenvector (wich we know exist), we 
		calculate it by hand using the power method."""
		# Start by taking a random guess, we choose (1/n, ..., 1/n)'
		N = A.shape[0]
		V = sparse.lil_matrix((1,N))
		V[0,0:N] = ones((1,N)) * 1/N
		V = V.transpose()
		# Iterate until we get sufficient precision
		while True:
			Vn = self.iterate_once(A,V)
			if allclose(Vn.todense(), V.todense()): break
			V = Vn
		return Vn.todense()
    
	def iterate_once(self,A,V):
		"""Performs one iteration in the power method for approximating
		an eigenvector."""
		V =  A * V
		Vend = float(V[size(V)-1,0])
		return 1 / Vend * V

##############################################################################
class BlogSpider(models.Manager):
	"""Manages the spidering of blogs."""
	MAX_DEPTH = 2

	def spider_from(self, url):
		"""Starts a new spidering, with URL as the center 
		node of the process."""
		blog = Blog.manager.find_or_create(url)
		self.__spider_blog(blog, 1)
			
	def build_link_graph(self):
		"""Creates the link graph for the random surfer,
		which we use when we build our pagerank."""
		blogs = Blog.objects.all()
		for blog in blogs:
			blog.update_blog_relations()

	def __spider_blog(self, blog, depth):
		"""Does the main spidering. Just recurses over 
		blog rolls until it hits maximal depth."""
		blogs = blog.index_blog_roll()
		if depth + 1 > self.MAX_DEPTH: return True
		for new_blog in blogs:
			self.__spider_blog(new_blog, depth+1)

##############################################################################
class BlogManager(models.Manager):
	"""Manages creating a new blog, things that strictly don't
	feel like a blogs responsibility."""
	
	def create_from_url(self, url):
		"""Creates a new blog from a URL and does an initial
		data pull for the blog."""
		if not (type(url) == type('s') or type(url) == type(u'u')):
			raise IllegalBlogException("URL must be valid")
		urlobj = urlparse(url)
		if not (urlobj[0] == 'http'):
			raise IllegalBlogException("Blog must use HTTP transport")
		url = canonical_url(url)
		blog = self.model(url=url, title=None, feed=None,\
		 traversable=False, rank=0.0, html=None)
		blog.fetch()
		blog.save()
		return blog
	
	def exists(self, url):
		"""True if blog with given URL exists in the database"""
		objects = Blog.objects.filter(url=canonical_url(url))
		return len(objects) > 0

	def exists_fuzzy(self, url):
		"""True if blog with given URL exists in the database"""
		objects = Blog.objects.filter(url__istartswith=url)
		if objects: return True
		else:
			objects = Blog.objects.filter(url__istartswith=www_url(url))
			if objects: return True

	def find_by_url(self, url):
		objects = Blog.objects.filter(url__iexact=url)
		if objects: return objects[0]

	def find_by_url_fuzzy(self, url):
		"""Does a fuzzy search, eg. tries partial matches too."""
		objects = Blog.objects.filter(url__istartswith=url)
		if objects: return objects[0]
		else:
			objects = Blog.objects.filter(url__istartswith=www_url(url))
			if objects: return objects[0]		
		
	def find_or_create(self, url):
		"""Either creates a new blog or returns the one in the database."""
		blog = self.find_by_url(url)
		if blog: return blog
		return self.create_from_url(url)

##############################################################################
class Blog(models.Model):
	"""Represents a separate blog, i.e. Fluokids or Bigstereo or similarly"""
	url = models.URLField(unique=True, verify_exists=False, max_length=330)
	title = models.CharField(max_length=200, null=True, blank=True)
	feed = models.OneToOneField(Feed, null=True, blank=True)
	traversable = models.BooleanField(default=False)
	rank = models.FloatField(default=0.0)
	html = models.TextField(null=True, blank=True)

	# Standard model manager, for querying etc.
	objects = models.Manager()
	
	# Spider, handles the "dirty" work of fetching blogs.
	spider = BlogSpider()
	
	# Things related to creating new blogs.
	manager = BlogManager()
	
	# PageRank object
	blog_rank = BlogRank()
	
	# Some private variable we'll use
	__blog_roll 	= None
	__data 			= None
	
	# Blog roll gives the blog roll for the blog
	def _get_blog_roll(self):
		if not self.__blog_roll:
			if self.data: self.__blog_roll = BlogRoll(self)
		return self.__blog_roll
	blog_roll = property(_get_blog_roll)
	
	# Gets the souped up data for the blog, or creates 
	# some if nothing exists.
	def _get_soup(self):
		if not self.__data:
			if self.html: self.__data = BeautifulSoup(self.html)
		return self.__data
	data = property(_get_soup)

	def __unicode__(self):
		return u'%s (%s)' % (self.title, self.url)
	
	def num_posts(self):
		return len(self.feed.post_set.all())
		
	def num_tracks(self):
		"""The number of tracks the blog currently has posted"""
		q = "select count(fe.id) from feeds_enclosure as fe where fe.post_id in " + \
		    "(select p.id from feeds_post as p where p.feed_id = '%d')"  % (self.feed.id)
		cursor = connection.cursor()
		cursor.execute(q, {})
		row = cursor.fetchone()
		return row[0]
		
		
	def page_rank(self):
		return round(self.rank*10,2)
		
	def outgoing(self):
		"""Links pointing to this blog."""
		return [b.destination for b in self.target_of.all()]

	def incoming(self):
		"""Links this blog points to."""
		return [b.source for b in self.source_of.all()]
		
	def fetch(self):
		"""Fetches a fresh HTML page from the server and updates
		the URL in case the page has moved."""
		html, url = get_data_from_url(self.url)
		if url: self.url = url
		if html: self.html = html
		self.__update_title()
		self.__update_feed()

	def index_blog_roll(self):
		"""Indexes the entire blog roll in to our index."""
		new_blogs = []
		for blog_url in self.blog_roll:
			if not Blog.manager.exists_fuzzy(blog_url):
				try:
					bl = Blog.manager.create_from_url(blog_url)
				except IllegalBlogException, inst: 
					print "Ingen blogg: " + blog_url + ": " + inst.str
				except IllegalFeedException, inst:
					print "Ingen blogg: " + blog_url + ": " + inst.str
				except:
					print "Ingen blogg: Dubbelnyckel"
				else: new_blogs.insert(0,bl)
		return new_blogs
		
	def update_blog_relations(self):
		"""Creates all the outgoing links from this blog, as 
		given by the blog roll. Should be run _after_ the blog
		roll has been indexed."""
		# First, clean out the old shit
		#relations = BlogRelation.objects.filter(source=self)
		#[rel.delete() for rel in relations]
		# Then just iterate over the blog roll and links
		# to blogs already in the database.
		for url in self.blog_roll:
			blog = Blog.manager.find_by_url_fuzzy(url)
			if blog:
				try:
					rel = BlogRelation(source=self,destination=blog)
					rel.save()
				except: 
					continue					
				
	def common_artists(self):
		posts = self.feed.post_set.all()
		entries = {}
		for post in posts:
			for enclosure in post.enclosure_set.all():
				if entries.has_key(enclosure.track.artist.name):
					entries[enclosure.track.artist.name] += 1
				else:
					entries[enclosure.track.artist.name] = 1
		
		ent = [(b,a) for a,b in entries.iteritems()]
		ent.sort(lambda a,b: b[0]-a[0])
		pops = [e[1] for e in ent]
		if len(pops) > 5:
			pops = pops[:5]
		return pops

	def __update_title(self):
		"""Updates the title. Do not call directly."""
		if not self.data: return
		if self.data.find('title'): 
			title = self.data.find('title').string
			if len(title) > 200:
				title = title[0:199]
			self.title = title
			return True
    
	def __update_feed(self):
		"""Updates the feed. Do not call directly."""
		self.feed = \
		 Feed.new_feed.update_or_create(self.feed, self.data)

	# Admin stuff
	class Admin:
		pass

##############################################################################
class BlogRoll(object):
	"""A run time interpretation of a blog roll for a given site"""

	# When looking for blog rolls, areas that contain any of the URLs in
	# REJECTABLES will be discarded entirely.
	REJECTABLES = ['^mailto:','http://(www.)?youtube.com.*',\
	 'http://www.americanapparel.net/.*', \
	 '.*wikipedia.org.*','http://www.Slate.com/.*',\
	 'http://(.+)?\.amazon\.','http://www.blogger.com.*']
	
	# These are sites that might occur in a music blog roll, but still
	# shouldn't be spidered, since they aren't music blogs, but rather
	# other popular sites. Also contains some doucebag entries for people
	# with odd URL situations, 
	# I.e. in the case that the link URL we're given is www.x.com,
	# which is nothing but a proxied redirect to x.blogspot.com, we still
	# want to discard archive pages and similarly.
	TOO_POPULAR = ['http://(www\.)?myspace.com',\
	 'http://(www\.)?last.fm.*','http://(www\.)?hypem.com.*',\
	 'http://hype.non-standard.net/.*','.*wikipedia.org.*'\
	 'http://(www\.)?pitchforkmagazine.com.*',\
	 'http://(www\.)?thefader.com.*','http://(www\.)?scissorkick.com/.*',\
	 'http://(www\.)?talk2action.org/.*','http://(www\.)?cableandtweed.blogspot.com/',\
	 'http://([a-z0-9_-])?.blogspot.com/(.+)_archive.html']

	def __init__(self, blog):
		self.blog = blog

		self.data = self.blog.data
		self.url = self.blog.url	
        
		# Add a www in front of the url
		if re.match('http://www.*', self.url):
			pageUrlWww = re.sub('^http://www\.', "http://", self.url)
		else:
			pageUrlWww = re.sub('^http://', "http://www\.", self.url)
        
 		# We should really extract these in to the database, 
		# turn blog roll in to a manager of these and let it operate
		# on a blog. That'd be nifty.
		blocks = [self.url, pageUrlWww] + self.REJECTABLES
		popsites = [self.url, pageUrlWww] + self.TOO_POPULAR
		
		self.blockexp = [re.compile(b, re.IGNORECASE) for b in blocks]
		self.popsites = [re.compile(b, re.IGNORECASE) for b in popsites]

	__blog_roll = None
	
	def __iter__(self):
		"""Returns an iterator for the blog roll. Mostly for 
		comfort. Just returns the explicit list iterator for
		the __blog_rolls-variable."""
		if not self.__blog_roll:
			self.__blog_roll = self.possible_blog_rolls()
		return iter(self.__blog_roll)

	def possible_blog_rolls(self):
		"""Finds possible blog rolls on the page"""
		# Find possible nests, where we have a UL tag
		# Formerly, we checked self.data.body, but some pages
		# miss a body tag, eg therichgirlsareweeping.blogspot.com
		nests = [x for x in self.data.findAll({'p': True, 'div': True}) \
		 if x.findAll('ul',recursive=False)]
		list = self.reject_pop_sites(uniq(flatten(self.link_lists(nests))))
		return [canonical_url(site) for site in list]
    
	def link_lists(self,lists):
		"""Returns true if `lists' contains a link list
		Uses two heuristics that work on most occurences of a blog roll"""
		linked_list = []
		# First, check for standard <ul>-type lists
		for list in lists:
			linked_list.extend(self.unordered_link_list(list))
		# If we can't find any valid <ul>-list, look for tightly
		# clustered <a>-tags
		if not linked_list:
			linked_list.extend(self.anchor_cluster_list(self.data))
		return linked_list
    
	def anchor_cluster_list(self, div):
		"""Finds places that are "anchor clusters", in the sense that
		they have a high ratio of anchor tags to other data
		Pretty intensive on calculations, very unoptimized"""
		atags = div.findAll('a')
		visited = set()
		link_list = []
		for anchor in atags:
			if anchor.has_key('href') and anchor.parent.contents and \
			 str(anchor.parent.contents) not in visited:
				visited.add(str(anchor.parent.contents))
				links = self.links_from_anchors(anchor.parent)
				if links: link_list.extend(links)
		return link_list
    
	def unordered_link_list(self, list):
		"""Looks for linked lists in the <ul>-sense of being unordered
		lists of item. Works for semantically ok blogs."""
		return [x for x in [self.linked_list(li) \
		 for li in list.findAll('ul')] if x]
    
	def links_from_anchors(self, aParent):
		"""Tries to find a links by scanning the parent of an anchor
		tag that might be part of a cluster."""
		anchors = aParent.findAll('a', recursive = False)
		if len(anchors) > 5:
			blockSize = sum([len(str(a)) for a in aParent.contents])
			anchorSize = sum([len(str(a)) for a in anchors])
			if (1.0*anchorSize)/blockSize > 0.9:
				valid_list = [x['href'] for x in anchors \
			 	 if x.has_key('href') and self.valid_href(x['href'])]
				if len(valid_list) == len(anchors): 
					return valid_list
    
	def linked_list(self, list):
		"""Check if a 'ul' item is a link list"""
		lis = list.findAll('li')
		# We don't accept short blog rolls, limit here is eight
		if len(lis) > 8:
			# Remove empty li (i.e. <li>\n</li> etc) cases
			lis = self.clean_li_list(lis)
			link_lis = [x for x in \
				[self.li_from_link_list(li) for li in lis] if x]
			# We reject lists where over 5% of the entries are
			# illegal. Setting this to a sharp zero turned out to
			# be too harsh, since some people link to themselves
			# once or twice in their blog roll (eg whothehell.net)
			if 1.0*(len(link_lis)-len(lis))/len(lis) < 0.05: 
				return link_lis
    
	def clean_li_list(self, lis):
		"""Cleans a linked list before processing it,
		which now means removing any empty <li>'s."""
		return [l for l in lis \
		 if l.contents and \
		 (len(l.contents) > 1 or l.contents[0] != '\n')]
 
	def li_from_link_list(self,li):
		"""Checks if a <li>-element is a likely candidate is in a list"""
		# Only accept LIs where the first item is a link,
		# highly unlikely to get <li>I Like <a href=''>
		if li.contents and vars(li.contents[0]).has_key('name') and \
		 li.contents[0].name == 'a':
			return self.valid_href(li.contents[0]['href'])
    
	def valid_href(self,href):
		"""Checks if a HREF is valid"""
		# First check we're moving to another site
		if not re.match('^http://',href): return None
		# Then check that we're not going to a bad site
		blocks = [True for x in self.blockexp if x.match(href)]
		if not blocks: return href
    
	def reject_pop_sites(self, list):
		"""Rejects popular sites that likely are unrelated to what we're
		looking for, such as MySpace and YouTube."""
		return [site for site in list if not self.is_pop_site(site)]
    
	def is_pop_site(self, url):
		"""Does a simple regular expression match to decide if a site is
		a popular site."""
		return [True for x in self.popsites if x.match(url)]
    
##############################################################################
class BlogRelation(models.Model):
	"""A directional link between two blogs in our graph.
	Backlinks are given by related_name."""
	source = models.ForeignKey(Blog, related_name = 'target_of')
	destination = models.ForeignKey(Blog, related_name = 'source_of')
	class Meta:
		unique_together = (("source", "destination"),)
