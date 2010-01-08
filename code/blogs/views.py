"""
zoid.blogs.views
Views related to blogs, like listing blogs, individual details etc.
"""
from zoid.blogs.models import Blog
from django.shortcuts import render_to_response
from django.template import RequestContext
from django.http import HttpResponse
from django.core.paginator import Paginator, InvalidPage

def index(request):
	c = RequestContext(request,{})
	return render_to_response('blogs_index.html', c)

def listing(request):
	return render_to_response('blogs_index.html')

def refresh(request, pno):
	blog = Blog.objects.filter(id=pno)
	blog = blog[0]
	if blog and blog.feed: 
		blog.feed.update()
		#return HttpResponse("OK!")
	#return HttpResponse("Not found.")
	return HttpResponse("%d posts" % blog.feed.post_set.count())
	
def list(request, pno):
	"""Generates a list view of the blogs"""
	if request.GET.has_key('q') and len(request.GET['q']) > 0:
		search = Blog.objects.filter(title__icontains=request.GET['q']).order_by('-rank')
	else:
		search = Blog.objects.all().order_by('-rank')
	pagin = Paginator(search, 10)
	if pno: pno = int(pno)
	else: pno = 1
	query_param = ''
	if request.GET.has_key('q'): query_param = request.GET['q']
	return render_to_response('blogs_list.html',\
	 {'blog_page': pagin.page(pno), 'index_list': pagin.page_range,
	'draw_pagin': len(pagin.page_range) > 1, 'current_index': pno, \
	'query_param': query_param})
	
def details(request, blog_id):
	"""Information about a certain blog"""
	blog = Blog.objects.filter(id=blog_id)
	blog = blog[0]
	return render_to_response('blogs_details.html', {'blog': blog})