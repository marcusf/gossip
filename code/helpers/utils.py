"""
utils.py

Small helper utilities and such.
"""
import re
import urllib2
import socket

##############################################################################
class RedirectHandler(urllib2.HTTPDefaultErrorHandler):  
	"""Catches exceptions from urllib2 and converts them to ordinary
	requests."""  
	def http_error_default(self, req, fp, code, msg, headers):
		result = urllib2.HTTPError(req.get_full_url(), code, msg, headers, fp)       
		result.status = code
		return result

##############################################################################
class IllegalBlogException(Exception):
	"""Is raised when we try to open a blog which is invalid in some
	spectacular way, such as that the web page does not exist or has been
	moved without having a new location specified. """
	def __init__(self, str):
		self.str = str
	def __str__(self):
		return self.str

##############################################################################
def get_data_from_url(url):
	"""Returns data and actual URL for the web site presumably
	located at URL."""
	# timeout in seconds. We need one of these to get the 
	# speed of the process up.
	socket.setdefaulttimeout(10)

	# Handle 3xx redirects of a page, and other error
	# events that might occurs
	opener = urllib2.build_opener(RedirectHandler)
	while True:			
		request = urllib2.Request(url)
		try: response = opener.open(request)
		# URL not found, bogus URL
		except urllib2.URLError: 
			if canonical_url(url) == url:
				url = www_url(url)
				if not url: 
					raise IllegalBlogException("URL "+url+" not found")
			else: raise IllegalBlogException("URL "+url+" not found")
		# Other unhandled error
		#except: raise IllegalBlogException("Unknown error ("+url+")")
		else:
			# Things went ok
			if not vars(response).has_key('status') or response.status == 200: 
				break
			# We've redirected, so let's give it another try
			if response.status in [301,302]:
				if not response.headers.has_key('Location'):
					raise IllegalBlogException("Bad redirect from "+ url)
				# Another unhandled error
				else: 
					raise IllegalBlogException(page, "Unknown error("+url+")")
	# Return the data and the URL
	return (response.read(), canonical_url(response.geturl()))

def canonical_url(url):
	"""Returns a canonical representation of a URL,
	i.e. dropping any tailing slashes and removing any WWW"""
	match = re.match("(.+?)/index.htm(l)?", url)
	if match: url = match.group(1)
	match = re.match("^(http://([^/]+)?)(/$|$)", url)
	if match: url = match.group(1)
	match = re.match("^http://www\.(.+)", url)
	if match: url = 'http://' + match.group(1)
	return url

def www_url(url):
	url = canonical_url(url)
	match = re.match("^http://(.+)", url)
	if match:
		url = 'http://www.' + match.group(1)
	return url

def flatten(L):
	"""	Flattens a list
	http://www.daniel-lemire.com/blog/archives/
	2006/05/10/flattening-lists-in-python/"""
	if type(L) != type([]): return [L]
	if L == []: return L
	return flatten(L[0]) + flatten(L[1:])

def uniq(li):
	"""Returns a list with all duplicates removed"""
	return list(set(li))