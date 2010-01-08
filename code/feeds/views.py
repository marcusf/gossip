"""
zoid.feeds.views
Views related to the feeds
"""
from zoid.feeds.models import Feed, Post, Enclosure
from django.shortcuts import render_to_response
from django.template import RequestContext
from django.http import HttpResponse
	
def show(request, pno):
	"""Shows a list view of a feed"""
	if not pno: return
	feed = Feed.feeds.get(id=int(pno))
	posts = feed.post_set.all().order_by('-published')
	return render_to_response('feeds_list.html',\
	 { 'feed': feed, 'posts': posts })