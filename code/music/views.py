from django.http import HttpResponse
from django.template import RequestContext
from django.shortcuts import render_to_response
from django.core.paginator import Paginator, InvalidPage
from django.contrib.auth import authenticate
from django.contrib.auth.decorators import login_required
from zoid.helpers.utils import *

from zoid.statistics.models import *
from zoid.music.models import Popularity, Track

def default_index(request):
	return index(request, "1")

def index(request, pno):
	c = RequestContext(request,{})
	tracks = TrackStatistics.manager.find_all()
	for track in tracks: track.set_user_for_relation(request.user)
	tracks.sort(lambda a,b: int(100*(b.trackstatistics.sort_score - a.trackstatistics.sort_score)))
	pagin = Paginator(tracks, 10)
	if pno: pno = int(pno)
	else: pno = 1
	rng = pagin.page_range[(pno-1):(pno+9)]
	if rng[0] != 1: rng = [1] + rng
	if rng[-1] != pagin.page_range[-1]:
		rng = rng + [pagin.page_range[-1]]
	return render_to_response('music_index.html', \
	 {'tracks': pagin.page(pno), 'pageno': pno, 'index_list': rng  }, c)

def explore(request, id):
	c = RequestContext(request,{})
	try:
		artist = Artist.objects.get(id=int(id))
	except:
		return HttpResponse("No such artist %s" % (id) )
	return render_to_response('music_artist.html', {'object': artist }, c)

def track(request, id):
	c = RequestContext(request,{})
	try:
		track_file = Track.objects.get(id=int(id))
	except:
		return HttpResponse("No such track %s" % (id) )
	return render_to_response('music_track.html', {'object': track_file }, c)

	
def similar(request, id):
	try:
		artist = Artist.objects.get(id=int(id))
	except: return HttpResponse("No such artist.")
	similars = get_similar(artist.name)
	similars = [similar[0] for similar in similars if similar[1] > 30.0]
	if len(similars) > 10:
		similars = similars[:10]
	return render_to_response('music_similar.html',{'artist': artist, 'similar': similars})

@login_required(redirect_field_name='redirect_to')
def love(request, tid):
	track = Track.objects.get(id=int(tid))
	if track: Popularity.popper.love(request.user, track)
	return HttpResponse("OK!")


@login_required(redirect_field_name='redirect_to')
def hate(request, tid):
	track = Track.objects.get(id=int(tid))
	if track: Popularity.popper.hate(request.user, track)
	return HttpResponse("OK!")